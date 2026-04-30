# 概念設計: T071 — Observability (A→B 乖離 / archive churn / front1 / FailureSummary 消費)

**作成日時**: 2026-04-30 19:24 JST (Round 2 改訂: 19:42 JST)
**設計者**: Claude
**M5**: 2/3 (T070 完了、 本 TODO で 2/3、 T072 残)
**前提**: synthesis Round 21 改訂後、 main@`04aa271` (T070 commit 後)
**改訂履歴**: Round 1 [C1-C6] / [W1-W4] / [S1-S4] 全反映
**前提検証** (C4):
- synthesis § 8.7 「A→B 乖離 監視 (warn-only)、 corr(A_proxy_score, B_pooled_score)、 q_force 自動引き上げ (上限 0.40 / 0.02 unit / 戻し条件 corr>=0.5)」 が確定文 ✓
- synthesis § 10.1 監視項目 7 件 (A→B 乖離 / session entropy / archive churn / bypass 比率 / feasible_ratio_ema / front1 cardinality / inflow per_run_max warmstart_share) が確定文 ✓
- synthesis § 18.2 T915 「Observability: A/B 乖離 / entropy / inflow / archive churn / front1 cardinality / feasible_ratio_ema 監視、 q_force 自動引き上げ (上限・戻し条件)」 が確定文 ✓
- T065 conceptual § 866 で「`src/alpha_factory/observability/selection_metrics.py` (新規) が GenerationSelectionResult を消費して front1 cardinality / feasible_ratio / violation distribution を観測」 が T071 担当として申し送り済 ✓
- T066 AdmissionReport / T067 WarmstartReport / T068 FailureSummary / RunFailureSummary が T071 消費対象として確定 ✓
- T068 § 99 で「T071 observability で FailureSummary を消費」、 § 135 で「`src/alpha_factory/observability/failure_metrics.py` (新規) で FailureSummary 消費」 が確定 ✓
- T067 § 107 で「AdmissionReport は observability のみ (emergency 判定入力では使わない)」 が確定 ✓

## 1. ゴール

synthesis § 8.7 / § 10.1 / § 18.2 T915 を厳密準拠した Observability layer の library 基盤実装 (Phase 1 = library + pure function、 caller 配線は Phase 2):

1. **A→B 乖離監視** (warn-only): `corr(A_proxy_score, B_pooled_score)` を Pearson correlation で計算、 閾値超過で warning + q_force 引き上げ推奨を返す
2. **q_force 自動補正推奨**: synthesis § 8.7 SSOT (上限 0.40 / 引き上げ 0.02 per Run / 戻し corr>=0.5)
3. **archive churn**: 直近 3 Run の eviction 率を AdmissionReport から計算
4. **bypass 比率**: archive 流入のうち score_bypass 経由の割合
5. **session entropy** (週次): archive 内 session_pass_pattern 分布の Shannon entropy
6. **feasible_ratio_ema**: Push/Pull FSM 切替指標 (T063 既存) を T071 観測 metric として記録
7. **front1 cardinality**: GenerationSelectionResult の Pareto rank 1 size、 pop promotion trigger
8. **inflow / per_run_max / warmstart_share 動作確認**: WarmstartReport / AdmissionReport から設定通り動作を検証
9. **FailureSummary 消費**: T068 の per-stage summary + RunFailureSummary を構造化 log emit

T915 (synthesis § 18.2) のうち observability 機能を T071 が担当、 audit (DSR/PBO/SPA) は **T073 (T916) で別 TODO**。

## 2. C2 parallel-path 5 段階 grep + Consumer Inventory

T071 は新設 layer (`src/alpha_factory/observability/`) で、 上流 dataclass (T063-T068) を消費し、 下流 (Phase 2 で run_ga.py / report) に提供する。 既存 observability 系の有無を確認:

### 2.1 並列実装検証 (5 段階)

| 段階 | 検査 | 結果 |
|---|---|---|
| 直 import | `from src.alpha_factory.observability` | 不在 (新規) |
| alias | `import observability as` | 不在 |
| relative | `from .observability` | 不在 |
| 再エクスポート | `__init__.py` 経由 | 不在 |
| runtime シンボル | `getattr(... "observability"` | 不在 |

→ T071 PR で新設、 並列実装なし。

### 2.2 上流 (消費する dataclass) Inventory

