"""Stage A / B / C ゲート実装 (T014)。

Alpha Factory の Genome 評価パイプラインの中核。3 つの Stage を pure function
として提供する:

- Stage A — Fast Screen（直近 60 営業日 sharpe + complexity penalty）
- Stage B — WF-OOS Gate (+ IS monitor)（過去 18 ヶ月 walk-forward OOS 検定）
- Stage C — Live Criteria + Stress（holdout で live_criteria + spread×1.5 stress）

仕様根拠:
- docs/alpha_factory/stage-gates.md
- docs/alpha_factory/concepts/stage-gate-implementation.md
- devnotes/20260421-1850-fx-skill-port/debate-synthesis.md §B/E
- devnotes/20260423-1540-stage-gate-implementation/{conceptual,detailed}-design.md

学術引用:
- López de Prado, M. (2018). Advances in Financial Machine Learning, Ch.7.
- Luke, S. & Panait, L. (2006). A Comparison of Bloat Control Methods for
  Genetic Programming. Evolutionary Computation, 14(3), 309-344.
"""

from __future__ import annotations

import math
import statistics as _stats
import time as _time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar, Final, Literal, Protocol, TypedDict, cast

import structlog

from src.alpha_factory.walk_forward import make_wf_folds
from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator
from src.ga.complexity import genome_size_norm

logger = structlog.get_logger(__name__)

# T034: Stage A fitness_pen sentinel 序列。
# archive `_required_float` は None → 0.0 fallback するため、Stage A の 3 失敗
# 経路 (system_failure / no_exposure / metric_unavailable) は payload に明示的な
# 大負値 sentinel を入れることで selection_score tie-break で「無取引優位」を解消する。
# 序列: system_failure < no_exposure < metric_unavailable < below_threshold (実値)
# 詳細: docs/alpha_factory/stage-gates.md / devnotes/20260425-0937-risk-no-trade-fitness-guard/
SYSTEM_FAILURE_FITNESS: Final[float] = -1e12
NO_EXPOSURE_FITNESS: Final[float] = -1e9
METRIC_UNAVAILABLE_FITNESS: Final[float] = -1e6

# T034: calibrate_gate が threshold 計算時に除外する sentinel 値の集合。
# 値一致 (set membership) で判定する (閾値分離は通常実値域と被るため安全でない)。
STAGE_A_FITNESS_SENTINELS: Final[frozenset[float]] = frozenset(
    {SYSTEM_FAILURE_FITNESS, NO_EXPOSURE_FITNESS, METRIC_UNAVAILABLE_FITNESS}
)

__all__ = [
    "METRIC_UNAVAILABLE_FITNESS",
    "NO_EXPOSURE_FITNESS",
    "STAGE_A_FITNESS_SENTINELS",
    "SYSTEM_FAILURE_FITNESS",
    "CrossPairEvaluator",
    "CrossPairInputs",
    "CrossPairResult",
    "StageGateConfig",
    "StageResult",
    "evaluate_stage_a",
    "evaluate_stage_b",
    "evaluate_stage_c",
]


