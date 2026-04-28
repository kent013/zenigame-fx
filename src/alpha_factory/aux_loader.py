"""T057 Phase 2 Gate A/B: aux data loader (raw container + per-stage alignment).

production GA で `RegistryEvaluator` に注入する `EconomicEventSnapshot` /
`VixSeriesSnapshot` / `aux_series` / `aux_pair_bars` を構築する loader。

設計の柱:
    - **AuxBundle (raw container)**: DB / CSV 由来の生データを保持する
      `daily_series` / `event_calendar` / `aux_pair_bars_index` の dict を持つ。
    - **AlignedAuxBundle (per-stage)**: `AuxBundle.align_to(bars)` で bars と
      同じ長さに整列された `aux_series: dict[str, np.ndarray]` /
      `aux_pair_bars: dict[str, list[PriceBar | None]]` 等を持つ。
    - **AuxAlignmentCache**: stage 別 (Stage A 60d / Stage B 18m / holdout) に
      align 結果を 1 度だけ計算してキャッシュする。

look-ahead bias 防止:
    - `DailyObservation.effective_from_utc` (`src/ingest/effective_from.py`)
      でしか forward-fill を許さない。`bar.bar_time >= obs.effective_from_utc`
      を満たす最新 obs を採用する.
    - aux_pair_bars は M1 解像度に正規化 (tz-aware UTC + 秒切り捨て) した上で
      `dict[bar_time, PriceBar]` lookup を行い欠番は None を返す。
    - 同一 minute に複数 PriceBar が DB にある場合は **fail-fast** (ValueError).

詳細: devnotes/20260427-2234-aux-data-loader-phase2/
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha_factory.primitives._base import (
    EconomicEventSnapshot,
    VixSeriesSnapshot,
)
from src.db.models import CurrencyPair, MacroIndexDaily, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.events.calendar import EconomicCalendar, EconomicEvent
from src.ingest.effective_from import (
    EffectiveFromSource,
    compute_effective_from_utc,
    max_policy_lag_days,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "DEFAULT_CALENDAR_PATH",
    "DEFAULT_FRED_DIR",
    "AlignedAuxBundle",
    "AuxAlignmentCache",
    "AuxBundle",
    "DailyObservation",
    "build_aux_bundle",
    "build_aux_bundle_from_db",
    "load_aux_pair_bars_index",
    "load_aux_series",
    "load_daily_series_from_db",
    "load_dxy_series",
    "load_event_calendar",
    "load_event_snapshot",
    "load_vix_snapshot",
    "series_id_to_aux_key",
]

DEFAULT_FRED_DIR: Final[Path] = Path("data/raw/fred")
DEFAULT_CALENDAR_PATH: Final[Path] = Path("data/raw/calendar/events.csv")


# series_id → primitive 側の aux_series key (例: "VIXCLS" → "macro.vix")
SERIES_ID_TO_AUX_KEY: Final[dict[str, str]] = {
    "VIXCLS": "macro.vix",
    "DTWEXBGS": "macro.dxy",
    # GOLDPMGBD228NLBM (LBMA London PM fix) は FRED で discontinued (2024-)。
    # Yahoo Finance GC=F (Gold Futures, daily) に切替。fetch は yfinance 経由 (scripts/fetch_gold_daily.py)。
    "GC_F_YAHOO": "macro.gold",
    "DCOILWTICO": "macro.wti",
    "PCOPPUSDM": "macro.copper",
    "PALLFNFINDEXM": "macro.commodity_index",
    "SP500": "macro.spx500",
    "DGS10": "macro.dgs10",
    "DGS2": "macro.dgs2",
    "T10YIE": "macro.t10yie",
}


def series_id_to_aux_key(series_id: str) -> str:
    """series_id を primitive 側の aux_series key に変換する."""
    return SERIES_ID_TO_AUX_KEY.get(
        series_id, f"macro.{series_id.lower()}"
    )


# ---------------------------------------------------------------------------
# DailyObservation / AuxBundle / AlignedAuxBundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyObservation:
    """daily macro indicator の単一 observation.

    `effective_from_utc` を満たして以降の bar_time でしか forward-fill されない。
    `source` はその effective_from_utc の出所 (Phase 2 既定: policy_conservative).
    """

    observation_date: date
    value: float
    effective_from_utc: datetime
    source: Literal[
        "fred_realtime_start", "policy_conservative", "oanda_release_time"
    ] = "policy_conservative"


@dataclass(frozen=True)
class AlignedAuxBundle:
    """bars と同じ長さに整列済みの aux bundle (per-stage instance).

    `aux_series` は `np.ndarray[float64]`、長さは bars と完全一致。
    """

    aux_series: Mapping[str, np.ndarray]
    event_snapshot: EconomicEventSnapshot | None
    vix_snapshot: VixSeriesSnapshot | None
    aux_pair_bars: Mapping[str, Sequence[PriceBar | None]]

    def as_evaluator_kwargs(self) -> dict[str, Any]:
        """RegistryEvaluator constructor に渡す dict."""
        return {
            "aux_series": dict(self.aux_series),
            "event_snapshot": self.event_snapshot,
            "vix_snapshot": self.vix_snapshot,
            "aux_pair_bars": dict(self.aux_pair_bars),
        }


@dataclass
class AuxBundle:
    """Raw aux container — stage 別 bars に align される前.

    Phase 1 互換のため、後方互換のフィールド (`aux_series` / `event_snapshot` /
    `vix_snapshot` / `aux_pair_bars`) も保持する。これらは「全 bars にわたって
    pre-align された結果ではなく、生データそのもの」である。
    """

    daily_series: dict[str, list[DailyObservation]] = field(default_factory=dict)
    event_calendar: EconomicCalendar | None = None
    vix_snapshot: VixSeriesSnapshot | None = None
    aux_pair_bars_index: dict[str, dict[datetime, PriceBar]] = field(
        default_factory=dict
    )

    # ---- Phase 1 後方互換 ----
    # build_aux_bundle (CSV 経路) は既存テスト互換のため `aux_series: list[float]`
    # / `event_snapshot` / `aux_pair_bars: list[PriceBar | None]` を保持できる
    aux_series: dict[str, list[float]] = field(default_factory=dict)
    event_snapshot: EconomicEventSnapshot | None = None
    aux_pair_bars: dict[str, list[PriceBar | None]] = field(default_factory=dict)

    def align_to(
        self,
        bars: Sequence[PriceBar],
        *,
        as_of_strict: bool = True,
    ) -> AlignedAuxBundle:
        """指定 bars に per-bar align した bundle を返す.

        空 bars 契約: warmup-only シナリオ等で空 bars が来たら空 bundle を返す.

        look-ahead 防止: `bar.bar_time >= obs.effective_from_utc` を満たす
        最新 obs しか採用しない。観測順は時系列昇順 (caller 責務).
        """
        if not bars:
            return AlignedAuxBundle(
                aux_series={},
                event_snapshot=None,
                vix_snapshot=None,
                aux_pair_bars={},
            )

        n = len(bars)

        # 1. aux_series を per-bar 展開 (np.ndarray[float64])
        aux_series: dict[str, np.ndarray] = {}
        for series_id, observations in self.daily_series.items():
            arr = np.zeros(n, dtype=np.float64)
            obs_iter = iter(observations)
            next_obs: DailyObservation | None = next(obs_iter, None)
            current_value = 0.0  # warmup default
            for i, bar in enumerate(bars):
                bt = _bar_time_utc(bar.bar_time)
                while (
                    next_obs is not None
                    and next_obs.effective_from_utc <= bt
                ):
                    current_value = next_obs.value
                    next_obs = next(obs_iter, None)
                arr[i] = current_value
            aux_series[series_id_to_aux_key(series_id)] = arr

        # 2. event_snapshot (as_of = 末尾 bar). per-bar lookup は primitive 側 (T039)
        event_snapshot = None
        if self.event_calendar is not None:
            last_bar_time = _bar_time_utc(bars[-1].bar_time)
            event_snapshot = EconomicEventSnapshot(
                calendar=self.event_calendar,
                as_of=last_bar_time,
                as_of_strict=as_of_strict,
            )

        # 3. vix_snapshot は raw のまま (bar 別 lookup ではなく primitive 側で
        #    publication_ts 比較の bisect を行う既存契約)
        vix_snapshot = self.vix_snapshot

        # 4. aux_pair_bars: bar_time strict 一致で取得、欠番は None
        aux_pair_bars: dict[str, list[PriceBar | None]] = {}
        for pair_id, bar_index in self.aux_pair_bars_index.items():
            aligned: list[PriceBar | None] = []
            for bar in bars:
                key = _normalize_bar_time(bar.bar_time)
                aligned.append(bar_index.get(key))
            aux_pair_bars[pair_id] = aligned

        return AlignedAuxBundle(
            aux_series=aux_series,
            event_snapshot=event_snapshot,
            vix_snapshot=vix_snapshot,
            aux_pair_bars=aux_pair_bars,
        )


class AuxAlignmentCache:
    """stage 別の AlignedAuxBundle キャッシュ.

    key = `(id(bars), as_of_strict)` 構造で、bars が変わったら別 cache entry。
    invalidation は `reset()` で明示的に行う (V14 反映).
    """

    def __init__(self, raw: AuxBundle) -> None:
        self._raw = raw
        self._cache: dict[tuple[int, bool], AlignedAuxBundle] = {}

    def get(
        self,
        bars: Sequence[PriceBar],
        *,
        as_of_strict: bool = True,
    ) -> AlignedAuxBundle:
        key = (id(bars), as_of_strict)
        if key not in self._cache:
            self._cache[key] = self._raw.align_to(
                bars, as_of_strict=as_of_strict
            )
        return self._cache[key]

    def reset(self) -> None:
        """全 cache entry を破棄する (V14 invalidation)."""
        self._cache.clear()


# ---------------------------------------------------------------------------
# bar_time 正規化 helpers
# ---------------------------------------------------------------------------


def _bar_time_utc(ts: datetime) -> datetime:
    """tz-aware UTC に揃える (秒切り捨ては行わない、比較用)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _normalize_bar_time(ts: datetime) -> datetime:
    """M1 bar_time を正規化: tz-aware UTC + 秒・マイクロ秒を 0 に丸める.

    aux_pair_bars の dict[bar_time] lookup で target bars と DB の datetime
    が完全一致するように、両側で同じ正規化を適用する。
    """
    ts_utc = _bar_time_utc(ts)
    return ts_utc.replace(second=0, microsecond=0)


