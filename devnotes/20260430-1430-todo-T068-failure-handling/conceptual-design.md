# 概念設計: T068 — Failure handling (NaN/Inf/crash → infeasible + run abort)

**作成日時**: 2026-04-30 15:45 JST、 Round 2 修正 16:00 JST
**前提**: synthesis Round 21 改訂後 (2026-04-30)、 T058-T067 設計 APPROVED
**マイルストーン**: M4 (Loop+緊急) の 2 番目の TODO、 T067 と組合せて Run loop の堅牢性を確保
**位置付け**: T061-T067 evaluator 群の上位 (per-individual / per-Run loop) で例外をキャッチし、 NaN/Inf/crash を infeasible 化、 全個体 fail で run abort する pure function module

## Round 1 review 反映

| Round 1 [Critical/Warning/Suggestion] | 概念設計での吸収 |
|---|---|
| [C1] n_failed = len(records) で同一 genome 複数 stage 失敗時に誤判定 | FailureSummary を **n_failure_records / n_failed_genomes / eligible_individuals / all_failed** に分離。 abort 判定は `n_failed_genomes == eligible_individuals` で行う |
| [C2] 全 fail 判定の分母が stage-local でない | **aggregate_failures を stage 単位** に変更: `aggregate_failures(records, *, stage, eligible_count)` で stage ごとの summary を返す。 abort 判定は stage-local |
| [C3] degraded result の downstream 伝搬契約が pending | **R1 案 A 確定 (概念で)**: `EvaluationOutcome` 統一 dataclass で `(result, failure_record, should_skip_downstream)` を返す。 caller (Phase 2 run_loop) は should_skip_downstream=True 個体を T065/T066/T067 入力から除外。 § 6.1 / § 10.4 / § 11.2 で API 統一 |
| [W1] contract_violation の分類規約未確定 (ValueError を別 reason に) | wrapper 擬似コードで `except ValueError as exc: failure_reason="contract_violation"` を分離 + `except Exception as exc: failure_reason="exception_raised"` の 2 段 catch。 § 6.1 で明文化 |
| [W2] validate_finite_canonical_five docstring と candidates 不整合 (trade_count) | `trade_count` は **int 型なので finite check 不要**。 docstring + candidates 両方から `trade_count` を削除して整合 |
| [W3] stage 型が wrapper API str / FailureRecord.stage Literal で不整合 | wrapper API も Literal 型注釈に統一、 cardinality 固定 |
| [W4] KeyboardInterrupt 透過のみ、 SystemExit 不明 | 「`except Exception as exc:` は SystemExit / KeyboardInterrupt / GeneratorExit を捕捉しない (Python 標準動作)」 を docstring 明示。 SystemExit / GeneratorExit は通す (BaseException subclass を別途 catch しない) |
| [W5] failure_rate の total=0 意味論曖昧 | `total_individuals=0` は warning 扱い、 `failure_rate=0.0` を返す + docstring に「分母 0 は空集合、 abort=False」 明記 |
| [S1] FailureSummary 4 field 分離 | 採用 (Critical 1 と統合) |
| [S2] FailureRecord に exception_fingerprint | `exception_fingerprint: str | None` field 追加 (例: `"ValueError@evaluate_canonical_five:NaN_in_slack_pnl"` の hashable string、 caller dedup 用) |
| [S3] validate_finite_bc_result の nested 検査方針 | nested sub-result (StageBResult / StageCLiteResult / StageCResult) も top-level scalar まで検査、 各 sub-result の主要 field (例: pooled_dd_per_fold_max / shadow_robustness_score) を candidates に含める。 詳細設計で完全リスト |
| [S4] R2 sentinel truth table の invariant 1 行固定 | § 8.4 に「is_feasible=True ⟺ mission_signed_margin >= 0 (finite) AND mission_inf_gap == 0 AND constraint_violation == 0」 invariant を 1 行明文化 |
| [S5] zenigame 踏襲度の stage-local 分母定義 | Critical 2 と統合 (stage 単位 aggregate) |

---

## 1. 背景・課題

synthesis § 7.7 で確定した **失敗 genome 扱い** を zenigame-fx に移植する:

> - backtest crash / NaN / Inf → `margin_inf = +inf` の infeasible 確定
> - 全個体 fail → run abort (silent legacy degrade 禁止)

T061-T067 の各 evaluator は **入口契約 (finite domain / ValueError raise)** を既に持つ。 T068 は **Run loop の上位で evaluator 呼出を例外 catch + degraded result で続行**、 全個体 fail 時に **明示 abort** する責務を担う。

T068 が提供する責務 (Phase 1 = 単体 module + テストのみ):

1. **per-individual evaluator 呼出の例外 catch** + degraded (infeasible) result 構築:
   - T061 evaluate_canonical_five (CanonicalFiveResult)
   - T062 evaluate_mission_inf_gap (MissionGapResult)
   - T063 evaluate_generation (Stage A、 caller が world で受け止める)
   - T064 evaluate_bc_for_a_pass (BCEvaluationResult)
   - T065 / T066 / T067: pure function、 例外時は caller (run loop) で abort 判定
2. **NaN / Inf 検出** (各 evaluator 戻り値の post-validation):
   - upstream evaluator の入口契約を補完する 2 段防御 (defense-in-depth)
