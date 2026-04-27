# 詳細設計: GA 並列ワーカー数指定機能

- 作成: 2026-04-27 12:10 JST
- 更新: 2026-04-27 12:30 JST (Round 1 detailed-review 反映)
- 更新: 2026-04-27 13:00 JST (Round 2 detailed-review 反映 — 深い不変性 / エイリアシング解消 / strict-memory-guard / children 指標厳密化)
- 更新: 2026-04-27 13:20 JST (Round 3 detailed-review 反映 — Mapping 実体凍結 / pid stale 対策 / pickle size 相対閾値)
- 更新: 2026-04-27 13:40 JST (Round 4 detailed-review 反映 — MappingProxyType pickle 非互換に `__getstate__/__setstate__` で対応 / pool_pids private API fallback / schema_version 明記)
- 更新: 2026-04-27 14:00 JST (Round 5 detailed-review **APPROVED** / 実装時メモ追記)

## 実装時メモ (Round 5 Suggestion)
- `summary.json.schema_version` の現行値を実装着手時に `grep "schema_version" reports/run-reports/run-*/summary.json scripts/alpha_factory/run_ga.py` で確認し、minor bump (`X.Y → X.(Y+1)`) を反映
- 詳細設計内の field 名 `peak_rss_mb_per_worker` / `ga_worker_max_rss_mb` / `all_children_max_rss_mb` の対応関係を実装前に最終 grep で整合性確認
  - `summary.json` 上の正規 field 名: `per_generation[*].peak_rss_mb_per_worker` (`measure_peak_rss_mb()` の `ga_worker_max_rss_mb` を proxy として記録)
  - 内部関数の戻り値 key と summary field 名は別物として扱い、変換 layer (`_summarize_rss_for_summary_json`) を 1 箇所に集約