# ---------------------------------------------------------------------------
# Config / Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageGateConfig:
    """Stage A/B/C 共通設定。

    各フィールドの説明は ``docs/alpha_factory/stage-gates.md`` 参照。
    ``__post_init__`` で軽い不変条件と ``live_criteria`` の必須キー検証を行う。
    ``live_criteria`` は ``MappingProxyType`` で frozen 化される。
    """

    # Stage A
    stage_a_window_days: int = 60
    stage_a_alpha: float = 0.03
    stage_a_threshold: float = 0.0  # 暫定固定 (calibrate-gate TODO で動的化)
    # T034: 取引が成立しなかった個体 (trade_count < min_exposure_trade_count) を
    # `no_exposure` reason + sentinel fitness_pen で淘汰する。
    # default 1 = 「1 trade 未満 = 取引未成立 = 評価不能」(従来 no_trades と同等)。
    # live_criteria.trade_count_min との不変条件: min_exposure_trade_count <
    # trade_count_min (live_criteria 緩和回避、__post_init__ で検証)。
    # 詳細: docs/alpha_factory/stage-gates.md (sentinel 序列)
    min_exposure_trade_count: int = 1

    # Stage B
    stage_b_window_months: int = 18
    wf_train_days: int = 120
    wf_test_days: int = 20
    wf_step_days: int = 20
    wf_embargo_days: int = 1
    # T042 Phase 0: trade-level スケール (per-fold trade_sharpe_raw との比較)。
    # 旧 0.20 は v1 bar-level 想定の legacy 値。Run 14-16 archive replay
    # (reports/sharpe-rescale/) で trade-level 分布が 0.05〜0.19 中央域だったため
    # 0.05 へ再校正した。詳細: docs/alpha_factory/sharpe-rescale.md
    stage_b_median_oos_sharpe_min: float = 0.05
    stage_b_positive_fold_min: float = 0.60
    stage_b_dsr_min: float = 0.0  # monitor only (Phase 4 で hard 化)
    # T044: pre-flight feasibility minimum
    # @why: LaneManager で max_folds < min なら全 lane 全個体 Stage B skip し
    # stage_b_pre_flight_underfilled で fail-fast。insufficient_folds の後段検出ではなく
    # 構造的に弾く。default 2 は WF 評価として最低限のサンプル数。
    wf_min_folds_required: int = 2

    # Stage C
    stage_c_holdout_days: int = 60
    spread_stress_multiplier: float = 1.5
    spread_stress_min_total_pnl: float = 0.0
    spread_stress_min_sharpe: float = 0.0
    # T045: GA selection で stage_c_feasible (PnL>0 ∧ Sharpe>0) を v3 selection_score に含める
    # @why: Run-20 で Stage B 突破したが best 個体 PnL=-16850 / Sharpe=-0.19 で
    # Stage C 不通過。soft fitness 合算では負 PnL/Sharpe 個体が GA 選抜で生き残る。
    # PnL>0 ∧ Sharpe>0 を T031 feasible 直後に挿入し可行性優先 2 段階最適化を実装。
    stage_c_feasibility_apply: bool = True

    # T-sharpe Phase 1A: trade-level Sharpe sample-size guard
    # config から compute_metrics へ伝搬する canonical 値
    trade_count_min_for_sharpe: int = 30

    # live_criteria
    live_criteria: Mapping[str, float | int] = field(
        default_factory=lambda: {
            "sharpe_min": 1.0,
            "total_pnl_min": 50000,
            "max_drawdown_max": 0.20,
            "trade_count_min": 50,
            "trade_count_max": 5000,
        }
    )

    _LIVE_CRITERIA_REQUIRED: ClassVar[frozenset[str]] = frozenset(
        {
            "sharpe_min",
            "total_pnl_min",
            "max_drawdown_max",
            "trade_count_min",
            "trade_count_max",
        }
    )

    def __post_init__(self) -> None:
        if not 0.0 <= self.stage_a_alpha <= 1.0:
            raise ValueError(
                f"stage_a_alpha must be in [0, 1]: got {self.stage_a_alpha}"
            )
        if self.wf_train_days < 1 or self.wf_test_days < 1 or self.wf_step_days < 1:
            raise ValueError(
                "wf_train_days/wf_test_days/wf_step_days must be >= 1: "
                f"got train={self.wf_train_days}, test={self.wf_test_days}, "
                f"step={self.wf_step_days}"
            )
        if self.wf_embargo_days < 0:
            raise ValueError(
                f"wf_embargo_days must be >= 0: got {self.wf_embargo_days}"
            )
        if self.wf_min_folds_required < 1:
            raise ValueError(
                f"wf_min_folds_required must be >= 1: "
                f"got {self.wf_min_folds_required}"
            )
        if self.spread_stress_multiplier <= 1.0:
            raise ValueError(
                "spread_stress_multiplier must be > 1.0: "
                f"got {self.spread_stress_multiplier}"
            )
        missing = self._LIVE_CRITERIA_REQUIRED - set(self.live_criteria.keys())
        if missing:
            raise ValueError(
                f"live_criteria missing required keys: {sorted(missing)}"
            )
        # T034: min_exposure_trade_count の不変条件:
        # 0 < min_exposure_trade_count < live_criteria.trade_count_min。
        # 上限を trade_count_min 未満に制限することで「Stage A で trade_count_min
        # まで要求 = 事実上 live_criteria.trade_count_min を緩和」を防ぐ
        # (禁止事項 #4 ガード)。
        if self.min_exposure_trade_count < 1:
            raise ValueError(
                "min_exposure_trade_count must be >= 1: "
                f"got {self.min_exposure_trade_count}"
            )
        # 禁止事項 #4 ガード: live_criteria.trade_count_min を Stage A 内で
        # 事実上強化することを禁ずる。trade_count_min が緩和テスト等で 0/小さい
        # 場合 (relaxed_lc) は live_criteria 自体が「制約無効」を表明している
        # ため本ガードは適用しない (defensive 動作)。
        lc_trade_count_min = int(self.live_criteria["trade_count_min"])
        if (
            lc_trade_count_min >= 1
            and self.min_exposure_trade_count >= lc_trade_count_min
        ):
            raise ValueError(
                "min_exposure_trade_count must be < live_criteria.trade_count_min "
                f"(禁止事項 #4 ガード): got min_exposure_trade_count="
                f"{self.min_exposure_trade_count}, "
                f"trade_count_min={lc_trade_count_min}"
            )
        # MappingProxyType で frozen dict 化（外部書換不能）
        object.__setattr__(
            self,
            "live_criteria",
            MappingProxyType(dict(self.live_criteria)),
        )

    # T052: multiprocessing.Pool initargs で worker process に配布する際、
    # mappingproxy は ForkingPickler で pickle 不可 (Python 3.11) なため
    # __getstate__/__setstate__ で dict ↔ mappingproxy 変換を行う。
    # 通常の copy.deepcopy / pickle.dumps の両方に作用する。
    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        # live_criteria を plain dict に変換 (pickle 互換)
        state["live_criteria"] = dict(self.live_criteria)
        return state

    def __setstate__(self, state: dict) -> None:
        # restore: live_criteria を MappingProxyType に再 wrap (深い不変性復元)
        for k, v in state.items():
            object.__setattr__(self, k, v)
        object.__setattr__(
            self, "live_criteria", MappingProxyType(dict(state["live_criteria"]))
        )