| Dataclass | 出所 | T071 で読む field |
|---|---|---|
| `GenerationSelectionResult` (T065) | `src/alpha_factory/ga/nsga2_selection.py` (T065 PR) | `pareto_front1_size`, `feasible_ratio`, `mean_constraint_violation`, ... |
| `AdmissionReport` (T066) | `src/alpha_factory/ga/cpps_archive.py` (T066 PR) | `n_admitted_ca`, `n_admitted_da`, `n_evicted_ca`, `n_evicted_da`, `n_admitted_by_role`, ... |
| `WarmstartReport` (T067) | `src/alpha_factory/ga/loop_closure.py` (T067 PR) | `n_filtered_by_epoch`, `n_filtered_by_cooldown`, `n_per_source_run_max`, `warmstart_share_actual`, `relaxation_steps`, ... |
| `FailureSummary` (T068, per stage) | `src/alpha_factory/ga/failure_handling.py` (T068 PR) | `n_failure_records`, `n_failed_genomes`, `eligible_individuals`, `all_failed`, `fingerprint_dedup_top_N`, ... |
| `RunFailureSummary` (T068, per Run) | 同上 | `per_stage_summaries: tuple[FailureSummary, ...]`, `run_aborted: bool` |
| `BCEvaluationResult` (T064) | `src/alpha_factory/stage_bc_evaluator.py` (T064 PR) | `b_pooled_score` (= A→B 乖離計算の B 側入力) |
| `StageAControllerState` (T063) | `src/alpha_factory/stage_a_evaluator.py` (T063 PR) | `feasible_ratio_ema`, `q_force_current`, `a_proxy_score` (= A→B 乖離計算の A 側入力) |
| `ArchiveState` (T066) | `src/alpha_factory/ga/cpps_archive.py` (T066 PR) | `ca_members`, `da_members` (= session entropy 計算入力) |

### 2.3 下流 (T071 を読む経路) Inventory (Phase 2 申し送り)

| Consumer | T071 が提供 | 担当 |
|---|---|---|
| run_ga.py / scripts/run_alpha_factory_ga | `RunObservabilityReport` を Run 末尾で受け取り、 log / report 出力 | Phase 2 |
| StageAControllerState 更新 (T063) | `q_force_recommendation: Decimal` を受け取り、 次 Run で q_force 引き上げ/戻し | Phase 2 (T063 詳細設計で配線) |
| docs / report.md | RunObservabilityReport の Markdown 表現 | Phase 2 |
| Audit layer (T073) | 一部 metric を継承 (DSR 等は別) | T073 |

## 3. アーキテクチャ概要

### 3.1 機能分割 (新設 module 群)

「やたらに複雑な案を提案する」 禁止事項に従い、 **単一新規 module** に集約:

```
src/alpha_factory/observability/
└── run_metrics.py     ← 新設 (T071 中核、 単一 module で機能集約)
    ├── ABDivergenceMetric   (dataclass, 2 field)
    ├── ArchiveChurnMetric   (dataclass, 4 field)
    ├── SessionEntropyMetric (dataclass, 2 field、 週次集計用)
    ├── SelectionMetric      (dataclass, T065 由来)
    ├── WarmstartMetric      (dataclass, T067 由来)
    ├── FailureMetric        (dataclass, T068 由来)
    ├── RunObservabilityReport (集約 dataclass)
    ├── compute_ab_divergence_on_b_evaluated()  (corr 計算、 conditioning 明示、 Round 1 [S2])
    ├── recommend_q_force_adjust()              (synthesis § 8.7 補正推奨)
    ├── compute_archive_churn()                 (直近 3 Run eviction 率)
    ├── compute_bypass_ratio()
    ├── compute_session_entropy()               (Shannon entropy)
    ├── extract_selection_metrics()
    ├── extract_inflow_consistency()            (Round 1 [C4] 反映で命名統一)
    ├── extract_failure_metrics()
    └── build_run_observability_report()        (集約)
```

複雑化が必要な場合 (= module が肥大化、 200 LoC 超え見込み) のみ Phase 2 で `selection_metrics.py` 等に分割を検討。 T071 PR では単一 module で開始。

### 3.2 A→B 乖離計算 (synthesis § 8.7 SSOT、 Round 1 [C2] / [S2] 反映で conditioning 明示)

```
corr_on_b_evaluated_population(A_proxy_score, B_pooled_score) を Pearson correlation で計算

集計対象 (Round 1 [C2] 反映): **B 評価が走った個体集合** (= A pass を経由して B stage に進んだ
個体のみ)。 これは「A pass で条件付けられた部分母集団」 であり、 母集団相関ではない。
C3 collider bias 観点で、 解釈は「B 評価対象の探索方向と A proxy の整合性」 に限定。

入力:
  - 個体ごとの A_proxy_score (T063 stage_a_evaluator から、 B 評価対象個体のみ)
  - 同個体の B_pooled_score (T064 stage_bc_evaluator から)
  - 両 sequence は同一個体順で並んでいる前提 (caller 責務)

corr の計算:
  numerator = mean((a - a_mean) * (b - b_mean))
  denom = sqrt(var(a) * var(b))
  corr = numerator / denom (denom > 0 のとき、 数値誤差で [-1, 1] 越境時は clamp)

status 判定 (Round 1 [C1] / [S1] 反映、 None 経路を排除して status field で表現):
  - n < 2:                                        status="insufficient_data", corr=Decimal(0) (使用禁止 sentinel)
  - var(a) == 0 or var(b) == 0:                   status="zero_variance",     corr=Decimal(0)
  - 通常:                                         status="ok",                corr ∈ [-1, 1] clamp 後
```