# ---------------------------------------------------------------------------
# CSV helpers (test fixture / Phase 1 backward compat)
# ---------------------------------------------------------------------------


def _read_csv_dict(path: Path) -> list[dict[str, str]] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as exc:
        logger.warning(
            "aux_loader.csv_read_failure",
            path=str(path),
            error=str(exc),
        )
        return None


def _parse_dt_utc(value: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(value)
        return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Loaders (CSV: Phase 1 互換 / DB: Phase 2 SSOT)
# ---------------------------------------------------------------------------


def load_dxy_series(
    fred_data_dir: Path = DEFAULT_FRED_DIR,
) -> list[float] | None:
    """DXY close 列を float list で返す (時系列の昇順、test fixture 用)."""
    rows = _read_csv_dict(fred_data_dir / "DXY.csv")
    if rows is None:
        return None
    if not rows or "close" not in rows[0]:
        return None
    out: list[float] = []
    for r in rows:
        try:
            out.append(float(r["close"]))
        except (KeyError, ValueError):
            continue
    return out or None


def load_vix_snapshot(
    fred_data_dir: Path = DEFAULT_FRED_DIR,
) -> VixSeriesSnapshot | None:
    """VIX.csv → VixSeriesSnapshot (publication_ts_utc, close 昇順) (test fixture 用)."""
    rows = _read_csv_dict(fred_data_dir / "VIX.csv")
    if rows is None:
        return None
    obs: list[tuple[datetime, float]] = []
    for r in rows:
        ts = _parse_dt_utc(r.get("publication_ts_utc", "") or r.get("date", ""))
        if ts is None:
            continue
        try:
            close = float(r["close"])
        except (KeyError, ValueError):
            continue
        obs.append((ts, close))
    if not obs:
        return None
    obs.sort(key=lambda x: x[0])
    try:
        return VixSeriesSnapshot(observations=tuple(obs))
    except ValueError as exc:
        logger.warning("aux_loader.vix_invalid", error=str(exc))
        return None


def load_event_calendar(
    calendar_path: Path = DEFAULT_CALENDAR_PATH,
) -> EconomicCalendar | None:
    """events.csv → EconomicCalendar."""
    rows = _read_csv_dict(calendar_path)
    if rows is None:
        return None
    events: list[EconomicEvent] = []
    for r in rows:
        ts = _parse_dt_utc(r.get("event_time_utc", ""))
        if ts is None:
            continue
        try:
            currency = str(r["currency"]).strip().upper()
            name = str(r.get("name", "")).strip() or "(unknown)"
            impact = int(r["impact"])
        except (KeyError, ValueError):
            continue
        forecast_raw = r.get("forecast", "")
        actual_raw = r.get("actual", "")
        forecast = (
            Decimal(forecast_raw) if forecast_raw and forecast_raw != "" else None
        )
        actual = (
            Decimal(actual_raw) if actual_raw and actual_raw != "" else None
        )
        events.append(
            EconomicEvent(
                event_time=ts,
                currency=currency,
                name=name,
                impact=impact,
                forecast=forecast,
                actual=actual,
            )
        )
    if not events:
        return None
    return EconomicCalendar(events)


def load_event_snapshot(
    *,
    as_of: datetime,
    as_of_strict: bool = False,
    calendar_path: Path = DEFAULT_CALENDAR_PATH,
) -> EconomicEventSnapshot | None:
    """events.csv → EconomicEventSnapshot."""
    cal = load_event_calendar(calendar_path)
    if cal is None:
        return None
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    return EconomicEventSnapshot(
        calendar=cal, as_of=as_of, as_of_strict=as_of_strict
    )


def load_aux_series(
    fred_data_dir: Path = DEFAULT_FRED_DIR,
) -> dict[str, list[float]]:
    """macro 系 aux series を CSV から load (Phase 1 互換、test fixture 用)."""
    out: dict[str, list[float]] = {}
    for key, fname in (
        ("macro.dxy", "DXY.csv"),
        ("macro.copper", "copper.csv"),
        ("macro.commodity_index", "commodity_index.csv"),
        ("macro.gold", "gold.csv"),
    ):
        path = fred_data_dir / fname
        rows = _read_csv_dict(path)
        if rows is None:
            continue
        values: list[float] = []
        for r in rows:
            try:
                values.append(float(r["close"]))
            except (KeyError, ValueError):
                continue
        if values:
            out[key] = values
    return out


def build_aux_bundle(
    *,
    as_of: datetime,
    as_of_strict: bool = False,
    fred_data_dir: Path = DEFAULT_FRED_DIR,
    calendar_path: Path = DEFAULT_CALENDAR_PATH,
) -> AuxBundle:
    """CSV 経路 (Phase 1 互換, test fixture 用)。

    既存テストの後方互換のため、`aux_series` / `event_snapshot` / `vix_snapshot` /
    `aux_pair_bars` をそのまま埋める。`daily_series` / `aux_pair_bars_index` は
    空のままにする (新 align_to 経路はテスト fixture では未使用)。
    """
    event_snapshot = load_event_snapshot(
        as_of=as_of,
        as_of_strict=as_of_strict,
        calendar_path=calendar_path,
    )
    vix_snapshot = load_vix_snapshot(fred_data_dir)
    aux_series = load_aux_series(fred_data_dir)
    return AuxBundle(
        aux_series=aux_series,
        event_snapshot=event_snapshot,
        vix_snapshot=vix_snapshot,
        aux_pair_bars={},
        event_calendar=load_event_calendar(calendar_path),
    )


# ---------------------------------------------------------------------------
# DB readers (Gate B: SSOT 一本化)
# ---------------------------------------------------------------------------


def load_daily_series_from_db(
    *,
    db_session: Session,
    series_id: str,
    period: tuple[datetime, datetime],
) -> list[DailyObservation]:
    """`MacroIndexDaily` から `DailyObservation` list を読み出す (時系列昇順).

    period (start, end) で filter。preflight buffer として
    `max_policy_lag_days() + 7` 日を `period[0]` 側に拡張して取得する
    (月次系列の lag を吸収)。
    """
    buffer_days = max_policy_lag_days() + 7
    start_date = period[0].date() - timedelta(days=buffer_days)
    end_date = period[1].date()
    rows = (
        db_session.scalars(
            select(MacroIndexDaily)
            .where(MacroIndexDaily.series_id == series_id)
            .where(MacroIndexDaily.date >= start_date)
            .where(MacroIndexDaily.date <= end_date)
            .order_by(MacroIndexDaily.date.asc())
        )
        .all()
    )
    out: list[DailyObservation] = []
    for r in rows:
        if r.value is None:
            continue
        eff = _row_effective_from_utc(r)
        out.append(
            DailyObservation(
                observation_date=r.date,
                value=float(r.value),
                effective_from_utc=eff,
                source=_row_source(r),
            )
        )
    return out


def _row_effective_from_utc(r: MacroIndexDaily) -> datetime:
    """row の `effective_from_utc` 列を返す。NULL の場合は policy で補完する.

    Migration 004 適用前の test 環境互換のため defensive.
    """
    eff = getattr(r, "effective_from_utc", None)
    if eff is not None:
        if eff.tzinfo is None:
            return eff.replace(tzinfo=UTC)
        return eff.astimezone(UTC)
    return compute_effective_from_utc(r.series_id, r.date)


def _row_source(r: MacroIndexDaily) -> Literal[
    "fred_realtime_start", "policy_conservative", "oanda_release_time"
]:
    src = getattr(r, "source", None)
    if src in (
        EffectiveFromSource.POLICY_CONSERVATIVE.value,
        EffectiveFromSource.FRED_REALTIME_START.value,
        EffectiveFromSource.OANDA_RELEASE_TIME.value,
    ):
        return src  # type: ignore[return-value]
    return "policy_conservative"


def load_aux_pair_bars_index(
    *,
    db_session: Session,
    pairs: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, dict[datetime, PriceBar]]:
    """aux pair の M1 bars を bar_time index で取得する.

    bar_time は M1 解像度に正規化 (tz-aware UTC + 秒切り捨て)。
    同 minute に複数 PriceBar がある場合は **fail-fast** (V15 反映).

    Returns:
        pair_id → {normalized_bar_time: PriceBar} の dict.
        align_to 側で target_bars をループしながら lookup する設計.
        欠番は None で padding される (caller 責務).
    """
    out: dict[str, dict[datetime, PriceBar]] = {}
    for pair_id in pairs:
        pair = db_session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == pair_id)
        ).one_or_none()
        if pair is None:
            out[pair_id] = {}
            logger.warning(
                "aux_loader.aux_pair_bars.pair_not_found",
                pair=pair_id,
            )
            continue
        rows = (
            db_session.scalars(
                select(PriceBarM1)
                .where(PriceBarM1.pair_id == pair.id)
                .where(PriceBarM1.bar_time >= period[0])
                .where(PriceBarM1.bar_time < period[1])
                .order_by(PriceBarM1.bar_time.asc())
            )
            .all()
        )
        index: dict[datetime, PriceBar] = {}
        for r in rows:
            key = _normalize_bar_time(r.bar_time)
            if key in index:
                # V15: 同 minute に複数 row → fail-fast (異常データ)
                raise ValueError(
                    f"aux_pair_bars duplicate bar_time after normalize "
                    f"for pair={pair_id} bar_time={key.isoformat()}"
                )
            index[key] = _bar_row_to_price_bar(r, pair_id)
        out[pair_id] = index
    return out


