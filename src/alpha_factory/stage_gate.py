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

import statistics as _stats
import time as _time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar, Literal, Protocol, TypedDict, cast

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

__all__ = [
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

    # Stage B
    stage_b_window_months: int = 18
    wf_train_days: int = 120
    wf_test_days: int = 20
    wf_step_days: int = 20
    wf_embargo_days: int = 1
    stage_b_median_oos_sharpe_min: float = 0.20
    stage_b_positive_fold_min: float = 0.60
    stage_b_dsr_min: float = 0.0  # monitor only (Phase 4 で hard 化)

    # Stage C
    stage_c_holdout_days: int = 60
    spread_stress_multiplier: float = 1.5
    spread_stress_min_total_pnl: float = 0.0
    spread_stress_min_sharpe: float = 0.0

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
        # MappingProxyType で frozen dict 化（外部書換不能）
        object.__setattr__(
            self,
            "live_criteria",
            MappingProxyType(dict(self.live_criteria)),
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
        ``system_failure`` > ``no_trades`` > ``metric_unavailable`` >
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
    exception_caught = False

    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars_60d, strategy, broker, backtest_config)
        bt = compute_metrics(result.trades, result.equity_curve)
        trade_count = bt.trade_count
        sharpe_raw = float(bt.sharpe) if bt.sharpe is not None else None
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
    #   system_failure > no_trades > metric_unavailable > below_threshold
    if exception_caught:
        reasons.append("system_failure")
    elif trade_count < 1:
        reasons.append("no_trades")
    elif sharpe_raw is None:
        reasons.append("metric_unavailable")
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
            "sharpe_raw": sharpe_raw,
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

    # 18 ヶ月全体 IS monitor
    is_full_sharpe: float | None = None
    is_full_total_pnl: float = 0.0
    is_full_trade_count = 0
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_18m, strategy, broker, backtest_config)
        bt = compute_metrics(res.trades, res.equity_curve)
        is_full_sharpe = float(bt.sharpe) if bt.sharpe is not None else None
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
            bt = compute_metrics(res.trades, res.equity_curve)
            fold_sharpe = float(bt.sharpe) if bt.sharpe is not None else None
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
        else:
            oos_sharpes_imputed.append(fold_sharpe)

    # 集計と判定
    median_oos: float | None = None
    positive_ratio: float | None = None
    if n_fold == 0:
        reasons.append("no_folds")
    elif n_fold == 1:
        reasons.append("insufficient_folds")
        median_oos = float(oos_sharpes_imputed[0])
        positive_ratio = 1.0 if oos_sharpes_imputed[0] > 0 else 0.0
    else:
        median_oos = float(_stats.median(oos_sharpes_imputed))
        positive_ratio = sum(1 for s in oos_sharpes_imputed if s > 0) / n_fold
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
            "oos_sharpes": tuple(oos_sharpes_imputed),
            "median_oos_sharpe": median_oos,
            "positive_fold_ratio": positive_ratio,
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
        bt = compute_metrics(res.trades, res.equity_curve)
        base_sharpe = float(bt.sharpe) if bt.sharpe is not None else None
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

    # live_criteria 判定 (base が成功した場合のみ意味を持つ)
    lc_pass: dict[str, bool] = {
        "sharpe": base_sharpe is not None and base_sharpe >= float(lc["sharpe_min"]),
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
            bt = compute_metrics(res.trades, res.equity_curve)
            s_sharpe = float(bt.sharpe) if bt.sharpe is not None else None
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

    metrics_envelope: dict[str, object] = {
        "stage": "C",
        "genome_name": genome.name,
        "n_bars": len(bars_holdout),
        "wall_time_seconds": elapsed,
        "payload": {
            "sharpe": base_sharpe,
            "total_pnl": base_total_pnl,
            "max_drawdown_frac": base_max_dd_frac,
            "trade_count": base_trade_count,
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
