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
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar, Final, Literal, Protocol, TypedDict, cast

import structlog

from src.alpha_factory.canonical_adapter import (
    compute_business_day_universe_from_bars,
    equity_curve_to_bar_equity_series,
    trade_to_trade_record,
)
from src.alpha_factory.canonical_metrics import (
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    evaluate_canonical_five,
)
from src.alpha_factory.walk_forward import make_wf_folds
from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import BacktestMetrics, compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.broker.orders import Trade as BrokerTrade
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator
from src.ga.complexity import genome_size_norm

logger = structlog.get_logger(__name__)


# B Phase 2 切替コミット step 1: dual-path canonical 5 metrics 計算用 default
# (= live_criteria に win_rate_min が含まれない既存運用との互換性、
#   詳細設計 § 4.2.3 + Codex Round 2 [Suggestion] 取込)。
# 0.45 は synthesis § 6.4 で参照される標準値。 後続 step で live_criteria に
# win_rate_min を追加する際に削除予定。
_CANONICAL_DUAL_PATH_DEFAULT_WIN_RATE_MIN: Final[float] = 0.45


def _build_canonical_thresholds_for_window(
    *,
    live_criteria: Mapping[str, float | int],
    window_days: int,
    baseline_dataset_days: int = 730,
) -> CanonicalFiveThresholds:
    """評価窓用 CanonicalFiveThresholds を構築 (= 全 Stage 共通).

    Stage A (60d) / Stage B IS (540d) / Stage C base (60d) で再利用される
    汎用 helper。 derive_stage_a_thresholds (= stage_a_evaluator) と異なり、
    live_criteria に win_rate_min が無くても _CANONICAL_DUAL_PATH_DEFAULT_WIN_RATE_MIN
    を default として使用 (= 既存 live_criteria 互換性維持)。

    Args:
        live_criteria: stage_gate.live_criteria (= MappingProxyType[str, float|int])。
        window_days: 評価窓日数 (= calendar day 基準で step 1/1.5 統一)。
        baseline_dataset_days: live_criteria の baseline 期間 (= 730d default)。

    Returns:
        CanonicalFiveThresholds: window scaling 後の thresholds。
    """
    ratio = window_days / baseline_dataset_days
    trade_min_window = max(
        1, math.ceil(live_criteria["trade_count_min"] * ratio)
    )
    trade_max_window = max(
        trade_min_window,
        math.floor(live_criteria["trade_count_max"] * ratio),
    )
    return CanonicalFiveThresholds(
        sharpe_min=float(live_criteria["sharpe_min"]),
        net_pnl_min=float(live_criteria["total_pnl_min"]) * ratio,
        max_dd_max=float(live_criteria["max_drawdown_max"]),
        trade_count_min=trade_min_window,
        trade_count_max=trade_max_window,
        win_rate_min=float(
            live_criteria.get(
                "win_rate_min",
                _CANONICAL_DUAL_PATH_DEFAULT_WIN_RATE_MIN,
            )
        ),
    )


