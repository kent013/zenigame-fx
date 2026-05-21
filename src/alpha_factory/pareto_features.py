"""T111 (Phase2 step3): ParetoFeaturesLite — NSGA-II selection 用 Stage B 完結軸の観測機構.

GA 主選抜 (T112 step5a NSGA-II) が消費する Pareto 3 軸 (net_pnl / max_dd /
mission_inf_gap) を **Stage B pooled fold-CV (OOS)** から算出する selection 専用
scalar sidecar。``BCEvaluationResult`` 全体や trade/equity 配列は保持しない
(multiprocessing 境界・メモリ保護)。

設計判断 (devnotes/20260521-0925-nsga2-cpps-selection-wiring/detailed-design.md):
- 軸源は **pooled fold-CV (OOS)**。IS-monitor canonical は汎化目的に不適のため不採用。
- ``stage_bc_evaluator.evaluate_stage_b`` を production に差さない (= period 再フィルタ
  / 再 backtest の off-by-one 回避)。代わりに既に算出済の per-fold canonical artifact
  を**直消費**して pool する純粋関数を提供する (Codex design-review Round 6-7 APPROVED)。
- ``try_build_pareto_lite_from_stage_b_fold_artifacts`` は完全 no-raise (LOG_ONLY 隔離)。

source_stage は常に "B"。Stage C / holdout / cross-pair を入力に取る経路は存在しない。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

import structlog

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    SessionBucket,
    TradeRecord,
    evaluate_canonical_five,
)
from src.alpha_factory.mission_inf_gap import evaluate_mission_inf_gap
from src.alpha_factory.stage_bc_evaluator import derive_stage_b_thresholds

logger = structlog.get_logger(__name__)

__all__ = [
    "FoldCanonicalArtifact",
    "ParetoFeaturesLite",
    "build_stage_b_pooled_cf_from_fold_artifacts",
    "try_build_pareto_lite_from_stage_b_fold_artifacts",
]

# Stage B fold 数 (= stage_bc_evaluator.STAGE_B_NUM_FOLDS と同値、循環 import 回避で複製)。
_EXPECTED_NUM_FOLDS: Final[int] = 5

# live_criteria に win_rate_min が無い既存 config 互換用 default
# (= stage_gate._CANONICAL_DUAL_PATH_DEFAULT_WIN_RATE_MIN=0.45 と同値、synthesis § 6.4
# 標準値)。stage_gate を import すると循環するためローカル複製。derive_stage_b_thresholds
# は win_rate_min を必須要求するため、欠落時に補完しないと production default で全件
# unusable になる (Codex impl-review Round 2 Critical)。後続で config に win_rate_min を
# 追加する際に削除予定。
_DEFAULT_WIN_RATE_MIN: Final[float] = 0.45


@dataclass(frozen=True)
class ParetoFeaturesLite:
    """T112 NSGA-II selection が消費する Stage B 完結 scalar (6 field)。

    trade/equity 配列・``CanonicalFiveResult`` 全体は保持しない。

    field:
    - ``net_pnl_after_cost``: f1 (max)、 pooled OOS canonical の net PnL (Stage B)
    - ``pooled_dd_per_fold_max``: f2 (min, >=0 invariant)、 per-fold max_dd の max
    - ``mission_inf_gap``: f3 (min)、 ``evaluate_mission_inf_gap(b_pooled_cf)`` (Stage B)
    - ``is_feasible_invariant``: 全 fold feasible なら True (T061)
    - ``pareto_axis_usable``: b_pooled_cf 算出可能 ∧ 3 scalar finite ∧ feasible
    - ``source_stage``: usable なら "B"、 未算出なら None (逆流監査用)
    """

    net_pnl_after_cost: float | None
    pooled_dd_per_fold_max: float | None
    mission_inf_gap: float | None
    is_feasible_invariant: bool
    pareto_axis_usable: bool
    source_stage: Literal["B"] | None = None

    @staticmethod
    def unusable() -> ParetoFeaturesLite:
        """軸算出不能時の sentinel (B fail / infeasible / 例外)。"""
        return ParetoFeaturesLite(
            net_pnl_after_cost=None,
            pooled_dd_per_fold_max=None,
            mission_inf_gap=None,
            is_feasible_invariant=False,
            pareto_axis_usable=False,
            source_stage=None,
        )


@dataclass(frozen=True)
class FoldCanonicalArtifact:
    """1 fold の **既に canonical 化済** 評価 artifact (直消費 pooling 入力)。

    stage_gate の fold ループで既に算出済の値を adapt せずそのまま受ける
    (= 再 backtest / period 再フィルタを行わない契約)。

    field:
    - ``fold_index``: fold 番号 (0-origin)
    - ``period_start`` / ``period_end``: fold test bar の最初/最後の bar 時刻
      (= fold 定義由来、 時系列順 / 非重複検証用。 period_end は inclusive)
    - ``canonical_trades``: 当 fold の canonical TradeRecord (時系列順)
    - ``canonical_bars``: 当 fold の BarEquitySeries
    - ``canonical_universe``: 当 fold の business_day_universe
    - ``cf_result``: 当 fold の per-fold CanonicalFiveResult (max_dd / feasibility source)
    """

    fold_index: int
    period_start: datetime
    period_end: datetime
    canonical_trades: tuple[TradeRecord, ...]
    canonical_bars: BarEquitySeries
    canonical_universe: Mapping[SessionBucket, frozenset[int]]
    cf_result: CanonicalFiveResult


def build_stage_b_pooled_cf_from_fold_artifacts(
    artifacts: Sequence[FoldCanonicalArtifact],
    *,
    thresholds: CanonicalFiveThresholds,
) -> tuple[CanonicalFiveResult | None, float | None, bool]:
    """既算出 per-fold canonical artifact を pool して b_pooled_cf を得る。

    ``stage_bc_evaluator.build_pooled_oos_input`` と同じ pooling 数式だが、
    ``individual_input`` からの period 再フィルタを行わず、**既に fold で切られた
    canonical artifact を直 concat** する (off-by-one / 二重評価回避)。

    手順:
    1. fold 数 / fold_index / 時系列順 / 非重複 invariant 検証 (違反は ValueError)
    2. いずれかの fold が infeasible → ``(None, None, False)`` (StageBResult contract)
    3. canonical trades / bars を時系列順 concat、 universe を union
    4. pooled に対し ``evaluate_canonical_five`` を 1 回呼び b_pooled_cf を得る
       (= 新規 backtest でなく metrics 集約)
    5. ``pooled_dd_per_fold_max`` = per-fold ``cf_result.max_dd`` の max

    Returns:
        ``(b_pooled_cf, pooled_dd_per_fold_max, is_feasible_invariant)``。
        infeasible なら ``(None, None, False)``。

    Raises:
        ValueError: fold 数 / 順序 / 重複 invariant 違反 (caller が no-raise で捕捉)。
    """
    if len(artifacts) != _EXPECTED_NUM_FOLDS:
        raise ValueError(
            f"expected {_EXPECTED_NUM_FOLDS} fold artifacts, got {len(artifacts)}"
        )
    for i, a in enumerate(artifacts):
        if a.fold_index != i:
            raise ValueError(
                f"fold artifact[{i}].fold_index ({a.fold_index}) != {i}"
            )
    for i in range(len(artifacts) - 1):
        cur, nxt = artifacts[i], artifacts[i + 1]
        if cur.period_start > nxt.period_start:
            raise ValueError(
                f"non-chronological fold order at {i}: "
                f"{cur.period_start} > {nxt.period_start}"
            )
        # period_end は fold 最終 bar 時刻 (inclusive) を保持するため、
        # end == next_start は同一 bar の二重所属 = overlap として弾く (>=)。
        if cur.period_end >= nxt.period_start:
            raise ValueError(
                f"overlapping fold periods at {i}: "
                f"end {cur.period_end} >= next start {nxt.period_start}"
            )

    is_feasible_invariant = all(
        a.cf_result.invariants.is_feasible for a in artifacts
    )
    if not is_feasible_invariant:
        return None, None, False

    pooled_trades: list[TradeRecord] = []
    pooled_bar_points: list[BarEquityPoint] = []
    union_universe: dict[SessionBucket, set[int]] = {}
    for a in artifacts:
        pooled_trades.extend(a.canonical_trades)
        pooled_bar_points.extend(a.canonical_bars.points)
        for bucket, day_set in a.canonical_universe.items():
            union_universe.setdefault(bucket, set()).update(day_set)

    if len(pooled_bar_points) == 0:
        raise ValueError("pooled bars empty across all folds")

    pooled_bars = BarEquitySeries(points=tuple(pooled_bar_points))
    pooled_universe: dict[SessionBucket, frozenset[int]] = {
        bucket: frozenset(day_set) for bucket, day_set in union_universe.items()
    }
    b_pooled_cf = evaluate_canonical_five(
        tuple(pooled_trades),
        pooled_bars,
        thresholds,
        pooled_universe,
    )
    pooled_dd_per_fold_max = max(a.cf_result.max_dd for a in artifacts)
    return b_pooled_cf, pooled_dd_per_fold_max, True


def _finite_or_none(value: float | None) -> float | None:
    """非有限 (NaN/±inf) / None を None に潰す。"""
    if value is None:
        return None
    return value if math.isfinite(value) else None


def try_build_pareto_lite_from_stage_b_fold_artifacts(
    artifacts: Sequence[FoldCanonicalArtifact],
    *,
    live_criteria: Mapping[str, float | int],
) -> ParetoFeaturesLite:
    """完全 no-raise の ParetoFeaturesLite builder (LOG_ONLY 隔離)。

    pooling / canonical 評価 / mission_inf_gap 算出の全例外を捕捉し、失敗時は
    ``ParetoFeaturesLite.unusable()`` を返す (gate / judgment 経路に波及させない)。
    閾値は ``derive_stage_b_thresholds`` で導出 (stage_bc_evaluator と同一)。

    軸の出所は常に Stage B pooled fold-CV (OOS)。Stage C / holdout は入力に存在しない。
    """
    try:
        lc = dict(live_criteria)
        # win_rate_min 欠落の既存 config 互換 (stage_gate canonical dual-path と同じ
        # 0.45 fallback)。これが無いと derive_stage_b_thresholds が必須 key 欠落で
        # raise → 全件 unusable になる。
        lc.setdefault("win_rate_min", _DEFAULT_WIN_RATE_MIN)
        thresholds = derive_stage_b_thresholds(lc)
        b_pooled_cf, pooled_dd, feasible = (
            build_stage_b_pooled_cf_from_fold_artifacts(
                artifacts, thresholds=thresholds
            )
        )
        if b_pooled_cf is None or not feasible:
            return ParetoFeaturesLite.unusable()
        mission = evaluate_mission_inf_gap(b_pooled_cf)
        net_pnl = _finite_or_none(b_pooled_cf.net_pnl_after_cost)
        dd = _finite_or_none(pooled_dd)
        gap = _finite_or_none(mission.mission_inf_gap)
        # dd は損失額の正値 (>=0) を invariant とする。負値は異常 → unusable。
        if dd is not None and dd < 0.0:
            logger.warning(
                "pareto_features.negative_pooled_dd", pooled_dd=dd
            )
            return ParetoFeaturesLite.unusable()
        usable = net_pnl is not None and dd is not None and gap is not None
        if not usable:
            return ParetoFeaturesLite.unusable()
        return ParetoFeaturesLite(
            net_pnl_after_cost=net_pnl,
            pooled_dd_per_fold_max=dd,
            mission_inf_gap=gap,
            is_feasible_invariant=True,
            pareto_axis_usable=True,
            source_stage="B",
        )
    except Exception as exc:
        logger.warning(
            "pareto_features.build_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return ParetoFeaturesLite.unusable()
