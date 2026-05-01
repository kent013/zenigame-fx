"""T068: Failure handling (NaN/Inf/crash → infeasible + run abort).

synthesis § 7.7 確定式の単一実装.

詳細:

- 概念設計: ``devnotes/20260430-1430-todo-T068-failure-handling/conceptual-design.md``
- 詳細設計: ``devnotes/20260430-1430-todo-T068-failure-handling/detailed-design.md``
- T061 / T062 / T064 evaluator の wrapper 提供
- :class:`EvaluationOutcome` で ``should_skip_downstream`` を caller に伝達
- stage-local :class:`FailureSummary` + :func:`decide_run_abort` で synthesis § 7.7 厳密準拠
- ``mission_signed_margin = -inf`` 等の T062 sentinel と整合 (§ 8.4 invariant)

設計判断:

- :class:`ValueError` → ``contract_violation`` / その他 :class:`Exception` →
  ``exception_raised`` の 2 段 catch
- BaseException 系 (:class:`SystemExit` / :class:`KeyboardInterrupt` /
  :class:`GeneratorExit` / :class:`asyncio.CancelledError`) は Python 標準動作で
  ``except Exception`` に捕捉されず透過する (Python 3.13 でも
  :class:`asyncio.CancelledError` は :class:`BaseException` 直接継承).
- ``exception_message`` は :data:`EXCEPTION_MESSAGE_MAX_LENGTH` (500) 文字切詰め.
- :class:`FailureSummary` は **stage-local** (``eligible_count`` を分母).
- abort 判定は ``n_failed_genomes`` (一意 genome) ベース、 record 数では判定しない.

Phase 1 (本 TODO = T068 PR 1): 単体実装 + テストのみ、 GA / archive 配線未変更.
T068 PR 1 単独 merge で runtime に影響なし (新規 module で他 module から import されない).

Phase 2 (別 PR): T065/T066/T067 + ``run_ga.py`` + T071 と同時、 8 箇所同時更新
(詳細設計 § Phase 2 申し送り参照).

ファイル配置規範:
    詳細設計は ``src/alpha_factory/ga/failure_handling.py`` (= ga/ subdir) を指定する
    が、 既存 ``src/alpha_factory/`` は flat module 構成 (= ga/ subdir 不存在).
    ファイル配置規範 (= 既存 flat module との一貫性優先) に従い flat 配置
    ``src/alpha_factory/failure_handling.py`` を採用 (T065 ``nsga2_selection.py`` /
    T066 ``cpps_archive.py`` / T067 ``loop_closure.py`` と同方針).

References:

- synthesis § 7.7
- zenigame ``ga/nsga2/core.py:1026-1095``
"""

from __future__ import annotations

import math
import types
import typing
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Generic, Literal, TypeVar

from src.alpha_factory.canonical_metrics import (
    CanonicalFiveResult,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBucket,
)
from src.alpha_factory.mission_inf_gap import MissionGapResult
from src.alpha_factory.stage_bc_evaluator import (
    BCEvaluationResult,
    MissionFailReason,
    SampleSizeFlag,
    StageBResult,
    StageCLiteResult,
    StageCResult,
    StagePassStatus,
)

__all__ = [
    "DEGRADED_LOG_PF_CLIP_FLOOR",
    "EXCEPTION_MESSAGE_MAX_LENGTH",
    "EvaluationOutcome",
    "FailureReason",
    "FailureRecord",
    "FailureSummary",
    "RunFailureSummary",
    "StageType",
    "aggregate_failures",
    "build_degraded_bc_result",
    "build_degraded_canonical_five",
    "build_degraded_mission_gap",
    "build_run_failure_summary",
    "decide_run_abort",
    "evaluate_bc_safe",
    "evaluate_canonical_five_safe",
    "evaluate_mission_inf_gap_safe",
    "validate_finite_bc_result",
    "validate_finite_canonical_five",
    "validate_finite_mission_gap",
    "validate_state_invariant_bc_result",
    "validate_state_invariant_canonical_five",
    "validate_state_invariant_mission_gap",
]


# ============================================================================
# Constants + Type aliases
# ============================================================================

EXCEPTION_MESSAGE_MAX_LENGTH: Final[int] = 500
"""構造化ログ肥大化防止. 例外 message は本上限で切詰め (Python str slice = code point 単位)."""

DEGRADED_LOG_PF_CLIP_FLOOR: Final[float] = -2.0
"""T061 :data:`~src.alpha_factory.canonical_metrics.LOG_PF_CLIP_RANGE` 下限と一致.

degraded 個体の ``log_pf_clip`` 既定値.
"""

StageType = Literal[
    "canonical_five",
    "mission_inf_gap",
    "bc_eval",
    "stage_a",
    "stage_b",
    "stage_c_lite",
    "stage_c",
]
"""failure handling 対象の stage 識別子.

各 wrapper の ``stage`` 引数として該当 stage のみ指定すること:

- :func:`evaluate_canonical_five_safe`: ``"canonical_five"`` / ``"stage_a"`` /
  ``"stage_b"`` / ``"stage_c_lite"`` / ``"stage_c"``
- :func:`evaluate_mission_inf_gap_safe`: ``"mission_inf_gap"``
- :func:`evaluate_bc_safe`: ``"bc_eval"``

実装層では Python 型システム制約で Literal 厳密制限は緩めるが、 caller が誤った
stage を渡した場合の検出は test (sub-suite 2.11) で cardinality 検証する.
"""


