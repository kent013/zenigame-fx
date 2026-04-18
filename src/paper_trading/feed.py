from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from typing import Protocol

import httpx
import structlog

from src.api.oanda.client import (
    OandaAuthError,
    OandaClient,
    OandaRateLimitError,
    OandaServerError,
)
from src.api.oanda.models import Candle
from src.domain.price import Ohlc, PriceBar
from src.utils.time import now_utc, to_utc

logger = structlog.get_logger(__name__)

# Live polling のバー欠落を許容する安全上限。30 分以上の遅延があれば count を拡張するが、
# 万が一の暴走で 500 本を超える要求はしない（OANDA の 5000 本上限に対しても安全側）。
_LIVE_COUNT_MIN = 2
_LIVE_COUNT_MAX = 500
_LIVE_BAR_BUFFER = 2


class BarFeed(Protocol):
    def __iter__(self) -> Iterator[PriceBar]: ...

    def stop(self) -> None: ...


class ReplayBarFeed:
    """事前に用意された PriceBar のリストを順次 yield するフィード。

    `speedup=0` は sleep なし（バックテスト同等）。speedup=60 で実時間の 60 倍速。
    """

    def __init__(self, bars: Iterable[PriceBar], speedup: float = 0.0, bar_interval_seconds: float = 60.0) -> None:
        self._bars = list(bars)
        self._speedup = speedup
        self._bar_interval = bar_interval_seconds
        self._stop_event = threading.Event()

    def __iter__(self) -> Iterator[PriceBar]:
        sleep_per_bar = 0.0 if self._speedup <= 0 else self._bar_interval / self._speedup
        for bar in self._bars:
            if self._stop_event.is_set():
                return
            yield bar
            if sleep_per_bar > 0 and not self._stop_event.is_set():
                self._stop_event.wait(timeout=sleep_per_bar)

    def stop(self) -> None:
        self._stop_event.set()


class LiveBarFeed:
    """OANDA の candles エンドポイントを定期 polling し、新規完成バーを yield する。

    例外ポリシー（audit follow-up）:
    - `OandaAuthError`（401 等）は即時 raise。無限ループ化させない
    - `OandaRateLimitError` / `OandaServerError` / `httpx.TransportError` は warning だけ出して次 tick に進む
    - その他の予期しない例外は error ログを出してから raise

    count 計算（audit follow-up）:
    - 前回 yield 以降に経過した分数 + buffer でリクエスト count を決める
    - 初回と通常時は `_LIVE_COUNT_MIN` (2)、長時間ダウンからの復帰時は最大 `_LIVE_COUNT_MAX` (500) まで拡張
    """

    def __init__(
        self,
        client: OandaClient,
        instrument: str,
        poll_interval_seconds: float = 10.0,
        granularity: str = "M1",
        bar_interval_seconds: float = 60.0,
    ) -> None:
        self._client = client
        self._instrument = instrument
        self._poll_interval = poll_interval_seconds
        self._granularity = granularity
        self._bar_interval = bar_interval_seconds
        self._stop_event = threading.Event()
        self._last_yielded: datetime | None = None

    def _compute_count(self) -> int:
        if self._last_yielded is None:
            return _LIVE_COUNT_MIN
        elapsed = (now_utc() - self._last_yielded).total_seconds()
        if elapsed <= 0:
            return _LIVE_COUNT_MIN
        expected_bars = int(elapsed // self._bar_interval) + _LIVE_BAR_BUFFER
        return max(_LIVE_COUNT_MIN, min(_LIVE_COUNT_MAX, expected_bars))

    def __iter__(self) -> Iterator[PriceBar]:
        while not self._stop_event.is_set():
            try:
                resp = self._client.get_candles(
                    instrument=self._instrument,
                    granularity=self._granularity,
                    price="BA",
                    count=self._compute_count(),
                )
            except OandaAuthError:
                # 認証情報の誤りは再試行で解決しないので fail-fast。
                raise
            except (OandaRateLimitError, OandaServerError, httpx.TransportError) as exc:
                logger.warning("live_feed.transient_error", error=str(exc))
                self._stop_event.wait(timeout=self._poll_interval)
                continue
            except Exception as exc:
                logger.error("live_feed.unexpected_error", error=str(exc))
                raise

            for candle in resp.candles:
                if not candle.complete:
                    continue
                candle_time = to_utc(candle.time)
                if self._last_yielded is not None and candle_time <= self._last_yielded:
                    continue
                bar = _candle_to_bar(self._instrument, candle)
                self._last_yielded = candle_time
                yield bar
            self._stop_event.wait(timeout=self._poll_interval)

    def stop(self) -> None:
        self._stop_event.set()


def _candle_to_bar(instrument: str, candle: Candle) -> PriceBar:
    if candle.bid is None or candle.ask is None:
        raise ValueError("bid/ask required (price=BA must be requested)")
    return PriceBar(
        pair_name=instrument,
        bar_time=to_utc(candle.time),
        bid=Ohlc(open=candle.bid.o, high=candle.bid.h, low=candle.bid.l, close=candle.bid.c),
        ask=Ohlc(open=candle.ask.o, high=candle.ask.h, low=candle.ask.l, close=candle.ask.c),
        volume=candle.volume,
        complete=candle.complete,
    )


def seconds_until_next_bar(now: datetime, bar_interval: timedelta = timedelta(minutes=1)) -> float:
    """次バー確定時刻までの秒数。Live polling のスリープ間隔ヒントに使う。"""
    now_utc_dt = to_utc(now)
    seconds_into = now_utc_dt.timestamp() % bar_interval.total_seconds()
    remaining = bar_interval.total_seconds() - seconds_into
    return remaining


# time モジュールが未使用の警告を避けるための再エクスポート（LiveBarFeed 拡張時に使う）
_ = time
