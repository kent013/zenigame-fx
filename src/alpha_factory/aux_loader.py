"""T047: pair_specific 用 aux data loader Phase 1 (scaffold + API).

production GA で `RegistryEvaluator` に注入する `EconomicEventSnapshot` /
`VixSeriesSnapshot` / `aux_series` / `aux_pair_bars` を構築する loader。
Phase 1 では CSV ベースの最小実装を提供し、データ未配置時は **空 snapshot を
返す**ことで既存挙動 (safe default 経路) との後方互換を保つ。

データ配置:
- ``data/raw/fred/DXY.csv`` (date, close)
- ``data/raw/fred/VIX.csv`` (publication_ts_utc, close)  # daily 想定
- ``data/raw/fred/copper.csv`` (date, close)
- ``data/raw/fred/gold.csv`` (date, close)
- ``data/raw/calendar/events.csv`` (event_time_utc, currency, name, impact)

CSV が無い場合は **None / 空 snapshot** を返し、production runner 側で
`strict_aux_required` を False にしておけば従来通りの safe default で動作。
strict mode を有効化するときはデータ配置を必須にする (T046 連動)。

詳細: devnotes/20260427-0100-bug-pair-specific-aux-loader/
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import structlog

from src.alpha_factory.primitives._base import (
    EconomicEventSnapshot,
    VixSeriesSnapshot,
)
from src.domain.price import PriceBar
from src.events.calendar import EconomicCalendar, EconomicEvent

logger = structlog.get_logger(__name__)

__all__ = [
    "DEFAULT_CALENDAR_PATH",
    "DEFAULT_FRED_DIR",
    "AuxBundle",
    "build_aux_bundle",
    "load_aux_series",
    "load_dxy_series",
    "load_event_calendar",
    "load_event_snapshot",
    "load_vix_snapshot",
]

DEFAULT_FRED_DIR: Final[Path] = Path("data/raw/fred")
DEFAULT_CALENDAR_PATH: Final[Path] = Path("data/raw/calendar/events.csv")


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


class AuxBundle:
    """RegistryEvaluator に渡す aux bundle (production runner 用 SSOT)."""

    __slots__ = (
        "aux_pair_bars",
        "aux_series",
        "event_snapshot",
        "vix_snapshot",
    )

    def __init__(
        self,
        *,
        event_snapshot: EconomicEventSnapshot | None,
        vix_snapshot: VixSeriesSnapshot | None,
        aux_series: Mapping[str, Sequence[float]],
        aux_pair_bars: Mapping[str, Sequence[PriceBar | None]],
    ) -> None:
        self.event_snapshot = event_snapshot
        self.vix_snapshot = vix_snapshot
        self.aux_series = dict(aux_series)
        self.aux_pair_bars = dict(aux_pair_bars)


# ---------------------------------------------------------------------------
# CSV helpers
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
# Loaders
# ---------------------------------------------------------------------------


def load_dxy_series(
    fred_data_dir: Path = DEFAULT_FRED_DIR,
) -> list[float] | None:
    """DXY close 列を float list で返す (時系列の昇順)。

    aux_series['macro.dxy'] として primitive (P9 等) に渡す想定。
    ファイル不在 / close 列不在 / 空なら None。
    """
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
    """VIX.csv → VixSeriesSnapshot (publication_ts_utc, close 昇順)。

    publication_ts_utc が tz-aware datetime であることを strict 化
    (`VixSeriesSnapshot.__post_init__` がチェック)。
    """
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
    """events.csv → EconomicCalendar.

    columns: event_time_utc, currency, name, impact (1=Low, 2=Medium, 3=High)
    """
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
    """events.csv → EconomicEventSnapshot.

    `as_of` の tz-aware は EconomicEventSnapshot.__post_init__ で強制 (T039)。
    """
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
    """macro 系 aux series を load (DXY / VIX close / Copper / Gold)。

    primitive の required_data 規約 (key = "macro.<name>") に合わせて返す。
    ファイル不在のキーは含まれない (空 dict)。
    """
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
    """production runner で RegistryEvaluator 構築用に呼ぶ entry point.

    各 source から CSV を読み snapshot/aux_series を組み立てる。
    データ不在時は対応 field に None / 空 dict を入れる (後方互換)。
    """
    event_snapshot = load_event_snapshot(
        as_of=as_of,
        as_of_strict=as_of_strict,
        calendar_path=calendar_path,
    )
    vix_snapshot = load_vix_snapshot(fred_data_dir)
    aux_series = load_aux_series(fred_data_dir)
    # aux_pair_bars (cross-pair bars) は別 TODO で整備、Phase 1 では空
    aux_pair_bars: dict[str, list[Any]] = {}
    return AuxBundle(
        event_snapshot=event_snapshot,
        vix_snapshot=vix_snapshot,
        aux_series=aux_series,
        aux_pair_bars=aux_pair_bars,
    )
