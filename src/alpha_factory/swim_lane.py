"""Swim lane manager — Tier 1 + Graduation lane オーケストレーション (T017)。

Tier 1 (通貨ペア毎 1 lane) と Graduation lane (universal alpha 探索) を
一元管理し、Stage A → B → C → cross-pair (ii-lite) shadow → graduation
判定の orchestration と、archive (``GenomeArchive``) への 4 段伝搬
(Stage A/B/C collect + ``mark_graduated``) を担保する。

本 TODO の責務範囲 (Phase 2):
    - SwimLane / Tier1Lane / GraduationLane dataclass
    - LaneManager による lane 状態保持 + 1 generation の評価 orchestration
    - graduation 判定 + Tier1 → Graduation 移送 (冪等性ガード付き)
    - archive 4 段伝搬 (Stage A/B/C + mark_graduated)

責務外 (別 TODO):
    - GA の selection / crossover / mutation 世代生成 (run-ga-full-rewrite)
    - Graduation Lane の Stage 評価実体 (cross-pair 集約 fitness evaluator)
    - 多通貨 bars / meta のロード経路
    - 並列実行
    - YAML loader (``SwimLaneConfig``)

仕様根拠:
    - devnotes/20260423-2112-swim-lane-manager/conceptual-design.md
    - devnotes/20260423-2112-swim-lane-manager/detailed-design.md
    - devnotes/20260423-2112-swim-lane-manager/design-review-r2.md
    - docs/alpha_factory/swim-lane.md
    - docs/alpha_factory/stage-gates.md
    - docs/alpha_factory/cross-pair.md

学術引用:
    - López de Prado, M. (2018). Advances in Financial Machine Learning.
    - Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014).
      The Probability of Backtest Overfitting. J. Comp. Finance.
"""

from __future__ import annotations

import math
import numbers
import time as _time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
    from src.alpha_factory.parallel_eval import (
        GenomeEvaluator,
    )

import structlog

from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.cross_pair import (
    CrossPairConfig,
    StageCRunCrossPairEvaluator,
)
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    StageResult,
    evaluate_stage_a,
    evaluate_stage_b,
    evaluate_stage_c,
)
from src.alpha_factory.walk_forward import (
    compute_max_folds,
    n_unique_dates,
    wf_min_unique_dates,
)
from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import PrimitiveEvaluator

logger = structlog.get_logger(__name__)

__all__ = [
    "GRADUATION_INSTRUMENT_SENTINEL",
    "GRADUATION_LANE_ID",
    "GraduationLane",
    "LaneManager",
    "LaneStatus",
    "SwimLane",
    "Tier1Lane",
]


# ---------------------------------------------------------------------------
# Constants / Type aliases
# ---------------------------------------------------------------------------

LaneStatus = Literal["active", "converged", "paused"]
_LANE_STATUS_VALID: frozenset[str] = frozenset({"active", "converged", "paused"})

GRADUATION_LANE_ID = "graduation"
"""Graduation lane 固定 lane_id。"""

GRADUATION_INSTRUMENT_SENTINEL = "multi"
"""Graduation lane row の archive `instrument` カラム sentinel 値。
Run-GA 統合 TODO で archive row 生成時に使用する予約値。"""

# T081 step 1: AB pair 集約用 score_source annotation 規範
#
# `ab_score_source` 値は run 内で **不変** であること (= mixing 検出 RuntimeError、
# run_ga.py 経路で fail-fast)。 Phase 1 採用 = fitness_pen / median_oos_sharpe、
# 後続別 TODO で SSOT (compute_a_b_correlation_source_score) に統一する場合は
# 別 source 文字列を導入し新 Run で切替 (= 同 Run 内 mixing は禁止)。
AB_SCORE_SOURCE_PHASE1: Final[str] = "fitness_pen+median_oos_sharpe_phase1"
AB_SCORE_SOURCE_NOOP: Final[str] = "noop"


# ---------------------------------------------------------------------------
# Dataclass hierarchy
# ---------------------------------------------------------------------------


@dataclass
class SwimLane:
    """全 lane の共通基底。

    Attributes:
        lane_id: lane の一意識別子。Tier 1 では ``"tier1_{instrument}"``、
            Graduation では :data:`GRADUATION_LANE_ID`。
        population: 現世代の個体集合。``run_generation`` が in-place に各個体を
            評価する。
        generation_count: run_generation 完了回数 (active state 以外では
            インクリメントしない)。
        state: lane の稼働状態。state 遷移ロジックは本 TODO 範囲外。
    """

    lane_id: str
    population: list[Genome] = field(default_factory=list)
    generation_count: int = 0
    state: LaneStatus = "active"


