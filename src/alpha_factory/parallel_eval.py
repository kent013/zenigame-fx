"""GA 評価の並列化レイヤ (T052)。

二層構造:
- evaluation 層: ``evaluate_genome`` (genome → :class:`GenomeStageResult`,
  純粋関数、副作用なし)
- task transport 層: :class:`GenomeEvaluator` (Pool 起動・寿命管理、
  in-process / multiprocessing.Pool 切替)

決定論性契約:
- L1 selection: ``cache[name].fitness_pen`` / ``best_name`` /
  ``live_criteria_passed`` が worker 数に依存しない
- L2 row-order: archive Parquet の数値 column が
  ``(lane_id, generation, genome_name)`` ソート下で一致
- L3 artifact bit equivalence: 非保証 (timestamp 系 field を含むため)

設計根拠: devnotes/20260427-1114-ga-parallel-workers/
"""

from __future__ import annotations

import logging
import multiprocessing
import multiprocessing.pool
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

from src.alpha_factory.aux_loader import AlignedAuxBundle, AuxAlignmentCache, AuxBundle
from src.alpha_factory.cross_pair import (
    CrossPairConfig,
    StageCRunCrossPairEvaluator,
)
from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    StageResult,
    evaluate_stage_a,
    evaluate_stage_b,
    evaluate_stage_c,
)
from src.backtest.engine import BacktestConfig
from src.broker import InstrumentMeta
from src.domain.price import PriceBar
from src.dsl.genome import Genome