- 概念設計: [conceptual-design.md](./conceptual-design.md) (Round 3 APPROVED)
- Round 1/2/3 conceptual review: [conceptual-review-round-{1,2,3}.md](./)
- Round 1 detailed review: [detailed-review-round-1.md](./detailed-review-round-1.md)

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- バグ修正はテストファースト: 再現最小テスト → FAIL 確認 → 修正 → PASS
- 全施策にテスト必須
- テスト命名は振る舞いを説明する汎用名（Run 名・日付・セッション固有 NG）
- テスト配置は対象モジュールに対応するテストファイル
- `uv run pytest tests/alpha_factory/`
- `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas

## Round 1 detailed-review 対応マトリクス

| 指摘 | 分類 | 対応箇所 |
|---|---|---|
| §1 Critical: tuple 化は浅い不変化、worker 内文脈変化経路が残る | Critical | §実装規約 §6 (decision determinism) — `LaneEvalContext.__post_init__` で要素検証、worker 側「context 変更禁止」規約、numpy.random seed を `(lane_id, generation, population_index)` 由来で固定、worker 数 1/2/6 の三段反復一致テスト |
| §2 Critical: preflight_underfilled の worker 短絡 | Critical | `LaneEvalContext.preflight_underfilled` / `preflight_payload` を追加、`evaluate_genome` で短絡 (option a 採用)、偽 StageResult は main の `_build_preflight_b_result` 共通ファクトリに集約 |
| §3 Warning: graduation の世代番号スナップショット固定 | Warning | `_collect_results_in_population_order` 冒頭で `generation_index = lane.generation_count` をローカル固定、collect/graduation/archive 全てこの値を使用 |
| §5 Warning: RegistryEvaluator picklability テスト | Warning | `tests/alpha_factory/test_parallel_eval.py` に空/非空 aux/numpy view 含むケースの pickle ラウンドトリップテスト追加 |
| §7 Warning: `_classify_exception` 網羅性 | Warning | 「workerで発生しうる例外集合」を §4.6.2 に明示、`pyarrow.lib.ArrowInvalid` / `pandas.errors.EmptyDataError` / `sqlalchemy.exc.*` は **到達不能** として理由を明記し、検知テスト (worker から直接 raise → `WORKER_UNCLASSIFIED` 経路) で fallback 確認 |
| §9 Warning: メモリ運用ガード強化 | Warning | §6.1 (運用ガード) を施策 5 に統合、`max_rss_mb_per_worker` 測定 / 起動時+世代中ピーク / `cfg.ga.max_workers` が `(available_mem - 4GB) / 0.4GB` を超えたら起動時 warning |
| §4 Suggestion: chunksize は性能調整、順序保証は map で十分 | Suggestion | コメントで明記 (chunksize 未指定で OK) |
| §6 Suggestion: timing は sum + max 併記 | Suggestion | 施策 5 schema を `stage_*_seconds_total` (sum) + `stage_*_seconds_max` (max) に拡張 |
| §8 Suggestion: lookahead 比較テスト | Suggestion | 同値性テストで「同 genome 集合の特徴量・シグナル・PnL 一致」を確認 (実質既に L2 で担保。明示テストとして追加) |
| §10 Suggestion: skill 互換性 | Suggestion | 施策 4 で skill 経由透過を確認するチェックリスト記載 |

## 概念設計リファレンス

[devnotes/20260427-1114-ga-parallel-workers/conceptual-design.md](./conceptual-design.md)

主要決定:
- `multiprocessing.Pool` (spawn context) で worker 並列化
- worker は **副作用なしの純粋関数** (Stage A/B/C 評価のみ)
- archive / diagnostics は **main process が population 順に collect**
- `lane_contexts` は **Pool initializer で immutable 一括 broadcast** (mutable update API なし)
- 決定論性: L1 selection / L2 row-order を必須保証、L3 artifact bit equivalence は非保証
- worker 例外は `GenomeEvalError(stage, error_code, fixed_message)` に **正規化決定表** で正規化
- pool 寿命は context manager (`__enter__`/`__exit__`) で管理 (close vs terminate を例外有無で分岐)

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `parallel_eval` モジュール新設 (evaluation 層 + transport 層) | 新規 src/alpha_factory/parallel_eval.py | High |
| 2 | `LaneManager` を evaluator 経由化 | src/alpha_factory/swim_lane.py | High |
| 3 | `GAConfig.max_workers` 追加 | src/alpha_factory/config.py + config/alpha_factory/default.yaml | High |
| 4 | `run_ga.py` CLI + 統合 | scripts/alpha_factory/run_ga.py | High |
| 5 | summary.json に stage 別 timing / max_rss を追加 | scripts/alpha_factory/run_ga.py | Medium |
| 6 | テスト: 同値性・単体 | tests/scripts/test_run_ga_parallel.py + tests/alpha_factory/test_parallel_eval.py + tests/alpha_factory/test_swim_lane.py | High |
| 7 | docs / AGENTS.md / runbook 反映 | docs/alpha_factory/runbook.md, AGENTS.md | Medium |

---

## 施策 1: `parallel_eval` モジュール新設

### 変更箇所
- 新規: [src/alpha_factory/parallel_eval.py](../../src/alpha_factory/parallel_eval.py) (全体)

### 波及変更
- `AGENTS.md`: 変更なし (この施策単独では skill 経由の利用法は変えない)
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: 変更なし
- `config/alpha_factory/default.yaml`: 施策 3 で扱う
- `docs/alpha_factory/*.md`: 施策 7 で扱う

### 構造

```python
# src/alpha_factory/parallel_eval.py

"""GA 評価の並列化レイヤ (T-XXX)。

二層構造:
- evaluation 層: evaluate_genome (genome → GenomeStageResult, 純粋関数)
- task transport 層: ParallelEvaluator / SequentialEvaluator (Pool 起動・寿命管理)

決定論性契約:
- L1 selection: cache[name].fitness_pen / best_name / live_criteria_passed が
  worker 数に依存しない
- L2 row-order: archive Parquet の数値 column が
  (lane_id, generation, genome_name) ソート下で一致
- L3 artifact bit equivalence: 非保証 (timestamp 系 field を含むため)

設計根拠: devnotes/20260427-1114-ga-parallel-workers/conceptual-design.md
"""

from __future__ import annotations

import logging
import multiprocessing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from src.alpha_factory.cross_pair import CrossPairConfig, StageCRunCrossPairEvaluator
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass hierarchy (worker ↔ main process 間で送受される pickle 可能型)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreflightPayload:
    """Stage B preflight (fold 不足) 時に main 側で偽 StageResult を組み立てるための
    snapshot 値を保持する。RUN 中 immutable (Round 2 detailed-review §1 反映)."""

    n_unique_dates: int
    wf_min_unique_dates: int
    max_folds: int
    wf_min_folds_required: int
    n_bars: int  # bars_18m の長さ (snapshot)


@dataclass(frozen=True)
class CrossPairLaneInputs:
    """Phase 2 では使われないが、将来 graduation.pair_bars 注入時に
    `cp_inputs` の代わりに使う専用 frozen dataclass。深い不変性確保。

    Phase 2 では `LaneEvalContext.cp_inputs is None` で常に skip。

    深い不変性 (Round 3 §1 Critical 反映 + Round 4 §1 Critical 反映):
        - 入力 dict を `dict(...)` で defensive copy (外部参照断絶)
        - pair_bars_map の value (list[PriceBar]) を tuple 化
        - MappingProxyType で wrap (キー・値の追加/削除を防ぐ)
        - **MappingProxyType は Python 3.13 で pickle 非互換** (Round 4 実機検証)
          → `__getstate__` / `__setstate__` で `mappingproxy ↔ dict` 変換を実装
          (worker 側で再構築時に MappingProxyType に戻す)
    """

    target_pair: str
    pair_bars_map: Mapping[str, tuple[PriceBar, ...]]
    meta_map: Mapping[str, InstrumentMeta]

    def __post_init__(self) -> None:
        # frozen dc では再代入に object.__setattr__ が必要
        frozen_pair_bars = MappingProxyType({
            k: tuple(v) for k, v in self.pair_bars_map.items()
        })
        frozen_meta = MappingProxyType(dict(self.meta_map))
        object.__setattr__(self, "pair_bars_map", frozen_pair_bars)
        object.__setattr__(self, "meta_map", frozen_meta)

    def __getstate__(self) -> dict[str, Any]:
        """pickle: MappingProxyType を picklable な dict に変換."""
        return {
            "target_pair": self.target_pair,
            "pair_bars_map": dict(self.pair_bars_map),  # mappingproxy → dict
            "meta_map": dict(self.meta_map),
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        """unpickle: dict を MappingProxyType に再 wrap (深い不変性復元)."""
        object.__setattr__(self, "target_pair", state["target_pair"])
        object.__setattr__(
            self, "pair_bars_map",
            MappingProxyType({
                k: tuple(v) for k, v in state["pair_bars_map"].items()
            }),
        )
        object.__setattr__(
            self, "meta_map",
            MappingProxyType(dict(state["meta_map"])),
        )


@dataclass(frozen=True)
class LaneEvalContext:
    """RUN 中 immutable な lane 評価用コンテキスト。

    Pool initializer 経由で全 worker に配布。Pool 寿命中は不変。

    深い不変性 (Round 2 detailed-review §1 Critical 反映):
        - bars_* は tuple 化 (PriceBar も frozen dataclass のため要素 mutation なし)
        - cp_inputs は CrossPairLaneInputs 専用 frozen dataclass (None 許容)
        - preflight_payload は PreflightPayload 専用 frozen dataclass (None 許容)
        - __post_init__ では **assert ではなく明示 raise** で型を強制
          (`python -O` で無効化されないため)
        - worker 側「context mutation 禁止」を §実装規約 で明記

    preflight_underfilled (Round 1 §2 反映):
        Stage B walk-forward fold が dataset 不足で組めない場合 True。
        worker 側 evaluate_genome は Stage A 通過後、preflight_underfilled=True
        なら Stage B/C を **短絡 skip** し、main 側で偽 StageResult を組み立てる。
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

    def __post_init__(self) -> None:
        # Round 2 §1 Critical: assert ではなく raise (python -O で無効化されない)
        if not isinstance(self.bars_a, tuple):
            raise TypeError(
                f"LaneEvalContext.bars_a must be tuple: got {type(self.bars_a).__name__}"
            )
        if not isinstance(self.bars_b, tuple):
            raise TypeError(
                f"LaneEvalContext.bars_b must be tuple: got {type(self.bars_b).__name__}"
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
                f"LaneEvalContext.cp_inputs must be CrossPairLaneInputs or None: "
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
                f"LaneEvalContext.preflight_payload must be PreflightPayload: "
                f"got {type(self.preflight_payload).__name__}"
            )


@dataclass(frozen=True)
class GenomeEvalError:
    """worker 例外を deterministic な構造体に正規化する。

    生 traceback は worker logger 専用、artifact には含めない (L1/L2 維持)。
    """

    stage: Literal["A", "B", "C"]
    error_code: str       # 決定表の固定 enum
    fixed_message: str    # 決定表の固定文 (str(e) を流入させない)


@dataclass(frozen=True)
class GenomeStageResult:
    """1 個体の Stage A/B/C 評価結果。

    Stage A fail なら stage_b/c は None。Stage B fail なら stage_c は None。
    error が non-None の場合 stage_a も None (worker 内で例外発生)。
    """

    genome_name: str
    stage_a: StageResult | None
    stage_b: StageResult | None
    stage_c: StageResult | None
    cross_pair: CrossPairResult | None
    error: GenomeEvalError | None = None


# ---------------------------------------------------------------------------
# Evaluation 層 (純粋関数、worker / in-process 共通)
# ---------------------------------------------------------------------------


def evaluate_genome(
    genome: Genome,
    ctx: LaneEvalContext,
    stage_gate_cfg: StageGateConfig,
    cross_pair_cfg: CrossPairConfig,
    primitive_evaluator: RegistryEvaluator,
) -> GenomeStageResult:
    """1 個体の Stage A → B → C 評価を実行する純粋関数。

    副作用なし。archive.collect_* / diagnostics.record_* は main process 側で行う。

    - Stage A fail → stage_b/c は None で早期 return
    - Stage B fail → stage_c は None で早期 return
    - 例外 → GenomeEvalError に正規化、stage_a/b/c は None

    cross-pair は ctx.cp_inputs が None なら skip (Phase 2 default)。
    """
    try:
        a_result = evaluate_stage_a(
            genome,
            list(ctx.bars_a),  # tuple → list (既存 API シグネチャ互換)
            ctx.meta,
            ctx.bt_cfg,
            primitive_evaluator,
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

    # Round 1 detailed-review §2 反映: preflight_underfilled なら Stage B/C 短絡
    # 偽 StageResult 生成は main で _build_preflight_b_result() 共通ファクトリに集約
    if ctx.preflight_underfilled:
        return GenomeStageResult(
            genome_name=genome.name,
            stage_a=a_result,
            stage_b=None,  # main 側で偽 result を組み立てる
            stage_c=None,
            cross_pair=None,
        )

    try:
        b_result = evaluate_stage_b(
            genome,
            list(ctx.bars_b),
            ctx.meta,
            ctx.bt_cfg,
            primitive_evaluator,
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

    cp_evaluator: StageCRunCrossPairEvaluator | None = None
    if ctx.cp_inputs is not None:
        cp_evaluator = StageCRunCrossPairEvaluator(
            primitive_evaluator=primitive_evaluator,
            cross_pair_config=cross_pair_cfg,
        )
    try:
        c_result = evaluate_stage_c(
            genome,
            list(ctx.bars_holdout),
            ctx.meta,
            ctx.bt_cfg,
            primitive_evaluator,
            stage_gate_cfg,
            cross_pair_evaluator=cp_evaluator,
            cross_pair_inputs=ctx.cp_inputs,
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
    """swim_lane.LaneManager._extract_cross_pair_result と同等のロジック (重複許容)。

    Stage C payload から CrossPairResult を取り出す。
    skipped / 型不一致なら None。
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
# 例外正規化決定表 (§4.6.1)
# ---------------------------------------------------------------------------


def _classify_exception(
    exc: BaseException, stage: Literal["A", "B", "C"]
) -> GenomeEvalError:
    """例外を (error_code, fixed_message) に正規化する。

    型ベース判定を優先し、文字列 substring 判定は最終フォールバック。
    KeyboardInterrupt / SystemExit は正規化せず再 raise (caller 責務)。

    Worker で発生しうる例外集合 (Round 1 detailed-review §7 反映):
    - 数値計算系: numpy.linalg.LinAlgError, MemoryError
    - DSL/primitive 系: RuntimeError ("primitive" in msg)
    - Stage B fold 系: ValueError ("stage_b" / "wf" in msg)
    - 制御系: KeyboardInterrupt / SystemExit (再 raise)
    - その他 → WORKER_UNCLASSIFIED

    到達不能と想定する例外 (worker 責務外):
    - pyarrow.lib.ArrowInvalid: archive Parquet 書き込みは main 専用 → worker から呼ばない
    - pandas.errors.EmptyDataError: bars は main で DB ロード済 → worker は受け取るのみ
    - sqlalchemy.exc.*: DB 接続も main 専用 → worker は DB アクセスしない
    上記が万一 worker で発生した場合は WORKER_UNCLASSIFIED に集約され、test で
    fallback 経路を検知 (test_classify_exception_unclassified_default)。
    """
    import numpy as np

    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc  # noqa: PLE0704 — 正規化対象外

    if isinstance(exc, np.linalg.LinAlgError):
        return GenomeEvalError(stage, "BACKTEST_LINALG_ERROR", "linalg numerical error")
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
        stage, genome_name, err.error_code, type(exc).__name__,
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


# Worker module-global (Pool initializer で 1 度だけ書き込み、以後 immutable 扱い)
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

    primitive registry を ensure_registered() で再構築 (spawn 経由で
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
    ctx = _WORKER_LANE_CONTEXTS[lane_id]
    assert _WORKER_STAGE_GATE_CFG is not None
    assert _WORKER_CROSS_PAIR_CFG is not None
    assert _WORKER_PRIM_EVALUATOR is not None
    return evaluate_genome(
        genome,
        ctx,
        _WORKER_STAGE_GATE_CFG,
        _WORKER_CROSS_PAIR_CFG,
        _WORKER_PRIM_EVALUATOR,
    )


class GenomeEvaluator:
    """LaneManager から呼ばれる evaluator API (シーケンシャル/並列共通)."""

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
        # MappingProxyType で immutable 化 (実装時の安全網)
        self._lane_contexts: Mapping[str, LaneEvalContext] = MappingProxyType(
            dict(lane_contexts)
        )
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
                    g, ctx, self._stage_gate_cfg,
                    self._cross_pair_cfg, self._prim_evaluator,
                )
                for g in population
            ]
        # pool.map は入力順保持 (Python multiprocessing 仕様) → population 順
        return self._pool.map(_eval_genome_worker, args)

    # --- context manager / 寿命管理 (§4.6) ---

    def __enter__(self) -> "GenomeEvaluator":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close(exc_type is not None)

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
```

### 実装規約 (Round 1 detailed-review §1 反映)

**worker 内 context 不変ルール** — 構造的不変化に加え、運用規約を以下の通り設計に明示する:

1. `LaneEvalContext` は frozen dataclass + bars_a/b/holdout を tuple 化
2. `LaneEvalContext.__post_init__` で `isinstance(bars_a, tuple)` 等を assert (浅い不変化を契約として強制)
3. `_eval_genome_worker` および `evaluate_genome` 内で `ctx.X` を **直接参照のみ** とし、`copy.deepcopy(ctx)` / `ctx.bars_a.append(...)` 等の mutation を **禁止** (CR / lint で検知)
4. PriceBar は frozen dataclass のため要素単位 mutation も発生しない (Verified: src/domain/price.py)
5. RNG: `evaluate_genome` 内で `numpy.random.seed` / `random.seed` を呼ぶ場合、**全て `(lane_id, generation, population_index)` 由来の derive seed** を使用 (worker process 起動時刻に依存しない)。Phase 2 では Stage A/B/C 評価関数自体に乱数依存はないため、この規約は将来の bootstrap 等の追加に備えた防御線

### 現行コード
（新規モジュール、現行コードなし）

### ルックアヘッドバイアスチェック
本施策は primitive 変更ではなく、評価 orchestration 層のみの変更。primitive 内部の数値計算は一切変更しない。

### パフォーマンスチェック
本施策は primitive 変更ではない。primitive 内部の `compute_all_bars` / SoA キャッシュは無変更。

### テスト計画
- [x] 単体テスト: `tests/alpha_factory/test_parallel_eval.py`
  - `evaluate_genome` (in-process) が現行 `_run_tier1_generation` の per-genome 結果と一致
  - `_classify_exception` が決定表マッピング通り (各例外型を pin)
  - `_to_error_result` が GenomeStageResult.error を埋める
  - `GenomeEvaluator(max_workers=1)` の `evaluate_population` が in-process 経路で動作
  - `GenomeEvaluator(max_workers=2)` の `evaluate_population` が pool 経路で動作 (mock primitive で StageResult を制御)
  - `__exit__` 正常系で `pool.close()` が呼ばれる / 異常系で `pool.terminate()` が呼ばれる (mock pool で確認)
  - `LaneEvalContext.bars_a` が tuple であることを assert (frozen 担保)

### リスク
- `multiprocessing.Pool` の spawn は macOS で `if __name__ == "__main__"` ガード必須だが、worker 関数 `_eval_genome_worker` / `_init_worker` はモジュールレベルにあり spawn 安全
- `RegistryEvaluator` を pickle 経由で worker に渡す際、`aux_pair_bars` が空 dict なら問題なし (Phase 2 default)。aux が注入されている将来ケースは初回 RUN で検出 (実装時に試験 pickle して確認)

---

## 施策 2: `LaneManager` を evaluator 経由化

### 変更箇所
- 修正: [src/alpha_factory/swim_lane.py](../../src/alpha_factory/swim_lane.py) (`LaneManager.__init__`, `_run_tier1_generation`, `_extract_cross_pair_result` の利用)

### 波及変更
- `AGENTS.md`: 変更なし
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: 変更なし
- `config/alpha_factory/default.yaml`: 施策 3
- `docs/alpha_factory/swim-lane.md`: 施策 7 で「evaluator 経由化」を追記

### 変更内容

`LaneManager.__init__` に `genome_evaluator: GenomeEvaluator | None = None` 引数追加 (None なら従来通りの直列評価で動作; 後方互換)。

```python
# swim_lane.py

class LaneManager:
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
        genome_evaluator: "GenomeEvaluator | None" = None,  # 新規
    ) -> None:
        # ... 既存 validate ...
        self._genome_evaluator = genome_evaluator
```

`_run_tier1_generation` の差分 (before / after 比較):

**Before** (現行 [swim_lane.py:458-625](../../src/alpha_factory/swim_lane.py#L458-L625)):
```python
def _run_tier1_generation(self, lane: Tier1Lane) -> dict[str, Any]:
    # ... preflight ...
    for genome in lane.population:
        a_result = evaluate_stage_a(genome, lane.bars_60d, ...)
        self._archive.collect_stage_a(genome, lane.lane_id, lane.generation_count, a_result, ...)
        if self._diagnostics: self._diagnostics.record_stage_a(...)
        if not a_result.passed: continue
        stage_a_pass += 1
        # ... Stage B ...
        # ... Stage C ...
    lane.generation_count += 1
    return {...}
```

**After**:
```python
def _run_tier1_generation(self, lane: Tier1Lane) -> dict[str, Any]:
    # ... preflight (lane_n_unique_dates / preflight_underfilled は現行と同じ) ...

    if self._genome_evaluator is not None:
        # 並列 / in-process 統一経路
        results = self._genome_evaluator.evaluate_population(
            lane.lane_id, lane.generation_count, lane.population
        )
        return self._collect_results_in_population_order(
            lane, results, preflight_underfilled, lane_n_unique_dates,
            wf_min_dates, lane_max_folds, wf_min_folds,
        )

    # 後方互換 fast path: genome_evaluator 未注入なら現行直列ロジックそのまま
    return self._run_tier1_generation_legacy(lane, ...)
```

`_collect_results_in_population_order(lane, results, ...)` (新規 private method):
- **世代番号スナップショットを冒頭で固定** (Round 1 detailed-review §3 反映):
  ```python
  generation_index = lane.generation_count  # ループ前にローカル固定
  # 以降の collect_stage_*, mark_graduated, _mark_for_graduation には全て
  # `generation_index` を渡す。lane.generation_count を直接参照しない
  ```
- `results` は population 順
- 各 result について `archive.collect_stage_a/b/c` / `diagnostics.record_stage_a/b/c` / graduation 判定を呼ぶ
- worker 例外 (`result.error is not None`) は fail-closed `StageResult` (`reason_codes=("worker_error",)`) に変換して `collect_stage_a` に渡す
- preflight_underfilled の Stage B 偽結果生成は **main 側で `_build_preflight_b_result(genome, ctx)` 共通ファクトリ** に集約 (Round 1 §2 反映)。worker は preflight_underfilled=True なら Stage B を短絡 None で返すので、main で当該 genome に対し共通ファクトリの偽結果を `archive.collect_stage_b` に渡す
- ループ末尾で `lane.generation_count += 1` を行う (現行と同じ)
- 集計 (`stage_a_pass / stage_b_pass / stage_c_pass / graduation_count`) を返す
- **stage 別 timing 集計** (施策 5 連動): `stage_a_seconds_total = sum(r.stage_a.metrics["wall_time_seconds"] for r in results if r.stage_a)`, `stage_a_seconds_max = max(...)` 等を summary に含める

`_build_preflight_b_result(genome, ctx)` の中身は現行 [swim_lane.py:528-555](../../src/alpha_factory/swim_lane.py#L528-L555) と同等で、`StageResult(stage="B", passed=False, reason_codes=("stage_b_pre_flight_underfilled",), metrics={...payload...})` を返す。`ctx.preflight_payload` (`PreflightPayload` frozen dc) から `n_unique_dates` / `wf_min_unique_dates` / `max_folds` / `wf_min_folds_required` を読む。

**エイリアシング回避** (Round 2 §2 Warning 反映): `ctx.preflight_payload` を `metrics["payload"]` に **そのまま参照共有しない**。`StageResult.metrics` に格納する dict は呼び出し毎に新規作成し、frozen dc から **値をコピー** で取り出す:

```python
def _build_preflight_b_result(self, genome: Genome, ctx: LaneEvalContext) -> StageResult:
    # Round 3 §2 Warning: fail-fast 化
    if ctx.preflight_payload is None:
        raise RuntimeError(
            "_build_preflight_b_result called without preflight_payload "
            "(invariant violation: ctx.preflight_underfilled でない)"
        )
    p = ctx.preflight_payload  # frozen dc → 値はそのまま安全だが metrics dict は新規
    return StageResult(
        stage="B",
        passed=False,
        metrics={
            "stage": "B",
            "genome_name": genome.name,
            "n_bars": p.n_bars,  # int は immutable
            "wall_time_seconds": 0.0,
            "payload": {
                "n_unique_dates": p.n_unique_dates,
                "wf_min_unique_dates": p.wf_min_unique_dates,
                "max_folds": p.max_folds,
                "wf_min_folds_required": p.wf_min_folds_required,
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
```

**重要**: cross-pair `cp_inputs` 構築は現行 `_build_cross_pair_args` のまま (lane.instrument が graduation.pair_bars に含まれる場合のみ inputs を組み立て)。並列モード時は `LaneEvalContext.cp_inputs` に既に格納済 (`run_ga.py` 側で構築)。`evaluate_genome` 内で `cp_inputs` から CrossPairEvaluator を都度生成するため、main 側 `_build_cross_pair_args` の戻り値はもう使わない。

### 現行コード
[swim_lane.py:458-625](../../src/alpha_factory/swim_lane.py#L458-L625) 参照。

### ルックアヘッドバイアスチェック
N/A (orchestration 層、数値計算未変更)

### パフォーマンスチェック
- evaluator 経由化のオーバーヘッド: `evaluate_population` 1 回呼ぶだけで現行ループと等価 (in-process 経路時)。マイクロ秒オーダー
- 並列経路ではむしろ大幅な短縮を期待

### テスト計画
- [x] 既存 `tests/alpha_factory/test_swim_lane.py` が regression なく pass (genome_evaluator=None で legacy path)
- [x] `tests/alpha_factory/test_swim_lane.py` に `LaneManager(genome_evaluator=GenomeEvaluator(max_workers=1, ...))` で `_run_tier1_generation` の戻り値集計が現行と一致するテスト追加
- [x] mock 評価器で同一 GenomeStageResult を返す場合、archive collect 順序が population 順であることを assert (`MagicMock.call_args_list` で順序確認)

### リスク
- legacy path と evaluator path の二重メンテ。実装時は evaluator path を default にし、legacy path は完全削除を視野に (将来別 TODO)。本 TODO では **後方互換のため両方残す** が、evaluator path 経由を新 default として `run_ga.py` から呼ぶ
- `_collect_results_in_population_order` で graduation 判定を呼ぶ際、`lane.generation_count` が **collect 完了まで pre-increment 値を保持** する必要あり。現行 `lane.generation_count += 1` は loop 末尾なのでこの順序は維持

---

## 施策 3: `GAConfig.max_workers` 追加

### 変更箇所
- 修正: [src/alpha_factory/config.py](../../src/alpha_factory/config.py) (GAConfig dataclass + `_build_ga`)
- 修正: [config/alpha_factory/default.yaml](../../config/alpha_factory/default.yaml) (`ga.max_workers: 1`)

### 波及変更
- `AGENTS.md`: 変更なし
- `.claude/skills/zenigame-fx-{skill}/SKILL.md`: 変更なし
- `docs/alpha_factory/runbook.md`: 施策 7

### 変更内容

```python
# config.py

@dataclass(frozen=True)
class GAConfig:
    # ... 既存 fields ...
    max_workers: int = 1  # 並列ワーカー数 (1 = sequential)

    def __post_init__(self) -> None:
        # ... 既存 validation ...
        if self.max_workers < 1:
            raise ValueError(
                f"ga.max_workers must be >= 1: {self.max_workers}"
            )

def _build_ga(raw: Mapping[str, Any]) -> GAConfig:
    return GAConfig(
        # ... 既存 fields ...
        max_workers=int(raw.get("max_workers", 1)),
        feasibility=_build_feasibility(raw.get("feasibility")),
    )
```

```yaml
# config/alpha_factory/default.yaml の ga: 配下に追加

ga:
  population_size: 40
  generations: 15
  ...
  # T-XXX: GA 評価並列ワーカー数 (1 = シーケンシャル)
  # @why: GA 評価の wall-time 短縮 (副次目標)。L1 selection / L2 row-order
  #       決定論性を保証 (L3 bit equivalence は非保証)。
  # @default: 1 (CI / local 既定)。autopilot/improve-cycle は変更しない。
  # @upper_bound: 物理コア数 / (24GB ÷ 1worker_3GB) の min。
  # @ref: devnotes/20260427-1114-ga-parallel-workers/
  max_workers: 1
```

### 現行コード
[config.py:124-173](../../src/alpha_factory/config.py#L124-L173) (`GAConfig` dataclass), [config.py:335-351](../../src/alpha_factory/config.py#L335-L351) (`_build_ga`)

### テスト計画
- [x] `tests/alpha_factory/test_config.py` (既存または新規) に以下を追加:
  - `GAConfig(max_workers=1)` が成功
  - `GAConfig(max_workers=0)` が `ValueError` を raise
  - `GAConfig(max_workers=8)` が成功
  - `_build_ga({...})` で `max_workers` 未指定時 `1` がデフォルト
  - `_build_ga({"max_workers": 4, ...})` で 4 が反映

### リスク
- 既存 fixture / config 互換性: `max_workers` は default=1 で `__post_init__` で fail しないため、既存 YAML / CLI が無変更で動作する

---

## 施策 4: `run_ga.py` CLI + 統合

### 変更箇所
- 修正: [scripts/alpha_factory/run_ga.py](../../scripts/alpha_factory/run_ga.py) (`_parse_args`, `_args_to_overrides`, `main`)

### 波及変更
- `AGENTS.md`: 運用コマンド例に `--max-workers` 追記
- `.claude/skills/zenigame-fx-run-alpha-factory/SKILL.md` 等: GA 実行コマンドが skill 経由でも `--max-workers` を透過できるか確認 (本施策では skill 自体は無変更、CLI 引数透過は既存仕組みで動く想定)
- `docs/alpha_factory/runbook.md`: 施策 7

### 変更内容

```python
# run_ga.py

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alpha Factory GA run (Phase 2 integration)")
    # ... 既存 args ...
    p.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="GA 評価並列ワーカー数 (1 = sequential, 既定は config の値)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        dest="workers_alias",
        help="--max-workers のエイリアス (zenigame との互換)",
    )
    p.add_argument("--no-report", action="store_true", help="...")
    args = p.parse_args(argv)
    # alias 統合 (両方指定時は --max-workers が canonical)
    if args.max_workers is None and args.workers_alias is not None:
        args.max_workers = args.workers_alias
    elif args.max_workers is not None and args.workers_alias is not None:
        if args.max_workers != args.workers_alias:
            raise SystemExit(
                "--max-workers と --workers が異なる値で指定されました"
            )
    return args


def _args_to_overrides(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "dataset": {...},
        "ga": {
            # ... 既存 ...
            "max_workers": args.max_workers,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = load_config(args.config, overrides=_args_to_overrides(args))
    # ... 既存 setup ...

    bundle = _load_lane_bars(cfg.dataset.instrument, cfg.dataset, cfg.stage_windows)

    # LaneEvalContext を構築 (RUN 中 immutable)
    lane_id = f"tier1_{cfg.dataset.instrument}"
    lane_ctx = LaneEvalContext(
        lane_id=lane_id,
        bars_a=tuple(bundle.bars_stage_a),
        bars_b=tuple(bundle.bars_stage_b),
        bars_holdout=tuple(bundle.bars_holdout),
        meta=bundle.meta,
        bt_cfg=bt_factory(cfg.dataset.instrument),
        cp_inputs=None,  # Phase 2 では graduation.pair_bars が空のため None
    )

    # GenomeEvaluator を with 文で寿命管理 (close 漏れ防止)
    with GenomeEvaluator(
        max_workers=cfg.ga.max_workers,
        stage_gate_cfg=cfg.stage_gate,
        cross_pair_cfg=cfg.cross_pair,
        prim_evaluator=primitive_evaluator,
        lane_contexts={lane_id: lane_ctx},
    ) as genome_evaluator:
        if cfg.ga.max_workers > os.cpu_count():
            logger.warning(
                "run_ga.max_workers_exceeds_cpu_count",
                requested=cfg.ga.max_workers,
                cpu_count=os.cpu_count(),
            )

        lane_manager = LaneManager(
            tier1={lane_id: tier1_lane},
            graduation=graduation_lane,
            stage_gate_config=cfg.stage_gate,
            cross_pair_config=cfg.cross_pair,
            primitive_evaluator=primitive_evaluator,
            archive=archive,
            backtest_config_factory=bt_factory,
            diagnostics_collector=diagnostics_collector,
            genome_evaluator=genome_evaluator,
        )
        # ... 既存 GA loop ...
```

### 現行コード
[run_ga.py:229-281](../../scripts/alpha_factory/run_ga.py#L229-L281) (`_parse_args`/`_args_to_overrides`),
[run_ga.py:890-1103](../../scripts/alpha_factory/run_ga.py#L890-L1103) (`main`)

### ルックアヘッドバイアスチェック
N/A

### パフォーマンスチェック
N/A (orchestration)

### テスト計画
- [x] `tests/scripts/test_run_ga_cli.py` (既存または新規) に:
  - `--max-workers 4` が `cfg.ga.max_workers == 4` になる
  - `--workers 4` が同上
  - `--max-workers 4 --workers 8` が `SystemExit` を raise
  - `--max-workers` 未指定時、YAML 値 (=1) が使われる

### リスク
- `_parse_args` の alias 統合ロジックは独立してテストする (CLI 単体テスト)
- skill 経由の引数透過: `zenigame-fx-run-alpha-factory` 等の skill が `argv` をパススルーする実装なら無変更で動く

### skill 互換性チェックリスト (Round 1 detailed-review §10 反映)

実装時に以下 skill SKILL.md を grep して、`scripts/alpha_factory/run_ga.py` の起動コマンドに `--max-workers` を追加できる箇所を確認:

| skill | チェック項目 | 必要な変更 |
|---|---|---|
| `zenigame-fx-run-alpha-factory` | run_ga.py 起動コマンドに引数オプションがあるか | 引数オプション説明に `--max-workers N` 追加 |
| `zenigame-fx-batch-ga` | バッチ N 回実行で全 RUN に同 max_workers を渡せるか | バッチ全体で 1 回指定 |
| `zenigame-fx-improve-cycle` | サイクル内 GA 実行で透過できるか | デフォルト 1、明示指定時のみ伝搬 |
| `zenigame-fx-autopilot` | 自走ループで自動増加させない | デフォルト 1 維持 (本概念設計の方針) |
| `zenigame-fx-profile-optimize` | プロファイル時 worker 数 | プロファイルは max_workers=1 推奨 (overhead と分離) |

---

## 施策 5: `summary.json` に stage 別 timing / max_rss を追加

### 変更箇所
- 修正: [scripts/alpha_factory/run_ga.py](../../scripts/alpha_factory/run_ga.py) (`_write_reports`)

### 波及変更
- `docs/alpha_factory/swim-lane.md` または `runbook.md`: summary.json schema 追記 (施策 7)

### 変更内容

`run_generation` が返す summary に既に `wall_time_seconds` (lane 全体) があるため、それを per-stage に分解する。
`StageResult.metrics["wall_time_seconds"]` (各 stage 評価の実時間) を **main 側で** `_collect_results_in_population_order` で集計:

```python
# _collect_results_in_population_order の戻り値に追加 (Round 1 §6 反映: sum + max 併記)
{
    # ... 既存 ...
    "stage_a_seconds_total": float,   # sum: 総計算量 (並列なら短縮されない指標)
    "stage_a_seconds_max": float,     # max: 1 個体最遅 (ボトルネック判定)
    "stage_b_seconds_total": float,
    "stage_b_seconds_max": float,
    "stage_c_seconds_total": float,
    "stage_c_seconds_max": float,
    "stage_a_pass_rate": float,  # stage_a_pass / n_evaluated
    "stage_b_pass_rate": float,  # stage_b_pass / max(stage_a_pass, 1)
    "stage_c_pass_rate": float,  # stage_c_pass / max(stage_b_pass, 1)
}
```

`summary.json.per_generation[*]` にこれらを追加 (既存 field は保持 = 後方互換)。

`max_rss_mb_per_worker` は `psutil` で main process 終了時に取得 (Round 1 §9 反映: ピーク測定強化):

```python
import psutil

def measure_peak_rss_mb(pool_pids: set[int] | None = None) -> dict[str, float]:
    """main + (指定 pool worker のみの) RSS ピークを記録。

    Round 2 §3 Warning 反映: children(recursive=True) は他用途で起動した
    子プロセスを含む可能性があるため、`pool_pids` で worker pool プロセスを
    明示指定すれば `ga_worker_*` 指標として絞り込める。指定なしの場合は
    全 children を `all_children_*` 指標として記録 (意味の混同を避ける)。

    Returns:
        {
            "main_rss_mb": float,
            "ga_worker_max_rss_mb": float,         # pool_pids 指定時のみ非ゼロ
            "ga_worker_total_rss_mb": float,       # 同上
            "n_ga_workers": int,                   # 同上
            "all_children_max_rss_mb": float,      # pool_pids 未指定時のみ非ゼロ
            "all_children_total_rss_mb": float,    # 同上
            "n_all_children": int,                 # 同上
        }
    """
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
        "n_ga_workers": len(ga_worker_rss),
        "all_children_max_rss_mb": max(all_child_rss, default=0.0),
        "all_children_total_rss_mb": sum(all_child_rss),
        "n_all_children": len(all_child_rss),
    }

# pool worker pids は GenomeEvaluator.pool_pids -> set[int] プロパティで公開。
# 世代毎ピーク追跡: 各世代終了時に measure_peak_rss_mb(evaluator.pool_pids) を呼ぶ。
#
# Round 3 §2 / Round 4 §2 Warning: pid stale 対策 + private API fallback
@property
def pool_pids(self) -> set[int]:
    """worker process pid を **getter 呼び出し時点で動的取得**。

    Round 3 §2: maxtasksperchild=None (Phase 2 default) では起動時 pid と一致するが、
    将来有限化した場合に stale pid を返さないことを契約として保証。

    Round 4 §2: `multiprocessing.pool.Pool._pool` は CPython private API。
    Python 3.13 では存在するが、将来変更されるリスクに備え以下のフォールバック:
    - try-except AttributeError で握り潰し空集合返却 + warning ログ
    - 失敗時は measure_peak_rss_mb(pool_pids=None) 経路で `all_children_*` 指標を使う
    """
    if self._pool is None:
        return set()
    try:
        return {p.pid for p in self._pool._pool if p.pid is not None}
    except AttributeError:
        logger.warning(
            "parallel_eval.pool_pids_unavailable: "
            "multiprocessing.pool.Pool._pool not accessible, "
            "falling back to all_children_* metrics"
        )
        return set()
```

**起動時 max_workers 自動抑制ガード** (Round 1 §9 反映 + Round 2 §4 Warning: strict mode 追加):

```python
# run_ga.py main() の GenomeEvaluator 構築直前
import psutil
available_mb = psutil.virtual_memory().available / 1024 / 1024
worker_budget_mb = available_mb - 4096  # main 400MB + OS マージン 4GB
recommended_max = max(1, int(worker_budget_mb // 400))
if cfg.ga.max_workers > recommended_max:
    logger.warning(
        "run_ga.max_workers_exceeds_memory_budget",
        requested=cfg.ga.max_workers,
        recommended=recommended_max,
        available_mb=available_mb,
    )
    if args.strict_memory_guard:  # 新規 CLI flag --strict-memory-guard
        raise SystemExit(
            f"strict-memory-guard: max_workers={cfg.ga.max_workers} > "
            f"recommended {recommended_max} (available_mb={available_mb:.0f})"
        )
    # 既定: warning のみ。autopilot などで明示的に opt-in する場合のみ fail-fast
```

CLI flag 追加 (施策 4 と統合):
```python
p.add_argument(
    "--strict-memory-guard",
    action="store_true",
    help="max_workers が memory budget を超えたら起動時 fail-fast (autopilot 等推奨)",
)
```

**summary schema 追記方針** (Round 2 §3 / Round 4 §4 反映):
既存契約は **追加 field のみ** で破壊的変更なし。strict schema consumer 用に `summary.json` の最上位 `schema_version` を bump:

| 現行値 | 新値 | 変更内容 |
|---|---|---|
| `"2.0"` (実装時に確認) | `"2.1"` | `per_generation[*]` に `stage_*_seconds_total` / `stage_*_seconds_max` / `peak_rss_mb_per_worker` 追加 / 最上位に `max_rss_mb_per_worker` (run 全体最大) 追加 |

下位互換性: consumer 側は未知 field を無視する義務 (`additionalProperties: true` 方針を `docs/alpha_factory/runbook.md` に明記)。
**実装時にまず `summary.json` の現行 schema_version を grep で確認** し、本 TODO の commit で minor bump (`"X.Y" → "X.(Y+1)"`) を行う。

### 現行コード
[run_ga.py:_write_reports](../../scripts/alpha_factory/run_ga.py#L760)

### テスト計画
- [x] `tests/scripts/test_run_ga_summary_schema.py`:
  - summary.json に `stage_a_seconds_total` 等の新 field が存在
  - 既存 field (`run_id`, `dataset`, `ga_config` 等) が保持されている (regression)

### リスク
- `psutil` は既に依存にある想定 (要確認、なければ `uv add psutil` 必要)
- per-stage timing 集計は **L1/L2 決定論性に影響しない** (artifact field なので summary level)

---

## 施策 6: テスト

### 変更箇所
- 新規: `tests/alpha_factory/test_parallel_eval.py` (施策 1 のテスト)
- 新規: `tests/scripts/test_run_ga_parallel.py` (同値性テスト)
- 修正: `tests/alpha_factory/test_swim_lane.py` (evaluator 経由のケース追加)
- 修正: `tests/scripts/test_run_ga_cli.py` (CLI 引数テスト)

### 同値性テスト (`test_run_ga_parallel.py`) の詳細

```python
"""GA 並列実行の決定論性 (L1 selection / L2 row-order) 同値性テスト."""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def small_run_config(tmp_path):
    """小さな fixture (population=8, generations=2, seed=42) を yaml に書き出す."""
    cfg = REPO_ROOT / "config/alpha_factory/default.yaml"
    raw = cfg.read_text(encoding="utf-8")
    # population_size / generations / seed を override
    # (本物の YAML 編集はテスト fixture util で安全に)
    out = tmp_path / "test_config.yaml"
    out.write_text(raw, encoding="utf-8")  # 簡略化、実際は population=8 等に書換
    return out


def _run_ga(config_path, max_workers, run_id):
    cmd = [
        "uv", "run", "python", "scripts/alpha_factory/run_ga.py",
        "--config", str(config_path),
        "--run-id", run_id,
        "--population-size", "8",
        "--generations", "2",
        "--seed", "42",
        "--max-workers", str(max_workers),
    ]
    res = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return res


# 数値 column のみ (L2 contract)
NUMERIC_COLUMNS = [
    "fitness", "fitness_pen", "sharpe", "total_pnl", "max_drawdown",
    "trade_count", "stage_a_passed", "stage_b_passed", "stage_c_passed",
    "live_criteria_passed", "cross_pair_passed",
]


def test_parallel_evaluation_preserves_selection_determinism(small_run_config):
    """L1: max_workers=1 と max_workers=4 で best_name / fitness_pen が一致."""
    _run_ga(small_run_config, 1, "test_seq")
    _run_ga(small_run_config, 4, "test_par")

    seq_summary = json.loads(
        (REPO_ROOT / "reports/run-reports/run-X-seq/summary.json").read_text()
    )
    par_summary = json.loads(
        (REPO_ROOT / "reports/run-reports/run-X-par/summary.json").read_text()
    )

    assert seq_summary["best"]["name"] == par_summary["best"]["name"]
    assert seq_summary["best"]["fitness"] == par_summary["best"]["fitness"]
    assert (
        seq_summary["live_criteria_passed"]
        == par_summary["live_criteria_passed"]
    )


def test_parallel_evaluation_preserves_row_order_determinism(small_run_config):
    """L2: archive Parquet 数値 column が (lane_id, generation, genome_name) 一致."""
    _run_ga(small_run_config, 1, "test_seq")
    _run_ga(small_run_config, 4, "test_par")

    seq_arch = pd.read_parquet(REPO_ROOT / ".cache/.../seq.parquet")
    par_arch = pd.read_parquet(REPO_ROOT / ".cache/.../par.parquet")

    sort_keys = ["lane_id", "generation", "genome_name"]
    seq_sorted = seq_arch.sort_values(sort_keys).reset_index(drop=True)
    par_sorted = par_arch.sort_values(sort_keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        seq_sorted[sort_keys + NUMERIC_COLUMNS],
        par_sorted[sort_keys + NUMERIC_COLUMNS],
    )
```

### 単体テスト (`test_parallel_eval.py`) の詳細

```python
"""parallel_eval module の単体テスト."""

import multiprocessing
import pickle
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.alpha_factory.parallel_eval import (
    GenomeEvalError,
    GenomeEvaluator,
    GenomeStageResult,
    LaneEvalContext,
    _classify_exception,
    _to_error_result,
    evaluate_genome,
)


def test_classify_exception_maps_linalg_to_fixed_code():
    err = _classify_exception(np.linalg.LinAlgError("foo"), "A")
    assert err.error_code == "BACKTEST_LINALG_ERROR"
    assert err.fixed_message == "linalg numerical error"
    assert err.stage == "A"


def test_classify_exception_maps_memory_error_to_oom():
    err = _classify_exception(MemoryError(), "C")
    assert err.error_code == "WORKER_OOM"


def test_classify_exception_maps_runtime_primitive_to_lookup_fail():
    err = _classify_exception(RuntimeError("primitive xyz not found"), "A")
    assert err.error_code == "PRIMITIVE_LOOKUP_FAIL"


def test_classify_exception_maps_value_stage_b_to_fold_invalid():
    err = _classify_exception(ValueError("stage_b fold issue"), "B")
    assert err.error_code == "STAGE_B_FOLD_INVALID"


def test_classify_exception_unclassified_default():
    err = _classify_exception(TypeError("random"), "A")
    assert err.error_code == "WORKER_UNCLASSIFIED"


def test_classify_exception_does_not_swallow_keyboard_interrupt():
    with pytest.raises(KeyboardInterrupt):
        _classify_exception(KeyboardInterrupt(), "A")


def test_lane_eval_context_bars_are_tuples():
    """frozen 担保 — bars_a が tuple 型であること."""
    ctx = LaneEvalContext(
        lane_id="tier1_X", bars_a=tuple(),
        bars_b=tuple(), bars_holdout=tuple(),
        meta=MagicMock(), bt_cfg=MagicMock(), cp_inputs=None,
    )
    assert isinstance(ctx.bars_a, tuple)


def test_lane_eval_context_is_picklable_with_real_objects():
    """worker への配布前提として pickle 可能."""
    # 実 PriceBar / InstrumentMeta / BacktestConfig fixture を使う
    # ... (省略)
    # data = pickle.dumps(ctx)
    # restored = pickle.loads(data)
    # assert restored == ctx (frozen dc なので __eq__ で OK)


def test_genome_evaluator_max_workers_1_uses_inproc():
    """max_workers=1 では pool を生成しない."""
    evaluator = GenomeEvaluator(
        max_workers=1,
        stage_gate_cfg=MagicMock(),
        cross_pair_cfg=MagicMock(),
        prim_evaluator=MagicMock(),
        lane_contexts={},
    )
    assert evaluator._pool is None
    evaluator.close()


def test_genome_evaluator_context_manager_close_on_normal_exit():
    """正常終了時 pool.close() が呼ばれる (terminate ではない)."""
    # MagicMock pool で確認
    # ... (詳細省略)


def test_genome_evaluator_context_manager_terminate_on_exception():
    """例外伝播時 pool.terminate() が呼ばれる."""
    # ... (詳細省略)


def test_evaluate_population_returns_results_in_population_order():
    """L2 contract: pool.map は入力順保持."""
    # mock evaluate_genome で genome.name → result.genome_name を入れて確認
    # max_workers=2 で実 multiprocessing.Pool 起動 (slow test)
    # @pytest.mark.slow でマーク


def test_evaluate_population_propagates_worker_errors_via_GenomeEvalError():
    """worker 内例外 → GenomeStageResult.error が non-None."""
    # ...
```

### Round 1 detailed-review 反映追加テスト

**1. 反復一致テスト (§1 Critical 対応)**:
```python
@pytest.mark.parametrize("max_workers", [1, 2, 6])
def test_evaluation_is_deterministic_across_repetitions(max_workers, fixture_population):
    """同 worker 数で 2 回実行して GenomeStageResult.stage_a.metrics["fitness_pen"]
    が完全一致 (RNG seed が固定されていることの証明)."""
    eval1 = GenomeEvaluator(max_workers, ...)
    eval2 = GenomeEvaluator(max_workers, ...)
    r1 = eval1.evaluate_population("tier1_X", 0, fixture_population)
    r2 = eval2.evaluate_population("tier1_X", 0, fixture_population)
    eval1.close(); eval2.close()
    for a, b in zip(r1, r2):
        assert a.stage_a.metrics["payload"]["fitness_pen"] == b.stage_a.metrics["payload"]["fitness_pen"]


@pytest.mark.parametrize("max_workers", [2, 6])
def test_parallel_matches_sequential_for_same_seed(max_workers, fixture_population):
    """L1 selection: max_workers=1 と max_workers=N で fitness_pen 完全一致."""
    eval_seq = GenomeEvaluator(1, ...)
    eval_par = GenomeEvaluator(max_workers, ...)
    r_seq = eval_seq.evaluate_population("tier1_X", 0, fixture_population)
    r_par = eval_par.evaluate_population("tier1_X", 0, fixture_population)
    eval_seq.close(); eval_par.close()
    for s, p in zip(r_seq, r_par):
        assert s.genome_name == p.genome_name  # 順序一致
        assert s.stage_a.passed == p.stage_a.passed
        # 数値 column 完全一致 (§4.7 NUMERIC_COLUMNS)
        for key in ("fitness", "fitness_pen", "trade_count"):
            assert s.stage_a.metrics["payload"].get(key) == p.stage_a.metrics["payload"].get(key)
```

**2. preflight_underfilled 短絡テスト (§2 Critical 対応)**:
```python
def test_evaluate_genome_short_circuits_when_preflight_underfilled():
    """preflight_underfilled=True の context で Stage A pass 後 Stage B が呼ばれない."""
    ctx = LaneEvalContext(..., preflight_underfilled=True, preflight_payload={...})
    mock_evaluate_b = MagicMock()
    monkeypatch.setattr("src.alpha_factory.parallel_eval.evaluate_stage_b", mock_evaluate_b)
    result = evaluate_genome(genome_passing_a, ctx, ...)
    assert result.stage_a.passed
    assert result.stage_b is None
    mock_evaluate_b.assert_not_called()


def test_collect_results_synthesizes_preflight_b_for_passed_a_genomes(...):
    """LaneManager._build_preflight_b_result が呼ばれ、archive.collect_stage_b に
    reason_codes=('stage_b_pre_flight_underfilled',) で渡される."""
```

**3. 世代番号スナップショット固定テスト (§3 Warning 対応)**:
```python
def test_collect_uses_snapshotted_generation_index_not_lane_counter():
    """collect ループ中に lane.generation_count が変動しても archive collect の
    引数 generation は冒頭スナップショット値で固定される."""
    # lane.generation_count を mock で「途中で +1 される」ように仕込み、
    # archive.collect_stage_a の call_args の generation が全て同じ値であることを assert
```

**4. RegistryEvaluator picklability テスト (§5 Warning 対応)**:
```python
def test_registry_evaluator_picklable_with_empty_aux():
    evaluator = RegistryEvaluator(pair="EUR_JPY")
    data = pickle.dumps(evaluator)
    restored = pickle.loads(data)
    assert restored._pair == "EUR_JPY"


def test_registry_evaluator_picklable_with_aux_pair_bars(fixture_aux_pair_bars):
    evaluator = RegistryEvaluator(pair="EUR_JPY", aux_pair_bars=fixture_aux_pair_bars)
    data = pickle.dumps(evaluator)
    restored = pickle.loads(data)
    assert "USD_JPY" in restored._aux_pair_bars
```

**5. 例外網羅性 fallback テスト (§7 Warning 対応)**:
```python
def test_classify_exception_to_unclassified_for_arrow_invalid():
    """到達不能と想定する pyarrow.lib.ArrowInvalid が万一来た場合、
    WORKER_UNCLASSIFIED に集約される (fallback の安全網)."""
    from pyarrow.lib import ArrowInvalid
    err = _classify_exception(ArrowInvalid("test"), "A")
    assert err.error_code == "WORKER_UNCLASSIFIED"


def test_classify_exception_to_unclassified_for_pandas_empty():
    from pandas.errors import EmptyDataError
    err = _classify_exception(EmptyDataError("test"), "B")
    assert err.error_code == "WORKER_UNCLASSIFIED"
```

**5b. 全段カバレッジ強化 (Round 2 §4 Warning 対応)**:
```python
@pytest.mark.parametrize("max_workers", [1, 2])
def test_parallel_matches_sequential_full_stage_results(max_workers, fixture_population):
    """Stage A/B/C 全段の StageResult と reason_codes を比較 (正規化ハッシュ)."""
    eval_seq = GenomeEvaluator(1, ...)
    eval_par = GenomeEvaluator(max_workers, ...)
    r_seq = eval_seq.evaluate_population("tier1_X", 0, fixture_population)
    r_par = eval_par.evaluate_population("tier1_X", 0, fixture_population)
    eval_seq.close(); eval_par.close()
    for s, p in zip(r_seq, r_par):
        assert s.genome_name == p.genome_name
        # Stage A
        assert _normalize_stage_result(s.stage_a) == _normalize_stage_result(p.stage_a)
        # Stage B (None なら両方 None)
        assert _normalize_stage_result(s.stage_b) == _normalize_stage_result(p.stage_b)
        # Stage C
        assert _normalize_stage_result(s.stage_c) == _normalize_stage_result(p.stage_c)
        # cross_pair
        assert s.cross_pair == p.cross_pair  # frozen dc → __eq__ で OK


def _normalize_stage_result(r):
    """L3 timing 系を除外した正規化 hash."""
    if r is None:
        return None
    payload = dict(r.metrics.get("payload", {}))
    return (r.stage, r.passed, tuple(r.reason_codes), tuple(sorted(
        (k, v) for k, v in payload.items()
        if k not in ("wall_time_seconds",)  # L3 除外 (§4.7)
    )))
```

**5c. preflight Stage B mock 呼び出し検証 (Round 2 Suggestion 対応)**:
```python
def test_evaluate_genome_does_not_call_stage_b_when_preflight_underfilled(monkeypatch):
    """preflight 短絡時 evaluate_stage_b が呼ばれないことを spy で確認."""
    spy = MagicMock(side_effect=AssertionError("Stage B should not be called"))
    monkeypatch.setattr("src.alpha_factory.parallel_eval.evaluate_stage_b", spy)
    ctx = LaneEvalContext(..., preflight_underfilled=True, preflight_payload=PreflightPayload(...))
    evaluate_genome(genome_passing_a, ctx, ...)
    spy.assert_not_called()
```

**5d. LaneEvalContext 不変性テスト (Round 2 §1 Critical 対応)**:
```python
def test_lane_eval_context_rejects_list_bars():
    """tuple 以外の bars を渡したら TypeError (assert ではなく raise)."""
    with pytest.raises(TypeError, match="bars_a must be tuple"):
        LaneEvalContext(
            lane_id="x", bars_a=[],  # list 渡し
            bars_b=tuple(), bars_holdout=tuple(),
            meta=MagicMock(), bt_cfg=MagicMock(),
        )


def test_lane_eval_context_rejects_dict_cp_inputs():
    """旧 dict 形式の cp_inputs を渡したら TypeError."""
    with pytest.raises(TypeError, match="cp_inputs must be CrossPairLaneInputs"):
        LaneEvalContext(
            lane_id="x", bars_a=tuple(), bars_b=tuple(), bars_holdout=tuple(),
            meta=MagicMock(), bt_cfg=MagicMock(),
            cp_inputs={"target_pair": "EUR_JPY"},  # dict ではダメ
        )


def test_lane_eval_context_preflight_payload_required_when_underfilled():
    with pytest.raises(ValueError, match="preflight_payload must be set"):
        LaneEvalContext(
            lane_id="x", bars_a=tuple(), bars_b=tuple(), bars_holdout=tuple(),
            meta=MagicMock(), bt_cfg=MagicMock(),
            preflight_underfilled=True,
        )
```

**5e. cp_inputs pickle サイズ計測 (Round 2 §3 / Round 3 §2 反映: 相対閾値併用)**:
```python
def test_lane_eval_context_pickle_size_within_budget():
    """cp_inputs を含む LaneEvalContext の pickle サイズが
    予算 (絶対閾値 200MB AND baseline の 1.5 倍以内) に収まる.

    Round 3 §5: 環境依存 flaky 化を防ぐため絶対値 + 相対値併用."""
    baseline_ctx = LaneEvalContext(  # cp_inputs なし版
        lane_id="tier1_EUR_JPY",
        bars_a=tuple(fixture_bars(60 * 1440)),
        bars_b=tuple(fixture_bars(180 * 1440)),
        bars_holdout=tuple(fixture_bars(60 * 1440)),
        meta=fixture_meta(), bt_cfg=fixture_bt_cfg(),
    )
    full_ctx = replace(baseline_ctx, cp_inputs=fixture_cross_pair_lane_inputs())
    baseline_mb = len(pickle.dumps(baseline_ctx)) / 1024 / 1024
    full_mb = len(pickle.dumps(full_ctx)) / 1024 / 1024
    assert full_mb < 200, f"absolute budget exceeded: {full_mb:.1f}MB"
    assert full_mb < baseline_mb * 1.5, (
        f"cp_inputs overhead too large: {full_mb:.1f}MB vs baseline {baseline_mb:.1f}MB"
    )
```

**5f. Mapping 実体凍結テスト (Round 3 §1 Critical 対応)**:
```python
def test_cross_pair_lane_inputs_immutable_against_external_dict_mutation():
    """生成元 dict を外部から変更しても CrossPairLaneInputs が不変であること."""
    src_pair_bars = {"USD_JPY": list(fixture_bars(100))}
    src_meta = {"USD_JPY": fixture_meta()}
    cp_inputs = CrossPairLaneInputs(
        target_pair="EUR_JPY",
        pair_bars_map=src_pair_bars,
        meta_map=src_meta,
    )
    # 元 dict を変更 (defensive copy 失敗ならテストが落ちる)
    src_pair_bars["EUR_USD"] = []
    src_pair_bars["USD_JPY"].append(fixture_bars(1)[0])
    src_meta["NEW"] = fixture_meta()
    # cp_inputs は影響を受けない
    assert "EUR_USD" not in cp_inputs.pair_bars_map
    assert len(cp_inputs.pair_bars_map["USD_JPY"]) == 100  # tuple 化済 + value defensive copy
    assert "NEW" not in cp_inputs.meta_map


def test_cross_pair_lane_inputs_pair_bars_map_is_mappingproxy():
    """pair_bars_map / meta_map が MappingProxyType (item 追加不可)."""
    cp_inputs = CrossPairLaneInputs(
        target_pair="EUR_JPY",
        pair_bars_map={"USD_JPY": (fixture_bars(1)[0],)},
        meta_map={"USD_JPY": fixture_meta()},
    )
    with pytest.raises(TypeError):
        cp_inputs.pair_bars_map["XXX"] = ()  # MappingProxyType は item assignment 不可
    with pytest.raises(TypeError):
        cp_inputs.meta_map["XXX"] = fixture_meta()
```

**5h. pickle round-trip テスト (Round 4 §1 Critical / §3 反映: 必須)**:
```python
def test_lane_eval_context_pickle_round_trip_preserves_immutability():
    """LaneEvalContext (cp_inputs 含む) を pickle/unpickle した後も:
    - 値が完全一致 (frozen dc __eq__)
    - 内部 mappingproxy が再構築されている (深い不変性復元)
    - 復元後の context が pool initializer 経由で worker に届けられる前提を満たす
    """
    cp = CrossPairLaneInputs(
        target_pair="EUR_JPY",
        pair_bars_map={"USD_JPY": (fixture_bars(1)[0],)},
        meta_map={"USD_JPY": fixture_meta()},
    )
    ctx = LaneEvalContext(
        lane_id="tier1_EUR_JPY",
        bars_a=tuple(fixture_bars(10)),
        bars_b=tuple(fixture_bars(10)),
        bars_holdout=tuple(fixture_bars(10)),
        meta=fixture_meta(),
        bt_cfg=fixture_bt_cfg(),
        cp_inputs=cp,
    )
    blob = pickle.dumps(ctx)
    restored = pickle.loads(blob)
    # 値一致
    assert restored == ctx  # frozen dc __eq__
    # mappingproxy 復元
    from types import MappingProxyType
    assert isinstance(restored.cp_inputs.pair_bars_map, MappingProxyType)
    assert isinstance(restored.cp_inputs.meta_map, MappingProxyType)
    # 復元後も外部変更を受け付けない
    with pytest.raises(TypeError):
        restored.cp_inputs.pair_bars_map["X"] = ()


def test_cross_pair_lane_inputs_picklable_directly():
    """CrossPairLaneInputs 単体でも pickle round-trip が成功する."""
    cp = CrossPairLaneInputs(
        target_pair="EUR_JPY",
        pair_bars_map={"USD_JPY": (fixture_bars(1)[0],)},
        meta_map={"USD_JPY": fixture_meta()},
    )
    restored = pickle.loads(pickle.dumps(cp))
    assert restored == cp
```

**5i. _build_preflight_b_result invariant violation テスト (Round 4 §2 反映)**:
```python
def test_build_preflight_b_result_raises_when_payload_missing():
    """preflight_payload=None の context を渡したら RuntimeError (invariant violation)."""
    lane_manager = LaneManager(...)
    ctx_without_payload = LaneEvalContext(
        ..., preflight_underfilled=False, preflight_payload=None,
    )
    with pytest.raises(RuntimeError, match="invariant violation"):
        lane_manager._build_preflight_b_result(fixture_genome(), ctx_without_payload)
```

**5j. pool_pids fallback テスト (Round 4 §2 反映)**:
```python
def test_pool_pids_returns_empty_set_when_pool_internal_attr_missing(monkeypatch, caplog):
    """multiprocessing.Pool._pool が将来削除されても空集合返却 + warning."""
    evaluator = GenomeEvaluator(max_workers=2, ...)
    # _pool 属性を一時的に削除して fallback 経路を発火
    original_pool = evaluator._pool
    monkeypatch.delattr(original_pool, "_pool", raising=False)
    pids = evaluator.pool_pids
    assert pids == set()
    assert "pool_pids_unavailable" in caplog.text
    evaluator.close()
```

**5g. worker pid 更新時 RSS 集計テスト (Round 3 §5 Suggestion 対応)**:
```python
def test_measure_peak_rss_uses_current_pool_pids_not_stale():
    """maxtasksperchild 等で worker process が再起動された場合でも
    measure_peak_rss_mb が最新 pid 集合で集計する (stale pid を使わない)."""
    evaluator = GenomeEvaluator(max_workers=2, ...)
    initial_pids = set(evaluator.pool_pids)
    # ... 何世代か実行して worker 再起動 (maxtasksperchild=1 fixture) ...
    later_pids = set(evaluator.pool_pids)
    # Phase 2 default は無限 maxtasksperchild なので initial == later
    # ただし getter が動的取得していることをテスト fixture (maxtasksperchild=1) で検証
    assert isinstance(later_pids, set)
    assert all(isinstance(p, int) for p in later_pids)
    evaluator.close()
```

**6. メモリ運用ガード測定テスト (§9 Warning 対応)**:
```python
def test_measure_peak_rss_returns_main_and_children():
    """measure_peak_rss_mb() が main / max_per_worker / total を返す."""
    result = measure_peak_rss_mb()
    assert "main_rss_mb" in result
    assert "max_rss_mb_per_worker" in result
    assert result["main_rss_mb"] > 0


def test_max_workers_exceeds_memory_budget_logs_warning(caplog):
    """available_mem に対して過剰な max_workers 指定で warning ログ."""
    # cfg.ga.max_workers = 100 で実行、warning が出ることを確認
```

### 既存テスト regression
- `tests/alpha_factory/test_swim_lane.py`: `LaneManager(genome_evaluator=None)` で legacy path、現行と同じ動作

### テスト命名規則
- `test_{module}_{behavior}` 形式
- Run 名・日付・session 固有名は禁止
- 例: ✅ `test_classify_exception_maps_linalg_to_fixed_code` / ❌ `test_run_42_works`

---

## 施策 7: docs / AGENTS.md / runbook 反映

### 変更箇所
- 修正: `docs/alpha_factory/runbook.md` (新節「並列実行」)
- 修正: `docs/alpha_factory/swim-lane.md` (LaneManager evaluator 経由化を追記)
- 修正: `AGENTS.md` (運用コマンド例に `--max-workers` 追加)

### 波及変更マトリクス

| ファイル | 追記内容 |
|---|---|
| `docs/alpha_factory/runbook.md` | 「GA 並列実行」節: `--max-workers N` の使い方 / max_rss 70% 閾値運用 / 1 worker 試算 / autopilot は default=1 維持 |
| `docs/alpha_factory/swim-lane.md` | `LaneManager.__init__` に `genome_evaluator` 引数追加。並列モード時の決定論性契約 (L1/L2/L3) 簡潔説明 |
| `AGENTS.md` | 運用節に「`uv run python scripts/alpha_factory/run_ga.py --max-workers 4`」のコマンド例。デフォルトは sequential であることを明記 |
| `config/alpha_factory/default.yaml` | 施策 3 で対応済 |

### テスト計画
- docs は手動レビュー (ユーザー承認)。skill 由来の自動 doc check は対象外

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **incremental** |
| 判断根拠 | (1) `LaneManager.__init__` に新引数追加するが default=None で後方互換 / (2) `GenomeEvaluator` は新規モジュール = 既存コードに影響なし / (3) 各施策が独立してテスト可能 / (4) 段階的にマージできる (parallel_eval 単体 → swim_lane 経由化 → run_ga 統合) |
| 競合リスク | 同時走行する他の TODO で `swim_lane.py` を触っているものがないか確認 (実装直前に `git log --since='1 week'` で確認) |
| 想定実装時間 | 中 (2-3 セッション程度) — 施策 1 と施策 6 のテストが大半 |

### 実装順序

1. **施策 1**: `parallel_eval.py` 新設 + 単体テスト (in-process 経路のみ確認)
2. **施策 3**: `GAConfig.max_workers` + YAML + config テスト
3. **施策 2**: `LaneManager` evaluator 経由化 (genome_evaluator=None で legacy path 維持)
   - **チェックポイント (Round 2 Suggestion)**: 施策 2 完了時点で **直列回帰テスト一式** を pass させ git commit。「並列導入で壊れた」のか「LaneManager 改修で壊れた」のかを後段で切り分けやすくする
4. **施策 4**: `run_ga.py` CLI + LaneEvalContext 構築 + with 文統合
5. **施策 5**: summary.json 追加 field
6. **施策 6**: 同値性テスト (max_workers=1 vs 4)
7. **施策 7**: docs / AGENTS.md 更新

各施策ごとに `uv run pytest` / `ruff check` / `mypy` を pass させてから次へ。