FailureReason = Literal[
    "exception_raised",
    "contract_violation",
    "non_finite_detected",
    "state_inconsistency",
]
"""failure reason taxonomy (詳細設計 § 設計判断 D4 / D7).

- ``"exception_raised"``: 一般 :class:`Exception` (backtest crash 等)
- ``"contract_violation"``: :class:`ValueError` (T065-T067 入口契約違反)
- ``"non_finite_detected"``: :func:`validate_finite_*` 検出の NaN/Inf
- ``"state_inconsistency"``: :func:`validate_state_invariant_*` 検出の § 8.4 invariant 違反
"""


T = TypeVar("T")


# ============================================================================
# dataclasses (frozen=True、 全 immutable)
# ============================================================================


@dataclass(frozen=True)
class FailureRecord:
    """per-individual / per-stage の失敗メタデータ (immutable).

    fields:

    - ``genome_id``: 個体 genome ID (caller 側で T065/T066/T067 と一致責務)
    - ``run_id``: 評価対象 run ID
    - ``generation_no``: 世代番号 (>=0)
    - ``stage``: :data:`StageType` (発生 stage)
    - ``failure_reason``: :data:`FailureReason`
    - ``exception_class``: 例外クラス名 (reason=``"exception_raised"`` /
      ``"contract_violation"`` 時のみ非 None)
    - ``exception_message``: 切詰め済み message (同上)
    - ``detected_field``: NaN/Inf 検出 field 名 (reason=``"non_finite_detected"`` 時のみ非 None)
    - ``detected_value``: NaN/Inf 値 (同上)
    - ``exception_fingerprint``: dedup / 監査用 key (全 reason で非 None)
    """

    genome_id: str
    run_id: str
    generation_no: int
    stage: StageType
    failure_reason: FailureReason
    exception_class: str | None
    exception_message: str | None
    detected_field: str | None
    detected_value: float | None
    exception_fingerprint: str | None


@dataclass(frozen=True)
class FailureSummary:
    """**stage-local** 失敗集計 (詳細 Round 1 [C1] / [C2] 反映).

    ``stage`` 単位で集計し、 abort 判定 (:func:`decide_run_abort`) は ``all_failed``
    で行う. ``failures_by_reason`` は Mapping protocol (実体 :class:`MappingProxyType`).
    """

    stage: StageType
    eligible_individuals: int
    n_failure_records: int
    n_failed_genomes: int
    n_succeeded_genomes: int
    all_failed: bool
    failed_genome_ids: tuple[str, ...]
    failures_by_reason: Mapping[str, int]
    failure_rate: float


@dataclass(frozen=True)
class RunFailureSummary:
    """per-Run 横断 monitor (各 stage の :class:`FailureSummary` 集約).

    abort 判定は per-stage で実施済、 本 dataclass は observability 用.
    """

    run_id: str
    per_stage_summaries: tuple[FailureSummary, ...]
    any_stage_all_failed: bool


@dataclass(frozen=True)
class EvaluationOutcome(Generic[T]):
    """evaluator wrapper の戻り値統一型 (Round 1 [C3]).

    fields:

    - ``result``: success 時は実 result、 failure 時は degraded result
    - ``failure_record``: success なら ``None``、 failure なら :class:`FailureRecord`
    - ``should_skip_downstream``: failure 時 ``True``. caller (Phase 2 run_loop) は
      本 flag が ``True`` の個体を T065/T066/T067 入力から除外する責務 (§ 10.4 最終契約).
    """

    result: T
    failure_record: FailureRecord | None
    should_skip_downstream: bool


# ============================================================================
# Internal helpers (FailureRecord 構築)
# ============================================================================


def _truncate_exception_message(msg: str) -> str:
    """例外メッセージを :data:`EXCEPTION_MESSAGE_MAX_LENGTH` 文字に切詰め (Unicode safe).

    Python str slice は code point 単位なので、 surrogate pair / 結合文字は壊さない
    (sub-suite 2.11 で検証).
    """
    if len(msg) <= EXCEPTION_MESSAGE_MAX_LENGTH:
        return msg
    return msg[:EXCEPTION_MESSAGE_MAX_LENGTH]


def _make_failure_record(
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,
    *,
    reason: Literal["exception_raised", "contract_violation"],
    exception: BaseException,
) -> FailureRecord:
    """例外由来 :class:`FailureRecord` を構築."""
    exc_class = type(exception).__name__
    exc_msg = _truncate_exception_message(str(exception))
    fingerprint = f"{exc_class}@{stage}:{exc_msg[:80]}"
    return FailureRecord(
        genome_id=genome_id,
        run_id=run_id,
        generation_no=generation_no,
        stage=stage,
        failure_reason=reason,
        exception_class=exc_class,
        exception_message=exc_msg,
        detected_field=None,
        detected_value=None,
        exception_fingerprint=fingerprint,
    )


def _make_failure_record_for_finite(
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,
    *,
    field_name: str,
    field_value: float,
) -> FailureRecord:
    """NaN/Inf 由来 :class:`FailureRecord` を構築."""
    fingerprint = f"non_finite@{stage}:{field_name}"
    return FailureRecord(
        genome_id=genome_id,
        run_id=run_id,
        generation_no=generation_no,
        stage=stage,
        failure_reason="non_finite_detected",
        exception_class=None,
        exception_message=None,
        detected_field=field_name,
        detected_value=field_value,
        exception_fingerprint=fingerprint,
    )