@dataclass(frozen=True)
class StageResult:
    """Stage 評価結果（unified return）。

    Attributes:
        stage: "A" / "B" / "C"。
        passed: 通過判定。
        metrics: 共通 envelope (stage / genome_name / n_bars /
            wall_time_seconds) + ``payload`` (stage-specific dict)。
        reason_codes: 失敗理由 code 列。空タプル = 通過。
    """

    stage: Literal["A", "B", "C"]
    passed: bool
    metrics: Mapping[str, object]
    reason_codes: tuple[str, ...] = ()

    @property
    def reason_if_failed(self) -> str:
        """display / log 用の `;` 連結文字列。空文字 = 通過。"""
        return ";".join(self.reason_codes)


# ---------------------------------------------------------------------------
# Cross-pair shadow hook (interface only — 実装は別 TODO)
# ---------------------------------------------------------------------------


class CrossPairInputs(TypedDict):
    """Stage C で cross_pair_evaluator に渡す入力 (型安全 TypedDict)."""

    target_pair: str
    pair_bars_map: Mapping[str, list[PriceBar]]
    meta_map: Mapping[str, InstrumentMeta]


@dataclass(frozen=True)
class CrossPairResult:
    """cross-pair (ii-lite) 評価の戻り値。

    Phase 2 では shadow only (passed は monitor、Stage C の最終 passed には
    影響させない)。Phase 4 で hard gate 化する際、本フィールドが
    ``StageResult.passed`` への AND 合成に使われる。
    """

    target_pair: str
    anchor_pairs: tuple[str, ...]
    aggregator_name: str
    window: tuple[datetime, datetime]
    passed: bool
    metrics: Mapping[str, object]
    reason_codes: tuple[str, ...] = ()


class CrossPairEvaluator(Protocol):
    """cross-pair (ii-lite) 評価関数の Protocol。実装は別 TODO."""

    def evaluate(
        self,
        genome: Genome,
        target_pair: str,
        pair_bars_map: Mapping[str, list[PriceBar]],
        meta_map: Mapping[str, InstrumentMeta],
        backtest_config: BacktestConfig,
    ) -> CrossPairResult: ...


def _validate_cross_pair_inputs(inputs: object) -> CrossPairInputs:
    """``cross_pair_inputs`` の実行時バリデーション."""
    if not isinstance(inputs, Mapping):
        raise TypeError(
            f"cross_pair_inputs must be a Mapping: got {type(inputs).__name__}"
        )
    required = {"target_pair", "pair_bars_map", "meta_map"}
    missing = required - set(inputs.keys())
    if missing:
        raise ValueError(f"cross_pair_inputs missing keys: {sorted(missing)}")
    if not isinstance(inputs["target_pair"], str):
        raise TypeError("cross_pair_inputs['target_pair'] must be str")
    if not isinstance(inputs["pair_bars_map"], Mapping):
        raise TypeError("cross_pair_inputs['pair_bars_map'] must be Mapping")
    if not isinstance(inputs["meta_map"], Mapping):
        raise TypeError("cross_pair_inputs['meta_map'] must be Mapping")
    return cast(CrossPairInputs, inputs)


# ---------------------------------------------------------------------------
# Stage A — Fast Screen
# ---------------------------------------------------------------------------