3. **FailureRecord** (per-individual / per-stage の失敗メタデータ)
4. **FailureSummary** (per-Run 集計、 abort 判定用)
5. **decide_run_abort** (全個体 fail 検出時に RuntimeError raise の判定)
6. **degraded result builder** (各 evaluator の infeasible 化 result 生成)
7. **failure logging** (caller observability に渡す情報、 構造化ログ用)

T068 が**触らない** (別 TODO 担当):

- evaluator 本体実装 — **T061-T064**
- Run loop オーケストレーション本体 — **Phase 2 run_ga.py 配線**
- observability emit (logging / metrics) — **T071** (T068 は構造化データ提供のみ)
- emergency mode 発動 — **T067** (failure summary は別軸、 emergency は mission_pass=0 連続が判定源)
- backtest engine 内部の crash 防御 — **既存 / T070**
- run abort 後の cleanup (archive 永続化等) — **Phase 2 配線**

### 1.1 synthesis § 7.7 主要規約

| 項目 | 値 |
|---|---|
| crash / NaN / Inf 個体扱い | `mission_signed_margin = -inf` (T062 sentinel) + infeasible 確定 |
| 全個体 fail 判定 | `n_failed == len(genomes)` |
| 全個体 fail 時動作 | RuntimeError raise (silent legacy degrade 禁止) |
| 部分 fail 時動作 | warning log + 続行 (caller 責務) |
| failure scope | per-stage (A / B / C-lite / C / mission_inf_gap / canonical_five) |

### 1.2 T061-T067 連携

| evaluator | 例外時 T068 振る舞い (戻り値は EvaluationOutcome[T] で統一) |
|---|---|
| T061 evaluate_canonical_five | EvaluationOutcome(result=build_degraded_canonical_five(), failure_record=record, should_skip_downstream=True) (Round 3 [W2] 反映) |
| T062 evaluate_mission_inf_gap | MissionGapResult(is_feasible=False, mission_inf_gap=+inf, mission_signed_margin=-inf, constraint_violation=+inf 相当の最大値、 per_metric_shortfall は immutable empty) |
| T064 evaluate_bc_for_a_pass | BCEvaluationResult(mission_pass=FAIL, progress_pass=FAIL, b_pooled_cf=None, pareto_axis_usable=False) |
| T065 / T066 / T067 | pure function なので入口契約違反のみ。 例外時は caller (Phase 2 run_loop) で abort 判定 |

### 1.3 zenigame 参考実装

| 機構 | zenigame 出典 | fx 流用方針 |
|---|---|---|
| evaluator 例外 catch + +inf 化 | `ga/nsga2/core.py:1026-1052` | パターン踏襲、 fx は immutable + dataclass で構造化 |
| 全個体 fail 時 RuntimeError | `ga/nsga2/core.py:1085-1089` | silent degrade 禁止原則を踏襲 |
| 部分 fail warning ログ | `ga/nsga2/core.py:1090-1095` | 構造化ログに改善 (T068 は構造化データ提供のみ、 emit は T071) |

### 1.4 Phase 1 / Phase 2 分離

**Phase 1 (T068 PR)**:
- `src/alpha_factory/ga/failure_handling.py` 新規 (FailureRecord / FailureSummary / decide_run_abort / per-stage degraded result builder + evaluate_with_failure_handling wrapper)
- `tests/alpha_factory/ga/test_failure_handling.py` 新規 (約 60 件、 10 sub-suite)
- 既存 evaluator / run loop に未配線

**Phase 2 (run_ga.py + 既存 evaluator + T071 と同時)**:
- `run_ga.py` per-individual chain で T068 wrapper 経由
- T061-T067 evaluator 呼出を T068 wrap で防御
- T071 observability で FailureSummary を消費

---

## 2. 前提検証 (C4) — current HEAD `main@2b69aff` (T067 commit 後) 基準

| 前提 | verified | 出典 |
|---|---|---|
| synthesis § 7.7 「crash/NaN/Inf → infeasible 確定、 全 fail で run abort」 | ✓ | synthesis § 7.7 |
| T061 InvariantFlags / CanonicalFiveResult / T062 MissionGapResult / T064 BCEvaluationResult が degraded 化可能な dataclass field 構成 | ✓ | T061-T064 詳細設計 APPROVED |
| zenigame `core.py:1026, 1085` に参照実装 | ✓ | grep 確認 |
| T067 EmergencyState は failure とは別軸 (mission_pass=0 連続) | ✓ | T067 設計 APPROVED |
| 既存 zenigame-fx に failure handling module 未存在 | ✓ | grep `FailureRecord\|decide_run_abort` で hit なし |

---

## 3. 責務範囲とスコープ分離

### 3.1 Phase 1 (T068 PR) スコープ

**新規 module**: `src/alpha_factory/ga/failure_handling.py`

提供 API は **§ 11.2 SSOT**:

- dataclass: `FailureRecord` / `FailureSummary` (stage-local) / `RunFailureSummary` / `EvaluationOutcome[T]` (詳細 Round 2 [W1] 反映、 旧 EvaluatorFailure は廃止)
- evaluator wrapper: `evaluate_canonical_five_safe` / `evaluate_mission_inf_gap_safe` / `evaluate_bc_safe` (T061/T062/T064 ラッパー、 EvaluationOutcome 返し)
- NaN/Inf check: `validate_finite_canonical_five` / `validate_finite_mission_gap` / `validate_finite_bc_result`
- state invariant check: `validate_state_invariant_canonical_five` / `validate_state_invariant_mission_gap` / `validate_state_invariant_bc_result` (§ 8.4 invariant)
- degraded builder: `build_degraded_canonical_five` / `build_degraded_mission_gap` / `build_degraded_bc_result`
- summary + abort: `aggregate_failures` (stage-local) / `decide_run_abort` / `build_run_failure_summary` (per-Run)

**新規テスト**: `tests/alpha_factory/ga/test_failure_handling.py` (10 sub-suite × 約 60 件)

### 3.2 Phase 2 (T065/T066/T067 + run_ga.py 配線、 別 PR)

- `scripts/alpha_factory/run_ga.py` per-individual evaluator 呼出を T068 wrapper 経由
- `src/alpha_factory/observability/failure_metrics.py` (新規) で FailureSummary 消費
- T071 と統合

### 3.3 non-責務 (touch しない)

- evaluator 本体 — T061-T064
- Run loop 全体 — Phase 2
- observability emit — T071
- backtest engine 内 crash 防御 — 既存 / T070
- emergency mode — T067

---

## 4. データフロー

### 4.1 per-individual evaluator wrapper (Round 2 [C2] § 11.2 SSOT 同期)

```
入力:
- genome_id / run_id / generation_no / stage: StageType
- evaluator_fn (T061 / T062 / T064 のいずれか)
- **evaluate_kwargs

処理:
1. try: result = evaluator_fn(**kwargs)
   except ValueError as exc:
       record = _make_failure_record(... reason="contract_violation", exception=exc)
       return EvaluationOutcome(degraded, record, should_skip_downstream=True)
   except Exception as exc:   # SystemExit / KeyboardInterrupt / GeneratorExit は通す
       record = _make_failure_record(... reason="exception_raised", exception=exc)
       return EvaluationOutcome(degraded, record, should_skip_downstream=True)
2. finite_check = validate_finite_*(result)
   if finite_check is not None:
       record = ... reason="non_finite_detected"
       return EvaluationOutcome(degraded, record, should_skip_downstream=True)
3. invariant_check = validate_state_invariant(result)   # § 8.4 SSOT
   if invariant_check is not None:
       record = ... reason="state_inconsistency"
       return EvaluationOutcome(degraded, record, should_skip_downstream=True)
4. return EvaluationOutcome(result, None, should_skip_downstream=False)

出力:
- EvaluationOutcome[T] (Round 1 [C3] 統一型)
```

### 4.2 per-stage aggregate + abort 判定 (Round 1 [C2] / Round 2 [C2] stage-local)

```
入力:
- failure_records: Sequence[FailureRecord] (caller 全 stage 横断 collect、 関数内で当 stage filter)
- stage: StageType
- eligible_count: int (当 stage に進入した個体数、 stage-local)

処理:
1. summary = aggregate_failures(failure_records, stage=stage, eligible_count=eligible_count)
2. if decide_run_abort(summary):
     raise RuntimeError(
       f"ALL {summary.eligible_individuals} eligible individuals failed at stage {stage}. "
       f"Reasons: {dict(summary.failures_by_reason)}"
     )
3. else: 部分 fail なら caller warning + 続行 (warning emit は T071)

出力:
- summary: FailureSummary (per-stage、 caller observability に提供)
- raise RuntimeError on stage-local all_failed
```

---

## 5. dataclass

### 5.1 FailureRecord (Round 1 [S2] 反映、 fingerprint 追加)

```python
@dataclass(frozen=True)
class FailureRecord:
    """per-individual / per-stage の失敗メタデータ (immutable).

    Phase 2 で run_ga.py が collect、 T071 observability で構造化ログに変換.
    fingerprint は dedup / 同一例外集約用 (Round 1 [S2]).
    """
    genome_id: str
    run_id: str
    generation_no: int
    stage: Literal["canonical_five", "mission_inf_gap", "bc_eval", "stage_a", "stage_b", "stage_c_lite", "stage_c"]
    failure_reason: Literal[
        "exception_raised",       # evaluator が予期しない例外 raise (BaseException 系除く)
        "contract_violation",     # ValueError = 入口契約違反 (T065/T066/T067 finite domain 違反等)
        "non_finite_detected",    # 戻り値に NaN/Inf 含む (post-validation)
        "state_inconsistency",    # § 8.4 invariant 違反 (is_feasible flag と sentinel state の不整合)
    ]
    exception_class: str | None    # 例: "ValueError" or "RuntimeError"、 例外時のみ
    exception_message: str | None  # 例外文字列、 500 文字切詰め、 例外時のみ
    detected_field: str | None     # NaN/Inf 検出時の field 名 (例: "slack_pnl")
    detected_value: float | None   # 検出値 (NaN なら math.nan、 ±inf なら ±math.inf)
    exception_fingerprint: str | None    # dedup 用 (例: "ValueError@canonical_five:slack_pnl_nan"、 Round 1 [S2]、 reason に応じて構築不能なら None も許容)
```