@dataclass
class Tier1Lane(SwimLane):
    """1 通貨ペア固有 GA lane。

    Note:
        ``meta`` は dataclass デフォルト規約のため ``None`` 許容だが、
        :class:`LaneManager` 構築時に non-None を validate する。

    Attributes:
        instrument: 通貨ペア名 (例: ``"EUR_JPY"``)。``lane_id`` の suffix
            (``lane_id.removeprefix("tier1_")``) と一致必須。
        bars_60d: Stage A (Fast Screen) 用 bars。
        bars_stage_b: Stage B (WF-OOS Gate) 用 bars。
        bars_holdout: Stage C (Live Criteria + Stress) 用 holdout bars。
        meta: 通貨ペア meta 情報。``None`` は LaneManager 初期化で拒否される。
    """

    instrument: str = ""
    bars_60d: list[PriceBar] = field(default_factory=list)
    bars_stage_b: list[PriceBar] = field(default_factory=list)
    bars_holdout: list[PriceBar] = field(default_factory=list)
    meta: InstrumentMeta | None = None
    provenance: dict[str, tuple[str | None, str | None]] = field(
        default_factory=dict
    )
    """genome.name -> (parent_a, parent_b)。

    T018 追加: run_ga.py が世代生成時に populate し、LaneManager が
    ``collect_stage_a`` 呼び出しで ``parent_a`` / ``parent_b`` を archive に
    伝搬する。未設定 (default 空 dict) は T017 までの挙動と後方互換
    (parent_a=parent_b=None)。
    """


@dataclass
class GraduationLane(SwimLane):
    """Universal alpha 探索 lane。

    Phase 2 (本 TODO) では Stage 評価実体は未実装。Tier 1 lane の cross-pair
    adapter が参照する multi-pair データ SSOT としての役割と、graduation
    された個体の受け皿 (``seed_graduates``) を担う。

    Attributes:
        seed_graduates: Tier 1 から graduation された個体の append-only 履歴。
        pair_bars: 通貨ペア → bars dict。cross-pair shadow の入力 SSOT として
            Tier 1 lane と共有される。
        pair_meta: 通貨ペア → InstrumentMeta dict。同上。
    """

    seed_graduates: list[Genome] = field(default_factory=list)
    pair_bars: dict[str, list[PriceBar]] = field(default_factory=dict)
    pair_meta: dict[str, InstrumentMeta] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# LaneManager
# ---------------------------------------------------------------------------