def _make_failure_record_for_state_inconsistency(
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,
    *,
    description: str,
) -> FailureRecord:
    """state invariant 違反 :class:`FailureRecord` を構築."""
    fingerprint = f"state_inconsistency@{stage}:{description[:80]}"
    return FailureRecord(
        genome_id=genome_id,
        run_id=run_id,
        generation_no=generation_no,
        stage=stage,
        failure_reason="state_inconsistency",
        exception_class=None,
        exception_message=_truncate_exception_message(description),
        detected_field=None,
        detected_value=None,
        exception_fingerprint=fingerprint,
    )


# ============================================================================
# evaluator wrappers
# ============================================================================


def evaluate_canonical_five_safe(
    *,
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    **evaluate_kwargs: Any,
) -> EvaluationOutcome[CanonicalFiveResult]:
    """T061 :func:`~src.alpha_factory.canonical_metrics.evaluate_canonical_five` の
    wrap (例外 catch + finite check + invariant check 4 段).

    例外 catch:

    - :class:`ValueError` → ``failure_reason="contract_violation"``
    - その他 :class:`Exception` → ``failure_reason="exception_raised"``
    - :class:`SystemExit` / :class:`KeyboardInterrupt` / :class:`GeneratorExit`
      (:class:`BaseException` 系) は Python 標準動作で ``except Exception`` に
      捕捉されず透過する (Python 3.8+ で :class:`asyncio.CancelledError` も
      :class:`BaseException` 直接継承、 Python 3.13 でも同).

    例外メッセージは :data:`EXCEPTION_MESSAGE_MAX_LENGTH` (500) 文字切詰め.
    finite check / state invariant check 経由時はそれぞれ ``"non_finite_detected"`` /
    ``"state_inconsistency"``.

    Args:
        genome_id: 個体 genome ID
        run_id: 評価対象 run ID
        generation_no: 世代番号
        stage: :data:`StageType`. canonical_five / stage_a / stage_b /
            stage_c_lite / stage_c のいずれか.
        evaluate_fn: T061 evaluate_canonical_five 相当 (caller が DI)
        **evaluate_kwargs: ``evaluate_fn`` に展開する keyword 引数

    Returns:
        :class:`EvaluationOutcome` [:class:`CanonicalFiveResult`]
    """
    try:
        result = evaluate_fn(**evaluate_kwargs)
    except ValueError as exc:
        record = _make_failure_record(
            genome_id,
            run_id,
            generation_no,
            stage,
            reason="contract_violation",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )
    except Exception as exc:
        record = _make_failure_record(
            genome_id,
            run_id,
            generation_no,
            stage,
            reason="exception_raised",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )

    finite_check = validate_finite_canonical_five(result)
    if finite_check is not None:
        field_name, field_value = finite_check
        record = _make_failure_record_for_finite(
            genome_id,
            run_id,
            generation_no,
            stage,
            field_name=field_name,
            field_value=field_value,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )

    invariant_check = validate_state_invariant_canonical_five(result)
    if invariant_check is not None:
        record = _make_failure_record_for_state_inconsistency(
            genome_id,
            run_id,
            generation_no,
            stage,
            description=invariant_check,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )

    return EvaluationOutcome(
        result=result, failure_record=None, should_skip_downstream=False,
    )


def evaluate_mission_inf_gap_safe(
    *,
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,
    evaluate_fn: Callable[..., MissionGapResult],
    **evaluate_kwargs: Any,
) -> EvaluationOutcome[MissionGapResult]:
    """T062 :func:`~src.alpha_factory.mission_inf_gap.evaluate_mission_inf_gap` の wrap.

    :func:`evaluate_canonical_five_safe` と同形 4 段:

    1. :class:`ValueError` catch → ``contract_violation``
    2. :class:`Exception` catch → ``exception_raised``
    3. :func:`validate_finite_mission_gap` → ``non_finite_detected``
    4. :func:`validate_state_invariant_mission_gap` → ``state_inconsistency``
    """
    try:
        result = evaluate_fn(**evaluate_kwargs)
    except ValueError as exc:
        record = _make_failure_record(
            genome_id,
            run_id,
            generation_no,
            stage,
            reason="contract_violation",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_mission_gap(),
            failure_record=record,
            should_skip_downstream=True,
        )
    except Exception as exc:
        record = _make_failure_record(
            genome_id,
            run_id,
            generation_no,
            stage,
            reason="exception_raised",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_mission_gap(),
            failure_record=record,
            should_skip_downstream=True,
        )

    finite_check = validate_finite_mission_gap(result)
    if finite_check is not None:
        field_name, field_value = finite_check
        record = _make_failure_record_for_finite(
            genome_id,
            run_id,
            generation_no,
            stage,
            field_name=field_name,
            field_value=field_value,
        )
        return EvaluationOutcome(
            result=build_degraded_mission_gap(),
            failure_record=record,
            should_skip_downstream=True,
        )

    invariant_check = validate_state_invariant_mission_gap(result)
    if invariant_check is not None:
        record = _make_failure_record_for_state_inconsistency(
            genome_id,
            run_id,
            generation_no,
            stage,
            description=invariant_check,
        )
        return EvaluationOutcome(
            result=build_degraded_mission_gap(),
            failure_record=record,
            should_skip_downstream=True,
        )

    return EvaluationOutcome(
        result=result, failure_record=None, should_skip_downstream=False,
    )