### 5.2 FailureSummary (Round 1 [C1] / [C2] / [S1] 反映で stage-local + 4 field 分離)

```python
@dataclass(frozen=True)
class FailureSummary:
    """**stage-local** 失敗集計 (immutable、 abort 判定 + observability 用).

    Round 1 [C1] / [S1] 反映: n_failure_records (event 数) と n_failed_genomes (一意 genome 数)
    を分離。 abort 判定は n_failed_genomes ベース.

    Round 1 [C2] 反映: stage-local (= 当 stage の eligible_count を分母とする)。
    例: Stage B には A-pass の N 個体だけが進む → eligible_count = N、 全 N 個体 fail で abort.
    """
    stage: Literal["canonical_five", "mission_inf_gap", "bc_eval", "stage_a", "stage_b", "stage_c_lite", "stage_c"]
    eligible_individuals: int                  # 当 stage に進入した個体数 (分母、 stage-local)
    n_failure_records: int                     # 失敗 event 数 (= len(records))
    n_failed_genomes: int                      # 一意 genome_id 失敗数 (abort 判定の分子)
    n_succeeded_genomes: int                   # = eligible_individuals - n_failed_genomes
    all_failed: bool                           # = n_failed_genomes == eligible_individuals AND eligible_individuals > 0
    failed_genome_ids: tuple[str, ...]         # genome_id 昇順 (deterministic)
    failures_by_reason: types.MappingProxyType[str, int]   # reason → event 数
    failure_rate: float                        # n_failed_genomes / max(eligible_individuals, 1)、 eligible=0 で 0.0


@dataclass(frozen=True)
class RunFailureSummary:
    """per-Run 横断 summary (各 stage の FailureSummary を集約、 observability 用).

    abort 判定は **per-stage** で実施 (各 FailureSummary.all_failed を順次評価)、
    本 dataclass は monitor 用のみ.
    """
    run_id: str
    per_stage_summaries: tuple[FailureSummary, ...]   # 各 stage の summary
    any_stage_all_failed: bool                         # abort raised stage が 1 つでもあるか
```

---

## 6. evaluator wrapper (T061 / T062 / T064 を degraded 化)

### 6.1 evaluate_canonical_five_safe (T061 wrap、 Round 1 [W1] / [W3] / [W4] / [C3] 反映)

```python
StageType = Literal[
    "canonical_five", "mission_inf_gap", "bc_eval",
    "stage_a", "stage_b", "stage_c_lite", "stage_c",
]


@dataclass(frozen=True)
class EvaluationOutcome[T]:
    """evaluator wrapper の戻り値統一型 (Round 1 [C3] 反映).

    should_skip_downstream=True の個体は caller (Phase 2 run_loop) が T065/T066/T067 入力から
    除外する責務 (R1 案 A 確定).
    """
    result: T                                  # 成功時は実 result、 失敗時は degraded result
    failure_record: FailureRecord | None        # 成功時 None
    should_skip_downstream: bool                # = (failure_record is not None)


def evaluate_canonical_five_safe(
    *,
    genome_id: str,
    run_id: str,
    generation_no: int,
    stage: StageType,                          # Round 1 [W3] Literal 統一
    evaluate_fn: Callable[..., CanonicalFiveResult],
    **evaluate_kwargs: Any,
) -> EvaluationOutcome[CanonicalFiveResult]:
    """T061 evaluate_canonical_five を例外 catch + finite check で wrap.

    例外 catch 規約 (Round 1 [W1] / [W4]):
    - ValueError → failure_reason="contract_violation" (入口契約違反)
    - その他 Exception → failure_reason="exception_raised"
    - SystemExit / KeyboardInterrupt / GeneratorExit (BaseException 系) は通す
      (Python 標準動作: `except Exception` は BaseException 系を捕捉しない)
    - 例外メッセージは 500 文字切詰め

    finite check 経由時は failure_reason="non_finite_detected" (post-validation).
    """
    try:
        result = evaluate_fn(**evaluate_kwargs)
    except ValueError as exc:
        record = _make_failure_record(
            genome_id, run_id, generation_no, stage,
            reason="contract_violation",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )
    except Exception as exc:   # SystemExit / KeyboardInterrupt は通す
        record = _make_failure_record(
            genome_id, run_id, generation_no, stage,
            reason="exception_raised",
            exception=exc,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )

    # NaN/Inf check (Round 1 [W4])
    finite_check = validate_finite_canonical_five(result)
    if finite_check is not None:
        field_name, field_value = finite_check
        record = _make_failure_record_for_finite(
            genome_id, run_id, generation_no, stage,
            field_name=field_name, field_value=field_value,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )

    # state invariant check (Round 3 [C1] / [Suggestion 1] 反映、 § 8.4 invariant)
    invariant_check = validate_state_invariant_canonical_five(result)
    if invariant_check is not None:
        record = _make_failure_record_for_state_inconsistency(
            genome_id, run_id, generation_no, stage,
            description=invariant_check,
        )
        return EvaluationOutcome(
            result=build_degraded_canonical_five(),
            failure_record=record,
            should_skip_downstream=True,
        )

    return EvaluationOutcome(
        result=result,
        failure_record=None,
        should_skip_downstream=False,
    )
```

`_make_failure_record` / `_make_failure_record_for_finite` は内部 helper (FailureRecord + fingerprint 構築)。 詳細設計で確定。