class LaneManager:
    """Tier 1 × N + Graduation lane を一元管理する orchestrator (T017)。

    constructor 受け取り:
        - ``tier1``: ``dict[lane_id, Tier1Lane]``。**dict キーは lane_id**
          (``"tier1_{instrument}"`` 形式)。``get_all_lanes()[i].lane_id`` を
          そのまま ``run_generation(lane_id)`` に渡せる公開 API 一貫性を保つ。
        - ``graduation``: ``GraduationLane`` (``lane_id == GRADUATION_LANE_ID``)。
        - ``stage_gate_config`` / ``cross_pair_config``: 全 lane / 全 stage で共有。
        - ``primitive_evaluator``: state-less、全 lane 共通。
        - ``archive``: ``GenomeArchive`` (4 段伝搬先)。
        - ``backtest_config_factory``: instrument → BacktestConfig を生成する
          callable。intraday 絶対制約 (``session_close_utc_hours`` 非空) を
          満たす config を返すことが契約。初期化時に試走して validate する。
        - ``deferred_promotion`` (keyword only): 将来拡張用 flag。Phase 2 では
          未実装 (True 指定時に ``promote_graduates`` で
          ``NotImplementedError``)。

    絶対制約契約:
        本 lane manager は per-lane の Stage 評価を駆動するだけで、intraday
        強制クローズ・long/short・swap/spread 反映は backtest engine 側で
        担保される。``backtest_config_factory`` の試走 (``__init__``) で
        contract を最低限確認する (``session_close_utc_hours`` 非空)。
    """

    def __init__(
        self,
        tier1: dict[str, Tier1Lane],
        graduation: GraduationLane,
        stage_gate_config: StageGateConfig,
        cross_pair_config: CrossPairConfig,
        primitive_evaluator: PrimitiveEvaluator,
        archive: GenomeArchive,
        backtest_config_factory: Callable[[str], BacktestConfig],
        *,
        deferred_promotion: bool = False,
        diagnostics_collector: DiagnosticsCollector | None = None,
        genome_evaluator: GenomeEvaluator | None = None,
    ) -> None:
        if not tier1:
            raise ValueError(
                "tier1 must be non-empty (at least one Tier1Lane)"
            )
        for lane_id, lane in tier1.items():
            if not isinstance(lane, Tier1Lane):
                raise TypeError(
                    f"tier1[{lane_id!r}] must be Tier1Lane: "
                    f"got {type(lane).__name__}"
                )
            if lane.lane_id != lane_id:
                raise ValueError(
                    f"tier1[{lane_id!r}].lane_id mismatch: "
                    f"got {lane.lane_id!r}"
                )
            if not lane_id.startswith("tier1_"):
                raise ValueError(
                    f"tier1 key must start with 'tier1_': got {lane_id!r}"
                )
            expected_instrument = lane_id.removeprefix("tier1_")
            if not expected_instrument:
                raise ValueError(
                    f"tier1 key must have non-empty suffix after 'tier1_': "
                    f"got {lane_id!r}"
                )
            if lane.instrument != expected_instrument:
                raise ValueError(
                    f"tier1[{lane_id!r}].instrument must match suffix "
                    f"(expected {expected_instrument!r}, "
                    f"got {lane.instrument!r})"
                )
            if lane.meta is None:
                raise ValueError(
                    f"tier1[{lane_id!r}].meta must be non-None"
                )
            if lane.state not in _LANE_STATUS_VALID:
                raise ValueError(
                    f"tier1[{lane_id!r}].state invalid: {lane.state!r}"
                )
        if not isinstance(graduation, GraduationLane):
            raise TypeError(
                f"graduation must be GraduationLane: "
                f"got {type(graduation).__name__}"
            )
        if graduation.lane_id != GRADUATION_LANE_ID:
            raise ValueError(
                f"graduation.lane_id must be {GRADUATION_LANE_ID!r}: "
                f"got {graduation.lane_id!r}"
            )
        if graduation.state not in _LANE_STATUS_VALID:
            raise ValueError(
                f"graduation.state invalid: {graduation.state!r}"
            )

        self._tier1 = tier1
        self._graduation = graduation
        self._stage_gate_config = stage_gate_config
        self._cross_pair_config = cross_pair_config
        self._primitive_evaluator = primitive_evaluator
        self._archive = archive
        self._bt_factory = backtest_config_factory
        self._deferred_promotion = deferred_promotion
        # T033: post-RUN sidecar diagnostics 用 collector (optional)。
        # None なら record_* は no-op (production 経路の opt-in)。
        self._diagnostics: DiagnosticsCollector | None = diagnostics_collector
        # 冪等性ガード: 二重昇格を in-memory set で抑止
        self._promoted_keys: set[tuple[str, int, str]] = set()
        # T052: GenomeEvaluator (シーケンシャル/並列共通 API)。
        # None なら legacy 直列ループを使用 (後方互換、既存テスト通過)。
        self._genome_evaluator: GenomeEvaluator | None = genome_evaluator
        # health-check: factory が intraday 制約を満たすか確認
        self._validate_intraday_constraint(backtest_config_factory)

    # ------------------------------------------------------------------
    # Properties (read-only exposure)
    # ------------------------------------------------------------------

    @property
    def tier1(self) -> dict[str, Tier1Lane]:
        """Tier 1 lane dict (lane_id → Tier1Lane)。read-only view."""
        return self._tier1

    @property
    def graduation(self) -> GraduationLane:
        """Graduation lane。read-only reference."""
        return self._graduation

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_lanes(self) -> list[SwimLane]:
        """tier1 + graduation の全 lane を順序固定で返す。

        順序は ``tier1`` dict の挿入順 → graduation。呼び出し側 (Run-GA) が
        決定論的に lane 巡回できることを保証する。

        Returns:
            SwimLane list (Tier1Lane...., GraduationLane の順)。
        """
        return [*self._tier1.values(), self._graduation]

    def run_generation(self, lane_id: str) -> dict[str, Any]:
        """指定 lane に対して 1 世代を回す (Stage A → B → C + graduation 判定)。

        Tier 1 lane では、``population`` の各個体に対して次の処理を実行する:

            1. Stage A 評価 + ``archive.collect_stage_a`` (全個体)
            2. Stage A 通過時のみ Stage B 評価 + ``archive.collect_stage_b``
            3. Stage B 通過時のみ Stage C 評価 (cross-pair shadow 含む) +
               ``archive.collect_stage_c``
            4. Stage C 通過 + cross-pair 通過時に ``_mark_for_graduation``

        ``lane.state != "active"`` の場合は NoOp summary を返す
        (generation_count 非増分、archive 未更新)。

        Graduation lane (``lane_id == GRADUATION_LANE_ID``) は Phase 2 では
        ``NotImplementedError`` を raise する (別 TODO で実装)。

        Args:
            lane_id: Tier 1 では ``"tier1_{instrument}"``、Graduation では
                :data:`GRADUATION_LANE_ID`。

        Returns:
            集計サマリー dict:
                ``lane_id``, ``state``, ``n_evaluated``, ``stage_a_pass``,
                ``stage_b_pass``, ``stage_c_pass``, ``graduation_count``,
                ``wall_time_seconds``。

        Raises:
            KeyError: lane_id が tier1 dict に存在しない場合。
            NotImplementedError: Graduation lane 評価は Phase 2 未実装。
        """
        start = _time.perf_counter()
        if lane_id == GRADUATION_LANE_ID:
            raise NotImplementedError(
                "GraduationLane.run_generation is not implemented in Phase 2 "
                "(planned for run-ga-full-rewrite TODO)"
            )
        if lane_id not in self._tier1:
            raise KeyError(f"unknown lane_id: {lane_id!r}")
        lane = self._tier1[lane_id]
        if lane.state != "active":
            elapsed = _time.perf_counter() - start
            return self._noop_summary(lane, elapsed)
        summary = self._run_tier1_generation(lane)
        summary["wall_time_seconds"] = _time.perf_counter() - start
        return summary

    def graduation_criteria(
        self,
        individual: Genome,
        stage_c_result: StageResult,
        cross_pair_result: CrossPairResult | None,
    ) -> bool:
        """Graduation 判定: Stage C 通過 AND cross-pair 通過の AND。

        ``cross_pair_result`` が ``None`` (skipped / 例外 fallback) の場合は
        conservative に ``False``。Phase 2 では cross-pair shadow が provider
        未注入で 2 条件 AND (mean / min) 縮退となるが、本関数は
        ``cross_pair_result.passed`` の bool 値のみを参照するため Phase 4 で
        3 条件拡張時も変更不要。

        Args:
            individual: 評価対象 Genome (未使用だが signature 安定のため保持)。
            stage_c_result: Stage C 評価結果。
            cross_pair_result: cross-pair (ii-lite) 評価結果。``None`` なら
                skipped / 評価未実行扱い。

        Returns:
            両通過なら True、それ以外 False。
        """
        if not stage_c_result.passed:
            return False
        if cross_pair_result is None:
            return False
        return bool(cross_pair_result.passed)

    def promote_graduates(self) -> int:
        """累積 graduation 件数を返す (Phase 2 実装は counter getter)。

        Phase 2 では ``_mark_for_graduation`` が即時
        ``seed_graduates.append`` + ``archive.mark_graduated`` を行うため、
        本メソッドは追加の副作用を持たず累積件数の getter として動作する。

        ``deferred_promotion=True`` が指定された場合 (Phase 4 拡張用予約) は
        本 TODO では未実装のため ``NotImplementedError`` を raise する。

        Returns:
            累積 graduation 件数 (= ``len(graduation.seed_graduates)``)。

        Raises:
            NotImplementedError: ``deferred_promotion=True`` 指定時。
        """
        if self._deferred_promotion:
            raise NotImplementedError(
                "deferred_promotion mode is reserved for "
                "run-ga-full-rewrite TODO"
            )
        return len(self._graduation.seed_graduates)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_intraday_constraint(
        self, factory: Callable[[str], BacktestConfig]
    ) -> None:
        """``backtest_config_factory`` が intraday 絶対制約を満たすか試走検証。

        条件:
            1. factory の返り値が :class:`BacktestConfig` であること。
            2. ``session_close_utc_hours`` が非空 (engine 側 EOD 強制クローズ
               以前に hour 粒度強制クローズを担保)。
            3. ``holding_cost_per_day_bps`` が 0 以上 (swap proxy 反映の
               最低契約)。

        試走は副作用無し (``BacktestConfig`` は frozen dataclass)。失敗時は
        ``ValueError`` / ``TypeError`` を raise。
        """
        sample_lane_id = next(iter(self._tier1))
        sample_inst = sample_lane_id.removeprefix("tier1_")
        cfg = factory(sample_inst)
        if not isinstance(cfg, BacktestConfig):
            raise TypeError(
                f"backtest_config_factory must return BacktestConfig: "
                f"got {type(cfg).__name__}"
            )
        if not cfg.session_close_utc_hours:
            raise ValueError(
                "backtest_config_factory must return BacktestConfig with "
                "non-empty session_close_utc_hours (intraday absolute "
                "constraint)"
            )
        if cfg.holding_cost_per_day_bps < 0:
            raise ValueError(
                "backtest_config_factory returned BacktestConfig with "
                f"holding_cost_per_day_bps < 0: {cfg.holding_cost_per_day_bps}"
            )

    def _compute_preflight(self, lane: Tier1Lane) -> tuple[int, int, int, int, bool]:
        """T035 + T044 の preflight 値を返す共通関数 (legacy / evaluator 共通)。

        Returns:
            ``(lane_n_unique_dates, wf_min_dates, lane_max_folds,
              wf_min_folds, preflight_underfilled)``
        """
        lane_n_unique_dates = n_unique_dates(lane.bars_stage_b)
        wf_min_dates = wf_min_unique_dates(
            self._stage_gate_config.wf_train_days,
            self._stage_gate_config.wf_embargo_days,
            self._stage_gate_config.wf_test_days,
        )
        lane_max_folds = compute_max_folds(
            lane_n_unique_dates,
            self._stage_gate_config.wf_train_days,
            self._stage_gate_config.wf_embargo_days,
            self._stage_gate_config.wf_test_days,
            self._stage_gate_config.wf_step_days,
        )
        wf_min_folds = self._stage_gate_config.wf_min_folds_required
        return (
            lane_n_unique_dates,
            wf_min_dates,
            lane_max_folds,
            wf_min_folds,
            lane_max_folds < wf_min_folds,
        )

    def _build_preflight_b_result(
        self,
        genome: Genome,
        lane_n_unique_dates: int,
        wf_min_dates: int,
        lane_max_folds: int,
        wf_min_folds: int,
        n_bars: int,
    ) -> StageResult:
        """preflight_underfilled 時の偽 Stage B StageResult を組み立てる共通ファクトリ。

        legacy / evaluator 経路で重複実装を避けるため private method として集約。
        (T052 detailed-design §2 反映)
        """
        return StageResult(
            stage="B",
            passed=False,
            metrics={
                "stage": "B",
                "genome_name": genome.name,
                "n_bars": n_bars,
                "wall_time_seconds": 0.0,
                "payload": {
                    "n_unique_dates": lane_n_unique_dates,
                    "wf_min_unique_dates": wf_min_dates,
                    "max_folds": lane_max_folds,
                    "wf_min_folds_required": wf_min_folds,
                    "n_fold": 0,
                    "n_fold_unavailable": 0,
                    "n_fold_effective": 0,
                    "oos_sharpes": (),
                    "median_oos_sharpe": None,
                    "positive_fold_ratio": None,
                    "positive_fold_ratio_effective": None,
                    "dsr": None,
                    "is_full_sharpe": None,
                    "is_full_total_pnl": None,
                    "is_full_trade_count": None,
                },
            },
            reason_codes=("stage_b_pre_flight_underfilled",),
        )

    def _run_tier1_generation(self, lane: Tier1Lane) -> dict[str, Any]:
        """Tier 1 lane の 1 世代を実行し、集計サマリーを返す。

        T052: ``self._genome_evaluator`` が None なら legacy 直列ループ
        (後方互換)、non-None なら evaluator 経由 (in-process or 並列)。

        Args:
            lane: 評価対象 Tier1Lane (``state == "active"`` 前提)。

        Returns:
            集計サマリー (``wall_time_seconds`` は呼び出し側で埋める)。
        """
        if self._genome_evaluator is not None:
            return self._run_tier1_generation_via_evaluator(lane)
        return self._run_tier1_generation_legacy(lane)

    def _run_tier1_generation_legacy(self, lane: Tier1Lane) -> dict[str, Any]:
        """legacy 直列ループ (genome_evaluator=None 経路)。"""
        assert lane.meta is not None  # constructor で validate 済み
        bt_cfg = self._bt_factory(lane.instrument)
        stage_a_pass = 0
        stage_b_pass = 0
        stage_c_pass = 0
        graduation_count = 0
        # T081 step 1: AB pair 集約 (= ABDivergenceMetric 実値配線、 詳細設計 § 3.4.2)
        ab_score_pairs: list[tuple[float, float]] = []
        ab_b_evaluated_count = 0
        ab_excluded_preflight_count = 0
        # T035 + T044: preflight feasibility (lane 単位で 1 回のみ計算)
        (
            lane_n_unique_dates,
            wf_min_dates,
            lane_max_folds,
            wf_min_folds,
            preflight_underfilled,
        ) = self._compute_preflight(lane)
        for genome in lane.population:
            # Stage A
            a_result = evaluate_stage_a(
                genome,
                lane.bars_60d,
                lane.meta,
                bt_cfg,
                self._primitive_evaluator,
                self._stage_gate_config,
            )
            parent_a, parent_b = lane.provenance.get(
                genome.name, (None, None)
            )
            self._archive.collect_stage_a(
                genome,
                lane.lane_id,
                lane.generation_count,
                a_result,
                instrument=lane.instrument,
                parent_a=parent_a,
                parent_b=parent_b,
            )
            # T033: sidecar diagnostics に Stage A 結果を記録
            if self._diagnostics is not None:
                self._diagnostics.record_stage_a(
                    lane.lane_id,
                    lane.generation_count,
                    genome.name,
                    a_result,
                )
            if not a_result.passed:
                continue
            stage_a_pass += 1
            # Stage B feasibility check (T044 が T035 wf_min_unique_dates を superset)
            # `wf_min_folds_required >= 1` なら lane_n_unique_dates < wf_min_dates の
            # 場合は必ず lane_max_folds = 0 < min となり pre_flight が成立する。
            # T035 の wf_min_unique_dates 単独経路は dead branch のため削除。
            if preflight_underfilled:
                b_result = self._build_preflight_b_result(
                    genome,
                    lane_n_unique_dates,
                    wf_min_dates,
                    lane_max_folds,
                    wf_min_folds,
                    n_bars=len(lane.bars_stage_b),
                )
                # T081 step 1: preflight 個体は AB pair 収集対象外 (= 推定値で実
                # backtest を走らせていない)、 但し counter で可視化
                ab_excluded_preflight_count += 1
                should_collect_ab_pair = False
            else:
                b_result = evaluate_stage_b(
                    genome,
                    lane.bars_stage_b,
                    lane.meta,
                    bt_cfg,
                    self._primitive_evaluator,
                    self._stage_gate_config,
                )
                ab_b_evaluated_count += 1
                should_collect_ab_pair = True
            # T081 step 1: AB pair 収集 (= 既存 archive collect / diagnostics record の
            # 前で実施、 副作用なし、 早期 continue 禁止 = Codex Round 2 [Critical] 1 取込)
            if should_collect_ab_pair:
                self._collect_ab_pair(
                    a_result, b_result, ab_score_pairs
                )
            self._archive.collect_stage_b(
                genome,
                lane.lane_id,
                lane.generation_count,
                b_result,
            )
            # T033: sidecar diagnostics に Stage B pass/fail を記録
            if self._diagnostics is not None:
                self._diagnostics.record_stage_b(
                    lane.lane_id,
                    lane.generation_count,
                    genome.name,
                    bool(b_result.passed),
                )
            if not b_result.passed:
                continue
            stage_b_pass += 1
            # Stage C (cross-pair shadow を含む)
            cp_evaluator, cp_inputs = self._build_cross_pair_args(lane, genome)
            c_result = evaluate_stage_c(
                genome,
                lane.bars_holdout,
                lane.meta,
                bt_cfg,
                self._primitive_evaluator,
                self._stage_gate_config,
                cross_pair_evaluator=cp_evaluator,
                cross_pair_inputs=cp_inputs,
            )
            self._archive.collect_stage_c(
                genome,
                lane.lane_id,
                lane.generation_count,
                c_result,
            )
            # T033: sidecar diagnostics に Stage C pass/fail を記録
            if self._diagnostics is not None:
                self._diagnostics.record_stage_c(
                    lane.lane_id,
                    lane.generation_count,
                    genome.name,
                    bool(c_result.passed),
                )
            if c_result.passed:
                stage_c_pass += 1
            # Graduation 判定 (Stage C 通過 AND cross-pair 通過の AND)
            cp_result = self._extract_cross_pair_result(c_result)
            if self.graduation_criteria(genome, c_result, cp_result):
                promoted = self._mark_for_graduation(lane, genome)
                if promoted:
                    graduation_count += 1
        lane.generation_count += 1
        return {
            "lane_id": lane.lane_id,
            "state": lane.state,
            "n_evaluated": len(lane.population),
            "stage_a_pass": stage_a_pass,
            "stage_b_pass": stage_b_pass,
            "stage_c_pass": stage_c_pass,
            "graduation_count": graduation_count,
            # T081 step 1: ABDivergenceMetric 実値配線用必須キー (詳細設計 § 3.4.2)
            "ab_score_pairs": ab_score_pairs,
            "ab_score_source": AB_SCORE_SOURCE_PHASE1,
            "ab_b_evaluated_count": ab_b_evaluated_count,
            "ab_excluded_preflight_count": ab_excluded_preflight_count,
        }

    def _run_tier1_generation_via_evaluator(
        self, lane: Tier1Lane
    ) -> dict[str, Any]:
        """T052: GenomeEvaluator 経由の評価 + main 側 collect 経路。

        worker は副作用なしの純粋関数 evaluate_genome のみ実行。
        archive.collect_* / diagnostics.record_* / graduation 判定は main で
        **population 順に** 実施 (L2 row-order 決定論性保証)。

        世代番号スナップショットを冒頭で固定 (Round 1 detailed-review §3 反映)。
        """
        assert lane.meta is not None
        assert self._genome_evaluator is not None
        # Round 1 detailed-review §3: 世代番号スナップショット固定
        # collect ループ中に lane.generation_count を直接参照しない
        generation_index = lane.generation_count

        stage_a_pass = 0
        stage_b_pass = 0
        stage_c_pass = 0
        graduation_count = 0
        stage_a_seconds: list[float] = []
        stage_b_seconds: list[float] = []
        stage_c_seconds: list[float] = []
        # T081 step 1: AB pair 集約 (= legacy 経路と同じ契約、 詳細設計 § 3.4.2)
        ab_score_pairs: list[tuple[float, float]] = []
        ab_b_evaluated_count = 0
        ab_excluded_preflight_count = 0

        (
            lane_n_unique_dates,
            wf_min_dates,
            lane_max_folds,
            wf_min_folds,
            preflight_underfilled,
        ) = self._compute_preflight(lane)

        # 評価実行 (GenomeEvaluator が in-process / pool を抽象化)
        results = self._genome_evaluator.evaluate_population(
            lane.lane_id, generation_index, lane.population
        )

        # main 側で population 順に collect (L2 row-order 保証)
        for genome, r in zip(lane.population, results, strict=True):
            # Stage A 結果 (worker 例外時は fail-closed StageResult を組み立て)
            if r.error is not None and r.stage_a is None:
                a_result = StageResult(
                    stage="A",
                    passed=False,
                    metrics={
                        "stage": "A",
                        "genome_name": genome.name,
                        "n_bars": len(lane.bars_60d),
                        "wall_time_seconds": 0.0,
                        "payload": {
                            "worker_error_code": r.error.error_code,
                            "worker_error_message": r.error.fixed_message,
                        },
                    },
                    reason_codes=("worker_error",),
                )
            else:
                assert r.stage_a is not None  # 例外なしなら必ず stage_a あり
                a_result = r.stage_a
            parent_a, parent_b = lane.provenance.get(genome.name, (None, None))
            self._archive.collect_stage_a(
                genome,
                lane.lane_id,
                generation_index,
                a_result,
                instrument=lane.instrument,
                parent_a=parent_a,
                parent_b=parent_b,
            )
            if self._diagnostics is not None:
                self._diagnostics.record_stage_a(
                    lane.lane_id, generation_index, genome.name, a_result
                )
            wts = a_result.metrics.get("wall_time_seconds")
            if isinstance(wts, (int, float)):
                stage_a_seconds.append(float(wts))
            if not a_result.passed:
                continue
            stage_a_pass += 1

            # Stage B: preflight_underfilled なら main 側で偽結果生成
            should_collect_ab_pair = False
            if preflight_underfilled:
                b_result = self._build_preflight_b_result(
                    genome,
                    lane_n_unique_dates,
                    wf_min_dates,
                    lane_max_folds,
                    wf_min_folds,
                    n_bars=len(lane.bars_stage_b),
                )
                # T081 step 1: preflight 個体は AB pair 収集対象外
                ab_excluded_preflight_count += 1
            elif r.error is not None and r.stage_b is None:
                # Stage B で worker 例外 → fail-closed (= AB pair 収集対象外)
                b_result = StageResult(
                    stage="B",
                    passed=False,
                    metrics={
                        "stage": "B",
                        "genome_name": genome.name,
                        "n_bars": len(lane.bars_stage_b),
                        "wall_time_seconds": 0.0,
                        "payload": {
                            "worker_error_code": r.error.error_code,
                            "worker_error_message": r.error.fixed_message,
                        },
                    },
                    reason_codes=("worker_error",),
                )
            elif r.stage_b is None:
                # Stage A pass / preflight OK / stage_b なし = 想定外
                # (起こり得るのは worker error のみで上で処理済)
                continue
            else:
                b_result = r.stage_b
                ab_b_evaluated_count += 1
                should_collect_ab_pair = True
            # T081 step 1: AB pair 収集 (= 既存処理の前で実施、 副作用なし)
            if should_collect_ab_pair:
                self._collect_ab_pair(
                    a_result, b_result, ab_score_pairs
                )
            self._archive.collect_stage_b(
                genome, lane.lane_id, generation_index, b_result
            )
            if self._diagnostics is not None:
                self._diagnostics.record_stage_b(
                    lane.lane_id,
                    generation_index,
                    genome.name,
                    bool(b_result.passed),
                )
            wts_b = b_result.metrics.get("wall_time_seconds")
            if isinstance(wts_b, (int, float)):
                stage_b_seconds.append(float(wts_b))
            if not b_result.passed:
                continue
            stage_b_pass += 1

            # Stage C
            if r.error is not None and r.stage_c is None:
                c_result = StageResult(
                    stage="C",
                    passed=False,
                    metrics={
                        "stage": "C",
                        "genome_name": genome.name,
                        "n_bars": len(lane.bars_holdout),
                        "wall_time_seconds": 0.0,
                        "payload": {
                            "worker_error_code": r.error.error_code,
                            "worker_error_message": r.error.fixed_message,
                        },
                    },
                    reason_codes=("worker_error",),
                )
            elif r.stage_c is None:
                continue
            else:
                c_result = r.stage_c
            self._archive.collect_stage_c(
                genome, lane.lane_id, generation_index, c_result
            )
            if self._diagnostics is not None:
                self._diagnostics.record_stage_c(
                    lane.lane_id,
                    generation_index,
                    genome.name,
                    bool(c_result.passed),
                )
            wts_c = c_result.metrics.get("wall_time_seconds")
            if isinstance(wts_c, (int, float)):
                stage_c_seconds.append(float(wts_c))
            if c_result.passed:
                stage_c_pass += 1
            # Graduation 判定
            cp_result = self._extract_cross_pair_result(c_result)
            if self.graduation_criteria(genome, c_result, cp_result):
                promoted = self._mark_for_graduation(lane, genome)
                if promoted:
                    graduation_count += 1
        lane.generation_count += 1
        return {
            "lane_id": lane.lane_id,
            "state": lane.state,
            "n_evaluated": len(lane.population),
            "stage_a_pass": stage_a_pass,
            "stage_b_pass": stage_b_pass,
            "stage_c_pass": stage_c_pass,
            "graduation_count": graduation_count,
            # T052: stage 別 timing 集計 (sum + max 併記)
            "stage_a_seconds_total": sum(stage_a_seconds),
            "stage_a_seconds_max": max(stage_a_seconds, default=0.0),
            "stage_b_seconds_total": sum(stage_b_seconds),
            "stage_b_seconds_max": max(stage_b_seconds, default=0.0),
            "stage_c_seconds_total": sum(stage_c_seconds),
            "stage_c_seconds_max": max(stage_c_seconds, default=0.0),
            # T081 step 1: ABDivergenceMetric 実値配線用必須キー (詳細設計 § 3.4.2)
            "ab_score_pairs": ab_score_pairs,
            "ab_score_source": AB_SCORE_SOURCE_PHASE1,
            "ab_b_evaluated_count": ab_b_evaluated_count,
            "ab_excluded_preflight_count": ab_excluded_preflight_count,
        }

    def _build_cross_pair_args(
        self, lane: SwimLane, genome: Genome
    ) -> tuple[StageCRunCrossPairEvaluator | None, dict[str, Any] | None]:
        """Tier 1 lane 用 cross-pair adapter と inputs を組み立てる。

        graduation lane から呼ばれるケース (Phase 2 では到達しない) や、
        ``graduation.pair_bars`` が未注入・当該 instrument を含まない場合は
        ``(None, None)`` を返す。``(None, None)`` が返ると Stage C は cross-pair
        shadow を ``skipped`` 扱いで payload に記録する (T014 契約)。

        Returns:
            (evaluator or None, inputs dict or None)
        """
        if not isinstance(lane, Tier1Lane):
            return None, None
        pair_bars = self._graduation.pair_bars
        pair_meta = self._graduation.pair_meta
        if not pair_bars or lane.instrument not in pair_bars:
            return None, None
        cp_evaluator = StageCRunCrossPairEvaluator(
            primitive_evaluator=self._primitive_evaluator,
            cross_pair_config=self._cross_pair_config,
        )
        cp_inputs: dict[str, Any] = {
            "target_pair": lane.instrument,
            "pair_bars_map": pair_bars,
            "meta_map": pair_meta,
        }
        return cp_evaluator, cp_inputs

    @staticmethod
    def _extract_cross_pair_result(
        stage_c_result: StageResult,
    ) -> CrossPairResult | None:
        """Stage C result の payload から :class:`CrossPairResult` を取り出す。

        payload.cross_pair が欠落 / skipped / ``result`` が None / 型不一致の
        いずれかなら ``None`` を返す (graduation_criteria 側で保守的 False)。

        archive 側の ``_extract_cross_pair`` とロジックは同等だが、archive
        内部 helper は公開 API ではないため、本モジュールで独自実装する
        (重複は許容、公開 API 化は別 TODO)。
        """
        payload_obj = stage_c_result.metrics.get("payload")
        if not isinstance(payload_obj, Mapping):
            return None
        cp_obj = payload_obj.get("cross_pair")
        if not isinstance(cp_obj, Mapping):
            return None
        if bool(cp_obj.get("skipped", True)):
            return None
        result_obj = cp_obj.get("result")
        if isinstance(result_obj, CrossPairResult):
            return result_obj
        return None

    def _mark_for_graduation(
        self, lane: Tier1Lane, genome: Genome
    ) -> bool:
        """個体を Graduation lane に昇格する (冪等性ガード付き)。

        key ``(lane_id, generation_count, genome.name)`` が既昇格なら skip +
        WARN ログ。新規なら seed_graduates に append + archive.mark_graduated
        を呼ぶ。

        Returns:
            新規昇格なら True、既昇格 (skip) なら False。
        """
        key = (lane.lane_id, lane.generation_count, genome.name)
        if key in self._promoted_keys:
            logger.warning(
                "swim_lane.graduation_duplicate_skipped",
                lane_id=lane.lane_id,
                generation=lane.generation_count,
                individual_name=genome.name,
            )
            return False
        self._promoted_keys.add(key)
        self._graduation.seed_graduates.append(genome)
        self._archive.mark_graduated(
            lane.lane_id, lane.generation_count, genome.name
        )
        return True

    @staticmethod
    def _noop_summary(lane: SwimLane, elapsed: float) -> dict[str, Any]:
        """state != "active" lane 用の no-op summary (契約仕様 §4.10)."""
        return {
            "lane_id": lane.lane_id,
            "state": lane.state,
            "n_evaluated": 0,
            "stage_a_pass": 0,
            "stage_b_pass": 0,
            "stage_c_pass": 0,
            "graduation_count": 0,
            "wall_time_seconds": elapsed,
            # T081 step 1: ABDivergenceMetric 実値配線用必須キー (= noop は空 + "noop" source)
            "ab_score_pairs": [],
            "ab_score_source": AB_SCORE_SOURCE_NOOP,
            "ab_b_evaluated_count": 0,
            "ab_excluded_preflight_count": 0,
        }

    @staticmethod
    def _collect_ab_pair(
        a_result: StageResult,
        b_result: StageResult,
        ab_score_pairs: list[tuple[float, float]],
    ) -> None:
        """T081 step 1: AB pair (a_score, b_score) を集約 list に append.

        Phase 1 score source (詳細設計 § 3.3 / § 3.4.2):
            - a_proxy_score = a_result.metrics["payload"]["fitness_pen"]
            - b_pooled_score = b_result.metrics["payload"]["median_oos_sharpe"]

        非数値型 / NaN / Inf / None は skip (Codex Round 2 [Suggestion] 4 +
        Round 3 [Warning] 1 取込: numbers.Real ガード、 bool 除外で
        numpy.float32 / numpy.int64 等も covered)。
        """
        a_payload = a_result.metrics.get("payload", {})
        b_payload = b_result.metrics.get("payload", {})
        if not isinstance(a_payload, Mapping) or not isinstance(
            b_payload, Mapping
        ):
            return
        a_score = a_payload.get("fitness_pen")
        b_score = b_payload.get("median_oos_sharpe")
        if (
            isinstance(a_score, numbers.Real)
            and not isinstance(a_score, bool)
            and isinstance(b_score, numbers.Real)
            and not isinstance(b_score, bool)
            and math.isfinite(float(a_score))
            and math.isfinite(float(b_score))
        ):
            ab_score_pairs.append((float(a_score), float(b_score)))