def evaluate_bc_safe(
    *,
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,
    evaluate_fn: Callable[..., BCEvaluationResult],
    **evaluate_kwargs: Any,
) -> EvaluationOutcome[BCEvaluationResult]:
    """T064 :func:`~src.alpha_factory.stage_bc_evaluator.evaluate_bc_for_a_pass` の wrap.

    :func:`evaluate_canonical_five_safe` と同形 4 段.

    ``individual_index`` は ``evaluate_kwargs`` から取得 (default=0). 本 index は
    :func:`build_degraded_bc_result` の引数として必須 (degraded 時の identity 維持).
    no-raise contract 維持のため :func:`int` 変換失敗時 (例: 非数 ``individual_index``)
    は ``0`` fallback とする (Codex impl-review pr1-r1 [Warning H8] 反映).
    """
    raw_index = evaluate_kwargs.get("individual_index", 0)
    try:
        individual_index = int(raw_index)
    except (TypeError, ValueError):
        individual_index = 0

    try:
        result = evaluate_fn(**evaluate_kwargs)
    except ValueError as exc:
        record = _make_failure_record(
            genome_id,
            run_id,
            generation_no,
            stage,
            reason="contract_violation",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_bc_result(individual_index),
            failure_record=record,
            should_skip_downstream=True,
        )
    except Exception as exc:
        record = _make_failure_record(
            genome_id,
            run_id,
            generation_no,
            stage,
            reason="exception_raised",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_bc_result(individual_index),
            failure_record=record,
            should_skip_downstream=True,
        )

    finite_check = validate_finite_bc_result(result)
    if finite_check is not None:
        field_name, field_value = finite_check
        record = _make_failure_record_for_finite(
            genome_id,
            run_id,
            generation_no,
            stage,
            field_name=field_name,
            field_value=field_value,
        )
        return EvaluationOutcome(
            result=build_degraded_bc_result(individual_index),
            failure_record=record,
            should_skip_downstream=True,
        )

    invariant_check = validate_state_invariant_bc_result(result)
    if invariant_check is not None:
        record = _make_failure_record_for_state_inconsistency(
            genome_id,
            run_id,
            generation_no,
            stage,
            description=invariant_check,
        )
        return EvaluationOutcome(
            result=build_degraded_bc_result(individual_index),
            failure_record=record,
            should_skip_downstream=True,
        )

    return EvaluationOutcome(
        result=result, failure_record=None, should_skip_downstream=False,
    )


# ============================================================================
# Validators (NaN/Inf check) — 詳細 Round 1 [C1] / [W2] / [S1]
# ============================================================================


def validate_finite_canonical_five(
    result: CanonicalFiveResult,
) -> tuple[str, float] | None:
    """:class:`CanonicalFiveResult` の全 float field を finite check.

    検査対象 (T061 main 実装 SSOT):

    - ``sr_session_worst_block_scale`` / ``sr_session_worst_annual_estimate``
    - ``net_pnl_after_cost`` / ``max_dd``
    - ``session_block_win_rate_worst``
    - ``log_pf_clip`` / ``gate_worst_gap``
    - ``slack_sharpe`` / ``slack_pnl`` / ``slack_dd`` / ``slack_tc`` / ``slack_wr``

    ``trade_count`` は :class:`int` (除外). ``per_bucket_sr`` / ``per_bucket_wr``
    の各値 (float) も検査対象に含める.

    Returns:
        ``(field_name, value)`` if non-finite found; ``None`` otherwise.
    """
    candidates: list[tuple[str, float]] = [
        ("sr_session_worst_block_scale", result.sr_session_worst_block_scale),
        ("sr_session_worst_annual_estimate", result.sr_session_worst_annual_estimate),
        ("net_pnl_after_cost", result.net_pnl_after_cost),
        ("max_dd", result.max_dd),
        ("session_block_win_rate_worst", result.session_block_win_rate_worst),
        ("log_pf_clip", result.log_pf_clip),
        ("gate_worst_gap", result.gate_worst_gap),
        ("slack_sharpe", result.slack_sharpe),
        ("slack_pnl", result.slack_pnl),
        ("slack_dd", result.slack_dd),
        ("slack_tc", result.slack_tc),
        ("slack_wr", result.slack_wr),
    ]
    for name, value in candidates:
        if not math.isfinite(value):
            return (name, value)

    # per_bucket_sr / per_bucket_wr (各値 float) も検査
    for bucket, sr in result.per_bucket_sr.items():
        if not math.isfinite(sr):
            return (f"per_bucket_sr[{bucket}]", sr)
    for bucket, wr in result.per_bucket_wr.items():
        if not math.isfinite(wr):
            return (f"per_bucket_wr[{bucket}]", wr)

    return None


def validate_finite_mission_gap(
    result: MissionGapResult,
) -> tuple[str, float] | None:
    """:class:`MissionGapResult` の全 float field を finite check (sentinel 許容).

    sentinel 規約 (§ 8.4 invariant に従う):

    - ``is_feasible=False`` の場合のみ ``-inf`` (``mission_signed_margin`` /
      ``mission_margin``) / ``+inf`` (``mission_inf_gap`` / ``constraint_violation``)
      を許容.
    - ``is_feasible=True`` で sentinel 検出は state_inconsistency
      (:func:`validate_state_invariant_mission_gap` で別途検出).
    - :data:`math.nan` は常に failure (どの状態でも).

    本関数では :data:`math.nan` のみ検出 (sentinel 許容)、 invariant 違反は
    :func:`validate_state_invariant_mission_gap` で検出する.
    """
    candidates: list[tuple[str, float]] = [
        ("mission_inf_gap", result.mission_inf_gap),
        ("mission_signed_margin", result.mission_signed_margin),
        ("constraint_violation", result.constraint_violation),
        ("mission_margin", result.mission_margin),
    ]
    for name, value in candidates:
        if math.isnan(value):
            return (name, value)
    # per_metric_shortfall も NaN check (Mapping[str, float])
    for key, value in result.per_metric_shortfall.items():
        if math.isnan(value):
            return (f"per_metric_shortfall[{key}]", value)
    # ±inf は sentinel として許容 (invariant check で is_feasible 整合検証)
    return None