### 6.2 同様の T062 / T064 wrapper

同じパターンで `evaluate_mission_inf_gap_safe` / `evaluate_bc_safe` を提供。

---

## 7. degraded result builder

### 7.1 build_degraded_canonical_five

```python
def build_degraded_canonical_five() -> CanonicalFiveResult:
    """T061 CanonicalFiveResult の infeasible degraded 版.

    - invariant_flags.is_feasible = False
    - 全 slack = -inf
    - gate_pass = False, gate_worst_gap = math.inf
    - log_pf_clip = LOG_PF_CLIP_FLOOR (= -2)、 末端 tie-break 用
    - net_pnl_after_cost = 0.0 (selection で feasible 個体に支配される)
    """
    ...
```

### 7.2 build_degraded_mission_gap (Round 3 [C2] / [Suggestion 2] 反映、 finite cap 言及削除)

```python
def build_degraded_mission_gap() -> MissionGapResult:
    """T062 MissionGapResult の infeasible degraded 版.

    - is_feasible = False
    - mission_inf_gap = +inf (T062 sentinel 規約)
    - mission_signed_margin = -inf (T062 sentinel 規約)
    - constraint_violation = +inf (T062 規約)
    - mission_margin = -inf (BACKWARD COMPAT)
    - per_metric_shortfall = empty MappingProxyType

    **degraded 個体は § 10.4 の最終契約に従い caller (Phase 2 run_loop) が should_skip_downstream=True
    で T065/T066/T067 入力から除外する責務。 T068 は finite cap 等の事前変換を行わない**.
    """
    ...
```

### 7.3 build_degraded_bc_result

```python
def build_degraded_bc_result(individual_index: int) -> BCEvaluationResult:
    """T064 BCEvaluationResult の degraded 版.

    - mission_pass = StagePassStatus.FAIL
    - progress_pass = StagePassStatus.FAIL
    - b_pooled_cf = None (T064 contract: invariant fail で None)
    - pareto_axis_usable = False
    - shadow_robustness_score = 0.0
    - c_pass_depth = 0.0 (Phase 0 follow-up 後)
    - 各 sub-result (b_result / c_lite_result / c_result) は最小限の dummy で構築
    """
    ...
```

---

## 8. NaN/Inf 検出 (post-validation、 defense-in-depth)

### 8.1 validate_finite_canonical_five (Round 1 [W2] 反映、 trade_count 除外)

```python
def validate_finite_canonical_five(
    result: CanonicalFiveResult,
) -> tuple[str, float] | None:
    """CanonicalFiveResult の全 float field を finite check.

    検出時は (field_name, value) を返す、 全 finite なら None.
    対象 field (float のみ、 trade_count は int で finite 概念なし、 Round 1 [W2]):
    net_pnl_after_cost / max_dd / sr_session_worst / session_block_win_rate_worst /
    log_pf_clip / gate_worst_gap / 各 slack_*
    """
    candidates = [
        ("net_pnl_after_cost", result.net_pnl_after_cost),
        ("max_dd", result.max_dd),
        ("sr_session_worst", result.sr_session_worst),
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
    return None
```

### 8.2 validate_finite_mission_gap / validate_finite_bc_result

同様のパターン。 mission_inf_gap / mission_signed_margin / constraint_violation / shadow_robustness_score / c_pass_depth 等を検証。

注: T062 では `mission_signed_margin = -inf` が **正規 sentinel** (infeasible 個体)。 validate では「is_feasible=True なのに mission_signed_margin=-inf」 等の **state inconsistency のみ failure 化**、 純粋な NaN は failure 化、 sentinel -inf は許容 (is_feasible flag と整合する場合のみ)。

### 8.3 validate_finite_bc_result の nested 検査範囲 (Round 1 [S3] 反映)

BCEvaluationResult は nested sub-result を持つ (StageBResult / StageCLiteResult / StageCResult)。 検査範囲:

- top-level: `shadow_robustness_score` / `c_pass_depth` / その他 float field
- StageBResult: `pooled_dd_per_fold_max` / `b_pooled_cf` (CanonicalFiveResult、 ある場合 recursive で validate_finite_canonical_five)
- StageCLiteResult: `worst_gap_15_cells` / 各 window 別 float
- StageCResult: `mission_pass_under_stress` 等の float

詳細設計で完全 candidates list 化。 nested 検査は recursive (sub-result が None でない場合のみ)。

### 8.4 sentinel 許容 invariant (Round 1 [S4] 反映、 1 行固定)

**MissionGapResult invariant**:
```
is_feasible=True ⟺ math.isfinite(mission_signed_margin) AND mission_signed_margin >= 0
                AND mission_inf_gap == 0.0 AND constraint_violation == 0.0

is_feasible=False ⟹ allowed sentinel:
  mission_signed_margin = -inf
  mission_inf_gap = +inf (or finite >= 0)
  constraint_violation = +inf (or finite > 0)
```

validate_finite_mission_gap は invariant 違反を `state_inconsistency` reason で failure 化。 詳細設計で truth table 完成 (R2 解消)。

---

## 9. aggregate_failures + decide_run_abort

### 9.1 aggregate_failures (Round 1 [C1] / [C2] 反映、 stage 単位 + 4 field 分離)