def _try_evaluate_canonical_five_safe(
    *,
    trades: list[BrokerTrade],
    equity_curve: list[tuple[datetime, Decimal]],
    bars: list[PriceBar],
    live_criteria: Mapping[str, float | int],
    window_days: int,
    stage_label: str,
    genome_name: str,
    enabled: bool,
) -> CanonicalFiveResult | None:
    """canonical_metrics 計算を例外 safe で実施 (= dual-path LOG_ONLY mode 用).

    Args:
        enabled: phase2_canonical_metrics_mode != "disabled" のとき True
            (= disabled mode は完全 skip で計算 overhead 0)。
        bars: 評価窓の全 price bars (= business_day_universe 構築用、
            Codex Round 2 [Suggestion] 入力契約)。
        live_criteria: stage_config.live_criteria (= window scaling 入力)。
        window_days: 評価窓日数 (= Stage A は stage_a_window_days)。

    例外時は WARN log のみで None 返り (= 既存判定経路は完全に不変)。
    no-raise 契約は evaluate_canonical_five 側にあるが、 adapter 経路 / thresholds
    構築で naive datetime / non-UTC / 不正 live_criteria が混入した場合は
    ValueError / ThresholdsInvalidError raise されるため、 本 helper で catch する。
    thresholds 構築も try 内で行う (= test fixture の live_criteria が不正でも
    legacy 経路を巻き込まない)。

    Returns:
        CanonicalFiveResult、 または None (= disabled / 例外時)。
    """
    if not enabled:
        return None
    try:
        thresholds = _build_canonical_thresholds_for_window(
            live_criteria=live_criteria,
            window_days=window_days,
        )
        canonical_trades = tuple(trade_to_trade_record(t) for t in trades)
        canonical_bars = equity_curve_to_bar_equity_series(equity_curve)
        canonical_universe = compute_business_day_universe_from_bars(bars)
        return evaluate_canonical_five(
            canonical_trades,
            canonical_bars,
            thresholds,
            canonical_universe,
        )
    except Exception as exc:
        logger.warning(
            "stage_gate.canonical_five.skipped",
            stage=stage_label,
            genome=genome_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None


def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,
    pair_label: str | None = None,
) -> None:
    """dual-path 結果 (legacy + canonical) を構造化 log に出力.

    Args:
        stage_label: § 4.7 ログ命名規約 SSOT
            (A / B_IS / B_fold / C_base / C_stress / C_cross_pair)。
            注: C_stress は step 1.7 で追加、 C_cross_pair は step 1.8 で追加。
        genome_name: genome 識別子 (= logger kwargs key `genome`)。
        legacy: BacktestMetrics (= 既存判定経路、 cross_pair の場合は per-pair `bt`)。
        canonical: CanonicalFiveResult or None (= helper 例外時 / disabled mode)。
        fold_index: per-fold 識別子 (= 0..n_fold-1)。 stage_label="B_fold" のとき必須、
            他 stage (= A / B_IS / C_base / C_stress / C_cross_pair) は None。
            step 1.6 detailed-design § 4.7 / acceptance C4 / D5 で SSOT 化
            (= B_fold log entry は (stage, genome, fold) で一意特定可能)。
        pair_label: per-pair 識別子 (= 実 pair 名、 例 "EUR_USD")。
            stage_label="C_cross_pair" のとき必須、 他 stage (= A / B_IS /
            B_fold / C_base / C_stress) は None。
            step 1.8 で追加 (= 詳細設計 § 2.5、 acceptance D5、
            役割識別 (target / anchor1 / anchor2) は dual-path log に出さず、
            将来 role 分析時は Stage C payload の `target_pair` / `anchor_pairs` と
            `(genome, pair)` で join する設計)。

    Raises:
        ValueError: stage_label="B_fold" かつ fold_index is None
            (= step 1.6 acceptance D5)。
        ValueError: stage_label="C_cross_pair" かつ pair_label が None / 空文字 /
            空白文字列 / 前後空白付き文字列 (= step 1.8 acceptance D5、
            識別子契約 SSOT、 C_cross_pair log entry は (stage, genome, pair) で
            一意特定可能でなければならない、 実 pair 名のみ許可)。
        ValueError: stage_label != "C_cross_pair" かつ pair_label is not None
            (= step 1.8 acceptance D5、 pair_label は C_cross_pair 専用、
            他 stage で指定するとログ名前空間汚染)。

    解釈規約 (Codex Round 1 [Warning] 3 取込):
    - dual-path log は **方向性監視** を目的とする (= 値一致や良し悪し判定ではない)。
    - 解釈軸は (1) reason_code、 (2) gate_pass / canonical_invariants_feasible、
      (3) 主要指標の数値 diff (= 規模感の確認のみ)。
    - 値の一致 / 不一致を理由に collider bias で 「canonical が間違っている」 と
      判断しない (= synthesis 評価哲学の差を尊重)。

    fail-fast flag 情報 (Codex Round 1 [Warning] 2 + Round 2 [Suggestion] 取込):
    - flags_source="default_false" + fail_fast_flags_comparable=False で
      step 1 では broker engine から伝搬していないことを明示。
    """
    # 識別子契約 SSOT (= step 1.6 + step 1.8、 fold_index も pair_label と
    # 対称的に non-B_fold で拒否 = Codex impl-review Round 1 [Warning] 反映)
    if stage_label == "B_fold" and fold_index is None:
        raise ValueError(
            "_log_canonical_dual_path(stage_label='B_fold') requires fold_index "
            "(= step 1.6 acceptance D5 / 識別子契約 SSOT、 "
            "B_fold log entry は (stage, genome, fold) で一意特定可能でなければならない)"
        )
    if stage_label != "B_fold" and fold_index is not None:
        raise ValueError(
            f"_log_canonical_dual_path(stage_label={stage_label!r}) does not accept "
            "fold_index (= step 1.8 識別子契約 SSOT、 fold_index は B_fold 専用、 "
            "他 stage で指定するとログ名前空間汚染、 "
            "Codex impl-review Round 1 [Warning] 反映)"
        )
    if stage_label == "C_cross_pair":
        if not isinstance(pair_label, str) or not pair_label.strip():
            raise ValueError(
                "_log_canonical_dual_path(stage_label='C_cross_pair') requires "
                "non-empty pair_label (= step 1.8 acceptance D5 / 識別子契約 SSOT、 "
                "C_cross_pair log entry は (stage, genome, pair) で一意特定可能 "
                "でなければならない、 None / 空文字 / 空白文字列はいずれも識別子契約違反)"
            )
        if pair_label != pair_label.strip():
            raise ValueError(
                "_log_canonical_dual_path(stage_label='C_cross_pair') requires "
                "pair_label without leading / trailing whitespace "
                "(= step 1.8 acceptance D5、 実 pair 名契約: 'EUR_USD' は OK、 "
                "' EUR_USD ' は NG)"
            )
    elif pair_label is not None:
        raise ValueError(
            f"_log_canonical_dual_path(stage_label={stage_label!r}) does not accept "
            "pair_label (= step 1.8 識別子契約 SSOT、 pair_label は C_cross_pair 専用、 "
            "他 stage で指定するとログ名前空間汚染)"
        )

    if canonical is None:
        log_kwargs: dict[str, object] = {
            "stage": stage_label,
            "genome": genome_name,
            "canonical_skipped": True,
        }
        if fold_index is not None:
            log_kwargs["fold"] = fold_index
        if pair_label is not None:
            log_kwargs["pair"] = pair_label
        logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)
        return

    log_kwargs = {
        "stage": stage_label,
        "genome": genome_name,
        # canonical の fail-fast flag 出所 (= step 1 では default False 固定、
        # Codex Round 2 [Suggestion] 取込で boolean field も併記)
        "flags_source": "default_false",
        "fail_fast_flags_comparable": False,
        # legacy
        "legacy_total_pnl": str(legacy.total_pnl),
        "legacy_trade_count": legacy.trade_count,
        "legacy_max_dd_pct": str(legacy.max_drawdown_pct),
        "legacy_sharpe": str(legacy.sharpe) if legacy.sharpe is not None else None,
        # canonical
        "canonical_net_pnl": canonical.net_pnl_after_cost,
        "canonical_trade_count": canonical.trade_count,
        "canonical_max_dd": canonical.max_dd,
        "canonical_sr_worst_block": canonical.sr_session_worst_block_scale,
        "canonical_sr_worst_annual": canonical.sr_session_worst_annual_estimate,
        "canonical_wr_worst": canonical.session_block_win_rate_worst,
        "canonical_gate_pass": canonical.gate_pass,
        "canonical_gate_worst_gap": canonical.gate_worst_gap,
        "canonical_invariants_feasible": canonical.invariants.is_feasible,
        # diff (= 規模感確認のみ、 値一致を要求しない)
        "pnl_diff": float(legacy.total_pnl) - canonical.net_pnl_after_cost,
        "trade_count_diff": legacy.trade_count - canonical.trade_count,
        # 解釈規約 (運用者向け sentinel)
        "interpretation_note": "direction_monitoring_only",
    }
    if fold_index is not None:
        log_kwargs["fold"] = fold_index
    if pair_label is not None:
        log_kwargs["pair"] = pair_label
    logger.info("stage_gate.canonical_five.dual_path", **log_kwargs)

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
    "STAGE_GATE_VERSION",
    "SYSTEM_FAILURE_FITNESS",
    "CrossPairEvaluator",
    "CrossPairInputs",
    "CrossPairResult",
    "FoldUnavailableReason",
    "StageGateConfig",
    "StageResult",
    "evaluate_stage_a",
    "evaluate_stage_b",
    "evaluate_stage_c",
]