### 3.3 q_force 自動補正推奨 (synthesis § 8.7 + T071 仮説値)

```
synthesis § 8.7 確定値 (= 厳密準拠):
  - 上限: q_force_max = 0.40 (固定)
  - 引き上げ単位: +0.02 / 連続乖離 Run
  - 戻し条件: corr >= 0.5 で -0.02 / Run
  - hard fail なし

T071 仮説値 (Round 1 [C3] / [S3] 反映、 = synthesis 未明示、 T071 設計判断):
  - 下限: q_force_min = 0.15 (= q_force 動的式の lower bound、 synthesis § 5.1)
  - divergence_threshold = 0.30 (= 「raise」 判定の corr 閾値、 hysteresis 上端)
    - 理由: restore_threshold = 0.50 と非対称 hysteresis で振動防止
    - synthesis 厳密準拠ではない、 T071 設計判断として明記
    - Phase 2 で実測 corr 分布から再校正検討

入力 (Round 1 [C1] / [W4] 反映、 ABDivergenceMetric 入力で None 経路排除):
  - current_q_force: Decimal (= 直近 q_force)
  - divergence: ABDivergenceMetric (= compute_ab_divergence の戻り値、 status field で計算可否を表現)
  - consecutive_divergent_runs: int (= caller 保持、 連続乖離 Run 数 = log/監視用、 delta 判定には使わない)

出力 QForceRecommendation:
  - new_q_force: Decimal
  - delta: Decimal (+0.02 / 0 / -0.02)
  - reason: Literal["raise", "hold", "restore", "insufficient_data", "zero_variance"]
  - clamped_at_max: bool
  - clamped_at_min: bool

適用モデル (Round 1 [W4] 反映で docstring 明示):
  caller は 1 Run 完了ごとに recommend_q_force_adjust を呼び、 戻り値 new_q_force を次 Run の
  q_force に適用する。 T071 自身は state を持たない (= 関数の idempotency)。
  consecutive_divergent_runs は 「報告用 / 監視 log」 のみで delta 判定式には使わない (= 1 Run
  あたり ±0.02 が SSOT)。

caller (Phase 2、 run_ga.py / T063) は consecutive_divergent_runs を state file 経由で保持して
T071 に渡す。
```

### 3.4 archive churn (synthesis § 10.1、 Round 1 [C1] 反映で Optional 経路排除)

```
SSOT: 「直近 3 Run の eviction 率」

入力: 直近 N Run (1 ≤ N ≤ 3) の AdmissionReport の sequence
計算:
  total_admissions = sum(report.n_admitted_ca + report.n_admitted_da for report in reports)
  total_evictions  = sum(report.n_evicted_ca + report.n_evicted_da for report in reports)
  churn_rate = total_evictions / total_admissions  (total_admissions=0 の場合は churn_rate=0)

出力 ArchiveChurnMetric:
  - status: Literal["ok", "insufficient_runs"]   # Round 1 [C1] 反映、 Optional 経路排除
  - churn_rate: Decimal
  - n_total_admissions: int
  - n_total_evictions: int
  - n_runs_used: int  (1, 2, 3 のいずれか)

status 判定:
  - n_runs_used == 0: ValueError raise (= 入力空、 caller bug)
  - 1 <= n_runs_used < 3: status="insufficient_runs"、 churn_rate は計算可能だが「3 Run 未満で
    信頼性が落ちる」 ことを caller が判断
  - n_runs_used == 3: status="ok"

RunObservabilityReport は **常に ArchiveChurnMetric を保持** (= None 経路なし)、 1 Run 目でも
status="insufficient_runs" + churn_rate=計算値で含まれる。
```

### 3.5 bypass 比率 (synthesis § 10.1)

```
SSOT: 「archive 流入のうち bypass 経由の割合」

入力: 直近 1 Run の AdmissionReport
計算:
  total_admissions = report.n_admitted_ca + report.n_admitted_da
  bypass_count = report.n_admitted_by_role["score_bypass"] (= AdmissionReport の archive_role 別カウント)
  bypass_ratio = bypass_count / max(total_admissions, 1)

出力 BypassRatioMetric:
  - bypass_ratio: Decimal
  - n_admitted_by_role: dict[ArchiveRole, int]
```

### 3.6 session entropy (synthesis § 10.1、 週次、 Round 1 [C1] / [C5] / [W3] 反映)