```python
def aggregate_failures(
    records: Sequence[FailureRecord],
    *,
    stage: StageType,                          # 当 stage の records のみ集計対象
    eligible_count: int,                        # 当 stage に進入した個体数 (分母、 stage-local)
) -> FailureSummary:
    """**stage-local** 失敗集計.

    Round 1 [C1] 反映: 同一 genome 複数 record でも一意 genome 数 (n_failed_genomes) で abort 判定.
    Round 1 [C2] 反映: eligible_count は stage 単位 (例 Stage B は A-pass 個体数のみ).
    Round 1 [W5] 反映: eligible_count=0 は warning 扱い、 failure_rate=0.0、 all_failed=False.
    """
    if eligible_count < 0:
        raise ValueError(f"eligible_count must be >= 0, got {eligible_count}")

    # 当 stage の records のみ集計 (caller 事前フィルタ前提、 defense-in-depth)
    stage_records = [r for r in records if r.stage == stage]
    n_failure_records = len(stage_records)
    failed_genome_ids = tuple(sorted({r.genome_id for r in stage_records}))
    n_failed_genomes = len(failed_genome_ids)

    if n_failed_genomes > eligible_count:
        raise ValueError(
            f"n_failed_genomes ({n_failed_genomes}) exceeds eligible_count ({eligible_count}) "
            f"at stage {stage}"
        )

    by_reason = Counter(r.failure_reason for r in stage_records)
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
```

### 9.2 decide_run_abort

```python
def decide_run_abort(summary: FailureSummary) -> bool:
    """stage-local 全個体 fail で True (synthesis § 7.7 silent degrade 禁止).

    Round 1 [C1] 反映: n_failed_genomes (一意 genome) で判定、 record 数では判定しない.
    eligible_individuals=0 の場合 False (空集合 = abort しない).
    """
    return summary.all_failed
```

caller (Phase 2 run_loop) は:

```python
if decide_run_abort(stage_summary):
    raise RuntimeError(
        f"ALL {stage_summary.eligible_individuals} eligible individuals failed at stage "
        f"{stage_summary.stage}. Reasons: {dict(stage_summary.failures_by_reason)}"
    )
```

---

## 10. 重要な設計判断

### 10.1 KeyboardInterrupt は通す

evaluator wrapper では `except Exception` で catch し、 `KeyboardInterrupt` は通す (Ctrl-C で abort 可能)。

### 10.2 例外メッセージの切詰め

`exception_message` は 500 文字に切詰め (構造化ログでの肥大化防止)。

### 10.3 sentinel -inf 許容ルール (T062 整合)

`mission_signed_margin = -inf` は T062 の正規 sentinel (infeasible 個体)。 validate_finite_mission_gap では:
- `is_feasible=True` かつ `mission_signed_margin = -inf` → state inconsistency → failure
- `is_feasible=False` かつ `mission_signed_margin = -inf` → 許容 (T062 sentinel 規約)
- `is_feasible=*` かつ NaN → failure (T062 既に NaN は raise だが defense-in-depth)

詳細設計で完全 truth table。

### 10.4 degraded result の T065 / T066 / T067 への伝搬 (Round 2 [Suggestion 2] 1 文固定)

**最終契約 (R1 確定、 概念で確定)**:
**`should_skip_downstream=True` の個体は caller (Phase 2 run_loop) が T065 / T066 / T067 入力から除外する責務、 finite cap 等の事前変換は不要。 T068 は EvaluationOutcome を提供するのみ。**

これにより degraded result が downstream に流れず、 T065/T066/T067 の入口契約 (finite domain) は無傷で保たれる。 caller は `[ind for ind in population if not outcomes[ind].should_skip_downstream]` のシンプルなフィルタで実装可能。

### 10.5 全 fail RuntimeError の caller 責務

T068 は `decide_run_abort` の bool 判定のみ提供、 RuntimeError raise は caller (Phase 2 run_loop) 責務。 T068 内では raise しない (pure function 維持)。

---

## 11. 主要 dataclass / API シグネチャ (Phase 1 SSOT)

### 11.1 dataclass (Round 2 [W1] / [W2] 反映、 stage-local + EvaluationOutcome)

- `FailureRecord` (per-individual / per-stage)
- `FailureSummary` (**stage-local**、 § 5.2 SSOT)
- `RunFailureSummary` (per-Run 横断 monitor)
- `EvaluationOutcome[T]` (`(result, failure_record, should_skip_downstream)`)
- `StageType` (Literal alias)

### 11.2 関数シグネチャ