def evaluate_stage_a(
    genome: Genome,
    bars_60d: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
) -> StageResult:
    """Stage A — Fast Screen 評価。

    sharpe を fitness_raw とし、complexity penalty (``α_A * size_norm``) を
    控除して ``fitness_pen`` を算出。``stage_a_threshold`` 超過で通過。

    判定優先順位 (canonical):
        ``system_failure`` > ``no_exposure`` > ``metric_unavailable`` >
        ``below_threshold`` > 通過。

    Args:
        genome: Clause Genome。
        bars_60d: 直近 60 観測日相当の bars。
        meta: 銘柄メタ。
        backtest_config: backtest 設定（イントラデイ絶対制約必須）。
        primitive_evaluator: PrimitiveEvaluator 実装。
        stage_config: Stage gate 設定。

    Returns:
        StageResult(stage="A", ...)。
    """
    start = _time.perf_counter()
    reasons: list[str] = []
    fitness_raw: float | None = None
    size_norm_val: float | None = None
    fitness_pen: float | None = None
    sharpe_raw: float | None = None
    trade_count = 0
    # T033: Stage A backtest の total_pnl を payload に in-memory only で添加。
    # archive Parquet には書かない (28+ カラム fixed schema を尊重)。
    # post-RUN sidecar diagnostics (`stage_a_provenance.parquet`) で参照する。
    total_pnl_a: float = 0.0
    # T037: Stage A backtest 中に runtime fired した clause idx 数 (observation
    # only, archive `active_clause` 列に記録される)。例外時 / strategy 未生成時は
    # 0 (測定不能を表すが、archive 既存契約 (non-null int32) との整合のため 0
    # を入れる)。
    active_clause_count: int = 0
    exception_caught = False

    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars_60d, strategy, broker, backtest_config)
        bt = compute_metrics(
            result.trades,
            result.equity_curve,
            trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
        )
        trade_count = bt.trade_count
        # T-sharpe Phase 1A: trade_sharpe_raw (v2) を fitness の入力に使用
        sharpe_raw = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        # T033: total_pnl を sidecar diagnostics 用に保持 (size_norm 例外と独立)
        try:
            total_pnl_a = float(bt.total_pnl)
            if not math.isfinite(total_pnl_a):
                total_pnl_a = 0.0
        except Exception:
            total_pnl_a = 0.0
        # T037: backtest 完了後の strategy.active_clause_indices を集計。
        # backtest 経路で必ず prepare()→on_bar が呼ばれているはずだが、
        # defensive に len() 経由で取り出す。
        active_clause_count = len(strategy.active_clause_indices)
    except Exception as exc:
        logger.warning(
            "stage_a.system_failure",
            genome=genome.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        exception_caught = True

    # size_norm は Genome 構造のみ依存で決定論
    try:
        size_norm_val = float(genome_size_norm(genome))
    except Exception as exc:
        logger.warning(
            "stage_a.size_norm_failure",
            genome=genome.name,
            error=str(exc),
        )
        exception_caught = True

    # 判定優先順位 (canonical):
    #   system_failure > no_exposure > metric_unavailable > below_threshold
    # T034: 3 失敗経路は payload に sentinel fitness_pen を入れる (None → 0.0
    # fallback の排除、selection_score tie-break で「無取引優位」を解消)。
    # fitness_raw は変更しない (観察値は保持、ペナルティは fitness_pen のみ)。
    if exception_caught:
        reasons.append("system_failure")
        fitness_pen = SYSTEM_FAILURE_FITNESS
    elif trade_count < stage_config.min_exposure_trade_count:
        reasons.append("no_exposure")
        fitness_pen = NO_EXPOSURE_FITNESS
    elif sharpe_raw is None:
        reasons.append("metric_unavailable")
        fitness_pen = METRIC_UNAVAILABLE_FITNESS
    else:
        assert size_norm_val is not None  # type narrowing
        fitness_raw = sharpe_raw
        fitness_pen = fitness_raw - stage_config.stage_a_alpha * size_norm_val
        if fitness_pen <= stage_config.stage_a_threshold:
            reasons.append("below_threshold")

    passed = len(reasons) == 0
    elapsed = _time.perf_counter() - start

    metrics_envelope: dict[str, object] = {
        "stage": "A",
        "genome_name": genome.name,
        "n_bars": len(bars_60d),
        "wall_time_seconds": elapsed,
        "payload": {
            "fitness_raw": fitness_raw,
            "size_norm": size_norm_val,
            "fitness_pen": fitness_pen,
            "alpha_a": stage_config.stage_a_alpha,
            "threshold": stage_config.stage_a_threshold,
            "trade_count": trade_count,
            # T-sharpe Phase 1A: payload key を "sharpe_raw" → "trade_sharpe_raw"
            "trade_sharpe_raw": sharpe_raw,
            # T037: runtime fired clause idx 数 (observation only)
            "active_clause": active_clause_count,
            # T033: sidecar diagnostics 用 in-memory only field。
            # archive Parquet には書かない (28+ カラム fixed schema 尊重)。
            "total_pnl": total_pnl_a,
        },
    }
    return StageResult(
        stage="A",
        passed=passed,
        metrics=metrics_envelope,
        reason_codes=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# Stage B — WF-OOS Gate (+ IS monitor)
# ---------------------------------------------------------------------------


def evaluate_stage_b(
    genome: Genome,
    bars_18m: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
) -> StageResult:
    """Stage B — Walk-Forward OOS gate + IS monitor。

    fold ごとの test 区間で sharpe を取り、median / 正 fold 比率で複合 AND 判定。
    18 ヶ月全体の IS metrics は monitor として記録 (hard gate には使わない)。

    fold metric_unavailable policy: ``oos_sharpe is None`` の fold は **0 と
    みなして母数に含める** (no-trade を hide させない設計)。

    Returns:
        StageResult(stage="B", ...)。
    """
    start = _time.perf_counter()
    reasons: list[str] = []

    folds = make_wf_folds(
        bars_18m,
        train_days=stage_config.wf_train_days,
        test_days=stage_config.wf_test_days,
        step_days=stage_config.wf_step_days,
        embargo_days=stage_config.wf_embargo_days,
    )
    n_fold = len(folds)
    n_fold_unavailable = 0
    oos_sharpes_imputed: list[float] = []
    # T035: fold ごとの unavailable フラグを保持し effective 集計に使う
    fold_was_unavailable: list[bool] = []

    # 18 ヶ月全体 IS monitor
    is_full_sharpe: float | None = None
    is_full_total_pnl: float = 0.0
    is_full_trade_count = 0
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_18m, strategy, broker, backtest_config)
        bt = compute_metrics(
            res.trades,
            res.equity_curve,
            trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
        )
        # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
        is_full_sharpe = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        is_full_total_pnl = float(bt.total_pnl)
        is_full_trade_count = bt.trade_count
    except Exception as exc:
        logger.warning(
            "stage_b.is_monitor_failure",
            genome=genome.name,
            error=str(exc),
        )

    # 各 fold の OOS Sharpe
    # engine の run_backtest は BacktestConfig.start/end を参照しないため
    # backtest_config をそのまま流用する (詳細設計 §3.2 参照)
    for i, (_train_bars, test_bars) in enumerate(folds):
        fold_sharpe: float | None = None
        try:
            strategy = DslStrategy(genome, primitive_evaluator)
            broker = MockBroker(instrument_meta=meta)
            res = run_backtest(test_bars, strategy, broker, backtest_config)
            bt = compute_metrics(
                res.trades,
                res.equity_curve,
                trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
            )
            # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
            # NOTE: stage_b_median_oos_sharpe_min=0.20 は v1 bar-level Sharpe スケール前提。
            # Phase 1B replay で v2 trade-level スケールに再校正する。
            fold_sharpe = (
                float(bt.trade_sharpe_raw)
                if bt.trade_sharpe_raw is not None
                else None
            )
        except Exception as exc:
            logger.warning(
                "stage_b.fold_failure",
                genome=genome.name,
                fold=i,
                error=str(exc),
            )
            fold_sharpe = None
        if fold_sharpe is None:
            n_fold_unavailable += 1
            oos_sharpes_imputed.append(0.0)
            fold_was_unavailable.append(True)
        else:
            oos_sharpes_imputed.append(fold_sharpe)
            fold_was_unavailable.append(False)

    # 集計と判定
    n_fold_effective = n_fold - n_fold_unavailable
    median_oos: float | None = None
    positive_ratio: float | None = None
    positive_ratio_effective: float | None = None
    # effective fold (unavailable=False のもの) のみを抜き出した OOS Sharpe 列
    effective_oos: list[float] = [
        s for i, s in enumerate(oos_sharpes_imputed)
        if not fold_was_unavailable[i]
    ]
    if n_fold == 0:
        reasons.append("no_folds")
    elif n_fold == 1:
        reasons.append("insufficient_folds")
        median_oos = float(oos_sharpes_imputed[0])
        positive_ratio = 1.0 if oos_sharpes_imputed[0] > 0 else 0.0
        if effective_oos:
            positive_ratio_effective = (
                sum(1 for s in effective_oos if s > 0) / len(effective_oos)
            )
    else:
        median_oos = float(_stats.median(oos_sharpes_imputed))
        positive_ratio = sum(1 for s in oos_sharpes_imputed if s > 0) / n_fold
        if effective_oos:
            positive_ratio_effective = (
                sum(1 for s in effective_oos if s > 0) / len(effective_oos)
            )
        if median_oos < stage_config.stage_b_median_oos_sharpe_min:
            reasons.append("median_oos_sharpe<min")
        if positive_ratio < stage_config.stage_b_positive_fold_min:
            reasons.append("positive_fold_ratio<min")

    # 全 fold metric_unavailable のときは別 reason で監査性を上げる
    if n_fold > 0 and n_fold_unavailable == n_fold:
        reasons.append("all_folds_unavailable")

    passed = len(reasons) == 0
    elapsed = _time.perf_counter() - start

    metrics_envelope: dict[str, object] = {
        "stage": "B",
        "genome_name": genome.name,
        "n_bars": len(bars_18m),
        "wall_time_seconds": elapsed,
        "payload": {
            "n_fold": n_fold,
            "n_fold_unavailable": n_fold_unavailable,
            "n_fold_effective": n_fold_effective,
            "oos_sharpes": tuple(oos_sharpes_imputed),
            "median_oos_sharpe": median_oos,
            "positive_fold_ratio": positive_ratio,
            "positive_fold_ratio_effective": positive_ratio_effective,
            "dsr": None,  # Phase 4 で hard 化
            "is_full_sharpe": is_full_sharpe,
            "is_full_total_pnl": is_full_total_pnl,
            "is_full_trade_count": is_full_trade_count,
        },
    }
    return StageResult(
        stage="B",
        passed=passed,
        metrics=metrics_envelope,
        reason_codes=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# Stage C — Live Criteria + Stress
# ---------------------------------------------------------------------------


# T042: trade-level Sharpe → annualized Sharpe 換算 (Phase 0 minimum)。
# - Stage C の live_criteria.sharpe_min (= 1.0 annualized) と GA fitness が
#   trade-level Sharpe (v2) で乖離していた問題を解消する。
# - 換算式: S_annual ≈ S_trade × sqrt(λ_day × 252) / sqrt(adj_corr)
#   Phase 0 では adj_corr=1 (no autocorrelation correction)、λ_day=trade_count/window。
# - 学術引用: Andrew W. Lo (2002), "The Statistics of Sharpe Ratios",
#   Financial Analysts Journal 58(4), 36-52.
# - 詳細: docs/alpha_factory/sharpe-rescale.md
TRADING_DAYS_PER_YEAR: Final[int] = 252


def _annualize_trade_sharpe(
    trade_sharpe_raw: float | None,
    trade_count: int,
    window_days: int,
) -> float | None:
    """trade-level Sharpe を annualized Sharpe に換算する。

    入力が None / 非有限 / trade_count<=0 / window_days<=0 のいずれかなら
    None を返す (caller 側で「換算不能 = lc.sharpe 判定不能 = 失格」扱いを期待)。

    Args:
        trade_sharpe_raw: trade-level Sharpe ratio (μ_trade / σ_trade)。
        trade_count: 観測 window 内の trade 数。
        window_days: 観測 window 日数。

    Returns:
        年率換算 Sharpe、または None。
    """
    if trade_sharpe_raw is None or trade_count <= 0 or window_days <= 0:
        return None
    if not math.isfinite(trade_sharpe_raw):
        return None
    lambda_day = trade_count / window_days
    return trade_sharpe_raw * math.sqrt(lambda_day * TRADING_DAYS_PER_YEAR)


# T043: mission_score (live_criteria 4 軸 soft 合算)
# - 詳細設計: devnotes/20260426-1030-phase0-mission-score/detailed-design.md
# - 各軸 i: score_i = clip((metric - lower) / (target - lower), 0, 1)
#   ただし max_drawdown は逆向き (小さいほど高 score)、trade_count は範囲外で 0
# - 0 を避けて log 表示可能化: score_i' = 0.1 + 0.9 * score_i
# - 幾何平均: mission_score = (Π score_i')^(1/4)  -> [0.1, 1.0]
# - GA fitness や stage_c.passed には影響しない (observation only)
_MISSION_SCORE_FLOOR: Final[float] = 0.1
_MISSION_SCORE_RANGE: Final[float] = 0.9  # = 1.0 - _MISSION_SCORE_FLOOR


def _compute_mission_score(
    *,
    sharpe: float | None,
    total_pnl: float,
    max_drawdown_frac: float,
    trade_count: int,
    live_criteria: Mapping[str, float | int],
) -> float | None:
    """live_criteria 4 軸の soft 合算スコア (幾何平均, [0.1, 1.0])。

    sharpe が None (= base 評価が trade を出せず Sharpe 計算不能) の場合は
    score 計算不能として None を返す (報告側で「未計測」表示)。
    その他の軸は数値必須 (Stage C base 評価が成功していれば自動で揃う)。
    """
    if sharpe is None:
        return None

    # sharpe: lower=0, target=sharpe_min (T042 換算後値が入る想定)
    sharpe_target = float(live_criteria["sharpe_min"])
    sharpe_lower = 0.0
    sharpe_score = _axis_score(sharpe, sharpe_lower, sharpe_target)

    # total_pnl: lower=0, target=total_pnl_min
    pnl_target = float(live_criteria["total_pnl_min"])
    pnl_lower = 0.0
    pnl_score = _axis_score(total_pnl, pnl_lower, pnl_target)

    # max_drawdown_frac: lower=max_drawdown_max (高 dd = 0 score), target=0 (低 dd = 1 score)
    dd_lower = float(live_criteria["max_drawdown_max"])
    dd_target = 0.0
    dd_score = _axis_score_inverted(max_drawdown_frac, dd_lower, dd_target)

    # trade_count: lower=0, target=trade_count_min。範囲外 (>max) は 0 score
    tc_target = float(live_criteria["trade_count_min"])
    tc_max = float(live_criteria["trade_count_max"])
    tc_score = (
        0.0
        if trade_count > tc_max
        else _axis_score(float(trade_count), 0.0, tc_target)
    )

    # 0 を避けて floor 0.1 にスケール
    floor = _MISSION_SCORE_FLOOR
    rng = _MISSION_SCORE_RANGE
    s = [floor + rng * x for x in (sharpe_score, pnl_score, dd_score, tc_score)]

    # 幾何平均
    product = 1.0
    for v in s:
        product *= v
    return product ** (1.0 / 4.0)


def _axis_score(metric: float, lower: float, target: float) -> float:
    """min-max 正規化 + clip([0, 1])。target == lower で metric>=target なら 1.0、
    target < lower (= 設定不整合) は 0.0 を返す (defensive)。"""
    if target <= lower:
        return 1.0 if metric >= target else 0.0
    raw = (metric - lower) / (target - lower)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def _axis_score_inverted(metric: float, lower: float, target: float) -> float:
    """逆向き軸 (drawdown 等、小さいほど良い)。lower > target を期待。"""
    if lower <= target:
        return 1.0 if metric <= target else 0.0
    raw = (lower - metric) / (lower - target)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def evaluate_stage_c(
    genome: Genome,
    bars_holdout: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
    *,
    cross_pair_evaluator: CrossPairEvaluator | None = None,
    cross_pair_inputs: Mapping[str, object] | None = None,
) -> StageResult:
    """Stage C — Live Criteria + Stress 評価。

    base evaluation で live_criteria を AND 判定、イントラデイ違反 trade の
    検出、spread × ``spread_stress_multiplier`` で stress test を行う。
    cross-pair (ii-lite) は Phase 2 では shadow のみ
    (``passed`` には影響しない、``cross_pair_evaluator=None`` 許容)。

    drawdown は **fraction (0-1)** に統一して比較
    (``BacktestMetrics.max_drawdown_pct`` は percent → ``/100`` 換算)。

    payload には observation 用に ``mission_score`` (T043) を含める。
    ``mission_score`` は live_criteria 4 軸の soft 合算で、GA fitness や
    ``passed`` 判定には影響しない。

    Returns:
        StageResult(stage="C", ...)。
    """
    start = _time.perf_counter()
    reasons: list[str] = []
    lc = stage_config.live_criteria

    base_sharpe: float | None = None
    base_total_pnl: float = 0.0
    base_max_dd_frac: float = 0.0
    base_trade_count = 0
    overnight_violations = 0
    base_failed = False

    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_holdout, strategy, broker, backtest_config)
        bt = compute_metrics(
            res.trades,
            res.equity_curve,
            trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
        )
        # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
        # T042 Phase 0 完了: live_criteria.sharpe_min=1.0 は **annualized** Sharpe
        # スケールで意味を保ち、trade-level base_sharpe は下流で _annualize_trade_sharpe
        # により stage_c.holdout_days を window として年率換算してから lc 判定する
        # (詳細: docs/alpha_factory/sharpe-rescale.md、Lo 2002 引用)。
        base_sharpe = (
            float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
        )
        base_total_pnl = float(bt.total_pnl)
        base_max_dd_frac = float(bt.max_drawdown_pct) / 100.0
        base_trade_count = bt.trade_count
        for t in res.trades:
            if t.entry_time.date() != t.exit_time.date():
                overnight_violations += 1
    except Exception as exc:
        logger.warning(
            "stage_c.base_failure",
            genome=genome.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        base_failed = True
        reasons.append("system_failure")

    # T042: trade-level base_sharpe を annualized 換算してから live_criteria 判定。
    # holdout_days = stage_c.stage_c_holdout_days (config) を window として用いる。
    base_sharpe_annualized = _annualize_trade_sharpe(
        base_sharpe, base_trade_count, stage_config.stage_c_holdout_days
    )

    # live_criteria 判定 (base が成功した場合のみ意味を持つ)
    lc_pass: dict[str, bool] = {
        "sharpe": (
            base_sharpe_annualized is not None
            and base_sharpe_annualized >= float(lc["sharpe_min"])
        ),
        "total_pnl": base_total_pnl >= float(lc["total_pnl_min"]),
        "max_drawdown": base_max_dd_frac <= float(lc["max_drawdown_max"]),
        "trade_count_min": base_trade_count >= int(lc["trade_count_min"]),
        "trade_count_max": base_trade_count <= int(lc["trade_count_max"]),
    }
    if not base_failed:
        if not lc_pass["sharpe"]:
            reasons.append("live_criteria.sharpe<min")
        if not lc_pass["total_pnl"]:
            reasons.append("live_criteria.total_pnl<min")
        if not lc_pass["max_drawdown"]:
            reasons.append("live_criteria.max_drawdown>max")
        if not lc_pass["trade_count_min"]:
            reasons.append("live_criteria.trade_count<min")
        if not lc_pass["trade_count_max"]:
            reasons.append("live_criteria.trade_count>max")

    intraday_compliant = overnight_violations == 0
    if not base_failed and not intraday_compliant:
        reasons.append("intraday_constraint_violation")

    # spread stress
    stress_payload: dict[str, object] = {
        "skipped": False,
        "sharpe": None,
        "total_pnl": 0.0,
        "max_drawdown_frac": 0.0,
        "trade_count": 0,
        "sharpe_degradation": None,
        "pnl_degradation": 0.0,
    }
    if backtest_config.max_spread_bps is None:
        stress_payload["skipped"] = True
        reasons.append("spread_stress_skipped")
    else:
        # Decimal × Decimal で型安全 (max_spread_bps が Decimal/float いずれでも安全)
        base_max = Decimal(str(backtest_config.max_spread_bps))
        multiplier_dec = Decimal(str(stage_config.spread_stress_multiplier))
        new_max = base_max * multiplier_dec
        stress_config = replace(backtest_config, max_spread_bps=new_max)
        try:
            strategy = DslStrategy(genome, primitive_evaluator)
            broker = MockBroker(instrument_meta=meta)
            res = run_backtest(bars_holdout, strategy, broker, stress_config)
            bt = compute_metrics(
                res.trades,
                res.equity_curve,
                trade_count_min_for_sharpe=stage_config.trade_count_min_for_sharpe,
            )
            # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
            s_sharpe = (
                float(bt.trade_sharpe_raw) if bt.trade_sharpe_raw is not None else None
            )
            s_total_pnl = float(bt.total_pnl)
            s_trade_count = bt.trade_count
            stress_payload["sharpe"] = s_sharpe
            stress_payload["total_pnl"] = s_total_pnl
            stress_payload["max_drawdown_frac"] = float(bt.max_drawdown_pct) / 100.0
            stress_payload["trade_count"] = s_trade_count
            if base_sharpe is not None and s_sharpe is not None:
                stress_payload["sharpe_degradation"] = base_sharpe - s_sharpe
            stress_payload["pnl_degradation"] = base_total_pnl - s_total_pnl
            # hard gate (AND): canonical reason code は <min 形式で統一
            if s_trade_count < int(lc["trade_count_min"]):
                reasons.append("spread_stress.trade_count<min")
            if s_total_pnl < float(stage_config.spread_stress_min_total_pnl):
                reasons.append("spread_stress.total_pnl<min")
            if s_sharpe is None or s_sharpe < float(
                stage_config.spread_stress_min_sharpe
            ):
                reasons.append("spread_stress.sharpe<min")
        except Exception as exc:
            logger.warning(
                "stage_c.stress_failure",
                genome=genome.name,
                error=str(exc),
            )
            stress_payload["skipped"] = True
            reasons.append("spread_stress_skipped")

    # cross-pair shadow hook (T016)
    # Phase 2: shadow only — passed には影響させない (mode='hard' は別 TODO)
    # 例外隔離 + skipped 伝搬 + audit 用 error_type 保持
    cross_pair_payload: dict[str, object] = {
        "skipped": True,
        "result": None,
        "error_type": None,
    }
    if cross_pair_evaluator is not None:
        if cross_pair_inputs is None:
            raise ValueError(
                "cross_pair_inputs required when cross_pair_evaluator is set"
            )
        validated = _validate_cross_pair_inputs(cross_pair_inputs)
        cp_result: CrossPairResult | None
        try:
            cp_result = cross_pair_evaluator.evaluate(
                genome=genome,
                target_pair=validated["target_pair"],
                pair_bars_map=validated["pair_bars_map"],
                meta_map=validated["meta_map"],
                backtest_config=backtest_config,
            )
        except Exception as exc:
            logger.warning(
                "stage_c.cross_pair_failure",
                genome=genome.name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            cp_result = None
            cross_pair_payload["error_type"] = type(exc).__name__
        if cp_result is None:
            # 例外 fallback: skipped 扱いで記録 (audit 用 error_type は残す)
            cross_pair_payload["skipped"] = True
            cross_pair_payload["result"] = None
        else:
            # CrossPairResult.metrics["skipped"] を Stage C payload に伝搬
            # (archive `_extract_cross_pair` が payload.skipped を見て
            #  ii_lite_pass=None を判定する契約)
            cp_metrics = cp_result.metrics
            cp_skipped = (
                bool(cp_metrics.get("skipped", False))
                if isinstance(cp_metrics, Mapping)
                else False
            )
            cross_pair_payload["skipped"] = cp_skipped
            cross_pair_payload["result"] = cp_result

    passed = len(reasons) == 0
    elapsed = _time.perf_counter() - start

    # T043 + T042: mission_score (4 軸 soft 合算)。sharpe 軸は live_criteria.sharpe_min
    # と同じ annualized スケールで評価する (T042 で base_sharpe_annualized を導入)。
    mission_score = _compute_mission_score(
        sharpe=base_sharpe_annualized,
        total_pnl=base_total_pnl,
        max_drawdown_frac=base_max_dd_frac,
        trade_count=base_trade_count,
        live_criteria=lc,
    )

    metrics_envelope: dict[str, object] = {
        "stage": "C",
        "genome_name": genome.name,
        "n_bars": len(bars_holdout),
        "wall_time_seconds": elapsed,
        "payload": {
            # T-sharpe Phase 1A: payload "sharpe" → "trade_sharpe_raw" にリネーム
            # base_sharpe には trade_sharpe_raw (v2) が入っている
            "trade_sharpe_raw": base_sharpe,
            # T042: 年率換算 Sharpe を別 key で露出 (live_criteria 比較用、報告用)。
            # base 評価の trade を出せず換算不能なら None。
            "trade_sharpe_annualized": base_sharpe_annualized,
            "total_pnl": base_total_pnl,
            "max_drawdown_frac": base_max_dd_frac,
            "trade_count": base_trade_count,
            "mission_score": mission_score,
            "live_criteria_pass": lc_pass,
            "intraday_compliant": intraday_compliant,
            "overnight_violations": overnight_violations,
            "stress": stress_payload,
            "cross_pair": cross_pair_payload,
        },
    }
    return StageResult(
        stage="C",
        passed=passed,
        metrics=metrics_envelope,
        reason_codes=tuple(reasons),
    )