```
SSOT: 「archive 内 session_pass_pattern 分布の Shannon entropy、 週次」

T071 内では履歴を持たない (= pure function)、 caller が「直近 7 Run 分の archive members」 を
集めて T071 に渡す (Round 1 [C5] 反映、 weekly 窓は caller 管理)。

入力:
  - archive_members: Sequence[ArchiveMember] (= 直近 N Run の集合 union)
  - n_runs_aggregated: int (= 何 Run 分の集計か、 caller が明示)

集計:
  - 各 archive member の session_pass_pattern (= "1,1,0" 等の Tokyo/London/NY pass 状況の 3 bit string)
  - 出現頻度の分布 p_i = count_i / total
  - Shannon entropy: H = -sum(p_i * log2(p_i))

パターン空間 (Round 1 [W3] 反映、 整合):
  - 3 bit (Tokyo/London/NY) で全 8 パターン (000, 001, ..., 111)
  - max entropy = log2(8) = 3.0 (= 全 8 パターン等頻度時)
  - relative_entropy = H / log2(8) で [0, 1] 正規化

status 判定 (Round 1 [C1] / [C5] 反映、 Optional 経路排除):
  - n_runs_aggregated < 7:                        status="insufficient_window", entropy=Decimal(0)
  - n_runs_aggregated >= 7, n_archive_members==0: status="empty_archive",       entropy=Decimal(0)
  - 通常:                                         status="ok",                  entropy ∈ [0, 3]

出力 SessionEntropyMetric:
  - status: Literal["ok", "insufficient_window", "empty_archive"]
  - shannon_entropy: Decimal
  - relative_entropy: Decimal   (= shannon_entropy / log2(8))
  - n_unique_patterns: int
  - n_archive_members: int
  - n_runs_aggregated: int     (caller 注入の窓サイズ、 status 判定に使用)
  - aggregation_window_target: Literal["weekly"] = "weekly"   # T071 SSOT、 T072 で別期間検討

注: session_pass_pattern field は T064 / T066 で管理、 T071 では消費するのみ。
RunObservabilityReport は **常に SessionEntropyMetric を保持** (= None 経路なし、 status で表現)。
```

### 3.7 feasible_ratio_ema 観測

T063 (StageAControllerState) で計算済の値を T071 が **読み取って記録のみ** (= 計算は T063 担当)。

```
入力: StageAControllerState.feasible_ratio_ema
出力 FeasibleRatioMetric:
  - feasible_ratio_ema: Decimal
  - fsm_state: Literal["push", "pull"]   # T066 から
  - n_feasible_individuals: int
```

### 3.8 front1 cardinality (synthesis § 10.1、 pop promotion trigger)

```
SSOT: 「Pareto front rank 1 のサイズ。 pop promotion (192→256) trigger に使用」

入力: GenerationSelectionResult (T065)
計算: result.pareto_front1_size (T065 field を直接使用)

出力 SelectionMetric:
  - front1_cardinality: int
  - feasible_ratio: Decimal
  - mean_constraint_violation: Decimal
  - generation: int

pop promotion 判定 (Phase 2 で run_ga.py 配線):
  if front1_cardinality < 20 for 連続 2 Run:
      pop_size = 192 → 256
```

### 3.9 inflow / per_run_max / warmstart_share 動作確認 (synthesis § 10.1、 Round 1 [C4] 反映で API 統合)

WarmstartReport (T067) + AdmissionReport (T066) + config 値の比較で「設定通り動作」 を検証:

```
入力 (Round 1 [C4] 反映、 AdmissionReport も統合):
  - warmstart_report: WarmstartReport
  - admission_report: AdmissionReport
  - config: WarmstartConfig + InflowConfig (= warmstart_share_target, per_run_max,
    ca_inflow_target, da_inflow_target, bypass_share_target 等)

判定:
  - warmstart_share_actual ≈ warmstart_share_target (許容誤差 ±0.01)
  - per_run_max_breached: bool (= max_per_source_run / max_per_session_pattern / max_family 違反)
  - inflow_balance: AdmissionReport.n_admitted_by_role の内訳
    - ca_inflow_actual / target、 da_inflow_actual / target、 bypass_inflow_actual / target

出力 InflowConsistencyMetric (Round 1 [C4] 反映、 命名統一):
  - warmstart_share_target: Decimal
  - warmstart_share_actual: Decimal
  - share_drift: Decimal (= actual - target)
  - within_tolerance: bool
  - relaxation_steps_count: int
  - per_source_run_violations: int  (= max_per_source_run cap 越え件数)
  - ca_inflow_actual: int
  - da_inflow_actual: int
  - bypass_inflow_actual: int
  - inflow_summary_by_role: dict[ArchiveRole, int]
```

### 3.10 FailureSummary 消費 (T068)

```
入力: RunFailureSummary (T068)
出力 FailureMetric:
  - run_id: str
  - run_aborted: bool
  - per_stage: dict[StageName, FailureMetricStage]
    - n_failure_records: int
    - n_failed_genomes: int
    - eligible_individuals: int
    - failure_rate: Decimal (= n_failed_genomes / max(eligible_individuals, 1))
    - fingerprint_top_3: tuple[FingerprintRecord, ...]   (= dedup 上位 3 件)

構造化 log:
  logger.info("observability.failure_summary", run_id=..., per_stage={...}, run_aborted=...)
```

## 4. データモデル (Phase 1 範囲)