```python
# evaluator wrappers (Round 1 [C3] EvaluationOutcome 統一)
def evaluate_canonical_five_safe(
    *, genome_id: str, run_id: str, generation_no: int, stage: StageType,
    evaluate_fn: Callable[..., CanonicalFiveResult], **evaluate_kwargs,
) -> EvaluationOutcome[CanonicalFiveResult]: ...

def evaluate_mission_inf_gap_safe(
    *, genome_id: str, run_id: str, generation_no: int, stage: StageType,
    evaluate_fn: Callable[..., MissionGapResult], **evaluate_kwargs,
) -> EvaluationOutcome[MissionGapResult]: ...

def evaluate_bc_safe(
    *, genome_id: str, run_id: str, generation_no: int, stage: StageType,
    evaluate_fn: Callable[..., BCEvaluationResult], **evaluate_kwargs,
) -> EvaluationOutcome[BCEvaluationResult]: ...

# NaN/Inf check
def validate_finite_canonical_five(result: CanonicalFiveResult) -> tuple[str, float] | None: ...
def validate_finite_mission_gap(result: MissionGapResult) -> tuple[str, float] | None: ...
def validate_finite_bc_result(result: BCEvaluationResult) -> tuple[str, float] | None: ...

# degraded builders
def build_degraded_canonical_five() -> CanonicalFiveResult: ...
def build_degraded_mission_gap() -> MissionGapResult: ...
def build_degraded_bc_result(individual_index: int) -> BCEvaluationResult: ...

# summary + abort (Round 1 [C1] / [C2] stage-local + 4 field 分離)
def aggregate_failures(
    records: Sequence[FailureRecord], *, stage: StageType, eligible_count: int,
) -> FailureSummary: ...

def decide_run_abort(summary: FailureSummary) -> bool: ...

def build_run_failure_summary(
    run_id: str, per_stage_summaries: Sequence[FailureSummary],
) -> RunFailureSummary: ...
```

---

## 12. テスト計画 (代表のみ、 詳細設計で完全リスト化)

### 12.1 PR DoD 必須

- `test_evaluate_canonical_five_safe_catches_exception_and_returns_degraded`
- `test_evaluate_mission_inf_gap_safe_catches_exception_and_returns_degraded`
- `test_decide_run_abort_returns_true_when_all_individuals_fail`
- `test_decide_run_abort_returns_false_when_partial_fail`

### 12.2 evaluator wrappers (T061 / T062 / T064)

- `test_evaluate_canonical_five_safe_returns_result_and_none_on_success`
- `test_evaluate_canonical_five_safe_keyboard_interrupt_propagates`
- `test_evaluate_canonical_five_safe_failure_record_contains_exception_class_and_message`
- `test_evaluate_canonical_five_safe_truncates_long_exception_message_at_500`
- (同様に mission_inf_gap / bc_eval)

### 12.3 NaN/Inf detection

- `test_validate_finite_canonical_five_detects_nan_in_slack_pnl`
- `test_validate_finite_canonical_five_detects_inf_in_max_dd`
- `test_validate_finite_canonical_five_returns_none_for_all_finite`
- `test_validate_finite_mission_gap_detects_nan_but_allows_neg_inf_sentinel_when_infeasible`
- `test_validate_finite_mission_gap_failure_when_neg_inf_sentinel_with_is_feasible_true`
- `test_validate_finite_bc_result_detects_nan_in_shadow_robustness_score`

### 12.4 degraded builders

- `test_build_degraded_canonical_five_invariant_feasible_false`
- `test_build_degraded_canonical_five_all_slacks_neg_inf`
- `test_build_degraded_canonical_five_log_pf_clip_at_floor`
- `test_build_degraded_mission_gap_is_feasible_false_signed_margin_neg_inf`
- `test_build_degraded_mission_gap_constraint_violation_inf`
- `test_build_degraded_bc_result_mission_pass_fail_b_pooled_cf_none`
- `test_build_degraded_bc_result_pareto_axis_usable_false`

### 12.5 aggregate_failures

- `test_aggregate_failures_empty_records_returns_zero_summary`
- `test_aggregate_failures_collects_failed_genome_ids_sorted`
- `test_aggregate_failures_filters_records_by_stage` (詳細 Round 2 [W3] 反映、 stage-local)
- `test_aggregate_failures_groups_by_reason`
- `test_aggregate_failures_failure_rate_computed_correctly`
- `test_aggregate_failures_raises_on_n_failed_genomes_exceeding_eligible_count` (詳細 Round 2 [W3])

### 12.6 decide_run_abort

- `test_decide_run_abort_zero_total_returns_false`
- `test_decide_run_abort_all_succeeded_returns_false`
- `test_decide_run_abort_some_failed_returns_false`
- `test_decide_run_abort_all_failed_returns_true`

### 12.7 Determinism + immutability

- `test_failure_record_is_frozen_dataclass`
- `test_failure_summary_failures_by_reason_is_mapping_proxy` (stage-local: stage は単一値で field なし)
- `test_aggregate_failures_deterministic_with_unsorted_input`

### 12.8 sentinel 許容ルール (T062 整合)

- `test_validate_finite_mission_gap_neg_inf_signed_margin_with_is_feasible_false_is_valid`
- `test_validate_finite_mission_gap_inf_constraint_violation_with_is_feasible_false_is_valid`
- `test_validate_finite_mission_gap_neg_inf_signed_margin_with_is_feasible_true_is_inconsistent`

### 12.9 Edge cases

- `test_evaluate_canonical_five_safe_handles_value_error_separately_with_contract_violation_reason`
- `test_aggregate_failures_total_individuals_zero_failure_rate_zero`
- `test_failure_record_truncation_does_not_break_unicode`

### 12.10 schema v2 / Round 21 整合性

- `test_failure_record_stage_enum_matches_synthesis_terms`
- `test_build_degraded_mission_gap_uses_t062_sentinel_neg_inf_for_signed_margin`