def validate_finite_bc_result(
    result: BCEvaluationResult,
) -> tuple[str, float] | None:
    """:class:`BCEvaluationResult` の top-level + nested sub-result の float field を
    finite check (詳細 Round 1 [C1] / [S1] 完全列挙).

    検査対象 (T064 main 実装 SSOT):

    top-level:

    - ``c_pass_depth`` (Follow-up Phase 0 後)

    nested:

    - ``b_pooled_cf`` (CanonicalFiveResult, optional): recursive
    - ``b_result`` (StageBResult): ``pooled_dd_per_fold_max`` (optional float),
      ``b_pooled_cf_result`` (optional CanonicalFiveResult, recursive),
      ``per_fold_results`` の各 ``cf_result`` (recursive)
    - ``c_lite_result`` (StageCLiteResult): ``cells_worst``,
      ``per_window_results`` の各 ``cf_result`` (recursive)
    - ``c_result`` (StageCResult): ``c_cf_result`` (recursive),
      ``stress_cf_result`` (optional, recursive),
      ``per_pair_results`` の各 CanonicalFiveResult (recursive),
      ``shadow_robustness_score`` (optional float)
    """
    # top-level float
    if not math.isfinite(result.c_pass_depth):
        return ("c_pass_depth", result.c_pass_depth)

    # b_pooled_cf (optional, recursive)
    if result.b_pooled_cf is not None:
        nested = validate_finite_canonical_five(result.b_pooled_cf)
        if nested is not None:
            return (f"b_pooled_cf.{nested[0]}", nested[1])

    # b_result.pooled_dd_per_fold_max (optional float)
    b = result.b_result
    if b.pooled_dd_per_fold_max is not None and not math.isfinite(b.pooled_dd_per_fold_max):
        return ("b_result.pooled_dd_per_fold_max", b.pooled_dd_per_fold_max)
    # b_result.b_pooled_cf_result (optional, recursive)
    if b.b_pooled_cf_result is not None:
        nested = validate_finite_canonical_five(b.b_pooled_cf_result)
        if nested is not None:
            return (f"b_result.b_pooled_cf_result.{nested[0]}", nested[1])
    # b_result.per_fold_results 各 cf_result (recursive)
    for fold in b.per_fold_results:
        nested = validate_finite_canonical_five(fold.cf_result)
        if nested is not None:
            return (
                f"b_result.per_fold_results[{fold.fold_index}].cf_result.{nested[0]}",
                nested[1],
            )

    # c_lite_result.cells_worst (float)
    cl = result.c_lite_result
    if not math.isfinite(cl.cells_worst):
        return ("c_lite_result.cells_worst", cl.cells_worst)
    for window in cl.per_window_results:
        nested = validate_finite_canonical_five(window.cf_result)
        if nested is not None:
            return (
                f"c_lite_result.per_window_results[{window.window_index}].cf_result.{nested[0]}",
                nested[1],
            )

    # c_result
    cr = result.c_result
    nested = validate_finite_canonical_five(cr.c_cf_result)
    if nested is not None:
        return (f"c_result.c_cf_result.{nested[0]}", nested[1])
    if cr.stress_cf_result is not None:
        nested = validate_finite_canonical_five(cr.stress_cf_result)
        if nested is not None:
            return (f"c_result.stress_cf_result.{nested[0]}", nested[1])
    for pair_name, pair_cf in cr.per_pair_results.items():
        nested = validate_finite_canonical_five(pair_cf)
        if nested is not None:
            return (f"c_result.per_pair_results[{pair_name}].{nested[0]}", nested[1])
    if cr.shadow_robustness_score is not None and not math.isfinite(
        cr.shadow_robustness_score
    ):
        return ("c_result.shadow_robustness_score", cr.shadow_robustness_score)

    return None


def _iter_float_fields_check(dataclass_instance: Any) -> tuple[str, float] | None:
    """dataclass instance の全 float field を iterate して non-finite 検出.

    詳細 Round 2 [C1] / Round 3 [C1] / [S1-S2] 反映:

    - :func:`typing.get_type_hints` で文字列化 annotation を resolve
    - ``float`` / ``float | None`` / ``Optional[float]`` / ``Annotated[float, ...]``
      を正規化判定
    - hint 不明 (resolve 失敗 or annotation なし) なら **value 型で fallback**:
      ``isinstance(value, float) and not isinstance(value, bool)``
    - :class:`int` field は除外、 :class:`bool` は :class:`int` subclass のため明示除外

    本 helper は将来 :func:`validate_finite_bc_result` で T064 dataclass field
    増加時の自動列挙 (Phase 2 申し送り) で利用する候補. 現状は明示列挙版を採用.
    """
    if not hasattr(dataclass_instance, "__dataclass_fields__"):
        return None

    try:
        hints = typing.get_type_hints(type(dataclass_instance), include_extras=True)
    except Exception:
        hints = {}

    for field_name in dataclass_instance.__dataclass_fields__:
        value = getattr(dataclass_instance, field_name)
        hint = hints.get(field_name)
        is_float_field = False

        if hint is float:
            is_float_field = True
        elif hint is not None:
            origin = typing.get_origin(hint)
            args = typing.get_args(hint)
            if origin is typing.Annotated:  # type: ignore[attr-defined]
                if args and args[0] is float:
                    is_float_field = True
            elif (
                origin is typing.Union or origin is types.UnionType
            ) and any(a is float for a in args):
                is_float_field = True
        elif isinstance(value, float) and not isinstance(value, bool):
            is_float_field = True

        if (
            is_float_field
            and isinstance(value, float)
            and not isinstance(value, bool)
            and not math.isfinite(value)
        ):
            return (field_name, value)

    return None