### 4.1 各 metric dataclass (frozen=True, immutable)

§3 で列挙した 9 dataclass:
- ABDivergenceMetric
- QForceRecommendation
- ArchiveChurnMetric
- BypassRatioMetric
- SessionEntropyMetric
- FeasibleRatioMetric
- SelectionMetric
- InflowConsistencyMetric (旧 WarmstartConsistencyMetric、 Round 1 [C4] 反映)
- FailureMetric (+ FailureMetricStage)

### 4.2 RunObservabilityReport (集約)

```python
@dataclass(frozen=True)
class RunObservabilityReport:
    """1 Run 全体の observability 集約 (= run_ga.py が末尾で構築、 log/report に渡す)."""

    run_id: str
    dataset_epoch_id: str   # T058 schema v2
    generation_count: int

    # Round 1 [C1] / [S1] 反映: None 排除、 全 metric は status field で「計算不能」 を表現
    ab_divergence: ABDivergenceMetric             # 常に存在、 status で計算可否
    q_force_recommendation: QForceRecommendation  # 常に存在、 reason で適用可否
    archive_churn: ArchiveChurnMetric             # 常に存在、 status で 3 Run 蓄積可否
    bypass_ratio: BypassRatioMetric
    session_entropy: SessionEntropyMetric         # 常に存在、 status で weekly 蓄積可否
    feasible_ratio: FeasibleRatioMetric
    selection: SelectionMetric
    inflow_consistency: InflowConsistencyMetric   # Round 1 [C4] 反映で命名・API 統合
    failure: FailureMetric
```

不変条件:
- `run_id`, `dataset_epoch_id` は非空 str
- `generation_count >= 0`
- `q_force_recommendation` は必ず存在 (`reason="insufficient_data"` で fallback)

## 5. API シグネチャ (§ 11.2 SSOT 規約)

### 5.1 compute_ab_divergence (Round 1 [C2] / [S2] 反映で conditioning 明示)

```python
def compute_ab_divergence_on_b_evaluated(
    a_proxy_scores_b_evaluated: Sequence[Decimal],
    b_pooled_scores: Sequence[Decimal],
) -> ABDivergenceMetric:
    """A→B 乖離 Pearson correlation を計算 (B 評価対象個体に条件付け).

    SSOT: 概念設計 §3.2.

    集計対象: B 評価が走った個体集合のみ (= A pass を経由した個体)。 A pass で条件付けられた
    部分母集団であり、 母集団相関ではない (C3 collider bias 観点)。 解釈は「B 評価対象の探索
    方向と A proxy の整合性」 に限定。

    Args:
        a_proxy_scores_b_evaluated: 各 B 評価対象個体の A proxy score (T063 由来).
        b_pooled_scores: 同個体の B pooled score (T064 由来).
            len(a_proxy_scores_b_evaluated) == len(b_pooled_scores) を要求.
            両 sequence は同一個体順 (caller 責務).

    Returns:
        ABDivergenceMetric. status field で計算可否を表現:
            status="ok": corr ∈ [-1, 1] (clamp 後) で有効
            status="insufficient_data": n < 2 (= corr = 0 sentinel、 使用禁止)
            status="zero_variance": var(a)=0 or var(b)=0 (= corr = 0 sentinel)
        n_pairs: 計算に使った組み数 (= B 評価済個体数).

    Raises:
        ValueError: 長さ不一致 (caller bug).
    """
```

### 5.2 recommend_q_force_adjust (Round 1 [C1] / [C3] / [W4] 反映)

```python
def recommend_q_force_adjust(
    current_q_force: Decimal,
    divergence: ABDivergenceMetric,
    consecutive_divergent_runs: int,
    *,
    # synthesis § 8.7 確定値 (= 厳密準拠):
    delta_per_run: Decimal = Decimal("0.02"),
    q_force_max: Decimal = Decimal("0.40"),
    restore_threshold: Decimal = Decimal("0.50"),
    # T071 仮説値 (Round 1 [C3] 反映、 synthesis 未明示):
    q_force_min: Decimal = Decimal("0.15"),
    divergence_threshold: Decimal = Decimal("0.30"),
) -> QForceRecommendation:
    """A→B 乖離に応じた q_force 補正推奨.

    SSOT: 概念設計 §3.3.

    Round 1 [C1] 反映: divergence: ABDivergenceMetric を入力、 status field で計算可否を判定
    (None 経路排除).
    Round 1 [C3] 反映: divergence_threshold / q_force_min は T071 仮説値 (synthesis 未明示).
    Round 1 [W4] 反映: consecutive_divergent_runs は report/log 用、 delta 判定式には使わない.

    判定 (1 Run あたり ±0.02 が SSOT、 連続回数で増分されない):
        if divergence.status != "ok":
            reason = "insufficient_data" or "zero_variance" (status に応じて)
            delta = 0
        elif divergence.corr < divergence_threshold:
            reason = "raise"
            delta = +delta_per_run (q_force_max で clamp)
        elif divergence.corr >= restore_threshold:
            reason = "restore"
            delta = -delta_per_run (q_force_min で clamp)
        else:
            reason = "hold"
            delta = 0

    適用モデル: caller が 1 Run ごとに本関数を再適用 (= idempotent pure function).
    consecutive_divergent_runs は監視 log のみで delta には影響しない (synthesis § 8.7 厳密準拠).

    Args:
        current_q_force: 現在の q_force 値.
        divergence: 現 Run の A→B 乖離 metric.
        consecutive_divergent_runs: caller 保持の連続乖離 Run 数 (report/log 用).

    Returns:
        QForceRecommendation.
    """
```