# T054: Stage gate logic version 識別子。
# state file (calibrate_state) で「異なる stage gate ロジックの履歴を適用しない」
# cross-run contamination guard に使用。Stage B fold reason 集計や
# fold-trade-count guard 等のロジック改変時にバージョンを上げる。
# T087: bars_stage_b が Stage A 期間と時系列上 disjoint 化されたため
# v3_stage_b_fold_min_trade_count → v4_stage_b_disjoint に bump。
# 過去 v3 history の threshold が新条件下で誤適用されないよう cross-run guard に伝搬。
STAGE_GATE_VERSION: Final[str] = "v4_stage_b_disjoint"


# T054: Stage B fold が unavailable になった理由の排他的 enum 化。
# 詳細設計 §「unavailable reason の排他的 enum 化」(Round 2) 反映。
# 最初にマッチした reason を採用 (排他的)、優先順位:
#   1. FOLD_EXCEPTION (例外発生は他の判定より優先)
#   2. NO_TRADES (trades 空)
#   3. ZERO_VARIANCE (trades あって 0 分散)
#   4. TRADE_COUNT_BELOW_MIN (trade_count < threshold)
#   5. OTHER (上記以外、要 follow-up)
class FoldUnavailableReason(StrEnum):
    """Stage B fold が trade-level Sharpe 計算不能になった理由 (排他的 enum)."""

    FOLD_EXCEPTION = "fold_exception"
    NO_TRADES = "no_trades"
    TRADE_COUNT_BELOW_MIN = "trade_count_below_min"
    ZERO_VARIANCE = "zero_variance"
    OTHER = "other"


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
    # cycle 2 (improve-cycle): 起動時 fail-closed 用 statistical safety floor。
    # `wf_min_folds_required` (worker 短絡判定 graceful degrade) と役割分離。
    # `compute_max_folds(...) < wf_min_safe_folds` で起動時 RuntimeError fail-closed。
    wf_min_safe_folds: int = 5

    # T057 Phase 2: aux data 必須化 flag (default False で互換性維持、
    # config / CLI で True に上書き可能)。True のとき preflight check で
    # hard_required (VIXCLS, DTWEXBGS, EUR_USD_M1, USD_JPY_M1) 不足は fail-closed.
    strict_aux_required: bool = False

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

    # cycle 4 (improve-cycle): GA selection の fold_robust 判定閾値。
    # cycle 7 で 0.4 → 0.55 に厳格化:
    # cycle 6 archive 解析で「pfre>=0.4 AND trade>=50」 個体が 591 件存在、
    # しかし全員 Stage B 閾値 0.6 不達で near-miss と verified (H10)。
    # 0.55 = Stage B 閾値 0.6 直前 (頭出し許容範囲)、 GA selection を
    # 「真の Stage B 通過候補」 のみに集中させる。 0.6 直接の場合は
    # selection 候補ゼロのリスク、 0.55 は exploration 余地を残す。
    # 詳細: devnotes/20260506-1622-fx-improve-c4/ + 20260506-2155-fx-improve-c7/
    fold_robust_threshold: float = 0.55

    # cycle 6 (improve-cycle): fitness_pen に trade_count adequacy penalty 追加。
    # GA 探索を「entry_count_min (= 50) 以上の取引を行う」 方向にシフト。
    # penalty = gamma * max(0, entry_count_min - trade_count) / entry_count_min
    #        ∈ [0, gamma] (trade_count >= entry_count_min で 0)
    # default 0.05 = 既存 alpha_a (size_norm penalty) と同オーダー
    # H8 (Stage B + feasible 個体不在) への構造的介入、 selection_score の
    # cycle 4/5 拡張と直交。
    # 詳細: devnotes/20260506-2015-fx-improve-c6/detailed-design.md
    stage_a_trade_count_penalty_gamma: float = 0.05

    # T054: Stage B fold 専用の trade-level Sharpe sample-size guard。
    # @why: Stage A は 60-day window で trade_count_min_for_sharpe=30 を要求
    # するが、Stage B fold は wf_test_days=10 と短い期間で同じ 30 trade
    # を要求すると trade rate 3 trades/day の個体しか fold 評価不能になり、
    # all_folds_unavailable 一色が発生する (T054 investigation §0.4 verified)。
    # 修正方針 (詳細設計 §仮説 B-X / 案 3): Stage B fold 専用閾値を独立化。
    # 値の根拠 (Lo 2002 SE 上限):
    #   - Sharpe SE ≈ √((1+0.5×SR²)/N)
    #   - 目標 SR ≈ stage_b_median_oos_sharpe_min=0.05、SE 上限 0.32 から逆算 N≈10
    #   - median + positive_fold_ratio の 2 段集約で fold 単位 noise を吸収
    #   - **Stage B median + positive_fold_ratio ベースの集約評価で許容**
    # default 10 = trade-level Sharpe 推定として最低限の妥当 N。
    # **緩和ではなく「機能していた当時 (run_20260426_145502 median 167) の挙動を
    # 意図的に再現する設計判断」** (詳細設計 仮説 B-X 案 3 / 禁止事項 4 抵触なし)。
    stage_b_fold_trade_count_min: int = 10

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

    # B Phase 2 切替コミット step 1: canonical_metrics dual-path 配線用 mode flag
    # (= AlphaFactoryConfig.phase2.canonical_metrics_mode から伝搬)。
    # log_only = dual-path 計算 + log のみ (default、 既存判定不変)
    # disabled = canonical 計算 skip (= 計算 overhead 0)
    # 詳細: devnotes/20260503-1024-B-phase2-step1-canonical-metrics/
    phase2_canonical_metrics_mode: Literal["log_only", "disabled"] = "log_only"

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
class _PairSidecarInputs:
    """canonical_five 計算用 input 集合 (= dual-path 経路でのみ使用).

    ``cross_pair.py`` で per-pair backtest 結果 (= trades / equity_curve / bt) を
    保持し、 ``stage_gate.py`` 側 dual-path 配線で canonical 5 軸を計算する際に
    使う ephemeral 入力集合。 deep copy なし、 既存経路の shallow copy
    (例: ``bars=list(pair_bars[pair])``) を許容。 canonical 計算後、
    ``CrossPairResult._shadow_sidecar_inputs`` の sanitize (= 空 dict 差し替え)
    で payload / IPC / archive に絶対漏れない契約 (= B step 1.8 詳細設計 § 2.4 /
    acceptance E)。

    本 dataclass は ``stage_gate.py`` 側に定義することで、 ``cross_pair.py`` から
    の単方向 import 経路を維持し循環依存を回避する (= B step 1.8 概念設計
    Round 2 [Critical 3] 反映)。

    Import 契約 (= B step 1.8 詳細設計 Round 1 [Suggestion 施策 1] 反映):
        ``cross_pair.py`` からは ``from src.alpha_factory.stage_gate import
        CrossPairResult, _PairSidecarInputs`` で参照する。
        - cross_pair.py → stage_gate.py の単方向 import (= 既存配線維持)
        - stage_gate.py → cross_pair.py の逆 import は禁止 (= 循環依存 防止)
        - 他 module からの import は想定しない (= leading underscore で
          module-private を明示)

    不変前提 (= B step 1.8 詳細設計 Round 1 [Warning 施策 1] 反映):
        bars / trades / equity_curve は production code (= cross_pair.py /
        stage_gate.py / canonical_adapter.py / canonical_metrics) で書き込まれない
        契約。 sidecar 構築から sanitize 完了までの間、 内容は不変
        (= acceptance E7 で deep equality 比較で固定)。 frozen=True dataclass で
        attr 再代入は防げるが、 list / dict は技術的に mutable のため、 production
        code の振る舞い契約として明文化する。
    """

    bars: list[PriceBar]
    trades: list[BrokerTrade]
    equity_curve: list[tuple[datetime, Decimal]]
    bt: BacktestMetrics


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
    # B step 1.8: dual-path 経路用 ephemeral sidecar (= public API ではない、
    # archive / payload transport には漏れない契約、 詳細設計 § 2.3)。
    # field 設定:
    #   - default_factory=dict: multiprocessing pickle 互換 (= MappingProxyType 不可、
    #     概念設計 Round 2 [Critical 2])
    #   - repr=False: snapshot 比較ノイズ排除 (= 概念設計 Round 2 [Warning])
    #   - compare=False: dataclass equality から除外 (= acceptance E5)
    _shadow_sidecar_inputs: dict[str, _PairSidecarInputs] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )


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
        # B Phase 2 切替コミット step 1: dual-path canonical 5 metrics (LOG_ONLY mode)
        # 既存 fitness 判定経路には影響させない (= regression 0、 sidecar 計算 + log のみ)。
        # 例外 safe wrapper で legacy 経路を保護 (= adapter / thresholds 例外で巻き込まない)。
        canonical_sidecar = _try_evaluate_canonical_five_safe(
            trades=result.trades,
            equity_curve=result.equity_curve,
            bars=bars_60d,
            live_criteria=stage_config.live_criteria,
            window_days=stage_config.stage_a_window_days,
            stage_label="A",
            genome_name=genome.name,
            enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
        )
        # Codex impl-review Round 1 [Warning] 取込: log 呼出も例外保護 (= logger
        # processor 異常時に legacy 経路を巻き込まない、 完全隔離)
        try:
            _log_canonical_dual_path(
                stage_label="A",
                genome_name=genome.name,
                legacy=bt,
                canonical=canonical_sidecar,
            )
        except Exception as exc:
            # logger 自身の例外は WARN log のみで legacy 経路は不変
            logger.warning(
                "stage_gate.canonical_five.log_failed",
                stage="A",
                genome=genome.name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        # canonical_sidecar は payload 非添付 (= archive Parquet schema 不変、 step 1 範囲)
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
        # cycle 6: trade_count adequacy penalty を追加
        # GA 探索を「entry_count_min 以上の取引」 方向にシフト
        # H8 (Stage B + feasible 個体不在) への構造的介入
        entry_count_min_lc = int(stage_config.live_criteria["trade_count_min"])
        if trade_count < entry_count_min_lc:
            trade_count_penalty = (
                stage_config.stage_a_trade_count_penalty_gamma
                * (entry_count_min_lc - trade_count)
                / entry_count_min_lc
            )
        else:
            trade_count_penalty = 0.0
        fitness_pen = (
            fitness_raw
            - stage_config.stage_a_alpha * size_norm_val
            - trade_count_penalty
        )
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
            "gamma_trade_count": stage_config.stage_a_trade_count_penalty_gamma,
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


def _classify_fold_unavailable(
    *,
    trade_count: int,
    trade_count_min: int,
) -> FoldUnavailableReason:
    """T054: trade_sharpe_raw=None になった理由を排他的 enum で分類する。

    優先順位 (排他的、最初にマッチした reason を採用):
    1. NO_TRADES (trade_count=0)
    2. TRADE_COUNT_BELOW_MIN (0 < trade_count < trade_count_min)
    3. ZERO_VARIANCE (trade_count >= max(2, trade_count_min) かつ std=0)
    4. OTHER (上記以外、要 follow-up — 例: trade_count >= 2 かつ < trade_count_min
       で max(2, trade_count_min) > trade_count_min のときの境界ケース)

    例外発生 (FOLD_EXCEPTION) は呼び出し元で別途設定する。

    Args:
        trade_count: fold 内の trade 数
        trade_count_min: trade_count_min_for_sharpe (Stage B 用 fold-min)
    """
    if trade_count == 0:
        return FoldUnavailableReason.NO_TRADES
    # _trade_sharpe_raw は len(returns) < max(2, trade_count_min) で None
    effective_min = max(2, trade_count_min)
    if trade_count < effective_min:
        return FoldUnavailableReason.TRADE_COUNT_BELOW_MIN
    # trade_count >= effective_min なのに None → 分散ゼロ
    return FoldUnavailableReason.ZERO_VARIANCE


def evaluate_stage_b(
    genome: Genome,
    bars_stage_b: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    stage_config: StageGateConfig,
    *,
    aux_bundle: object | None = None,
) -> StageResult:
    """Stage B — Walk-Forward OOS gate + IS monitor。

    fold ごとの test 区間で sharpe を取り、median / 正 fold 比率で複合 AND 判定。
    Stage B 全体の IS metrics は monitor として記録 (hard gate には使わない)。

    T087: ``bars_stage_b`` は Stage A 期間を時系列上 disjoint に除外したもの
    (`stage_partition_guard.validate_stage_partition` で起動時保証)。
    旧引数名 ``bars_18m`` は ``stage_b_window_months=18`` 由来の legacy 命名。

    fold metric_unavailable policy: ``oos_sharpe is None`` の fold は **0 と
    みなして母数に含める** (no-trade を hide させない設計)。

    Returns:
        StageResult(stage="B", ...)。
    """
    start = _time.perf_counter()
    reasons: list[str] = []

    folds = make_wf_folds(
        bars_stage_b,
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
    # cycle 21: fold ごとの trade_count を観測 (= time-concentrated 仮説検証用、
    # diagnostics sidecar に出力するため payload に追加。 archive 列拡張なし)
    fold_trade_counts: list[int] = []
    # T054: 排他的 reason 別カウント。sum(reason_counts.values()) == n_fold_unavailable
    # の不変条件を保つ (test_stage_gate.py で検証)。
    reason_counts: dict[FoldUnavailableReason, int] = dict.fromkeys(
        FoldUnavailableReason, 0
    )

    # 18 ヶ月全体 IS monitor
    is_full_sharpe: float | None = None
    is_full_total_pnl: float = 0.0
    is_full_trade_count = 0
    try:
        strategy = DslStrategy(genome, primitive_evaluator)
        broker = MockBroker(instrument_meta=meta)
        res = run_backtest(bars_stage_b, strategy, broker, backtest_config)
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
        # B Phase 2 切替コミット step 1.5: dual-path canonical 5 metrics (LOG_ONLY mode)
        # IS monitor (= bars_stage_b 全体 backtest) に対する dual-path 観測拡張。
        # window_days は step 1 と同じ calendar day 基準 (= stage_b_window_months * 30)。
        # 既存 fitness 判定経路には影響させない (= regression 0、 sidecar 計算 + log のみ)。
        canonical_sidecar_b_is = _try_evaluate_canonical_five_safe(
            trades=res.trades,
            equity_curve=res.equity_curve,
            bars=bars_stage_b,
            live_criteria=stage_config.live_criteria,
            window_days=stage_config.stage_b_window_months * 30,
            stage_label="B_IS",
            genome_name=genome.name,
            enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
        )
        # log 呼出も例外保護 (= step 1 と同型、 logger processor 異常時に
        # legacy 経路を巻き込まない、 完全隔離)
        try:
            _log_canonical_dual_path(
                stage_label="B_IS",
                genome_name=genome.name,
                legacy=bt,
                canonical=canonical_sidecar_b_is,
            )
        except Exception as exc:
            logger.warning(
                "stage_gate.canonical_five.log_failed",
                stage="B_IS",
                genome=genome.name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        # canonical_sidecar_b_is は payload 非添付 (= archive Parquet schema 不変)
    except Exception as exc:
        logger.warning(
            "stage_b.is_monitor_failure",
            genome=genome.name,
            error=str(exc),
        )

    # 各 fold の OOS Sharpe
    # engine の run_backtest は BacktestConfig.start/end を参照しないため
    # backtest_config をそのまま流用する (詳細設計 §3.2 参照)
    fold_min_trade_count = stage_config.stage_b_fold_trade_count_min
    # T057 follow-up: aux_bundle が渡された場合、各 fold の test_bars 長に
    # align し直した evaluator を作る (per-fold aux alignment)。
    # T057 Phase 2 で「per-stage alignment」は実装したが「Stage B fold
    # 単位の alignment」が抜けており、aux_series length が Stage B 全体長
    # (例: 183403) で固定されたまま fold (例: 11646 bars) に渡されて
    # `_check_aux_series_length` で MISALIGNMENT raise していた。
    _aux_supports_with_aux = aux_bundle is not None and hasattr(
        primitive_evaluator, "with_aux"
    )
    for i, (_train_bars, test_bars) in enumerate(folds):
        fold_sharpe: float | None = None
        fold_reason: FoldUnavailableReason | None = None
        # B Phase 2 step 1.6: dual-path 経路用に legacy 結果を保持
        # (= 別 try ブロックに渡す、 acceptance D4 物理隔離契約)
        fold_bt: BacktestMetrics | None = None
        fold_trades: list[BrokerTrade] | None = None
        fold_equity: list[tuple[datetime, Decimal]] | None = None
        # === 既存 legacy fold 計算 (= fold_sharpe / fold_reason 確定、 完全不変) ===
        try:
            if _aux_supports_with_aux:
                aligned_for_fold = aux_bundle.align_to(test_bars)  # type: ignore[union-attr]
                evaluator_for_fold = primitive_evaluator.with_aux(  # type: ignore[attr-defined]
                    **aligned_for_fold.as_evaluator_kwargs()
                )
            else:
                evaluator_for_fold = primitive_evaluator
            strategy = DslStrategy(genome, evaluator_for_fold)
            broker = MockBroker(instrument_meta=meta)
            res = run_backtest(test_bars, strategy, broker, backtest_config)
            # T054: Stage B fold 専用 trade_count_min を適用 (Stage A の
            # trade_count_min_for_sharpe=30 と分離)。
            bt = compute_metrics(
                res.trades,
                res.equity_curve,
                trade_count_min_for_sharpe=fold_min_trade_count,
            )
            # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用
            fold_sharpe = (
                float(bt.trade_sharpe_raw)
                if bt.trade_sharpe_raw is not None
                else None
            )
            # T054: trade_sharpe_raw が None の場合、なぜ None になったかを
            # 排他的 enum で classify する (FoldUnavailableReason)。
            if fold_sharpe is None:
                fold_reason = _classify_fold_unavailable(
                    trade_count=bt.trade_count,
                    trade_count_min=fold_min_trade_count,
                )
            # B Phase 2 step 1.6: dual-path 用に legacy 結果を保持
            fold_bt = bt
            fold_trades = res.trades
            fold_equity = res.equity_curve
            # cycle 21: fold trade_count 観測 (= time-concentrated 仮説検証)
            fold_trade_counts.append(int(bt.trade_count))
        except Exception as exc:
            logger.warning(
                "stage_b.fold_failure",
                genome=genome.name,
                fold=i,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            fold_sharpe = None
            fold_reason = FoldUnavailableReason.FOLD_EXCEPTION
            fold_trade_counts.append(-1)  # cycle 21: fold_exception sentinel

        # === B Phase 2 step 1.6: per-fold dual-path (= 別 try で物理隔離、
        # acceptance D1-D5)。 legacy fold 計算成功時のみ実行、 失敗時は skip
        # (= 既存 fold_failure WARN log で legacy 経路の状態は記録済)。
        # この block 内では fold_sharpe / fold_reason / reason_counts を
        # 絶対書き換えない (= D4 物理隔離契約) ===
        if (
            fold_bt is not None
            and fold_trades is not None
            and fold_equity is not None
        ):
            try:
                canonical_sidecar_b_fold = _try_evaluate_canonical_five_safe(
                    trades=fold_trades,
                    equity_curve=fold_equity,
                    bars=test_bars,
                    live_criteria=stage_config.live_criteria,
                    window_days=stage_config.wf_test_days,
                    stage_label="B_fold",
                    genome_name=genome.name,
                    enabled=(
                        stage_config.phase2_canonical_metrics_mode != "disabled"
                    ),
                )
                # log 呼出も例外保護 (= step 1.5 と同型、 logger processor 異常時に
                # legacy 経路を巻き込まない、 完全隔離)
                try:
                    _log_canonical_dual_path(
                        stage_label="B_fold",
                        genome_name=genome.name,
                        legacy=fold_bt,
                        canonical=canonical_sidecar_b_fold,
                        fold_index=i,
                    )
                except Exception as log_exc:
                    logger.warning(
                        "stage_gate.canonical_five.log_failed",
                        stage="B_fold",
                        fold=i,
                        genome=genome.name,
                        error=str(log_exc),
                        error_type=type(log_exc).__name__,
                    )
            except Exception as canonical_exc:
                # 想定外例外でも fold_sharpe / fold_reason は絶対変えない (= D1)
                logger.warning(
                    "stage_gate.canonical_five.unexpected_failure",
                    stage="B_fold",
                    fold=i,
                    genome=genome.name,
                    error=str(canonical_exc),
                    error_type=type(canonical_exc).__name__,
                )

        # === 既存 fold_sharpe / fold_reason ハンドリング (= 完全不変) ===
        if fold_sharpe is None:
            n_fold_unavailable += 1
            oos_sharpes_imputed.append(0.0)
            fold_was_unavailable.append(True)
            # T054: classify 漏れ防止: fold_reason が None なら OTHER
            if fold_reason is None:
                fold_reason = FoldUnavailableReason.OTHER
            reason_counts[fold_reason] += 1
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

    # T054: 不変条件 — sum(reason_counts.values()) == n_fold_unavailable
    # (排他的 enum 分類の正しさ保証)
    assert sum(reason_counts.values()) == n_fold_unavailable, (
        f"reason_counts sum invariant violated: "
        f"sum={sum(reason_counts.values())}, n_fold_unavailable={n_fold_unavailable}"
    )

    # cycle 21: stage_b_pass=True 個体について fold_trade_counts を log 出力
    # (= time-concentrated 仮説検証、 後続の log grep で集計)
    if passed:
        logger.info(
            "stage_b.fold_trade_counts_observation",
            genome=genome.name,
            fold_trade_counts=fold_trade_counts,
            n_fold=n_fold,
            n_fold_unavailable=n_fold_unavailable,
            median_oos_sharpe=median_oos,
            positive_fold_ratio=positive_ratio,
        )

    metrics_envelope: dict[str, object] = {
        "stage": "B",
        "genome_name": genome.name,
        "n_bars": len(bars_stage_b),
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
            # T054: 排他的 reason 別 fold count (key は string 値、archive 互換)
            "unavailable_reason_counts": {
                r.value: c for r, c in reason_counts.items()
            },
            # cycle 21: fold trade_count 観測 (= time-concentrated 仮説検証用、
            # archive 列拡張なし、 payload only。 -1 は fold_exception sentinel)
            "fold_trade_counts": tuple(fold_trade_counts),
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
        # B Phase 2 切替コミット step 1.5: dual-path canonical 5 metrics (LOG_ONLY mode)
        # base evaluation (= bars_holdout 60d backtest) に対する dual-path 観測拡張。
        # window_days は step 1 と同じ calendar day 基準 (= stage_c_holdout_days)。
        # stress / cross_pair は別軸で step 1.5 スコープ外 (= 別 log で混入なし)。
        canonical_sidecar_c_base = _try_evaluate_canonical_five_safe(
            trades=res.trades,
            equity_curve=res.equity_curve,
            bars=bars_holdout,
            live_criteria=stage_config.live_criteria,
            window_days=stage_config.stage_c_holdout_days,
            stage_label="C_base",
            genome_name=genome.name,
            enabled=(stage_config.phase2_canonical_metrics_mode != "disabled"),
        )
        # log 呼出も例外保護 (= step 1 と同型)
        try:
            _log_canonical_dual_path(
                stage_label="C_base",
                genome_name=genome.name,
                legacy=bt,
                canonical=canonical_sidecar_c_base,
            )
        except Exception as exc:
            logger.warning(
                "stage_gate.canonical_five.log_failed",
                stage="C_base",
                genome=genome.name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        # canonical_sidecar_c_base は payload 非添付 (= archive Parquet schema 不変)
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
        # B Phase 2 step 1.7: legacy stress skip → dual-path も skip (= 何も emit しない)
    else:
        # Decimal × Decimal で型安全 (max_spread_bps が Decimal/float いずれでも安全)
        base_max = Decimal(str(backtest_config.max_spread_bps))
        multiplier_dec = Decimal(str(stage_config.spread_stress_multiplier))
        new_max = base_max * multiplier_dec
        stress_config = replace(backtest_config, max_spread_bps=new_max)
        # B Phase 2 step 1.7: dual-path 経路用に legacy 結果を保持 (= 別 try に渡す、
        # acceptance D4 物理隔離契約)
        stress_bt: BacktestMetrics | None = None
        stress_trades: list[BrokerTrade] | None = None
        stress_equity: list[tuple[datetime, Decimal]] | None = None
        # === 既存 legacy stress 計算 (= stress_payload / reasons 確定、 完全不変) ===
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
            # B Phase 2 step 1.7: dual-path 用に legacy 結果を保持
            stress_bt = bt
            stress_trades = res.trades
            stress_equity = res.equity_curve
        except Exception as exc:
            logger.warning(
                "stage_c.stress_failure",
                genome=genome.name,
                error=str(exc),
            )
            stress_payload["skipped"] = True
            reasons.append("spread_stress_skipped")
            # B Phase 2 step 1.7: stress 例外 → stress_bt は None のまま、 dual-path も skip

        # === B Phase 2 step 1.7: stress dual-path (= 別 try で物理隔離、
        # acceptance D1-D4)。 legacy stress 計算成功時のみ dual-path 観測
        # (= 失敗時 skip、 既存 stress_failure WARN log で legacy 経路状態は記録済)。
        # stress_payload / reasons は dual-path で絶対書き換えない (= D4) ===
        if (
            stress_bt is not None
            and stress_trades is not None
            and stress_equity is not None
        ):
            try:
                canonical_sidecar_c_stress = _try_evaluate_canonical_five_safe(
                    trades=stress_trades,
                    equity_curve=stress_equity,
                    bars=bars_holdout,
                    live_criteria=stage_config.live_criteria,
                    window_days=stage_config.stage_c_holdout_days,
                    stage_label="C_stress",
                    genome_name=genome.name,
                    enabled=(
                        stage_config.phase2_canonical_metrics_mode != "disabled"
                    ),
                )
                # log 呼出も例外保護 (= step 1.5 / 1.6 と同型)
                try:
                    _log_canonical_dual_path(
                        stage_label="C_stress",
                        genome_name=genome.name,
                        legacy=stress_bt,
                        canonical=canonical_sidecar_c_stress,
                        # fold_index=None default (= C_stress は fold key 不在)
                    )
                except Exception as log_exc:
                    logger.warning(
                        "stage_gate.canonical_five.log_failed",
                        stage="C_stress",
                        genome=genome.name,
                        error=str(log_exc),
                        error_type=type(log_exc).__name__,
                    )
            except Exception as canonical_exc:
                # 想定外例外でも stress_payload / reasons は絶対変えない (= D1)
                logger.warning(
                    "stage_gate.canonical_five.unexpected_failure",
                    stage="C_stress",
                    genome=genome.name,
                    error=str(canonical_exc),
                    error_type=type(canonical_exc).__name__,
                )

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

    # === B Phase 2 step 1.8: cross_pair dual-path (= 別 try-finally で物理隔離 +
    # 常時 sanitize、 acceptance D1-D5 + E1-E6)。 cp_result 受け取り後・
    # cross_pair_payload 確定後に走る。 dual-path 経路の例外有無 / disabled mode /
    # sidecar 空 / pair_failure / cp_result is None 全分岐で finally 句の sanitize は
    # 常時実行される (= Codex detailed-review Round 1 [Critical 施策 5] 反映で
    # try-finally に強化) ===
    try:
        cp_result_local = cross_pair_payload.get("result")
        if (
            isinstance(cp_result_local, CrossPairResult)
            and not bool(cross_pair_payload["skipped"])
        ):
            sidecar_map: dict[str, _PairSidecarInputs] = (
                getattr(cp_result_local, "_shadow_sidecar_inputs", {}) or {}
            )
            cp_enabled = (
                stage_config.phase2_canonical_metrics_mode != "disabled"
            )
            # disabled mode 軽量分岐 (= per-pair iterate は走るが canonical 計算のみ
            # skip、 lightweight log を emit、 Codex detailed-review Round 1 + Round 3
            # [Warning 施策 5] 反映、 step 1.6 disabled mode と整合)
            if not cp_enabled:
                for pair_name in list(sidecar_map.keys()):
                    if not isinstance(pair_name, str) or not pair_name.strip():
                        logger.warning(
                            "stage_gate.canonical_five.invalid_pair_key",
                            stage="C_cross_pair",
                            genome=genome.name,
                            pair=repr(pair_name),
                        )
                        continue
                    try:
                        _log_canonical_dual_path(
                            stage_label="C_cross_pair",
                            genome_name=genome.name,
                            legacy=sidecar_map[pair_name].bt,
                            canonical=None,
                            pair_label=pair_name,
                        )
                    except Exception as log_exc:
                        logger.warning(
                            "stage_gate.canonical_five.log_failed",
                            stage="C_cross_pair",
                            genome=genome.name,
                            pair=pair_name,
                            error=str(log_exc),
                            error_type=type(log_exc).__name__,
                        )
            else:
                # enabled mode: per-pair canonical 計算 + log emit
                for pair_name, sidecar in sidecar_map.items():
                    # pair キー妥当性検証 (= Codex detailed-review Round 1
                    # [Warning 施策 5] 反映、 内部不整合の早期検出)
                    if not isinstance(pair_name, str) or not pair_name.strip():
                        logger.warning(
                            "stage_gate.canonical_five.invalid_pair_key",
                            stage="C_cross_pair",
                            genome=genome.name,
                            pair=repr(pair_name),
                        )
                        continue
                    try:
                        canonical_sidecar_cp = _try_evaluate_canonical_five_safe(
                            trades=sidecar.trades,
                            equity_curve=sidecar.equity_curve,
                            bars=sidecar.bars,
                            live_criteria=stage_config.live_criteria,
                            window_days=stage_config.stage_c_holdout_days,
                            stage_label="C_cross_pair",
                            genome_name=genome.name,
                            enabled=True,
                        )
                        try:
                            _log_canonical_dual_path(
                                stage_label="C_cross_pair",
                                genome_name=genome.name,
                                legacy=sidecar.bt,
                                canonical=canonical_sidecar_cp,
                                pair_label=pair_name,
                            )
                        except Exception as log_exc:
                            logger.warning(
                                "stage_gate.canonical_five.log_failed",
                                stage="C_cross_pair",
                                genome=genome.name,
                                pair=pair_name,
                                error=str(log_exc),
                                error_type=type(log_exc).__name__,
                            )
                    except Exception as canonical_exc:
                        logger.warning(
                            "stage_gate.canonical_five.unexpected_failure",
                            stage="C_cross_pair",
                            genome=genome.name,
                            pair=pair_name,
                            error=str(canonical_exc),
                            error_type=type(canonical_exc).__name__,
                        )
    finally:
        # === sanitize 経路 (= sidecar が payload / IPC / archive に絶対漏れない契約、
        # acceptance E1-E6、 詳細設計 § 2.4)。 dual-path 経路の例外有無 / 中断 /
        # disabled mode / pair_failure / cp_result is None / skipped 全分岐で常時実行
        # (= Codex detailed-review Round 1 [Critical 施策 5] 反映、 finally 保証) ===
        cp_result_for_sanitize = cross_pair_payload.get("result")
        if isinstance(cp_result_for_sanitize, CrossPairResult) and getattr(
            cp_result_for_sanitize, "_shadow_sidecar_inputs", None
        ):
            cross_pair_payload["result"] = replace(
                cp_result_for_sanitize, _shadow_sidecar_inputs={}
            )

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
