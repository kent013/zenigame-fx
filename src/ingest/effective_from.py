"""effective_from_utc 計算 (T057 Phase 2 Gate A).

DailyObservation の `effective_from_utc` 契約は **保守的 policy** を既定とする:

- daily 系列 (VIXCLS / DTWEXBGS / SP500 など): observation_date + 24h
- 月次系列 (PCOPPUSDM / PALLFNFINDEXM): observation_date + 35d (lag を吸収)

`alpha_factory.aux_loader` と `ingest.fred` の両方からインポートされるため、
レイヤ汚染を避けるためここに分離する (Round 1 [Warning] 反映).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Final


class EffectiveFromSource(StrEnum):
    """effective_from_utc の出所を区別する enum (Round 1 [Suggestion] 反映)."""

    POLICY_CONSERVATIVE = "policy_conservative"
    FRED_REALTIME_START = "fred_realtime_start"  # 将来 TODO で昇格
    OANDA_RELEASE_TIME = "oanda_release_time"   # 将来拡張


# series 別の保守的 lag (時間単位).
# observation_date + lag_hours = effective_from_utc.
# 月次系列 (PCOPPUSDM / PALLFNFINDEXM) は 35 日 lag で改定遅延を吸収.
SERIES_POLICY_CONSERVATIVE: Final[dict[str, dict[str, int]]] = {
    "VIXCLS":           {"lag_hours": 24},
    "DTWEXBGS":         {"lag_hours": 24},
    "DGS10":            {"lag_hours": 24},
    "DGS2":             {"lag_hours": 24},
    "T10YIE":           {"lag_hours": 24},
    "GC_F_YAHOO":       {"lag_hours": 24},   # Yahoo Finance Gold Futures (FRED LBMA Gold 廃止 後継)
    "DCOILWTICO":       {"lag_hours": 24},
    "PCOPPUSDM":        {"lag_hours": 24 * 35},
    "PALLFNFINDEXM":    {"lag_hours": 24 * 35},
    "SP500":            {"lag_hours": 24},
}


_DEFAULT_LAG_HOURS: Final[int] = 24


def compute_effective_from_utc(series_id: str, observation_date: date) -> datetime:
    """observation_date + 保守的 lag で effective_from_utc を返す (UTC tz-aware).

    未知 series は `_DEFAULT_LAG_HOURS` (=24h) を採用する。
    """
    lag = SERIES_POLICY_CONSERVATIVE.get(
        series_id, {"lag_hours": _DEFAULT_LAG_HOURS}
    )["lag_hours"]
    return datetime.combine(observation_date, time.min, tzinfo=UTC) + timedelta(
        hours=lag
    )


def max_policy_lag_days() -> int:
    """SERIES_POLICY_CONSERVATIVE の最大 lag (日単位).

    aux_loader の DB filter buffer (period 開始の何日前まで遡るか) 計算に使用。
    月次系列を含めると 35 日。
    """
    if not SERIES_POLICY_CONSERVATIVE:
        return _DEFAULT_LAG_HOURS // 24
    return max(p["lag_hours"] // 24 for p in SERIES_POLICY_CONSERVATIVE.values())
