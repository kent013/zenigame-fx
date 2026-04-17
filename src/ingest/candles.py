from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.api.cache.http_cache import HttpCache
from src.api.oanda.client import OandaClient
from src.api.oanda.models import Candle
from src.db.models import PriceBarM1
from src.utils.time import granularity_delta, now_utc, rfc3339_utc, to_utc

logger = structlog.get_logger(__name__)

DEFAULT_CHUNK_COUNT = 5000
CACHE_FRESHNESS_MARGIN = timedelta(hours=1)


@dataclass(frozen=True)
class HistoricalRange:
    instrument: str
    start: datetime
    end: datetime
    granularity: str = "M1"
    price: str = "BA"
    chunk_count: int = DEFAULT_CHUNK_COUNT


class CandleFetcher:
    def __init__(self, client: OandaClient, cache: HttpCache | None = None) -> None:
        self._client = client
        self._cache = cache

    def iter_range(self, plan: HistoricalRange) -> Iterator[Candle]:
        """`[plan.start, plan.end)` を跨ぐ完成済みバーを順次 yield する。"""
        start = to_utc(plan.start)
        end = to_utc(plan.end)
        if end <= start:
            return
        delta = granularity_delta(plan.granularity)

        cursor = start
        include_first = True
        while cursor < end:
            cache_key_params = self._cache_params(plan, cursor, include_first)
            cacheable = self._is_chunk_cacheable(cursor, plan.chunk_count, delta)
            cached = self._cache.get("candles", cache_key_params) if (self._cache and cacheable) else None
            if cached is not None:
                response_candles = [Candle.model_validate(c) for c in cached]
                logger.debug("ingest.candles.cache_hit", instrument=plan.instrument, from_time=rfc3339_utc(cursor))
            else:
                response = self._client.get_candles(
                    instrument=plan.instrument,
                    granularity=plan.granularity,
                    price=plan.price,
                    count=plan.chunk_count,
                    from_time=rfc3339_utc(cursor),
                    include_first=include_first,
                )
                response_candles = response.candles
                if self._cache is not None and cacheable and response_candles:
                    self._cache.set(
                        "candles",
                        cache_key_params,
                        [c.model_dump(mode="json") for c in response_candles],
                    )

            if not response_candles:
                return

            for candle in response_candles:
                candle_time = to_utc(candle.time)
                if candle_time >= end:
                    return
                if candle.complete:
                    yield candle

            # count 未満の応答 = OANDA が利用可能なバーを出し切った = 取得終端
            if len(response_candles) < plan.chunk_count:
                return

            last_time = to_utc(response_candles[-1].time)
            if last_time <= cursor and not include_first:
                # 進捗しなかった場合は無限ループ防止で終了
                return
            cursor = last_time
            include_first = False

    def fetch_latest(
        self, instrument: str, count: int = 60, granularity: str = "M1", price: str = "BA"
    ) -> list[Candle]:
        """直近の `count` 本を取得し、完成バーのみ返す。"""
        response = self._client.get_candles(
            instrument=instrument,
            granularity=granularity,
            price=price,
            count=count,
        )
        return [c for c in response.candles if c.complete]

    @staticmethod
    def _cache_params(plan: HistoricalRange, cursor: datetime, include_first: bool) -> dict[str, Any]:
        return {
            "instrument": plan.instrument,
            "granularity": plan.granularity,
            "price": plan.price,
            "count": plan.chunk_count,
            "from": rfc3339_utc(cursor),
            "includeFirst": include_first,
        }

    @staticmethod
    def _is_chunk_cacheable(cursor: datetime, count: int, delta: timedelta) -> bool:
        """chunk の理論終端が現在時刻より十分過去なら永続キャッシュ対象。"""
        chunk_end = cursor + delta * count
        return chunk_end <= now_utc() - CACHE_FRESHNESS_MARGIN


def store_bars(session: Session, pair_id: int, candles: Iterable[Candle]) -> int:
    """`complete=true` かつ bid/ask 両方が揃っているバーを price_bar_m1 に UPSERT する。戻り値は書き込み件数。"""
    count = 0
    for candle in candles:
        if not candle.complete:
            continue
        if candle.bid is None or candle.ask is None:
            continue
        values = {
            "pair_id": pair_id,
            "bar_time": to_utc(candle.time),
            "open_bid": candle.bid.o,
            "high_bid": candle.bid.h,
            "low_bid": candle.bid.l,
            "close_bid": candle.bid.c,
            "open_ask": candle.ask.o,
            "high_ask": candle.ask.h,
            "low_ask": candle.ask.l,
            "close_ask": candle.ask.c,
            "volume": candle.volume,
            "complete": candle.complete,
        }
        stmt = insert(PriceBarM1).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["pair_id", "bar_time"],
            set_={k: v for k, v in values.items() if k not in ("pair_id", "bar_time")},
        )
        session.execute(stmt)
        count += 1
    session.commit()
    return count