総テスト数: 約 60 件 (10 sub-suite)

---

## 13. 残論点 / Decision Pending

### R1: degraded result の T065/T066/T067 への伝搬規約 (Round 1 [C3] / Round 2 解消、 概念で確定)

- 採用: **案 A** (caller 除外)
- EvaluationOutcome.should_skip_downstream で明示 (Round 1 [C3] 反映)
- Phase 2 run_loop は should_skip_downstream=True 個体を T065 入力から除外する責務

### R2: sentinel 許容 truth table (Round 1 [S4] / Round 2 一行 invariant 固定、 概念で確定)

§ 8.4 invariant 1 行: `is_feasible=True ⟺ math.isfinite(mission_signed_margin) AND mission_signed_margin >= 0 AND mission_inf_gap == 0.0 AND constraint_violation == 0.0`. 完全 truth table は詳細設計で確定 (本 invariant 違反時は state_inconsistency reason).

### R3: KeyboardInterrupt 以外の signal の扱い

SystemExit / 子プロセス kill 時の例外も通すか。 詳細設計で確定。

### R4: T065/T066/T067 自身の例外 handling

T065/T066/T067 は pure function なので入口契約違反のみ ValueError。 T068 はこれらを wrap しない (caller が直接呼出、 ValueError は契約違反 indicator として上位 abort)。

### R5: 部分 fail の許容率閾値

N% 以上の部分 fail で run abort するか。 採用: 閾値なし (synthesis § 7.7 「全 fail のみ abort」 厳密準拠)、 部分 fail は warning + 続行。 INCONCLUSIVE (smoke 後 R5 検討候補、 例えば 50% 超で警告強化)。

---

## 14. Phase 2 申し送り (T065/T066/T067 + run_ga.py 配線、 別 PR) DoD (8 箇所)

| # | ファイル / 箇所 | 担当 | 内容 |
|---|---|---|---|
| 1 | `src/alpha_factory/ga/__init__.py` で `from .failure_handling import ...` | T068 Phase 2 | T065/T066/T067 と同時 export |
| 2 | `scripts/alpha_factory/run_ga.py` per-individual chain で T068 wrapper 経由 | T068 Phase 2 | T061-T064 evaluator 呼出を防御 |
| 3 | (新規) `src/alpha_factory/observability/failure_metrics.py` | T071 | FailureSummary を消費、 構造化ログ emit |
| 4 | (新規) `tests/integration/test_failure_handling_e2e.py` | T068 Phase 2 | T068 + T061-T064 の例外伝搬統合 test |
| 5 | `config/alpha_factory/default.yaml` に failure logging 設定 (max_message_length 等) | T068 Phase 2 | T058 schema v2 準拠 |
| 6 | (新規) `docs/alpha_factory/runbook.md` に「全 fail → run abort」 運用ガイド | T068 Phase 2 | smoke / production 運用 |
| 7 | (Phase 0) T064 BCEvaluationResult.c_pass_depth field 利用 | T064 follow-up | T066 / T067 と共通 |
| 8 | (新規) caller (run_ga.py) で degraded 個体を T065 入力から除外する config / logic | Phase 2 配線 | R1 採用案 A の実装 |

---

## 15. zenigame コード参考

| 機構 | zenigame ファイル | 行番号 | fx 流用方針 |
|---|---|---|---|
| evaluator 例外 catch + +inf 化 | `ga/nsga2/core.py` | 1026-1052 | 構造化 (FailureRecord) で fx 化 |
| 全 fail RuntimeError | `ga/nsga2/core.py` | 1085-1089 | T068 では bool 返し、 caller raise |
| 部分 fail warning ログ | `ga/nsga2/core.py` | 1090-1095 | 構造化 (FailureSummary) で T071 emit |

---

## 16. 完了判定 (概念設計 APPROVED 条件)

- [ ] § 1 で T068 責務範囲 (Phase 1 / Phase 2 分離 + 非責務 6 件) が明確
- [ ] § 2 で前提検証 (C4) が verified、 出典明示
- [ ] § 5 で FailureRecord / FailureSummary が確定
- [ ] § 6 で evaluator wrapper の例外 catch + finite check pattern 確定
- [ ] § 7 で degraded builder の T061/T062/T064 整合性確定
- [ ] § 8 で sentinel 許容ルール (T062 整合) 確定
- [ ] § 9 で aggregate + decide_run_abort 確定 (RuntimeError raise は caller 責務)
- [ ] § 11 で API SSOT が揃う
- [ ] § 12 で PR DoD 必須 4 件含む
- [ ] § 13 で残論点 3 件 (R3 / R4 / R5) が Decision Pending、 R1 / R2 は概念で確定済 (Round 3 [W1] / [Suggestion 3] 反映)
- [ ] § 14 で Phase 2 申し送り 8 箇所が具体ファイル名 + 担当 TODO 名で列挙
- [ ] Codex 概念レビュー APPROVED

---

## 17. synthesis Round 21 改訂後の整合性

T068 は archive / mission_signed_margin 等の T062 sentinel 規約と整合 (§ 8.3 / § 10.3 sentinel 許容ルール)。 mission_margin (BACKWARD COMPAT) は参照しない。 mission_signed_margin = -inf を degraded sentinel として T062 contract に従う。