__all__ = [
    "CrossPairLaneInputs",
    "GenomeEvalError",
    "GenomeEvaluator",
    "GenomeStageResult",
    "LaneEvalContext",
    "PreflightPayload",
    "evaluate_genome",
    "measure_peak_rss_mb",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass hierarchy (worker ↔ main 間で送受される pickle 可能型)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreflightPayload:
    """Stage B preflight (fold 不足) 時の偽 StageResult 用 snapshot 値。

    RUN 中 immutable (フィールドは int のみで深い不変性は自然に成立)。
    """

    n_unique_dates: int
    wf_min_unique_dates: int
    max_folds: int
    wf_min_folds_required: int
    n_bars: int


@dataclass(frozen=True)
class CrossPairLaneInputs:
    """cross-pair (ii-lite) 評価用入力。Phase 2 default では None で常に skip。

    深い不変性確保:
        - 入力 dict を defensive copy
        - pair_bars_map の value (list[PriceBar]) を tuple 化
        - MappingProxyType wrap (キー追加/削除を防ぐ)
        - MappingProxyType は Python 3.13 で pickle 非互換のため
          ``__getstate__`` / ``__setstate__`` で dict ↔ mappingproxy 変換
    """

    target_pair: str
    pair_bars_map: Mapping[str, tuple[PriceBar, ...]]
    meta_map: Mapping[str, InstrumentMeta]

    def __post_init__(self) -> None:
        frozen_pair_bars = MappingProxyType(
            {k: tuple(v) for k, v in self.pair_bars_map.items()}
        )
        frozen_meta = MappingProxyType(dict(self.meta_map))
        object.__setattr__(self, "pair_bars_map", frozen_pair_bars)
        object.__setattr__(self, "meta_map", frozen_meta)

    def __getstate__(self) -> dict[str, Any]:
        return {
            "target_pair": self.target_pair,
            "pair_bars_map": dict(self.pair_bars_map),
            "meta_map": dict(self.meta_map),
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        object.__setattr__(self, "target_pair", state["target_pair"])
        object.__setattr__(
            self,
            "pair_bars_map",
            MappingProxyType(
                {k: tuple(v) for k, v in state["pair_bars_map"].items()}
            ),
        )
        object.__setattr__(
            self,
            "meta_map",
            MappingProxyType(dict(state["meta_map"])),
        )


@dataclass(frozen=True)
class LaneEvalContext:
    """RUN 中 immutable な lane 評価用コンテキスト。

    Pool initializer 経由で worker に配布。Pool 寿命中は不変。

    深い不変性:
        - bars_* は tuple 化 (PriceBar 自体も frozen dataclass)
        - cp_inputs / preflight_payload は専用 frozen dataclass
        - ``__post_init__`` では assert ではなく ``raise TypeError`` で
          型を強制 (``python -O`` で無効化されない)
    """

    lane_id: str
    bars_a: tuple[PriceBar, ...]
    bars_b: tuple[PriceBar, ...]
    bars_holdout: tuple[PriceBar, ...]
    meta: InstrumentMeta
    bt_cfg: BacktestConfig
    cp_inputs: CrossPairLaneInputs | None = None
    preflight_underfilled: bool = False
    preflight_payload: PreflightPayload | None = None
    # T057 Phase 2 Gate B: aux 生データ。各 stage で AlignedAuxBundle に展開して
    # primitive_evaluator に注入する。Pool initargs 経由で worker に broadcast.
    aux_bundle: AuxBundle | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.bars_a, tuple):
            raise TypeError(
                f"LaneEvalContext.bars_a must be tuple: "
                f"got {type(self.bars_a).__name__}"
            )
        if not isinstance(self.bars_b, tuple):
            raise TypeError(
                f"LaneEvalContext.bars_b must be tuple: "
                f"got {type(self.bars_b).__name__}"
            )
        if not isinstance(self.bars_holdout, tuple):
            raise TypeError(
                f"LaneEvalContext.bars_holdout must be tuple: "
                f"got {type(self.bars_holdout).__name__}"
            )
        if self.cp_inputs is not None and not isinstance(
            self.cp_inputs, CrossPairLaneInputs
        ):
            raise TypeError(
                "LaneEvalContext.cp_inputs must be CrossPairLaneInputs or None: "
                f"got {type(self.cp_inputs).__name__}"
            )
        if self.preflight_underfilled and self.preflight_payload is None:
            raise ValueError(
                "preflight_payload must be set when preflight_underfilled=True"
            )
        if self.preflight_payload is not None and not isinstance(
            self.preflight_payload, PreflightPayload
        ):
            raise TypeError(
                "LaneEvalContext.preflight_payload must be PreflightPayload: "
                f"got {type(self.preflight_payload).__name__}"
            )


@dataclass(frozen=True)
class GenomeEvalError:
    """worker 例外を deterministic な構造体に正規化する。

    生 traceback は worker logger 専用。artifact には含めない (L1/L2 維持)。
    """

    stage: Literal["A", "B", "C"]
    error_code: str
    fixed_message: str


@dataclass(frozen=True)
class GenomeStageResult:
    """1 個体の Stage A/B/C 評価結果。

    早期 return:
        - Stage A fail → stage_b/c は None
        - preflight_underfilled → stage_b/c は None (main 側で偽結果生成)
        - Stage B fail → stage_c は None
        - 例外 → ``error`` non-None、stage_a 以降は呼ばれた段階まで保持
    """

    genome_name: str
    stage_a: StageResult | None
    stage_b: StageResult | None
    stage_c: StageResult | None
    cross_pair: CrossPairResult | None
    error: GenomeEvalError | None = None


# ---------------------------------------------------------------------------
# Evaluation 層 (純粋関数)
# ---------------------------------------------------------------------------


# T057 Phase 2 Gate B: process-local aux alignment cache (key = LaneEvalContext id).
# 同 ctx 内では bars_a/b/holdout の identity が stable なので id(bars) ベースで
# 再利用可能。worker process が複数 ctx を扱う場合 (現状 lane 1 個前提) も問題なし。
_PROC_AUX_CACHE: dict[int, AuxAlignmentCache] = {}


def _get_aligned_for_stage(
    ctx: LaneEvalContext, bars: tuple[PriceBar, ...]
) -> AlignedAuxBundle | None:
    """ctx.aux_bundle が None でない場合に bars に align された bundle を返す.

    process-local cache で同じ bars (identity 一致) には 1 回しか展開しない.
    """
    if ctx.aux_bundle is None:
        return None
    cache_key = id(ctx.aux_bundle)
    cache = _PROC_AUX_CACHE.get(cache_key)
    if cache is None:
        cache = AuxAlignmentCache(ctx.aux_bundle)
        _PROC_AUX_CACHE[cache_key] = cache
    return cache.get(bars)


def _evaluator_for_stage(
    base: RegistryEvaluator,
    ctx: LaneEvalContext,
    bars: tuple[PriceBar, ...],
) -> RegistryEvaluator:
    """ctx.aux_bundle がある場合に bars に align された aux を注入した evaluator を返す."""
    aligned = _get_aligned_for_stage(ctx, bars)
    if aligned is None:
        return base
    return base.with_aux(**aligned.as_evaluator_kwargs())


def evaluate_genome(
    genome: Genome,
    ctx: LaneEvalContext,
    stage_gate_cfg: StageGateConfig,
    cross_pair_cfg: CrossPairConfig,
    primitive_evaluator: RegistryEvaluator,
) -> GenomeStageResult:
    """1 個体の Stage A → B → C 評価を実行する純粋関数。

    副作用なし。``archive.collect_*`` / ``diagnostics.record_*`` は main
    process 側で行う。

    T057 Phase 2: ``ctx.aux_bundle`` が non-None の場合、各 stage の bars に
    align された AlignedAuxBundle を注入した evaluator で評価する.

    短絡条件:
        - Stage A fail → 早期 return
        - preflight_underfilled → 早期 return (main 側で偽 Stage B 生成)
        - Stage B fail → 早期 return
    """
    ev_a = _evaluator_for_stage(primitive_evaluator, ctx, ctx.bars_a)
    try:
        a_result = evaluate_stage_a(
            genome,
            list(ctx.bars_a),
            ctx.meta,
            ctx.bt_cfg,
            ev_a,
            stage_gate_cfg,
        )
    except Exception as exc:
        return _to_error_result(genome.name, "A", exc)
    if not a_result.passed:
        return GenomeStageResult(
            genome_name=genome.name,
            stage_a=a_result,
            stage_b=None,
            stage_c=None,
            cross_pair=None,
        )

    if ctx.preflight_underfilled:
        return GenomeStageResult(
            genome_name=genome.name,
            stage_a=a_result,
            stage_b=None,
            stage_c=None,
            cross_pair=None,
        )

    ev_b = _evaluator_for_stage(primitive_evaluator, ctx, ctx.bars_b)
    try:
        b_result = evaluate_stage_b(
            genome,
            list(ctx.bars_b),
            ctx.meta,
            ctx.bt_cfg,
            ev_b,
            stage_gate_cfg,
        )
    except Exception as exc:
        return _to_error_result(genome.name, "B", exc, stage_a=a_result)
    if not b_result.passed:
        return GenomeStageResult(
            genome_name=genome.name,
            stage_a=a_result,
            stage_b=b_result,
            stage_c=None,
            cross_pair=None,
        )

    ev_c = _evaluator_for_stage(primitive_evaluator, ctx, ctx.bars_holdout)
    cp_evaluator: StageCRunCrossPairEvaluator | None = None
    cp_inputs_dict: dict[str, Any] | None = None
    if ctx.cp_inputs is not None:
        cp_evaluator = StageCRunCrossPairEvaluator(
            primitive_evaluator=ev_c,
            cross_pair_config=cross_pair_cfg,
        )
        cp_inputs_dict = {
            "target_pair": ctx.cp_inputs.target_pair,
            "pair_bars_map": {
                k: list(v) for k, v in ctx.cp_inputs.pair_bars_map.items()
            },
            "meta_map": dict(ctx.cp_inputs.meta_map),
        }
    try:
        c_result = evaluate_stage_c(
            genome,
            list(ctx.bars_holdout),
            ctx.meta,
            ctx.bt_cfg,
            ev_c,
            stage_gate_cfg,
            cross_pair_evaluator=cp_evaluator,
            cross_pair_inputs=cp_inputs_dict,
        )
    except Exception as exc:
        return _to_error_result(
            genome.name, "C", exc, stage_a=a_result, stage_b=b_result
        )

    cp_result = _extract_cross_pair_result(c_result)
    return GenomeStageResult(
        genome_name=genome.name,
        stage_a=a_result,
        stage_b=b_result,
        stage_c=c_result,
        cross_pair=cp_result,
    )


def _extract_cross_pair_result(stage_c: StageResult) -> CrossPairResult | None:
    """Stage C payload から CrossPairResult を取り出す。

    skipped / 型不一致なら None。``swim_lane.LaneManager._extract_cross_pair_result``
    と同等のロジック (重複は許容、公開 API 化は別 TODO)。
    """
    payload_obj = stage_c.metrics.get("payload")
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


# ---------------------------------------------------------------------------
# 例外正規化決定表
# ---------------------------------------------------------------------------


def _classify_exception(
    exc: BaseException, stage: Literal["A", "B", "C"]
) -> GenomeEvalError:
    """例外を (error_code, fixed_message) に正規化する。

    型ベース判定を優先し、文字列 substring 判定は最終フォールバック。
    KeyboardInterrupt / SystemExit は正規化せず再 raise (caller 責務)。

    Worker で発生しうる例外集合:
        - 数値計算系: numpy.linalg.LinAlgError, MemoryError
        - DSL/primitive 系: RuntimeError ("primitive" in msg)
        - Stage B fold 系: ValueError ("stage_b" / "wf" in msg)
        - 制御系: KeyboardInterrupt / SystemExit (再 raise)
        - その他 → WORKER_UNCLASSIFIED

    到達不能と想定する例外 (worker 責務外):
        - pyarrow.lib.ArrowInvalid: archive Parquet 書込は main 専用
        - pandas.errors.EmptyDataError: bars は main で DB ロード済
        - sqlalchemy.exc.*: DB 接続も main 専用
        万一発生時は WORKER_UNCLASSIFIED に集約され、test で fallback 確認。
    """
    import numpy as np

    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc
    if isinstance(exc, np.linalg.LinAlgError):
        return GenomeEvalError(
            stage, "BACKTEST_LINALG_ERROR", "linalg numerical error"
        )
    if isinstance(exc, MemoryError):
        return GenomeEvalError(stage, "WORKER_OOM", "worker out of memory")
    msg = str(exc).lower()
    if isinstance(exc, RuntimeError) and "primitive" in msg:
        return GenomeEvalError(
            stage, "PRIMITIVE_LOOKUP_FAIL", "primitive registry lookup failed"
        )
    if (
        isinstance(exc, ValueError)
        and stage == "B"
        and ("stage_b" in msg or "wf" in msg)
    ):
        return GenomeEvalError(
            stage, "STAGE_B_FOLD_INVALID", "walk-forward fold invalid"
        )
    return GenomeEvalError(
        stage, "WORKER_UNCLASSIFIED", "unclassified worker exception"
    )


def _to_error_result(
    genome_name: str,
    stage: Literal["A", "B", "C"],
    exc: BaseException,
    *,
    stage_a: StageResult | None = None,
    stage_b: StageResult | None = None,
) -> GenomeStageResult:
    """例外を GenomeStageResult.error に格納。生 traceback は logger に WARNING."""
    err = _classify_exception(exc, stage)
    logger.warning(
        "parallel_eval.worker_exception stage=%s genome=%s code=%s err=%s",
        stage,
        genome_name,
        err.error_code,
        type(exc).__name__,
    )
    return GenomeStageResult(
        genome_name=genome_name,
        stage_a=stage_a,
        stage_b=stage_b,
        stage_c=None,
        cross_pair=None,
        error=err,
    )


# ---------------------------------------------------------------------------
# Task transport 層
# ---------------------------------------------------------------------------


# Worker module-global (Pool initializer で 1 度だけ書込、以後 immutable 扱い)
_WORKER_STAGE_GATE_CFG: StageGateConfig | None = None
_WORKER_CROSS_PAIR_CFG: CrossPairConfig | None = None
_WORKER_PRIM_EVALUATOR: RegistryEvaluator | None = None
_WORKER_LANE_CONTEXTS: dict[str, LaneEvalContext] = {}


def _init_worker(
    stage_gate_cfg: StageGateConfig,
    cross_pair_cfg: CrossPairConfig,
    prim_evaluator: RegistryEvaluator,
    lane_contexts: dict[str, LaneEvalContext],
) -> None:
    """Pool initializer。spawn された worker process で 1 度だけ呼ばれる。

    primitive registry を ``ensure_registered()`` で再構築 (spawn 経由で
    module-global が空のため必須)。
    """
    global _WORKER_STAGE_GATE_CFG, _WORKER_CROSS_PAIR_CFG
    global _WORKER_PRIM_EVALUATOR, _WORKER_LANE_CONTEXTS
    ensure_registered()
    _WORKER_STAGE_GATE_CFG = stage_gate_cfg
    _WORKER_CROSS_PAIR_CFG = cross_pair_cfg
    _WORKER_PRIM_EVALUATOR = prim_evaluator
    _WORKER_LANE_CONTEXTS = lane_contexts


def _eval_genome_worker(
    args: tuple[str, int, Genome],
) -> GenomeStageResult:
    """worker entrypoint。args = (lane_id, generation, genome)."""
    lane_id, _generation, genome = args
    if (
        _WORKER_STAGE_GATE_CFG is None
        or _WORKER_CROSS_PAIR_CFG is None
        or _WORKER_PRIM_EVALUATOR is None
    ):
        raise RuntimeError(
            "_eval_genome_worker called before _init_worker (invariant violation)"
        )
    ctx = _WORKER_LANE_CONTEXTS[lane_id]
    return evaluate_genome(
        genome,
        ctx,
        _WORKER_STAGE_GATE_CFG,
        _WORKER_CROSS_PAIR_CFG,
        _WORKER_PRIM_EVALUATOR,
    )


class GenomeEvaluator:
    """LaneManager から呼ばれる evaluator API (シーケンシャル/並列共通)。

    寿命管理は context manager (``with`` 文) で行う:
        - 正常終了: ``pool.close()`` + ``pool.join()`` (graceful)
        - 異常終了 (例外伝播): ``pool.terminate()`` + ``pool.join()``
    """

    def __init__(
        self,
        max_workers: int,
        stage_gate_cfg: StageGateConfig,
        cross_pair_cfg: CrossPairConfig,
        prim_evaluator: RegistryEvaluator,
        lane_contexts: Mapping[str, LaneEvalContext],
    ) -> None:
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1: {max_workers}")
        self._max_workers = max_workers
        self._stage_gate_cfg = stage_gate_cfg
        self._cross_pair_cfg = cross_pair_cfg
        self._prim_evaluator = prim_evaluator
        # 内部 storage は plain dict (defensive copy 済)。
        # 外部公開しないため MappingProxyType wrap は不要 (pickle 互換優先)。
        self._lane_contexts: dict[str, LaneEvalContext] = dict(lane_contexts)
        self._pool: multiprocessing.pool.Pool | None = None
        self._closed = False

        if max_workers > 1:
            mp_ctx = multiprocessing.get_context("spawn")
            self._pool = mp_ctx.Pool(
                processes=max_workers,
                initializer=_init_worker,
                initargs=(
                    stage_gate_cfg,
                    cross_pair_cfg,
                    prim_evaluator,
                    dict(self._lane_contexts),
                ),
            )

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def pool_pids(self) -> set[int]:
        """worker process pid を **getter 呼び出し時点で動的取得**。

        ``multiprocessing.pool.Pool._pool`` は CPython private API。
        将来変更されるリスクに備え、AttributeError 捕捉で空集合返却 + warning。
        """
        if self._pool is None:
            return set()
        try:
            internal = self._pool._pool  # type: ignore[attr-defined]
            return {p.pid for p in internal if p.pid is not None}
        except AttributeError:
            logger.warning(
                "parallel_eval.pool_pids_unavailable: "
                "multiprocessing.pool.Pool._pool not accessible, "
                "falling back to all_children_* metrics"
            )
            return set()

    def evaluate_population(
        self,
        lane_id: str,
        generation: int,
        population: Sequence[Genome],
    ) -> list[GenomeStageResult]:
        """評価結果を **population 順** で返す (L2 row-order の根拠)."""
        if self._closed:
            raise RuntimeError("GenomeEvaluator is already closed")
        args = [(lane_id, generation, g) for g in population]
        if self._pool is None:
            ctx = self._lane_contexts[lane_id]
            return [
                evaluate_genome(
                    g,
                    ctx,
                    self._stage_gate_cfg,
                    self._cross_pair_cfg,
                    self._prim_evaluator,
                )
                for g in population
            ]
        return self._pool.map(_eval_genome_worker, args)

    def __enter__(self) -> GenomeEvaluator:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        self.close(errored=exc_type is not None)

    def close(self, errored: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if self._pool is None:
            return
        if errored:
            self._pool.terminate()
        else:
            self._pool.close()
        self._pool.join()


# ---------------------------------------------------------------------------
# Memory observability
# ---------------------------------------------------------------------------


def measure_peak_rss_mb(pool_pids: set[int] | None = None) -> dict[str, float]:
    """main + (指定 pool worker のみの) RSS を記録。

    ``pool_pids`` を指定すると ``ga_worker_*`` 指標として絞り込める。
    指定なしなら ``all_children_*`` 指標として全 children を集計
    (worker 以外の子プロセスも含む)。

    Returns:
        ``main_rss_mb`` / ``ga_worker_max_rss_mb`` / ``ga_worker_total_rss_mb``
        / ``n_ga_workers`` / ``all_children_max_rss_mb`` /
        ``all_children_total_rss_mb`` / ``n_all_children``
    """
    try:
        import psutil
    except ImportError:
        logger.warning("parallel_eval.psutil_unavailable")
        return {
            "main_rss_mb": 0.0,
            "ga_worker_max_rss_mb": 0.0,
            "ga_worker_total_rss_mb": 0.0,
            "n_ga_workers": 0.0,
            "all_children_max_rss_mb": 0.0,
            "all_children_total_rss_mb": 0.0,
            "n_all_children": 0.0,
        }
    process = psutil.Process()
    main_rss_mb = process.memory_info().rss / 1024 / 1024
    ga_worker_rss: list[float] = []
    all_child_rss: list[float] = []
    for child in process.children(recursive=True):
        try:
            rss_mb = child.memory_info().rss / 1024 / 1024
        except psutil.NoSuchProcess:
            continue
        if pool_pids is not None and child.pid in pool_pids:
            ga_worker_rss.append(rss_mb)
        elif pool_pids is None:
            all_child_rss.append(rss_mb)
    return {
        "main_rss_mb": main_rss_mb,
        "ga_worker_max_rss_mb": max(ga_worker_rss, default=0.0),
        "ga_worker_total_rss_mb": sum(ga_worker_rss),
        "n_ga_workers": float(len(ga_worker_rss)),
        "all_children_max_rss_mb": max(all_child_rss, default=0.0),
        "all_children_total_rss_mb": sum(all_child_rss),
        "n_all_children": float(len(all_child_rss)),
    }


# Suppress unused field warning for future extension hook
_ = field