### 5.3 compute_archive_churn

```python
def compute_archive_churn(
    recent_admission_reports: Sequence[AdmissionReport],
) -> ArchiveChurnMetric:
    """直近 N Run (max 3) の eviction 率を計算.

    Args:
        recent_admission_reports: 新しい順でも古い順でも可、 単純合計するため.
            空入力 → ValueError.

    Returns:
        ArchiveChurnMetric (n_runs_used <= 3).
    """
```

### 5.4 compute_bypass_ratio

```python
def compute_bypass_ratio(
    report: AdmissionReport,
) -> BypassRatioMetric:
    """1 Run の bypass 比率を計算.

    Args:
        report: AdmissionReport.

    Returns:
        BypassRatioMetric.
    """
```

### 5.5 compute_session_entropy (Round 1 [C5] 反映で weekly 窓を caller 管理に)

```python
def compute_session_entropy(
    archive_members: Sequence[ArchiveMember],
    n_runs_aggregated: int,
    *,
    weekly_window_size: int = 7,
) -> SessionEntropyMetric:
    """archive 内 session_pass_pattern 分布の Shannon entropy.

    SSOT: 概念設計 §3.6.

    Round 1 [C5] 反映: T071 内では履歴を持たない (= pure function)、 caller が「直近 N Run 分の
    archive members」 を集めて n_runs_aggregated と共に渡す。 weekly 判定は本関数内で行う。

    Args:
        archive_members: 直近 n_runs_aggregated Run 分の ArchiveState.ca_members +
                         da_members の集合 union.
        n_runs_aggregated: 何 Run 分集計したか (caller 注入).
        weekly_window_size: weekly 判定の Run 数 (default 7).

    Returns:
        SessionEntropyMetric. status field で計算可否を表現:
            status="insufficient_window": n_runs_aggregated < weekly_window_size (= entropy=0)
            status="empty_archive": archive_members が空 (= entropy=0)
            status="ok": entropy ∈ [0, log2(8)=3.0]
    """
```

### 5.6 extract_selection_metrics / extract_inflow_consistency / extract_failure_metrics

```python
def extract_selection_metrics(result: GenerationSelectionResult) -> SelectionMetric: ...

def extract_inflow_consistency(
    warmstart_report: WarmstartReport,
    admission_report: AdmissionReport,
    config: WarmstartConfig | InflowConfig,
) -> InflowConsistencyMetric:
    """Round 1 [C4] 反映: warmstart + admission + config を統合して inflow 整合性を判定."""
    ...

def extract_failure_metrics(summary: RunFailureSummary) -> FailureMetric: ...
```

### 5.7 build_run_observability_report (集約、 Round 1 [C1] / [C4] 反映で None 排除)

```python
def build_run_observability_report(
    run_id: str,
    dataset_epoch_id: str,
    generation_count: int,
    *,
    ab_divergence: ABDivergenceMetric,            # 常に存在 (Round 1 [C1])
    q_force_recommendation: QForceRecommendation,
    archive_churn: ArchiveChurnMetric,            # 常に存在
    bypass_ratio: BypassRatioMetric,
    session_entropy: SessionEntropyMetric,        # 常に存在
    feasible_ratio: FeasibleRatioMetric,
    selection: SelectionMetric,
    inflow_consistency: InflowConsistencyMetric,  # 旧 warmstart_consistency、 [C4] 反映
    failure: FailureMetric,
) -> RunObservabilityReport:
    """1 Run の集約 report を構築する pure function."""
```

## 6. 関連 module 変更点

### 6.1 src/alpha_factory/observability/run_metrics.py (新規)

§3 / §4 / §5 の全関数 + dataclass。 単一 module で集約。

### 6.2 src/alpha_factory/observability/__init__.py (新規)

```python
from src.alpha_factory.observability.run_metrics import (
    ABDivergenceMetric,
    ArchiveChurnMetric,
    BypassRatioMetric,
    FailureMetric,
    FeasibleRatioMetric,
    QForceRecommendation,
    RunObservabilityReport,
    SelectionMetric,
    SessionEntropyMetric,
    InflowConsistencyMetric,                     # Round 1 [C4] 命名統一
    build_run_observability_report,
    compute_ab_divergence_on_b_evaluated,        # Round 1 [S2] 命名統一
    compute_archive_churn,
    compute_bypass_ratio,
    compute_session_entropy,
    extract_failure_metrics,
    extract_selection_metrics,
    extract_inflow_consistency,                  # Round 1 [C4] 命名統一
    recommend_q_force_adjust,
)

__all__ = [
    # ... (上記全シンボル)
]
```