def _bar_row_to_price_bar(r: PriceBarM1, pair_name: str) -> PriceBar:
    return PriceBar(
        pair_name=pair_name,
        bar_time=r.bar_time,
        bid=Ohlc(
            open=r.open_bid,
            high=r.high_bid,
            low=r.low_bid,
            close=r.close_bid,
        ),
        ask=Ohlc(
            open=r.open_ask,
            high=r.high_ask,
            low=r.low_ask,
            close=r.close_ask,
        ),
        volume=r.volume,
        complete=r.complete,
    )


def build_aux_bundle_from_db(
    *,
    db_session: Session,
    period: tuple[datetime, datetime],
    series_ids: Sequence[str],
    aux_pairs: Sequence[str] = (),
    calendar_path: Path = DEFAULT_CALENDAR_PATH,
) -> AuxBundle:
    """DB SSOT から AuxBundle (raw) を構築する (Gate B production entry).

    Args:
        db_session: SQLAlchemy session.
        period: 取得対象期間 (UTC datetime range).
        series_ids: macro_index_daily から取得する series_id list.
        aux_pairs: aux_pair_bars として取得する OANDA pair name list.
            default は空 (P5 不要なら空のままでよい).
        calendar_path: economic_event は DB ではなく CSV 経路を維持
            (Phase 2 段階では DB ↔ CSV 経路の整合は別 TODO).

    Returns:
        AuxBundle. `daily_series` / `aux_pair_bars_index` / `event_calendar` /
        `vix_snapshot` を埋めて返す.
    """
    daily_series: dict[str, list[DailyObservation]] = {}
    for series_id in series_ids:
        observations = load_daily_series_from_db(
            db_session=db_session,
            series_id=series_id,
            period=period,
        )
        daily_series[series_id] = observations

    # vix_snapshot を VIXCLS 由来で構築 (publication_ts = effective_from_utc)
    vix_snapshot: VixSeriesSnapshot | None = None
    vixcls_obs = daily_series.get("VIXCLS")
    if vixcls_obs:
        obs_pairs = tuple(
            (o.effective_from_utc, o.value) for o in vixcls_obs
        )
        try:
            vix_snapshot = VixSeriesSnapshot(observations=obs_pairs)
        except ValueError as exc:
            logger.warning(
                "aux_loader.vix_snapshot_invalid",
                error=str(exc),
            )
            vix_snapshot = None

    aux_pair_bars_index = (
        load_aux_pair_bars_index(
            db_session=db_session,
            pairs=aux_pairs,
            period=period,
        )
        if aux_pairs
        else {}
    )

    event_calendar = load_event_calendar(calendar_path)

    return AuxBundle(
        daily_series=daily_series,
        event_calendar=event_calendar,
        vix_snapshot=vix_snapshot,
        aux_pair_bars_index=aux_pair_bars_index,
    )
