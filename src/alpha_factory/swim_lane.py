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

import time as _time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

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
        bars_18m: Stage B (WF-OOS Gate) 用 bars。
        bars_holdout: Stage C (Live Criteria + Stress) 用 holdout bars。
        meta: 通貨ペア meta 情報。``None`` は LaneManager 初期化で拒否される。
    """

    instrument: str = ""
    bars_60d: list[PriceBar] = field(default_factory=list)
    bars_18m: list[PriceBar] = field(default_factory=list)
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
        # 冪等性ガード: 二重昇格を in-memory set で抑止
        self._promoted_keys: set[tuple[str, int, str]] = set()
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

    def _run_tier1_generation(self, lane: Tier1Lane) -> dict[str, Any]:
        """Tier 1 lane の 1 世代を実行し、集計サマリーを返す。

        Args:
            lane: 評価対象 Tier1Lane (``state == "active"`` 前提)。

        Returns:
            集計サマリー (``wall_time_seconds`` は呼び出し側で埋める)。
        """
        assert lane.meta is not None  # constructor で validate 済み
        bt_cfg = self._bt_factory(lane.instrument)
        stage_a_pass = 0
        stage_b_pass = 0
        stage_c_pass = 0
        graduation_count = 0
        # T035: Stage B 入力窓充足契約 (lane 単位で 1 回のみ計算)
        lane_n_unique_dates = n_unique_dates(lane.bars_18m)
        wf_min_dates = wf_min_unique_dates(
            self._stage_gate_config.wf_train_days,
            self._stage_gate_config.wf_embargo_days,
            self._stage_gate_config.wf_test_days,
        )
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
            if not a_result.passed:
                continue
            stage_a_pass += 1
            # Stage B (T035: 観測日数充足検査 → underfilled なら skip-path)
            if lane_n_unique_dates < wf_min_dates:
                b_result = StageResult(
                    stage="B",
                    passed=False,
                    metrics={
                        "stage": "B",
                        "genome_name": genome.name,
                        "n_bars": len(lane.bars_18m),
                        "wall_time_seconds": 0.0,
                        "payload": {
                            "n_unique_dates": lane_n_unique_dates,
                            "wf_min_unique_dates": wf_min_dates,
                            "n_fold": 0,
                            "n_fold_unavailable": 0,
                            "n_fold_effective": 0,
                            "oos_sharpes": (),
                            "median_oos_sharpe": None,
                            "positive_fold_ratio": None,
                            "positive_fold_ratio_effective": None,
                            "dsr": None,
                            # 未評価を明示するため None
                            "is_full_sharpe": None,
                            "is_full_total_pnl": None,
                            "is_full_trade_count": None,
                        },
                    },
                    reason_codes=("stage_b_window_underfilled",),
                )
            else:
                b_result = evaluate_stage_b(
                    genome,
                    lane.bars_18m,
                    lane.meta,
                    bt_cfg,
                    self._primitive_evaluator,
                    self._stage_gate_config,
                )
            self._archive.collect_stage_b(
                genome,
                lane.lane_id,
                lane.generation_count,
                b_result,
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
        }