### 6.3 既存 module への影響

T071 PR は **library 単独**、 既存 module への signature 変更なし。 caller 配線は Phase 2:
- `scripts/alpha_factory/run_ga.py`: build_run_observability_report 呼び出し + log/report 出力
- `src/alpha_factory/stage_a_evaluator.py` (T063): q_force_recommendation の caller 配線 (StageAControllerState 更新)
- `docs/alpha_factory/stage-gates.md`: T071 セクション追記 (T071 PR 内で実施)

## 7. C9 Falsification-first

T071 が壊れる経路を **先に列挙**:

| 失敗モード | 検出方法 | 対処 |
|---|---|---|
| F1: Pearson corr で n=0 / n=1 で divide by zero | n<2 で `status="insufficient_data"` (corr=0 sentinel) (Round 2 [W2] 反映) | unit test で確認 |
| F2: var(a) == 0 / var(b) == 0 で nan | denom 0 check で `status="zero_variance"` (corr=0 sentinel) (Round 2 [W2] 反映) | unit test で確認 |
| F3: 数値誤差で corr が [-1, 1] を越境 | clamp([-1, 1]) を __post_init__ で適用 | invariant test |
| F4: q_force が max/min を越境 | clamp を recommendation 関数で適用 | clamped_at_max / clamped_at_min field |
| F5: hysteresis 不整合 (raise / restore で同 corr 値で振動) | divergence_threshold (0.30) < restore_threshold (0.50) で hysteresis | docstring 明示 |
| F6: archive_churn の denom 0 (= total_admissions=0) | max(total, 1) で防御 | unit test |
| F7: bypass_ratio の denom 0 | 同上 | unit test |
| F8: session_entropy で archive_members 空 | n=0 → entropy=0 で no-raise | unit test |
| F9: InflowConsistencyMetric の許容誤差不整合 (Round 1 [C4] 命名統一) | tolerance=0.01 で SSOT | unit test |
| F10: RunObservabilityReport の None field 経路で caller crash | Round 2 [C1] / Round 2 [W2] 反映で Optional 経路完全排除、 全 metric は status field で「計算不能」 を表現、 caller は status を読んで「使用可否」 を判定 | §4.2 / §3 全節 |
| F11: T065-T068 dataclass field 名変更で T071 が壊れる | §9.0 hard dependency で T065-T068 先行 merge 必須化、 T071 PR 内で全 field 名を具体的 grep + 一致確認 (cross-PR change-detection)、 PR description に merge commit hash 明記 (Round 1 [C6] / [S4] 反映) | hard dependency |
| F12: corr 計算で個体 a/b の対応がずれる | 入力 sequence が同一個体順で並んでいる前提を docstring 明示 + len 一致 check | ValueError raise |
| F13: divergence_threshold 0.30 が synthesis 確定値でない | T071 SSOT で固定 + Codex レビューで合意、 caller (Phase 2) で override 可 | concept-level 確定 |
| F14: 連続乖離 Run カウントの保持責務 | T071 自身は state を持たない (= 関数 input)、 caller が保持 | docstring 明示 |
| F15: q_force_recommendation の delta 適用順序 (raise → restore) | hysteresis (0.30 < 0.50) で同 corr 値で両方発火しない | unit test で振動なし確認 |

## 8. 期待効果

### 8.1 synthesis § 8.7 / § 10.1 厳密準拠