# ============================================================================
# Validators (state invariant check) — 詳細 Round 3 [C1] / § 8.4
# ============================================================================


def validate_state_invariant_canonical_five(
    result: CanonicalFiveResult,
) -> str | None:
    """:class:`CanonicalFiveResult` の state invariant check (詳細 Round 1 [C2] 反映).

    invariant:

    - ``invariants.is_feasible=True`` ⟹ 全 ``slack_*`` が :func:`math.isfinite` かつ
      ``-inf`` 不在 (canonical 5 invariant、 T061 § 6.1 contract).
    - ``is_feasible=False`` ⟹ 制約違反検出済 (sentinel ``-inf`` もしくは
      ``max(0, -slack) > 0`` を許容).

    Returns:
        invariant 違反の description string、 整合なら ``None``.
    """
    invariants = result.invariants
    if invariants.is_feasible:
        slack_pairs: list[tuple[str, float]] = [
            ("slack_sharpe", result.slack_sharpe),
            ("slack_pnl", result.slack_pnl),
            ("slack_dd", result.slack_dd),
            ("slack_tc", result.slack_tc),
            ("slack_wr", result.slack_wr),
        ]
        for name, value in slack_pairs:
            if not math.isfinite(value):
                return f"is_feasible=True but {name} not finite ({value})"
            if value < 0:
                return f"is_feasible=True but {name} < 0 ({value})"
    return None


def validate_state_invariant_mission_gap(
    result: MissionGapResult,
) -> str | None:
    """:class:`MissionGapResult` の § 8.4 invariant check.

    invariant: ``is_feasible=True`` ⟺ :func:`math.isfinite`
    (``mission_signed_margin``) AND ``>= 0`` AND ``mission_inf_gap == 0.0``
    AND ``constraint_violation == 0.0``.

    Returns:
        違反時は description string、 整合なら ``None``.
    """
    if result.is_feasible:
        if not math.isfinite(result.mission_signed_margin):
            return (
                f"is_feasible=True but mission_signed_margin not finite "
                f"({result.mission_signed_margin})"
            )
        if result.mission_signed_margin < 0:
            return (
                f"is_feasible=True but mission_signed_margin < 0 "
                f"({result.mission_signed_margin})"
            )
        if result.mission_inf_gap != 0.0:
            return (
                f"is_feasible=True but mission_inf_gap != 0 "
                f"({result.mission_inf_gap})"
            )
        if result.constraint_violation != 0.0:
            return (
                f"is_feasible=True but constraint_violation != 0 "
                f"({result.constraint_violation})"
            )
        if result.mission_margin != 0.0:
            return (
                f"is_feasible=True but mission_margin != 0 "
                f"({result.mission_margin})"
            )
    else:
        # is_feasible=False の整合性 (詳細 Round 2 [C3] 反映、 sentinel 符号整合)
        if result.mission_inf_gap == 0.0 and result.constraint_violation == 0.0:
            return (
                "is_feasible=False but both mission_inf_gap and "
                "constraint_violation are 0"
            )
        if math.isinf(result.mission_signed_margin) and result.mission_signed_margin > 0:
            return (
                "is_feasible=False but mission_signed_margin = +inf "
                "(sentinel sign violation)"
            )
        if math.isinf(result.mission_inf_gap) and result.mission_inf_gap < 0:
            return (
                "is_feasible=False but mission_inf_gap = -inf "
                "(sentinel sign violation)"
            )
        if math.isinf(result.constraint_violation) and result.constraint_violation < 0:
            return (
                "is_feasible=False but constraint_violation = -inf "
                "(sentinel sign violation)"
            )
        if result.constraint_violation < 0:
            return (
                f"constraint_violation must be >= 0, got "
                f"{result.constraint_violation}"
            )
        if result.mission_inf_gap < 0:
            return (
                f"mission_inf_gap must be >= 0, got {result.mission_inf_gap}"
            )
    return None


def validate_state_invariant_bc_result(
    result: BCEvaluationResult,
) -> str | None:
    """:class:`BCEvaluationResult` の state invariant check.

    invariant:

    - ``pareto_axis_usable=True`` ⟺ ``b_pooled_cf is not None`` (T064 main 契約)
    - ``mission_pass=PASS`` なら ``c_lite_result.progress_pass=PASS`` 必須
      (mission_pass は progress_pass の上位条件、 T064 truth table)
    - ``c_pass_depth`` 値域 ``[0.0, 1.75]`` (T064 follow-up Phase 0)
    """
    if result.pareto_axis_usable and result.b_pooled_cf is None:
        return "pareto_axis_usable=True but b_pooled_cf is None"
    if (not result.pareto_axis_usable) and result.b_pooled_cf is not None:
        return "pareto_axis_usable=False but b_pooled_cf is not None"
    if (
        result.mission_pass == StagePassStatus.PASS
        and result.c_lite_result.progress_pass != StagePassStatus.PASS
    ):
        return (
            f"mission_pass=PASS but c_lite_result.progress_pass="
            f"{result.c_lite_result.progress_pass}"
        )
    if not (0.0 <= result.c_pass_depth <= 1.75):
        return (
            f"c_pass_depth out of range [0.0, 1.75], got {result.c_pass_depth}"
        )
    return None


