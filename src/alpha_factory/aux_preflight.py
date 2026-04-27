"""T057 Gate B/C: aux data preflight check (run_ga 起動時).

設計の核:
    - **HARD_REQUIRED**: 不足すると本番 RUN を fail-closed (override 可).
      VIXCLS / DTWEXBGS (DXY) / EUR_USD_M1 / USD_JPY_M1.
    - **SOFT_REQUIRED**: 不足は WARN log のみ (該当 primitive は safe default 経路).
      Gold / WTI / Copper / commodity_index / SP500.
    - **finite coverage check**: 単に行数があるだけではなく、period extended で
      `finite_coverage_pct >= min_finite_coverage_pct (50%)` を要求 (V13).
    - **両端 freshness check**: `latest_effective_from >= extended_start` も要求.

preflight period は **Stage B 18ヶ月 + holdout** を含めて計算 (Round 1 [Critical] 反映).

詳細: devnotes/20260427-2234-aux-data-loader-phase2/detailed-design.md §施策7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import CurrencyPair, MacroIndexDaily, PriceBarM1
from src.ingest.effective_from import max_policy_lag_days

logger = structlog.get_logger(__name__)


# series_id → primitive 側 aux_series key の説明 (log 用)
HARD_REQUIRED_AUX: Final[dict[str, str]] = {
    "VIXCLS": "macro.vix",
    "DTWEXBGS": "macro.dxy",
}
HARD_REQUIRED_PAIRS: Final[tuple[str, ...]] = ("EUR_USD", "USD_JPY")

SOFT_REQUIRED_AUX: Final[dict[str, str]] = {
    "GOLDPMGBD228NLBM": "macro.gold",
    "DCOILWTICO": "macro.wti",
    "PCOPPUSDM": "macro.copper",
    "PALLFNFINDEXM": "macro.commodity_index",
    "SP500": "macro.spx500",
}


def compute_extended_period(
    period: tuple[datetime, datetime],
    *,
    stage_b_window_months: int,
    stage_c_holdout_days: int,
) -> tuple[datetime, datetime]:
    """preflight / aux_bundle 構築で共通使用する拡張期間計算 helper.

    Codex impl-review-round-2 [Suggestion] 反映: preflight と
    `build_aux_bundle_from_db` で同じロジックを使い、period のズレで
    `safe default 経路` に落ちるリスクを排除する.

    Args:
        period: dataset (start, end).
        stage_b_window_months: Stage B history を含めるための月数 (1ヶ月=30日 換算).
        stage_c_holdout_days: holdout 日数.

    Returns:
        (extended_start, extended_end) tuple.
    """
    extended_start = period[0] - timedelta(days=stage_b_window_months * 30)
    extended_end = period[1] + timedelta(days=stage_c_holdout_days)
    return extended_start, extended_end


@dataclass(frozen=True)
class PreflightResult:
    """preflight check 結果."""

    hard_satisfied: list[str] = field(default_factory=list)
    hard_missing: list[str] = field(default_factory=list)
    soft_satisfied: list[str] = field(default_factory=list)
    soft_missing: list[str] = field(default_factory=list)
    coverage_pct_by_series: dict[str, float] = field(default_factory=dict)
    latest_effective_from_by_series: dict[str, datetime | None] = field(
        default_factory=dict
    )

    @property
    def passes(self) -> bool:
        return not self.hard_missing


def _series_finite_coverage_pct(
    db_session: Session,
    series_id: str,
    period: tuple[datetime, datetime],
) -> float:
    """series の period 内で「value が non-NULL の日 / 期間日数」を 0-100 で返す.

    Codex impl-review-round-1 [Warning] 反映: 全件 ORM ロード回避し DB 側 COUNT.
    """
    period_days = max(1, int((period[1] - period[0]).total_seconds() // 86400))
    finite = db_session.execute(
        select(func.count())
        .select_from(MacroIndexDaily)
        .where(MacroIndexDaily.series_id == series_id)
        .where(MacroIndexDaily.date >= period[0].date())
        .where(MacroIndexDaily.date <= period[1].date())
        .where(MacroIndexDaily.value.is_not(None))
    ).scalar_one()
    return min(100.0, 100.0 * float(finite) / period_days)


def _series_latest_effective_from(
    db_session: Session, series_id: str
) -> datetime | None:
    rows = (
        db_session.scalars(
            select(MacroIndexDaily)
            .where(MacroIndexDaily.series_id == series_id)
            .order_by(MacroIndexDaily.date.desc())
        )
        .all()
    )
    if not rows:
        return None
    for r in rows:
        eff = getattr(r, "effective_from_utc", None)
        if eff is not None:
            # SQLite からは naive datetime で返ることがあるため tz-aware に正規化
            if eff.tzinfo is None:
                eff = eff.replace(tzinfo=UTC)
            return eff
    return None


def _pair_bars_finite_coverage_pct(
    db_session: Session,
    pair_id: str,
    period: tuple[datetime, datetime],
) -> float:
    """pair_bars の period 内 finite coverage を 0-100 で返す (M1 解像度)."""
    pair = db_session.scalars(
        select(CurrencyPair).where(CurrencyPair.oanda_name == pair_id)
    ).one_or_none()
    if pair is None:
        return 0.0
    # Codex impl-review-round-1 [Warning] 反映: 18ヶ月 M1 = 約 70 万 row のため
    # 全件 ORM ロード ({.all()} → len) を避けて DB 側 COUNT(*) を使う.
    n_rows = db_session.execute(
        select(func.count())
        .select_from(PriceBarM1)
        .where(PriceBarM1.pair_id == pair.id)
        .where(PriceBarM1.bar_time >= period[0])
        .where(PriceBarM1.bar_time < period[1])
    ).scalar_one()
    expected_minutes = max(1, int((period[1] - period[0]).total_seconds() // 60))
    return min(100.0, 100.0 * float(n_rows) / expected_minutes)


def preflight_check_aux_data(
    *,
    db_session: Session,
    period: tuple[datetime, datetime],
    stage_b_window_months: int,
    stage_c_holdout_days: int,
    allow_missing: bool = False,
    min_finite_coverage_pct: float = 50.0,
) -> PreflightResult:
    """aux データの preflight check を行う.

    Args:
        db_session: SQLAlchemy session.
        period: dataset (start, end) (Stage A 評価期間 = dataset).
        stage_b_window_months: stage_gate.stage_b_window_months
            (extended_start 計算用).
        stage_c_holdout_days: stage_gate.stage_c_holdout_days
            (extended_end 計算用).
        allow_missing: True なら hard_missing でも raise しない (--allow-aux-missing).
        min_finite_coverage_pct: finite coverage の下限 (0-100, 既定 50%).

    Returns:
        PreflightResult.

    Raises:
        RuntimeError: hard_missing があり allow_missing=False の場合.
    """
    # Stage B 18ヶ月履歴 + holdout を含む拡張 period (compute_extended_period 統一)
    extended_period = compute_extended_period(
        period,
        stage_b_window_months=stage_b_window_months,
        stage_c_holdout_days=stage_c_holdout_days,
    )
    extended_start, extended_end = extended_period

    coverage: dict[str, float] = {}
    latest_eff: dict[str, datetime | None] = {}
    safety_lag_days = max_policy_lag_days() + 7

    def _check_series(series: str) -> bool:
        cov = _series_finite_coverage_pct(db_session, series, extended_period)
        coverage[series] = cov
        eff = _series_latest_effective_from(db_session, series)
        latest_eff[series] = eff
        if cov < min_finite_coverage_pct:
            return False
        # 両端 freshness check (V13):
        # latest_effective_from >= extended_start
        # かつ latest_effective_from >= extended_end - safety_lag (近日まで取得済か)
        if eff is None:
            return False
        if eff < extended_start:
            return False
        if eff < extended_end - timedelta(days=safety_lag_days):
            # 末端 freshness 不足: log だけ出して FAIL とする
            logger.warning(
                "preflight.series_stale",
                series=series,
                latest_effective_from=eff.isoformat(),
                expected_at_least=(
                    extended_end - timedelta(days=safety_lag_days)
                ).isoformat(),
            )
            return False
        return True

    hard_satisfied: list[str] = []
    hard_missing: list[str] = []
    for series in HARD_REQUIRED_AUX:
        if _check_series(series):
            hard_satisfied.append(series)
        else:
            hard_missing.append(series)

    for pair in HARD_REQUIRED_PAIRS:
        cov = _pair_bars_finite_coverage_pct(
            db_session, pair, extended_period
        )
        coverage[f"{pair}_M1"] = cov
        if cov >= min_finite_coverage_pct:
            hard_satisfied.append(f"{pair}_M1")
        else:
            hard_missing.append(f"{pair}_M1")

    soft_satisfied: list[str] = []
    soft_missing: list[str] = []
    for series in SOFT_REQUIRED_AUX:
        if _check_series(series):
            soft_satisfied.append(series)
        else:
            soft_missing.append(series)

    result = PreflightResult(
        hard_satisfied=hard_satisfied,
        hard_missing=hard_missing,
        soft_satisfied=soft_satisfied,
        soft_missing=soft_missing,
        coverage_pct_by_series=coverage,
        latest_effective_from_by_series=latest_eff,
    )

    if not result.passes and not allow_missing:
        raise RuntimeError(
            f"preflight aux check FAILED: hard_missing={hard_missing}. "
            "Run scripts/fetch_aux_data.sh to populate, or pass "
            "--allow-aux-missing for dev. "
            f"coverage_pct={coverage}"
        )
    return result