- A→B 乖離監視 + q_force 自動補正で探索誤誘導を warn-only で抑止 (= synthesis Risk #1 緩和)
- archive churn / bypass 比率で品質低下を可視化
- front1 cardinality で pop promotion trigger を提供
- session entropy で multi-pattern 達成を週次監視

### 8.2 副次効果

- T065-T068 dataclass の消費経路を T071 で集中、 cascade port 全体の整合性向上
- Phase 2 で run_ga.py / report.md 配線時に最小変更
- Audit layer (T073) との責務分離 (= T071 = 観測、 T073 = 統計検定)

## 9. Phase 1 / Phase 2 申し送り

### 9.0 Hard dependency (Round 1 [C6] / [S4] 反映)

**T065-T068 PR が先行 merge されていることが必須** (T071 単独 merge 不可):
- T065 GenerationSelectionResult / T066 AdmissionReport, ArchiveState, ArchiveMember /
  T067 WarmstartReport, WarmstartConfig / T068 RunFailureSummary, FailureSummary, StageName を
  T071 が import し、 field を直接読む
- mock fixture は T071 PR 内 test 用に最小限定義するが、 本番 import は T065-T068 シンボル必須
- PR description に「T065 / T066 / T067 / T068 merge commit hash」 を明記
- field rename / semantic change を検出する mitigation: T065-T068 の全 dataclass field 名を
  T071 PR 内で具体的に grep + 一致確認 (= cross-PR change-detection)

### 9.1 Phase 1 (T071 PR で同時更新)

| # | 箇所 | 変更内容 |
|---|---|---|
| 1 | `src/alpha_factory/observability/__init__.py` | 新設 (公開 API export) |
| 2 | `src/alpha_factory/observability/run_metrics.py` | 新設 (dataclass 群 + 関数群) |
| 3 | `tests/alpha_factory/observability/test_run_metrics.py` | F1-F15 unit test |
| 4 | `docs/alpha_factory/stage-gates.md` | T071 セクション追記 |

### 9.2 Phase 2 (cascade port 切替 commit)

| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 5 | `scripts/alpha_factory/run_ga.py` | build_run_observability_report 呼び出し + log/report 出力 + 連続乖離 Run カウント保持 | Phase 2 |
| 6 | `src/alpha_factory/stage_a_evaluator.py` (T063) | q_force_recommendation の caller 配線 (StageAControllerState 更新) | T063 詳細設計改訂 / Phase 2 |
| 7 | `docs/alpha_factory/observability.md` (新規) | RunObservabilityReport の Markdown 表現 + 監視運用 ガイド | Phase 2 |
| 8 | T073 audit layer | DSR 等は T073、 T071 metric の一部 (= ab_divergence) は audit input | T073 |
| 9 | run report (Phase 2 配線) | RunObservabilityReport を Markdown 化 (run_ga.py / report skill 経由) | Phase 2 |

## 10. 制約 / 非目標 (T071 範囲外)

| 項目 | 担当 |
|---|---|
| DSR / PBO / SPA 計算 | T073 (T916) audit layer |
| q_force の caller 配線 (StageAControllerState 更新) | T063 詳細設計改訂 / Phase 2 |
| RunObservabilityReport の Markdown 化 | Phase 2 (run_report skill) |
| 連続乖離 Run カウントの永続化 | Phase 2 (run_ga.py が state file 経由で保持) |
| pop promotion (192→256) 実行 | Phase 2 (run_ga.py が front1<20 連続 2 Run で trigger) |

## 11. 削除対象 (Big-bang)

T071 では削除なし。 純粋追加 (= library 新設)。

## 12. テスト方針 (Phase 1)

- `tests/alpha_factory/observability/test_run_metrics.py`:
  - F1-F15 各失敗モードの unit test (Pearson corr の n<2 / var=0 / 越境 / hysteresis / q_force 範囲)
  - happy path: 通常入力で各 metric が正しく計算される
- 既存 dataclass (T065-T068) は **mock fixture** で代用 (= T065-T068 PR が先行 merge される前提、 fixture は最低限 field を埋める)

外部通信なし (= pure function テスト中心)。

## 13. 主要な設計判断サマリー (Round 1 反映後)

1. **単一 module `run_metrics.py` で機能集約**: 「複雑案禁止」 制約に従い、 dataclass + 関数を 1 ファイルに集約。 Phase 2 で肥大化したら分割
2. **Pearson corr で A→B 乖離計算 (B 評価対象個体集合に conditioning)** (Round 1 [C2] / [S2]): synthesis SSOT 通り linear corr、 conditioning set を関数名 (`compute_ab_divergence_on_b_evaluated`) で明示
3. **q_force 補正は推奨のみ、 caller (Phase 2) で適用**: T071 自身は state を持たない、 idempotent pure function
4. **synthesis 確定値 vs T071 仮説値の分離** (Round 1 [C3]): 上限 0.40 / 0.02 / 戻し 0.5 は synthesis 厳密、 divergence_threshold=0.30 / q_force_min=0.15 は T071 仮説値として明記
5. **status field で「計算不能」 を表現、 None 経路排除** (Round 1 [C1] / [S1]): 全 metric 常に存在、 ab_divergence.status / archive_churn.status / session_entropy.status で計算可否
6. **T065-T068 hard dependency 明文化** (Round 1 [C6] / [S4]): §9.0 で先行 merge 必須化、 PR description に merge commit hash 記載、 field grep で cross-PR change-detection
7. **DSR/PBO/SPA は T073 で別 layer**: T071 = 観測、 T073 = 統計検定の責務分離
8. **連続乖離 Run カウントは caller 責務、 delta 判定式には使わない** (Round 1 [W4]): T071 は input として受ける、 state 永続化は run_ga.py / state file
9. **session_entropy weekly 窓は caller 管理** (Round 1 [C5]): T071 は履歴を持たず、 caller が n_runs_aggregated を渡す、 status="insufficient_window" で表現
10. **inflow_consistency に AdmissionReport も統合** (Round 1 [C4]): WarmstartReport + AdmissionReport + config を 1 関数で受け、 ca/da/bypass inflow を網羅