# ============================================================================
# Degraded result builders
# ============================================================================


def _build_degraded_invariant_flags() -> InvariantFlags:
    """degraded 個体用 :class:`InvariantFlags` (is_feasible=False)."""
    return InvariantFlags(
        session_close_drop_count=0,
        negative_equity_drop_open_count=0,
        infeasible_reason_codes=frozenset(
            {InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST}
        ),
    )


def build_degraded_canonical_five() -> CanonicalFiveResult:
    """T061 :class:`CanonicalFiveResult` の infeasible degraded 版.

    NSGA-II constrained-domination で最低 priority になる構成:

    - ``invariants.is_feasible=False`` (``infeasible_reason_codes`` が非空)
    - 全 ``slack_*=-inf`` (制約違反 sentinel)
    - ``log_pf_clip=`` :data:`DEGRADED_LOG_PF_CLIP_FLOOR` (-2.0)
    - ``gate_worst_gap=+inf`` / ``gate_pass=False``
    """
    return CanonicalFiveResult(
        sr_session_worst_block_scale=0.0,
        sr_session_worst_annual_estimate=0.0,
        net_pnl_after_cost=0.0,
        max_dd=0.0,
        trade_count=0,
        session_block_win_rate_worst=0.0,
        per_bucket_sr={b: 0.0 for b in SessionBucket},
        per_bucket_wr={b: 0.0 for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=-math.inf,
        slack_pnl=-math.inf,
        slack_dd=-math.inf,
        slack_tc=-math.inf,
        slack_wr=-math.inf,
        gate_worst_gap=math.inf,
        gate_pass=False,
        log_pf_clip=DEGRADED_LOG_PF_CLIP_FLOOR,
        bucket_validator_version="degraded",
        invariants=_build_degraded_invariant_flags(),
    )


def build_degraded_mission_gap() -> MissionGapResult:
    """T062 :class:`MissionGapResult` の infeasible degraded 版.

    archive eviction で最低 priority + NSGA-II constrained-domination で
    infeasible 側の最悪 violation を取る構成:

    - ``is_feasible=False``
    - ``mission_inf_gap=+inf`` / ``constraint_violation=+inf``
    - ``mission_signed_margin=-inf`` (= :data:`MISSION_SIGNED_MARGIN_INFEASIBLE_SENTINEL`)
    - ``mission_margin=-inf``
    - ``per_metric_shortfall``: empty MappingProxyType (frozen 互換)

    **degraded 個体は § 10.4 最終契約に従い caller (Phase 2 run_loop) が
    ``should_skip_downstream=True`` で T065/T066/T067 入力から除外する責務、
    T068 は finite cap 等の事前変換を行わない**.
    """
    return MissionGapResult(
        mission_inf_gap=math.inf,
        constraint_violation=math.inf,
        mission_margin=-math.inf,
        mission_signed_margin=-math.inf,
        per_metric_shortfall=types.MappingProxyType({}),
        is_feasible=False,
    )


def build_degraded_bc_result(individual_index: int) -> BCEvaluationResult:
    """T064 :class:`BCEvaluationResult` の degraded 版.

    sub-result (b_result / c_lite_result / c_result) は最小限 dummy:

    - ``mission_pass=FAIL`` (terminal)
    - ``b_pooled_cf=None`` ⟺ ``pareto_axis_usable=False``
    - ``c_pass_depth=0.0`` (T064 follow-up Phase 0 値域 [0.0, 1.75] 下限)
    """
    return BCEvaluationResult(
        individual_index=individual_index,
        b_result=_build_dummy_stage_b_result(),
        c_lite_result=_build_dummy_stage_c_lite_result(),
        c_result=_build_dummy_stage_c_result(),
        mission_pass=StagePassStatus.FAIL,
        b_pooled_cf=None,
        pareto_axis_usable=False,
        c_pass_depth=0.0,
    )


def _build_dummy_stage_b_result() -> StageBResult:
    """:func:`build_degraded_bc_result` 内部 helper、 minimal dummy.

    T064 :class:`StageBResult` invariant を満たす最小値:

    - ``b_pooled_cf_result=None`` (Pareto axis source なし)
    - ``pooled_dd_per_fold_max=None``
    - ``per_fold_results=()``
    - ``is_feasible_invariant=False``
    - ``is_b_pass=False``
    """
    return StageBResult(
        b_pooled_cf_result=None,
        pooled_dd_per_fold_max=None,
        per_fold_results=(),
        is_feasible_invariant=False,
        is_b_pass=False,
    )


def _build_dummy_stage_c_lite_result() -> StageCLiteResult:
    """:func:`build_degraded_bc_result` 内部 helper、 minimal dummy.

    T064 :class:`StageCLiteResult` invariant を満たす最小値:

    - ``per_window_results=()``
    - ``cells_worst=+inf`` (worst sentinel)
    - ``mission_pass=FAIL`` / ``progress_pass=FAIL``
    - ``sample_size_flag=INSUFFICIENT`` (sample size guard)
    - ``n_pass_windows=0`` (``__post_init__`` で
      ``[0, STAGE_C_LITE_NUM_WINDOWS]`` + ``<= len(per_window_results)`` 検証)
    """
    return StageCLiteResult(
        per_window_results=(),
        cells_worst=math.inf,
        mission_pass=StagePassStatus.FAIL,
        progress_pass=StagePassStatus.FAIL,
        sample_size_flag=SampleSizeFlag.INSUFFICIENT,
        n_pass_windows=0,
    )


def _build_dummy_stage_c_result() -> StageCResult:
    """:func:`build_degraded_bc_result` 内部 helper、 minimal dummy.

    T064 :class:`StageCResult` invariant を満たす最小値:

    - ``c_cf_result``: degraded :class:`CanonicalFiveResult`
    - ``stress_cf_result=None`` (stress_pass=PENDING)
    - ``per_pair_results={}`` (cross_pair_pass=FAIL に整合)
    - ``live_criteria_pass=False``
    - ``stress_pass=PENDING`` / ``cross_pair_pass=FAIL``
    - ``mission_pass=FAIL`` / ``mission_fail_reason=LIVE_CRITERIA``
    - ``shadow_robustness_score=0.0``
    """
    return StageCResult(
        c_cf_result=build_degraded_canonical_five(),
        stress_cf_result=None,
        per_pair_results={},
        live_criteria_pass=False,
        stress_pass=StagePassStatus.PENDING,
        cross_pair_pass=StagePassStatus.FAIL,
        mission_pass=StagePassStatus.FAIL,
        mission_fail_reason=MissionFailReason.LIVE_CRITERIA,
        shadow_robustness_score=0.0,
    )


# ============================================================================
# Aggregate + abort (Round 1 [C1] / [C2] stage-local)
# ============================================================================


def aggregate_failures(
    records: Sequence[FailureRecord],
    *,
    stage: StageType,
    eligible_count: int,
) -> FailureSummary:
    """**stage-local** 失敗集計.

    入力 ``records`` は全 stage 横断 collect で OK (本関数で当 ``stage`` filter).

    abort 判定は ``n_failed_genomes`` (一意 genome) ベース、 record 数では判定しない
    (詳細 Round 1 [C1]).

    ``eligible_count=0`` で warning 扱い、 ``failure_rate=0.0`` / ``all_failed=False``.
    eligible_count=0 warning 出力責務は **caller 責務** (T068 module 内では log emit
    しない、 T071 が消費).

    Args:
        records: 全 stage 横断 :class:`FailureRecord` 列
        stage: 集計対象 :data:`StageType`
        eligible_count: 当 stage の eligible 個体数 (>= 0)

    Returns:
        :class:`FailureSummary`

    Raises:
        ValueError: ``eligible_count < 0`` または
            ``n_failed_genomes > eligible_count`` のとき.
    """
    if eligible_count < 0:
        raise ValueError(f"eligible_count must be >= 0, got {eligible_count}")

    stage_records = [r for r in records if r.stage == stage]
    n_failure_records = len(stage_records)
    failed_genome_ids = tuple(sorted({r.genome_id for r in stage_records}))
    n_failed_genomes = len(failed_genome_ids)

    if n_failed_genomes > eligible_count:
        raise ValueError(
            f"n_failed_genomes ({n_failed_genomes}) exceeds eligible_count "
            f"({eligible_count}) at stage {stage}"
        )

    by_reason: Counter[str] = Counter(str(r.failure_reason) for r in stage_records)
    all_failed = n_failed_genomes == eligible_count and eligible_count > 0
    failure_rate = n_failed_genomes / max(eligible_count, 1)

    return FailureSummary(
        stage=stage,
        eligible_individuals=eligible_count,
        n_failure_records=n_failure_records,
        n_failed_genomes=n_failed_genomes,
        n_succeeded_genomes=eligible_count - n_failed_genomes,
        all_failed=all_failed,
        failed_genome_ids=failed_genome_ids,
        failures_by_reason=types.MappingProxyType(dict(by_reason)),
        failure_rate=failure_rate,
    )


def decide_run_abort(summary: FailureSummary) -> bool:
    """stage-local 全個体 fail で ``True`` (synthesis § 7.7).

    ``n_failed_genomes`` ベース判定 (詳細 Round 1 [C1]). ``eligible_count=0`` の
    場合は ``all_failed=False`` (= 当 stage に到達した個体がいないだけ、 abort 不要).
    """
    return summary.all_failed


def build_run_failure_summary(
    run_id: str,
    per_stage_summaries: Sequence[FailureSummary],
) -> RunFailureSummary:
    """per-Run monitor 用集約 (各 stage の summary を保持).

    abort 判定は per-stage で実施済 (:func:`decide_run_abort`)、 本 dataclass は
    observability 用.

    Args:
        run_id: 評価対象 run ID (非空)
        per_stage_summaries: 各 stage の :class:`FailureSummary`

    Returns:
        :class:`RunFailureSummary`

    Raises:
        ValueError: ``run_id`` が空のとき.
    """
    if not run_id:
        raise ValueError("run_id must be non-empty")
    summaries_tuple = tuple(per_stage_summaries)
    any_all_failed = any(s.all_failed for s in summaries_tuple)
    return RunFailureSummary(
        run_id=run_id,
        per_stage_summaries=summaries_tuple,
        any_stage_all_failed=any_all_failed,
    )
