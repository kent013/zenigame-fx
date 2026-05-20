"""T057 Phase 2 Gate A/B: aux data loader (raw container + per-stage alignment).

production GA で `RegistryEvaluator` に注入する `EconomicEventSnapshot` /
`VixSeriesSnapshot` / `aux_series` / `aux_pair_mid_close` を構築する loader。

設計の柱:
    - **AuxBundle (raw container)**: DB / CSV 由来の生データを保持する
      `daily_series` / `event_calendar` / `aux_pair_mid_index` の dict を持つ。
    - **AlignedAuxBundle (per-stage)**: `AuxBundle.align_to(bars)` で bars と
      同じ長さに整列された `aux_series: dict[str, np.ndarray]` /
      `aux_pair_mid_close: dict[str, np.ndarray]` 等を持つ (T107 columnar)。
    - **AuxAlignmentCache**: stage 別 (Stage A 60d / Stage B 18m / holdout) に
      align 結果を 1 度だけ計算してキャッシュする。

look-ahead bias 防止:
    - `DailyObservation.effective_from_utc` (`src/ingest/effective_from.py`)
      でしか forward-fill を許さない。`bar.bar_time >= obs.effective_from_utc`
      を満たす最新 obs を採用する.
    - aux pair は M1 解像度に正規化 (tz-aware UTC + 秒切り捨て) した epoch ns で
      columnar 保持し、align_to が searchsorted exact-match で整列する (欠番 NaN)。
    - 同一 minute に複数 row が DB にある場合は **fail-fast** (ValueError).

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
from src.domain.price import PriceBar
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
    "AuxPairMidSeries",
    "DailyObservation",
    "build_aux_bundle",
    "build_aux_bundle_from_db",
    "load_aux_pair_mid_index",
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

# T106: aux pair bars の server-side cursor streaming バッチサイズ
# (run_ga._LOAD_BARS_BATCH_SIZE と同値で一貫させる)。
_LOAD_BARS_BATCH_SIZE: Final[int] = 10_000

# T106: PriceBar 構築に必要な列のみ取得 (ORM entity を identity map に載せない)。
_PRICE_BAR_M1_COLUMNS: Final = (
    PriceBarM1.bar_time,
    PriceBarM1.open_bid,
    PriceBarM1.high_bid,
    PriceBarM1.low_bid,
    PriceBarM1.close_bid,
    PriceBarM1.open_ask,
    PriceBarM1.high_ask,
    PriceBarM1.low_ask,
    PriceBarM1.close_ask,
    PriceBarM1.volume,
    PriceBarM1.complete,
)

# T107: aux pair mid streaming に必要な列のみ (bid/ask close)。
_AUX_PAIR_MID_COLUMNS: Final = (
    PriceBarM1.bar_time,
    PriceBarM1.close_bid,
    PriceBarM1.close_ask,
)

# T107: epoch ナノ秒の単一権威 (float 経路を使わず整数算出)。
_EPOCH_UTC: Final = datetime(1970, 1, 1, tzinfo=UTC)


def _to_epoch_ns(dt: datetime) -> int:
    """tz-aware/naive datetime → UTC epoch ナノ秒 int (T107)。

    epoch 単位の単一権威。float 経路 (timestamp()*1e9) は丸め誤差を生むため
    使わず、 timedelta の整数フィールド (days/seconds/microseconds) から ns を
    整数算出する。raw 構築と target 整列の双方が本関数のみを使う契約。
    """
    d = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    d = d.astimezone(UTC)
    delta = d - _EPOCH_UTC
    total_us = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    return total_us * 1_000


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
class AuxPairMidSeries:
    """aux pair の bar_time → mid_close を columnar に保持する (T107).

    契約 (構築時 fail-fast 検証):
      - ts_epoch_ns: UTC epoch ナノ秒 int64、 strict monotonic increasing + unique
      - mid_close: float64、 ts_epoch_ns と同一長
      - mid_close[i] = (bid_close + ask_close)/2 (P5 と同一の float 演算)
    両配列は read-only。pickle 復元後も __setstate__ で再 freeze する
    (cross-evaluation contamination 防御)。
    """

    ts_epoch_ns: np.ndarray
    mid_close: np.ndarray

    def _validate_and_freeze(self) -> None:
        """dtype/shape/strict monotonic を fail-fast 検証し read-only 化する。

        searchsorted exact-match が依存する不変条件 (sorted/unique) を構築・
        復元の両時点で保証する。setflags は in-place なので frozen でも可。
        """
        ts, mid = self.ts_epoch_ns, self.mid_close
        if ts.dtype != np.int64 or mid.dtype != np.float64:
            raise ValueError(
                f"AuxPairMidSeries dtype invalid: ts={ts.dtype} mid={mid.dtype}"
            )
        if ts.ndim != 1 or mid.ndim != 1 or ts.shape != mid.shape:
            raise ValueError(
                f"AuxPairMidSeries shape invalid: ts={ts.shape} mid={mid.shape}"
            )
        if ts.size > 1 and not bool(np.all(np.diff(ts) > 0)):
            raise ValueError(
                "AuxPairMidSeries ts_epoch_ns must be strict monotonic + unique"
            )
        ts.setflags(write=False)
        mid.setflags(write=False)

    def __post_init__(self) -> None:
        self._validate_and_freeze()

    def __setstate__(self, state: dict) -> None:
        # unpickle 後に検証 + read-only 再適用 (pickle は writable に戻すため)。
        # slots 化耐性のため object.__setattr__ を使う。
        object.__setattr__(self, "ts_epoch_ns", state["ts_epoch_ns"])
        object.__setattr__(self, "mid_close", state["mid_close"])
        self._validate_and_freeze()


def _empty_aux_pair_mid_series() -> AuxPairMidSeries:
    """read-only 空 AuxPairMidSeries (pair_not_found 等で使用)."""
    ts = np.empty(0, dtype=np.int64)
    mid = np.empty(0, dtype=np.float64)
    return AuxPairMidSeries(ts_epoch_ns=ts, mid_close=mid)


@dataclass(frozen=True)
class AlignedAuxBundle:
    """bars と同じ長さに整列済みの aux bundle (per-stage instance).

    `aux_series` は `np.ndarray[float64]`、長さは bars と完全一致。
    `aux_pair_mid_close` は cross-pair の mid close 整列配列 (欠番 NaN, read-only)。
    """

    aux_series: Mapping[str, np.ndarray]
    event_snapshot: EconomicEventSnapshot | None
    vix_snapshot: VixSeriesSnapshot | None
    aux_pair_mid_close: Mapping[str, np.ndarray]

    def as_evaluator_kwargs(self) -> dict[str, Any]:
        """RegistryEvaluator constructor に渡す dict."""
        return {
            "aux_series": dict(self.aux_series),
            "event_snapshot": self.event_snapshot,
            "vix_snapshot": self.vix_snapshot,
            "aux_pair_mid_close": dict(self.aux_pair_mid_close),
        }


@dataclass
class AuxBundle:
    """Raw aux container — stage 別 bars に align される前.

    Phase 1 互換のため、後方互換のフィールド (`aux_series` / `event_snapshot` /
    `vix_snapshot`) も保持する。これらは「全 bars にわたって pre-align された
    結果ではなく、生データそのもの」である。

    T107: aux pair は重い `dict[datetime, PriceBar]` ではなく columnar
    `AuxPairMidSeries` (ts_epoch_ns + mid_close) で保持する。
    """

    daily_series: dict[str, list[DailyObservation]] = field(default_factory=dict)
    event_calendar: EconomicCalendar | None = None
    vix_snapshot: VixSeriesSnapshot | None = None
    aux_pair_mid_index: dict[str, AuxPairMidSeries] = field(
        default_factory=dict
    )

    # ---- Phase 1 後方互換 ----
    # build_aux_bundle (CSV 経路) は既存テスト互換のため `aux_series: list[float]`
    # / `event_snapshot` を保持できる
    aux_series: dict[str, list[float]] = field(default_factory=dict)
    event_snapshot: EconomicEventSnapshot | None = None

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
                aux_pair_mid_close={},
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

        # 4. aux_pair_mid_close: target bars の epoch に searchsorted で exact-match。
        #    align_to is the sole authority for exact timestamp matching (SSOT)。
        #    forward-fill 禁止 (exact-match のみ、 look-ahead 防止)。consumer は
        #    bar_time を再検証しない。欠番は NaN。
        # raw 側と同じ正規化 (秒/マイクロ秒切捨て) を target にも適用する。
        # 非対称だと target に秒成分があるとき silent NaN になるため (T107 review)。
        target_ns = np.fromiter(
            (_to_epoch_ns(_normalize_bar_time(b.bar_time)) for b in bars),
            dtype=np.int64,
            count=n,
        )
        aux_pair_mid_close: dict[str, np.ndarray] = {}
        for pair_name, series in self.aux_pair_mid_index.items():
            out = np.full(n, np.nan, dtype=np.float64)
            raw_ts = series.ts_epoch_ns
            if raw_ts.size > 0:
                pos = np.searchsorted(raw_ts, target_ns, side="left")
                in_range = pos < raw_ts.size
                valid = np.zeros(n, dtype=bool)
                # exact-match 行のみ採用 (raw_ts[pos] == target_ns)
                valid[in_range] = raw_ts[pos[in_range]] == target_ns[in_range]
                out[valid] = series.mid_close[pos[valid]]
            out.setflags(write=False)
            aux_pair_mid_close[pair_name] = out

        return AlignedAuxBundle(
            aux_series=aux_series,
            event_snapshot=event_snapshot,
            vix_snapshot=vix_snapshot,
            aux_pair_mid_close=aux_pair_mid_close,
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

    aux pair の bar_time 整列で target bars と DB の datetime
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

    既存テストの後方互換のため、`aux_series` / `event_snapshot` / `vix_snapshot`
    をそのまま埋める。`daily_series` / `aux_pair_mid_index` は空のままにする
    (CSV 経路は aux pair を持たない)。
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


def load_aux_pair_mid_index(
    *,
    db_session: Session,
    pairs: Sequence[str],
    period: tuple[datetime, datetime],
) -> dict[str, AuxPairMidSeries]:
    """aux pair の M1 mid close を columnar (ts_epoch_ns + mid_close) で取得する (T107).

    bar_time は M1 解像度に正規化 (tz-aware UTC + 秒切り捨て) し epoch ns へ変換。
    同 minute に複数 row / 非単調がある場合は **fail-fast** (V15 + monotonic/unique).

    Returns:
        pair_name → AuxPairMidSeries (ts_epoch_ns sorted/unique + mid_close).
        align_to が searchsorted で exact-match 整列する (SSOT)。
    """
    out: dict[str, AuxPairMidSeries] = {}
    for pair_name in pairs:
        pair = db_session.scalars(
            select(CurrencyPair).where(CurrencyPair.oanda_name == pair_name)
        ).one_or_none()
        if pair is None:
            out[pair_name] = _empty_aux_pair_mid_series()
            logger.warning(
                "aux_loader.aux_pair_bars.pair_not_found",
                pair=pair_name,
            )
            continue
        out[pair_name] = _stream_aux_pair_mid(
            db_session,
            pair_db_id=pair.id,
            pair_name=pair_name,
            start=period[0],
            end=period[1],
        )
    return out


def _stream_aux_pair_mid(
    db_session: Session,
    *,
    pair_db_id: int,
    pair_name: str,
    start: datetime,
    end: datetime,
    batch_size: int = _LOAD_BARS_BATCH_SIZE,
) -> AuxPairMidSeries:
    """server-side cursor streaming で (ts_epoch_ns, mid_close) を構築する (T107).

    bid/ask close のみ取得 (PriceBar dataclass を作らない)。 caller-owned
    ``db_session`` を渡すが ORM entity ではなく必要列のみ取得するため identity
    map を汚さない。 ORDER BY asc + ns<=prev で strict monotonic + unique を
    fail-fast 検証 (V15: 同 minute normalize 重複も検出)。 途中例外時も
    ``result.close()`` で cursor を解放。 row は属性アクセスのみで消費する。
    """
    stmt = (
        select(*_AUX_PAIR_MID_COLUMNS)
        .where(PriceBarM1.pair_id == pair_db_id)
        .where(PriceBarM1.bar_time >= start)
        .where(PriceBarM1.bar_time < end)
        .order_by(PriceBarM1.bar_time.asc())
        .execution_options(yield_per=batch_size)
    )
    ts_list: list[int] = []
    mid_list: list[float] = []
    seen_last_ns: int | None = None
    result = db_session.execute(stmt)
    try:
        for row in result:
            key = _normalize_bar_time(row.bar_time)  # tz-aware UTC, 秒切捨て
            ns = _to_epoch_ns(key)
            if seen_last_ns is not None and ns <= seen_last_ns:
                # V15 + monotonic/unique: normalize 重複 or 非単調 → fail-fast
                raise ValueError(
                    f"aux_pair_mid non-monotonic/duplicate bar_time after "
                    f"normalize for pair={pair_name} ns={ns} (prev={seen_last_ns})"
                )
            seen_last_ns = ns
            ts_list.append(ns)
            # P5 と同一の float 演算順序 (bid+ask)*0.5
            mid_list.append((float(row.close_bid) + float(row.close_ask)) * 0.5)
    finally:
        result.close()
    ts = np.asarray(ts_list, dtype=np.int64)
    mid = np.asarray(mid_list, dtype=np.float64)
    return AuxPairMidSeries(ts_epoch_ns=ts, mid_close=mid)


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
        aux_pairs: aux pair mid として取得する OANDA pair name list.
            default は空 (P5 不要なら空のままでよい).
        calendar_path: economic_event は DB ではなく CSV 経路を維持
            (Phase 2 段階では DB ↔ CSV 経路の整合は別 TODO).

    Returns:
        AuxBundle. `daily_series` / `aux_pair_mid_index` / `event_calendar` /
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

    aux_pair_mid_index = (
        load_aux_pair_mid_index(
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
        aux_pair_mid_index=aux_pair_mid_index,
    )
