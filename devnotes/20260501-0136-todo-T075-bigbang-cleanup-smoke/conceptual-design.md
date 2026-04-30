# T075 — Big-bang cleanup + smoke (概念設計)

**作成日時**: 2026-05-01 01:36 JST (Round 2 改訂: 02:30 JST、 Round 3 改訂: 03:00 JST、 Round 4 改訂: 03:30 JST)
**Round 3 反映**: C1 / W1-W5 / S1-S4 全反映:
- Round R3 [C1] [S1]: **max 集約で inconclusive が warning に隠れる問題** 解消、 `AggregateEvidence(severity, has_inconclusive, inconclusive_reasons)` dataclass 新設で別軸保持、 C8 規範「データ不足は正当な結論」 を保護
- Round R3 [S2]: `decide_release_action` 優先順位変更: `hard_fail → has_inconclusive → FM observed → warning → ok` の順
- Round R3 [W1]: `EvidenceClassifierProtocol` に **`supported_metric_names() -> frozenset[str]`** method 追加、 conformance test fixture 規範
- Round R3 [W2]: epoch field rename: per-run `epoch_consistency_class` / cross-run `cross_run_epoch_pollution_class`
- Round R3 [W3]: `source_clause_id` は synthesis 改訂で stable clause anchor 導入を Round 22 改訂候補追加 (= 既存 synthesis に anchor 体系不在前提)
- Round R3 [W4]: DeletionTarget / MigrationTarget に **`change_group_id`** + **`supersedes`** field 追加、 複合 case grouping
- Round R3 [W5]: `candidate_proceed` → **`no_blocker_observed`** に rename (= 「自動承認」 誤読 risk 低減)
- Round R3 [S3]: dual-path enforce allowlist 追加 (= `docs/runbook` warning、 `docs/historical` / `devnotes` 除外)
- Round R3 [S4]: `select_rollback_relevant_failure_modes(observed, policy)` API 名を T075 で **予約** (= 関数 stub、 Phase 2 別 TODO で実装)

**Round 2 反映**: C1-C3 / W1-W6 / S1-S4 全反映:
**Round 2 反映**: C1-C3 / W1-W6 / S1-S4 全反映:
- Round R2 [C1]: `Severity` に **`inconclusive` を追加** (= EvidenceClass と同型 4 値)、 型体系統一
- Round R2 [C2]: `decide_release_action` に **`inconclusive` 分岐追加** (→ "hold_for_review")
- Round R2 [C3]: **`EvidenceClassifierProtocol`** を概念で SSOT 化 (= caller 実装する Protocol、 入力 provenance / 分類根拠 / 未対応時 inconclusive を規範)
- Round R2 [W1] [S2]: `SmokeDoDItem` に **`scope: Literal["per_run", "cross_run"]`** field 追加
- Round R2 [W2] [S2]: `ReleaseActionRecommendation.recommended_action` 値名弱化 (= "proceed" → "candidate_proceed" / "delay" → "hold_for_delay" / "manual_review" → "hold_for_review"、 hint only 強調)
- Round R2 [W3]: `DeletionTarget.source_clause` を **`source_clause_id` + `source_excerpt_hash`** に変更 (= synthesis 改訂同期負債回避)
- Round R2 [W4]: `RemovalMode` を **cleanup 用 (= "git_rm" / "yaml_key_delete") と migrate 用 (= "yaml_value_replace") に分離**、 後者は別 manifest (`MigrationTarget`) に分離
- Round R2 [W5]: dual-path enforce grep DoD を **source / config / scripts / docs runbook の 4 経路に拡張**
- Round R2 [W6]: typed projection に **`epoch_consistency_class: EvidenceClass`** field 追加 (= FM2 対応)
- Round R2 [S1]: `EvidenceClass` 順序 (= "hard_fail" > "warning" > "inconclusive" > "ok") を invariant 化
- Round R2 [S3]: `observed_fms` → `observed_failure_modes` に rename
- Round R2 [S4]: T075 PR が synthesis Round 22 改訂前に先 merge する場合は **CI / tests で `runtime unreachable` + `no release decision authority` を固定**
**親 TODO**: T075 (synthesis § 18.2 T918 — Big-bang cleanup + smoke)
**Milestone**: M6 最終 (T073 / T074 完了済、 T075 で **cascade port 設計 18 件完了**)
**前提 commit**: `main@b591988` (T074 commit 後)
**Round 1 反映**: C1-C6 / W1-W6 / S1-S5 全反映

**関連設計 (前提)**:
- `devnotes/20260428-2300-cascade-port-debate/synthesis.md` § 12 / § 16 / § 18.2 T918 / § 18.3
- T058-T074 全 17 設計
- T071 RunObservabilityReport (= status field 方式)
- T072 / T073 / T074 collider bias 規範

---

## 0. 結論 (TL;DR、 Round 2)

T075 は cascade port v2 への big-bang 切替最終 PR の **設計フェーズ**、 **synthesis local projection に限定** (Round R1 [C1] 反映で「親 SSOT 再定義」 を回避):

1. **新規 module (純ライブラリ)**: `src/alpha_factory/smoke.py`、 Phase 1 は library + 単体テストのみ
2. **synthesis local projection SSOT** (Round R1 [C1] [S1] 反映): T075 module は synthesis / T071-T074 SSOT を **参照のみ**。 FM1-FM5 / new_cascade 非採用 / DoD 機械検証形式 等は **synthesis Round 22 改訂を blocked-by 依存** として明示、 T075 で「再定義」 しない。 改訂が main merge されるまで T075 は **evidence collection のみ**、 manual review に委ねる
3. **DoD 二層分離** (Round R1 [C2] [S2] 反映): `PerRunSmokeDoDResult` (= DoD1-DoD7、 1 Run 単位) / `CrossRunSmokeDoDResult` (= DoD8、 5 Run 集約) を分離、 `BigBangCleanupReport` が両者を束ねる
4. **threshold-free classification** (Round R1 [C3] [S3] 反映): `EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]` で evidence 収集のみ、 数値 threshold (= FM1=0.3 等) は **T075 で SSOT 化しない**。 数値確定は別 TODO + smoke 後再校正、 T075 では caller (= manual review or 後段別 TODO) が evidence_class を判定材料として使う
5. **rollback decision 2 段階化** (Round R1 [C4] [S5] 反映): `classify_smoke_outcome` (= 事実認定、 evidence_class 集計) と `decide_release_action` (= 運用判断 hint、 manual review に委ねる前段) を分離。 自動 rollback / proceed の硬い truth table は廃止、 `severity` (= "hard_fail" / "warning" / "ok") 軸 + FM kind の 2 次元を report
6. **typed projection** (Round R1 [C5] 反映): `SmokeRunSummary.observability_metrics_snapshot` を `Mapping[str, Decimal]` から **typed dataclass** (= `SmokeObservabilityProjection`) に変更、 SSOT 漏れ排除
7. **削除対象 manifest 規約 + 全件列挙生成手順** (Round R1 [C6] [S4] 反映): 概念設計で manifest schema (= path / category / source_section / source_clause / removal_mode / owner) を SSOT 化。 全件列挙は **詳細設計で synthesis 全文 grep + default.yaml dump で生成する手順** を概念で明示
8. **dual-path operational definition** (Round R1 [W3] 反映): 「並走」 = runtime 到達可能 OR feature flag で切替可能 OR 同じ出力契約を二経路で生成。 「同居」 (= source tree に残るが runtime 到達不能) は OK
9. **collider bias non-goal 明記** (Round R1 [W6] 反映): T075 では stratified audit / 因果解釈 / 比率差を判定しない、 T072-T074 と衝突しない
10. **observed_fms / rollback_relevant_fms 分離** (Round R1 [W4] 反映): 観測 FM 全集合と「rollback 判定材料となる FM」 を別軸 (= synthesis Round 22 改訂後にどの FM が rollback_relevant か再確定)
11. **1 cycle = run cadence** (Round R1 [W2] 反映): `ROLLBACK_DELAY_CYCLE_DAYS = 7` を **概念設計から削除**、 「1 cycle = run cadence (= Phase 2 で別途確定)」 と概念で記述
12. **status field 方式継承** (T071 / T073 / T074): `EvidenceClass` 4 値で None 経路完全排除
13. **early gate ではない / read-only**: smoke harness は archive read-only、 selection 経路 touch しない
14. **archive 配線は Phase 2**: T071 RunObservabilityReport.smoke_dod field 配線 + run_ga.py の smoke 統合は Phase 2 別 PR
15. **scaffold 数値 field なし** (T073 / T074 SSOT 継承): SmokeDoDItem は status + detail (= 文字列) のみ、 数値判定は caller / 別 TODO

---

## 1. T075 が解決する問題

### 1.1 synthesis § 12 / § 18.2 T918 / § 18.3 で確定済の責務 (Round 1 [C1] 反映、 T075 は projection)

| 項目 | synthesis 文言 | T075 対応 (Round 2) |
|---|---|---|
| 削除対象 | § 12.1 | DeletionTarget manifest 規約 SSOT、 全件列挙は詳細設計で synthesis grep + yaml dump |
| 全面置換対象 | § 12.2 | 同上 manifest |
| 縮退保持対象 | § 12.3 | DeletionTarget に含めず、 lint で誤削除防止 |
| 切替戦略 | § 12.4 | dual-path operational definition + 切替コミット 1-shot |
| smoke DoD | § 18.3 | PerRunSmokeDoDResult (DoD1-7) + CrossRunSmokeDoDResult (DoD8) で機械検証 |
| ロールバック | § 12.4「FM1/FM4」 | T075 では数値 threshold 持たず、 evidence_class 集計のみ。 「FM1/FM4」 文言の確定は synthesis Round 22 改訂 blocked-by |
| Risk Top 5 | § 16 | FailureModeKind (FM1-FM5) Literal で **enum 定義のみ**、 数値判定 / threshold は T075 範囲外 |

### 1.2 synthesis Round 22 改訂候補 (Round R1 [C1] [S1] 反映、 blocked-by 明示)

T075 PR merge 前に synthesis Round 22 改訂が必要な項目:

| 改訂項目 | T075 動作 (改訂前) | T075 動作 (改訂後) |
|---|---|---|
| § 12.4 「new_cascade 名前空間」 文言 | T075 module は new_cascade 採用しない方針を **本文に non-goal として記述**、 ただし synthesis 改訂前は blocked-by | synthesis Round 22 で「採用しない、 直接 src/alpha_factory/* で実装」 と明文化後、 T075 docstring から blocked-by 解除 |
| § 12.4 「FM1/FM4」 ロールバック条件 | T075 は FM1-FM5 enum を Literal で持つが、 **どの FM が rollback_relevant か synthesis 改訂後に確定**。 改訂前は manual review | synthesis Round 22 で FM1-FM5 SSOT 定義 + rollback_relevant 集合を明文化 |
| § 18.3 Smoke DoD 8 項目 | DoD1-DoD8 を Literal で持つ、 synthesis_text は原文を quote。 機械検証形式は T075 で構造化、 ただし synthesis 文言の解釈は parent SSOT 依存 | synthesis Round 22 で「DoD8 は cross-run、 DoD1-7 は per-run」 等を明文化 |

T075 PR merge 順序: **synthesis Round 22 改訂 PR を先 merge**、 T075 PR は本依存を blocked-by として記述。 synthesis 改訂が無い場合は T075 docstring 「synthesis 改訂後の SSOT 移行待ち」 を明示し、 evidence collection only mode で動作。

### 1.3 既存実装との関係 (Round R1 [C6] 反映、 manifest 規約)

T075 PR ではこれら全てを Phase 2 切替コミットで **同日削除** (dual-path 並走なし、 同居は許容)。 削除対象は **DeletionTarget manifest schema** で SSOT 化:

```python
@dataclass(frozen=True)
class DeletionTarget:
    path: str                      # 例: "src/alpha_factory/calibrate_gate.py" / "stage_gate.stage_a.target_pass_rate"
    category: str                  # "並走機構" / "旧 config キー" / "旧 script" / "全面置換"
    source_section: str            # synthesis section "12.1" / "12.2"
    source_clause: str             # synthesis 該当 bullet (= 引用文字列)
    removal_mode: Literal["git_rm", "yaml_key_delete", "yaml_value_replace"]
    owner: str                     # 削除責務 PR (= "T058 PR" / "T069 PR" 等の文字列参照)
```

全件列挙は **詳細設計フェーズ**で:
1. `synthesis.md` から § 12.1 / § 12.2 を grep、 全 bullet を抽出
2. `config/alpha_factory/default.yaml` を yaml.safe_load → 全 key dump
3. T058-T074 詳細設計の「Phase 2 で削除」 申し送りを集約
4. 上記 3 source の和集合を DeletionTarget tuple として fixture 化
5. CI lint で synthesis bullet count == DeletionTarget count を検証 (= 漏れ防止)

---

## 2. 設計の SSOT 原則

### 2.1 不変 (T058-T074 / synthesis SSOT)

- T058-T074 全 17 設計の SSOT
- synthesis § 12.1-12.4 / § 16 / § 18.3
- T071 RunObservabilityReport
- T072 / T073 / T074 collider bias 規範
- T073 / T074 scaffold SSOT (= 数値 field なし)

### 2.2 T075 で新設 (SSOT、 Round R1 [C1] [C2] [C3] [C5] 反映で local projection 限定)

#### 型・定数

- `EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]` (Round R1 [C3] [S3] / Round R2 [S1] 反映)
  - **順序 SSOT (Round R2 [S1])**: "hard_fail" > "warning" > "inconclusive" > "ok" (= severity 集約時の max 規約)
  - inconclusive は manual review 推奨 (= データ不足、 C8 規範整合)
- `Severity = Literal["hard_fail", "warning", "inconclusive", "ok"]` (Round R2 [C1] 反映で **EvidenceClass と同型 4 値**、 inconclusive 型落ち排除)
- `FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]` (synthesis § 16 enum、 数値 threshold は T075 範囲外)
- `DoDIdPerRun = Literal["DoD1", "DoD2", "DoD3", "DoD4", "DoD5", "DoD6", "DoD7"]` (Round R1 [W5] 表記修正、 1 Run 単位)
- `DoDIdCrossRun = Literal["DoD8"]` (Round R1 [C2] 分離、 5 Run 集約単位)
- `RemovalMode = Literal["git_rm", "yaml_key_delete"]` (Round R2 [W4] 反映、 cleanup 専用、 migrate は別 manifest `MigrationTarget`)
- `MigrationMode = Literal["yaml_value_replace"]` (Round R2 [W4] 別 manifest、 cleanup と分離)
- `SMOKE_RUNS_REQUIRED: Final[int] = 5` (synthesis § 18.3)
- `PER_RUN_DOD_ITEMS_COUNT: Final[int] = 7` (= DoD1-DoD7)
- `CROSS_RUN_DOD_ITEMS_COUNT: Final[int] = 1` (= DoD8)
- `SMOKE_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"`

**Round R1 [C3] [W2] 反映で削除した数値定数**:
- ~~FM1_DIVERGENCE_THRESHOLD = 0.3~~ → T075 範囲外、 別 TODO
- ~~FM3_WARMSTART_SHORTFALL_RUN_COUNT = 2~~ → 同上
- ~~FM4_BYPASS_RATIO_THRESHOLD = 0.7~~ → 同上
- ~~FM5_ENTROPY_THRESHOLD = 0.5~~ → 同上
- ~~ROLLBACK_DELAY_CYCLE_DAYS = 7~~ → 「1 cycle = run cadence」 (Phase 2 確定)

#### dataclass (frozen)

- `DeletionTarget` (Round R1 [C6] [S4] / Round R2 [W3] [W4] / Round R3 [W4]): path / category / source_section / source_clause_id / source_excerpt_hash / removal_mode / owner / **change_group_id** (= 同一論理変更 grouping) / **supersedes: tuple[str, ...]** (= 新 module 参照)
- `MigrationTarget` (Round R2 [W4] / Round R3 [W4]): path / category / source_section / source_clause_id / source_excerpt_hash / migration_mode / owner / new_value_reference / change_group_id / supersedes
- `EvidenceClassifierProtocol` (Round R2 [C3] / Round R3 [W1] 反映): 2 method Protocol (= caller 実装責務、 conformance test fixture):
  - `supported_metric_names() -> frozenset[str]` (= classifier がサポートする metric name 集合、 fixture で contract 担保)
  - `__call__(metric_value, metric_name, provenance) -> tuple[EvidenceClass, str]` (= 未対応 metric_name は inconclusive 必須)
- `AggregateEvidence` (Round R3 [C1] [S1] 新設): inconclusive を warning に隠さないための別軸:
  - `severity: Severity`
  - `has_inconclusive: bool`
  - `inconclusive_reasons: tuple[str, ...]`
- `DeletionTargetCategory`: name / targets
- `SmokeDoDItem` (Round R2 [W1] [S2] scope 追加): dod_id / **scope: Literal["per_run", "cross_run"]** (= dod_id から推論せず明示) / synthesis_text / check_function_name / status (= EvidenceClass) / detail (= 文字列)
- `PerRunSmokeDoDResult` (Round R1 [C2] [S2]): items: tuple (= len=7、 DoD1-DoD7 全網羅) / overall_evidence_class / observed_fms: frozenset / smoke_report_schema_version
- `CrossRunSmokeDoDResult` (Round R1 [C2]): item: SmokeDoDItem (= DoD8) / observed_fms / smoke_report_schema_version
- `SmokeObservabilityProjection` (Round R1 [C5] / Round R2 [W6] / Round R3 [W2]、 per-run 単位):
  - `ab_divergence_class: EvidenceClass` (FM1)
  - `epoch_consistency_class: EvidenceClass` (Round R3 [W2] = per-run dataset_epoch_id 伝搬チェック、 FM2 per-run 部分対応)
  - `warmstart_shortfall_class: EvidenceClass` (FM3)
  - `bypass_ratio_class: EvidenceClass` (FM4)
  - `session_entropy_class: EvidenceClass` (FM5)
  - `dataset_epoch_id_present: bool` (= per-record schema lint 結果)
  - `report_ref: str`
- `CrossRunSmokeObservabilityProjection` (Round R3 [W2] 新設、 cross-run 単位):
  - `cross_run_epoch_pollution_class: EvidenceClass` (= 5 Run 集約 epoch 汚染、 FM2 cross-run 部分、 DoD8 と同 source)
  - `report_ref: str`
- `SmokeRunSummary`: run_id / dataset_epoch_id / run_succeeded / per_run_dod: PerRunSmokeDoDResult / observability_projection: SmokeObservabilityProjection / **observed_failure_modes** (Round R2 [S3] rename from observed_fms): frozenset[FailureModeKind]
- `FiveRunConsistencyResult`: runs / cross_run_dod: CrossRunSmokeDoDResult / epoch_pollution_observed: bool / config_drift_observed: bool / schema_version_consistent: bool / overall_severity: Severity
- `SmokeOutcomeClassification` (Round R1 [C4] [S5] 事実認定): observed_fms / per_run_severity / cross_run_severity / overall_severity (= 最も厳しい)
- `ReleaseActionRecommendation` (Round R1 [C4] [S5] / Round R2 [W2] [S2] / Round R3 [W5] hint only 強調):
  - outcome_classification
  - **review_hint: Literal["no_blocker_observed", "hold_for_delay", "hold_for_review"]** (Round R3 [W5] 「自動承認」 誤読 risk 低減で `candidate_proceed` → `no_blocker_observed`)
  - rationale: str
  - requires_manual_review: bool
- `BigBangCleanupReport`: deletion_targets / per_run_smoke_results: tuple[PerRunSmokeDoDResult, ...] / cross_run_smoke_result: CrossRunSmokeDoDResult / outcome_classification / release_action_recommendation / report_schema_version

#### 関数

- `enumerate_deletion_targets() -> tuple[DeletionTargetCategory, ...]`: synthesis § 12.1 / § 12.2 + T058-T074 申し送りを参照、 詳細設計で全件列挙
- `check_per_run_smoke_dod(*, run_observability_report) -> PerRunSmokeDoDResult`: DoD1-DoD7 を per-run 検証
- `check_cross_run_smoke_dod(*, run_summaries) -> CrossRunSmokeDoDResult`: DoD8 を 5 Run 集約検証
- `check_five_run_consistency(*, run_summaries) -> FiveRunConsistencyResult`: epoch / config / schema 一貫性検証
- `classify_smoke_outcome(*, per_run_results, cross_run_result, five_run_result) -> SmokeOutcomeClassification`: 事実認定
- `decide_release_action(*, classification) -> ReleaseActionRecommendation`: 運用判断 hint (= manual review に委ねる前段)
- `compose_bigbang_cleanup_report(...) -> BigBangCleanupReport`: 全集約
- `select_rollback_relevant_failure_modes(*, observed, policy) -> frozenset[FailureModeKind]` (Round R3 [S4] **API 名予約のみ、 Phase 1 では NotImplementedError raise**、 Phase 2 別 TODO で実装、 synthesis Round 22 改訂後の rollback_relevant 集合決定経路)

### 2.3 T075 で扱わない (Round R1 [C1] [C3] [W2] [W6] 反映)

- 既存 src の **実削除コミット** (= Phase 2)
- T071 RunObservabilityReport.smoke_dod field 配線 (= Phase 2)
- run_ga.py で smoke 関数呼出 (= Phase 2)
- selection 経路への接続 (= 永久に不在)
- new_cascade 名前空間 (= 採用しない、 synthesis Round 22 改訂候補)
- **FM threshold 数値 SSOT 化** (Round R1 [C3]、 別 TODO + smoke 後再校正)
- **自動 rollback / proceed 判定** (Round R1 [C4]、 manual review に委ねる)
- **ROLLBACK_DELAY_CYCLE_DAYS** の数値定数 (Round R1 [W2]、 1 cycle = run cadence)
- **collider bias 判定** (Round R1 [W6]、 stratified audit / 因果解釈 / 比率差判定は T072-T074 同様 Phase 2 で T071 経由)

---

## 3. アーキテクチャ概観

```
src/alpha_factory/
├── (T058-T074 で実装される 17 module)
│
└── smoke.py                       [T075 新規]
    ├── EvidenceClass / Severity / FailureModeKind                 [SSOT enum]
    ├── DoDIdPerRun / DoDIdCrossRun / RemovalMode                  [SSOT enum]
    ├── SMOKE_RUNS_REQUIRED = 5                                     [synthesis § 18.3]
    ├── PER_RUN_DOD_ITEMS_COUNT = 7                                 [DoD1-DoD7]
    ├── CROSS_RUN_DOD_ITEMS_COUNT = 1                               [DoD8]
    ├── DeletionTarget / DeletionTargetCategory                     [Round R1 [C6] manifest]
    ├── SmokeDoDItem                                                 [SSOT、 数値 field なし]
    ├── PerRunSmokeDoDResult / CrossRunSmokeDoDResult               [Round R1 [C2] 二層分離]
    ├── SmokeObservabilityProjection                                 [Round R1 [C5] typed projection]
    ├── SmokeRunSummary                                              [SSOT]
    ├── FiveRunConsistencyResult                                     [SSOT]
    ├── SmokeOutcomeClassification                                   [Round R1 [C4] [S5] 事実認定]
    ├── ReleaseActionRecommendation                                  [Round R1 [C4] [S5] 運用判断 hint]
    ├── BigBangCleanupReport                                         [SSOT]
    ├── enumerate_deletion_targets
    ├── check_per_run_smoke_dod / check_cross_run_smoke_dod
    ├── check_five_run_consistency
    ├── classify_smoke_outcome / decide_release_action
    └── compose_bigbang_cleanup_report
```

### 3.1 T075 が touch する既存ファイル

| ファイル | 改造内容 | 既存挙動への影響 |
|---|---|---|
| (なし) | T075 PR (Phase 1) は新規 module + 単体テストのみ | 既存ファイルへの影響なし |

### 3.2 T075 で新設するファイル

| ファイル | 内容 | 行数概算 |
|---|---|---|
| `src/alpha_factory/smoke.py` | 上記 SSOT 群 | +400 |
| `tests/alpha_factory/test_smoke.py` | F1-F35 + happy path | +500 |

---

## 4. データ構造 SSOT (Round 2、 Round 1 [C1-C6] [W3-W6] [S2-S5] 反映)

### 4.1 EvidenceClass / Severity / FailureModeKind (Round R1 [C3] [C4] [W4])

```python
EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]   # threshold-free 4 値
Severity = Literal["hard_fail", "warning", "ok"]                          # 事実認定 3 値
FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]              # synthesis § 16 enum、 数値 threshold は T075 範囲外
```

**Round R1 [W4] 分離**:
- `observed_fms: frozenset[FailureModeKind]`: T075 module で観測された全 FM (= 数値 threshold によらない、 caller が evidence_class から導出)
- `rollback_relevant_fms: frozenset[FailureModeKind]`: synthesis Round 22 改訂後に確定する rollback 判定対象 FM (= T075 module は **持たない**、 caller / synthesis が決定)

### 4.2 SmokeDoDItem (数値 field なし、 T073 / T074 SSOT 継承)

```python
@dataclass(frozen=True)
class SmokeDoDItem:
    """smoke DoD 1 項目 (Round R1 [C5] 数値 field 排除).

    SSOT (synthesis § 18.3 + Round R1 [C2] 分離):
        DoD1-DoD7: per-run (= PerRunSmokeDoDResult.items)
        DoD8: cross-run (= CrossRunSmokeDoDResult.item、 5 Run 集約でしか確定不能)
    """
    dod_id: DoDIdPerRun | DoDIdCrossRun     # Literal union
    synthesis_text: str                      # synthesis § 18.3 原文 quote
    check_function_name: str                 # 検証関数名
    status: EvidenceClass                    # threshold-free 4 値
    detail: str                              # 文字列のみ、 数値 field なし
```

### 4.3 PerRunSmokeDoDResult / CrossRunSmokeDoDResult (Round R1 [C2] [S2] 二層分離)

```python
@dataclass(frozen=True)
class PerRunSmokeDoDResult:
    """1 Run 単位の DoD1-DoD7 集約."""
    items: tuple[SmokeDoDItem, ...]          # len == PER_RUN_DOD_ITEMS_COUNT (= 7)
    overall_evidence_class: EvidenceClass    # 全 items.status から集約
    observed_fms: frozenset[FailureModeKind] # この run で観測された FM
    smoke_report_schema_version: str

    def __post_init__(self) -> None:
        # invariant:
        #   len(items) == 7、 dod_id ∈ {DoD1..DoD7} 全網羅、 重複なし
        #   overall_evidence_class は items.status の集約 (= "hard_fail" 1 個でも → "hard_fail")
        ...


@dataclass(frozen=True)
class CrossRunSmokeDoDResult:
    """5 Run 集約単位の DoD8."""
    item: SmokeDoDItem                       # dod_id == "DoD8"
    observed_fms: frozenset[FailureModeKind]
    smoke_report_schema_version: str

    def __post_init__(self) -> None:
        # invariant:
        #   item.dod_id == "DoD8"
        ...
```

### 4.4 SmokeObservabilityProjection (Round R1 [C5] typed projection)

```python
@dataclass(frozen=True)
class SmokeObservabilityProjection:
    """T071 RunObservabilityReport の typed projection (Round R1 [C5] 反映、 untyped dict 排除).

    各 metric は EvidenceClass で表現 (= 数値 threshold 持たない、 caller が evidence_class から FM 導出).

    Round R1 [C5] 反映: Mapping[str, Decimal] を排除、 typed field で SSOT 漏れ防止.
    """
    ab_divergence_class: EvidenceClass        # T071 ABDivergenceMetric → EvidenceClass
    bypass_ratio_class: EvidenceClass         # T071 BypassRatioMetric → EvidenceClass
    session_entropy_class: EvidenceClass      # T071 SessionEntropyMetric → EvidenceClass
    warmstart_shortfall_class: EvidenceClass  # T067/T071 WarmstartReport → EvidenceClass
    dataset_epoch_id_present: bool            # T058 schema lint
    report_ref: str                           # T071 RunObservabilityReport の id 参照
```

### 4.5 SmokeRunSummary

```python
@dataclass(frozen=True)
class SmokeRunSummary:
    run_id: str
    dataset_epoch_id: str
    run_succeeded: bool
    per_run_dod: PerRunSmokeDoDResult
    observability_projection: SmokeObservabilityProjection
    observed_fms: frozenset[FailureModeKind]
```

### 4.6 FiveRunConsistencyResult (synthesis § 18.3)

```python
@dataclass(frozen=True)
class FiveRunConsistencyResult:
    """5 Run 連続検証 (synthesis § 18.3 「連続 5 Run で epoch 汚染なし」)."""
    runs: tuple[SmokeRunSummary, ...]                # len == SMOKE_RUNS_REQUIRED (= 5)
    cross_run_dod: CrossRunSmokeDoDResult            # DoD8
    epoch_pollution_observed: bool                   # prev_epoch 比率 > 20% の Run が >= 1 つ
    config_drift_observed: bool                      # config hash mismatch の Run が >= 1 つ
    schema_version_consistent: bool                  # 全 Run で archive schema_version=2 一貫
    overall_severity: Severity                        # "hard_fail" / "warning" / "ok"
```

### 4.7 SmokeOutcomeClassification (Round R1 [C4] [S5] 事実認定)

```python
@dataclass(frozen=True)
class SmokeOutcomeClassification:
    """smoke 結果の事実認定 (= severity + observed FMs).

    Round R1 [C4] [S5] 反映: 自動判定の硬い truth table を廃止、
    classify_smoke_outcome は事実認定のみ、 decide_release_action は運用判断 hint.
    """
    observed_fms: frozenset[FailureModeKind]
    per_run_severity: Severity                       # PerRunSmokeDoDResult の最厳 severity
    cross_run_severity: Severity                     # CrossRunSmokeDoDResult の severity
    overall_severity: Severity                        # max(per_run, cross_run)
```

### 4.8 ReleaseActionRecommendation (Round R1 [C4] [S5] 運用判断 hint)

```python
@dataclass(frozen=True)
class ReleaseActionRecommendation:
    """運用判断の hint (= 自動判定ではなく manual review 前段)."""
    outcome_classification: SmokeOutcomeClassification
    recommended_action: Literal["proceed", "delay", "manual_review"]
    rationale: str                                    # 推奨理由
    requires_manual_review: bool                       # True なら CI gate で manual review 必須

    def __post_init__(self) -> None:
        # invariant:
        #   recommended_action="proceed" → overall_severity == "ok" AND observed_fms 中 rollback_relevant 該当なし (= synthesis Round 22 改訂後判定)
        #   recommended_action="delay" → overall_severity == "warning"
        #   recommended_action="manual_review" → overall_severity == "hard_fail" OR observed_fms 中 rollback_relevant 該当 (= synthesis Round 22 後)
        #   requires_manual_review == (recommended_action == "manual_review")
        ...
```

注: `recommended_action` は **hint のみ**、 自動的な切替トリガーではない。 切替コミット責務は caller (= run_ga.py adapter) と reviewer。

### 4.9 BigBangCleanupReport

```python
@dataclass(frozen=True)
class BigBangCleanupReport:
    deletion_targets: tuple[DeletionTargetCategory, ...]
    per_run_smoke_results: tuple[PerRunSmokeDoDResult, ...]   # len == SMOKE_RUNS_REQUIRED
    cross_run_smoke_result: CrossRunSmokeDoDResult
    five_run_consistency_result: FiveRunConsistencyResult
    outcome_classification: SmokeOutcomeClassification
    release_action_recommendation: ReleaseActionRecommendation
    report_schema_version: str
```

---

## 5. 主要関数 API SSOT (§ 11.2 SSOT 規約準拠)

```python
# src/alpha_factory/smoke.py

EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]
Severity = Literal["hard_fail", "warning", "ok"]
FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]
DoDIdPerRun = Literal["DoD1", "DoD2", "DoD3", "DoD4", "DoD5", "DoD6", "DoD7"]
DoDIdCrossRun = Literal["DoD8"]
RemovalMode = Literal["git_rm", "yaml_key_delete", "yaml_value_replace"]

SMOKE_RUNS_REQUIRED: Final[int] = 5
PER_RUN_DOD_ITEMS_COUNT: Final[int] = 7
CROSS_RUN_DOD_ITEMS_COUNT: Final[int] = 1
SMOKE_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"


@dataclass(frozen=True)
class DeletionTarget: ...
@dataclass(frozen=True)
class DeletionTargetCategory: ...
@dataclass(frozen=True)
class SmokeDoDItem: ...
@dataclass(frozen=True)
class PerRunSmokeDoDResult: ...
@dataclass(frozen=True)
class CrossRunSmokeDoDResult: ...
@dataclass(frozen=True)
class SmokeObservabilityProjection: ...
@dataclass(frozen=True)
class SmokeRunSummary: ...
@dataclass(frozen=True)
class FiveRunConsistencyResult: ...
@dataclass(frozen=True)
class SmokeOutcomeClassification: ...
@dataclass(frozen=True)
class ReleaseActionRecommendation: ...
@dataclass(frozen=True)
class BigBangCleanupReport: ...


def enumerate_deletion_targets() -> tuple[DeletionTargetCategory, ...]: ...
def check_per_run_smoke_dod(*, run_observability_report) -> PerRunSmokeDoDResult: ...
def check_cross_run_smoke_dod(*, run_summaries: tuple[SmokeRunSummary, ...]) -> CrossRunSmokeDoDResult: ...
def check_five_run_consistency(*, run_summaries: tuple[SmokeRunSummary, ...]) -> FiveRunConsistencyResult: ...
def classify_smoke_outcome(
    *,
    per_run_results: tuple[PerRunSmokeDoDResult, ...],
    cross_run_result: CrossRunSmokeDoDResult,
    five_run_result: FiveRunConsistencyResult,
) -> SmokeOutcomeClassification: ...
def decide_release_action(
    *,
    classification: SmokeOutcomeClassification,
) -> ReleaseActionRecommendation: ...
def compose_bigbang_cleanup_report(...) -> BigBangCleanupReport: ...
```

---

## 6. アルゴリズム詳細 (Round R1 [C2] [C4] 反映、 二層分離 + 2 段階判定)

### 6.0 EvidenceClassifierProtocol (Round R2 [C3] SSOT)

```python
from typing import Protocol

class EvidenceClassifierProtocol(Protocol):
    """T071 metric 値 → EvidenceClass への分類を行う caller-supplied classifier.

    SSOT (Round R2 [C3] caller マッピング規約):
        - T075 module は EvidenceClass の **数値 threshold を持たない** (= threshold-free)
        - caller (= Phase 2 別 TODO) が本 Protocol を実装
        - 入力 metric_name (= "ab_divergence" / "bypass_ratio" 等) は T075 で SSOT 化された名前
        - 未対応 metric_name は **必ず "inconclusive" を返す** (= 暗黙 ok 禁止、 fail-closed)
        - provenance: 分類根拠の記述 (= "T071 v1.0 ABDivergenceMetric" 等)、 audit 用
        - 戻り値の str は detail (= 分類理由の人間可読説明)
    """

    def __call__(
        self,
        metric_value: object,
        metric_name: str,
        provenance: str,
    ) -> tuple[EvidenceClass, str]:
        """metric_value を EvidenceClass に分類.

        Returns:
            (evidence_class, detail) tuple.
        Returns "inconclusive" for unknown metric_name (= fail-closed).
        """
        ...
```

caller 実装 (= Phase 2 別 TODO) で:
- 「未対応 metric_name は inconclusive」 を構造的に強制 (= switch-case の default が inconclusive)
- T075 module は本 Protocol type を `Protocol` として import 用に export、 自身は instance 持たない (= 純ライブラリ + threshold-free)

### 6.1 check_per_run_smoke_dod (DoD1-DoD7、 1 Run 単位)

```python
def check_per_run_smoke_dod(*, run_observability_report):
    items = (
        _check_dod1_run_completion(run_observability_report),
        _check_dod2_a_pass_only_b_eval(run_observability_report),
        _check_dod3_main_selection_b_pooled(run_observability_report),
        _check_dod4_dataset_epoch_id_required(run_observability_report),
        _check_dod5_inflow_consistency(run_observability_report),
        _check_dod6_ca_da_allocation(run_observability_report),
        _check_dod7_invariant_fail_fast(run_observability_report),
    )
    overall = _aggregate_evidence_class(items)
    observed_fms = _detect_fms_from_per_run(items, run_observability_report)
    return PerRunSmokeDoDResult(
        items=items, overall_evidence_class=overall, observed_fms=observed_fms,
        smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )
```

### 6.2 check_cross_run_smoke_dod (DoD8、 5 Run 集約)

```python
def check_cross_run_smoke_dod(*, run_summaries):
    if len(run_summaries) != SMOKE_RUNS_REQUIRED:
        raise ValueError(f"len(run_summaries) == {SMOKE_RUNS_REQUIRED} required")
    item = _check_dod8_epoch_no_pollution_5run(run_summaries)
    observed_fms = _detect_fms_from_cross_run(run_summaries)
    return CrossRunSmokeDoDResult(
        item=item, observed_fms=observed_fms,
        smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )
```

### 6.3 classify_smoke_outcome (事実認定、 Round R1 [C4] [S5])

```python
def classify_smoke_outcome(*, per_run_results, cross_run_result, five_run_result):
    """事実認定 (= severity + observed FMs)、 運用判断は decide_release_action に分離."""
    per_run_severity = _max_severity(p.overall_evidence_class for p in per_run_results)
    cross_run_severity = _evidence_class_to_severity(cross_run_result.item.status)
    five_run_severity = five_run_result.overall_severity
    overall_severity = _max_severity((per_run_severity, cross_run_severity, five_run_severity))

    observed_fms = frozenset()
    for p in per_run_results:
        observed_fms |= p.observed_fms
    observed_fms |= cross_run_result.observed_fms

    return SmokeOutcomeClassification(
        observed_fms=observed_fms,
        per_run_severity=per_run_severity,
        cross_run_severity=cross_run_severity,
        overall_severity=overall_severity,
    )
```

### 6.4 decide_release_action (運用判断 hint、 Round R3 [C1] [S2] [W5] inconclusive 別軸 + 優先順位変更)

```python
def decide_release_action(*, classification):
    """運用判断 hint (= manual review 前段、 自動切替指示ではない).

    SSOT (Round R3 [C1] [S2] [W5] 反映、 inconclusive を warning に隠さず別軸):

    優先順位 (Round R3 [S2]):
        1. severity == "hard_fail"               → "hold_for_review"
        2. has_inconclusive == True              → "hold_for_review" (Round R3 [C1]、 C8 規範)
        3. observed_failure_modes 観測あり        → "hold_for_review"
        4. severity == "warning" AND 上記不在     → "hold_for_delay"
        5. severity == "ok" AND 上記すべて不在    → "no_blocker_observed" (Round R3 [W5])

    AggregateEvidence:
        severity = max("hard_fail", "warning", "ok") の 3 値で集約 (= inconclusive は別軸)
        has_inconclusive = 任意 metric で inconclusive あり
        inconclusive_reasons = 検出された inconclusive の reason 列
    """
    severity = classification.aggregate_evidence.severity   # 3 値: hard_fail / warning / ok
    has_inconclusive = classification.aggregate_evidence.has_inconclusive
    has_fms = bool(classification.observed_failure_modes)

    # 優先順位 1: hard_fail
    if severity == "hard_fail":
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=f"hard_fail (severity={severity})、 manual review 必要",
            requires_manual_review=True,
        )
    # 優先順位 2: has_inconclusive (Round R3 [C1]、 C8 規範でデータ不足を warning に隠さず)
    if has_inconclusive:
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=f"inconclusive 観測 (= データ不足: {classification.aggregate_evidence.inconclusive_reasons[:3]})、 C8 規範で manual review 必要",
            requires_manual_review=True,
        )
    # 優先順位 3: FM 観測
    if has_fms:
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=f"FM 観測 ({sorted(classification.observed_failure_modes)})、 manual review 必要",
            requires_manual_review=True,
        )
    # 優先順位 4: warning + 上記すべて不在
    if severity == "warning":
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_delay",
            rationale="warning level + FM 不在 + inconclusive 不在、 1 cycle 後再 smoke 推奨",
            requires_manual_review=False,
        )
    # 優先順位 5: ok + 全クリア → no_blocker_observed (Round R3 [W5])
    return ReleaseActionRecommendation(
        outcome_classification=classification,
        review_hint="no_blocker_observed",
        rationale="全 DoD ok + FM 不在 + inconclusive 不在、 切替コミット blocker 観測なし (= reviewer が最終判断)",
        requires_manual_review=False,
    )
```

**Round R2 [W2] / Round R3 [W5] 注意**: `review_hint` は **hint only**、 自動切替指示ではない。 値名 `no_blocker_observed` は「ブロッカー観測なし」 を強調 (= 「proceed すべき」 ではなく「proceed の blocker が無い」)、 reviewer が自動承認しないよう誘導。 synthesis Round 22 改訂後に `rollback_relevant_failure_modes` 導入 + `select_rollback_relevant_failure_modes(observed, policy)` (Round R3 [S4] API 名予約) を別 TODO で実装、 そこで自動判定強化。

---

## 7. 既存挙動への影響 (C2 parallel-path verification)

### 7.1 直 import 経路

`src/alpha_factory/smoke.py` は **新規ファイル**。 既存ファイル touch なし。

### 7.2 dual-path operational definition (Round R1 [W3] / Round R2 [W5])

「並走」 (= 禁止) の定義:
- runtime から **両方が到達可能** (= source import 経路 OR CLI entrypoint OR config key OR script path OR dynamic import OR 環境変数経由)
- feature flag で **動的切替可能**
- **同じ出力契約を二経路で生成可能**

「同居」 (= 許容) の定義:
- source tree に旧 module が残っているが runtime から **どの経路でも到達不能**
- import / CLI / config / script / dynamic / env のすべてで caller 不在

**Round R2 [W5] 反映 dual-path enforce 4 経路 grep DoD**:

| 検出経路 | 検索対象 | 検出方法 |
|---|---|---|
| (1) source import | `src/**/*.py` | AST `ast.ImportFrom` / `ast.Import` で `archive` / `swim_lane` / `cross_pair` 等 forbidden module 検出 |
| (2) CLI entrypoint / scripts | `scripts/**/*.py` | 同 AST 解析 + shebang / `__main__` block 検出 |
| (3) config key | `config/**/*.yaml` | yaml parse 後 dot-notation key check |
| (4) docs runbook | `docs/runbook/**/*.md` | 自然言語、 substring match で旧 path 言及検出 (= warning level、 raise しない) |
| (除外) historical / devnotes | `docs/historical/**` / `devnotes/**` | Round R3 [S3] allowlist、 設計記録 / 履歴は除外 (= 古い path 言及あっても OK) |

T075 PR (Phase 1) では旧 module は **同居 OK**、 切替コミット (Phase 2) で:
- (1) git rm + import 経路 grep DoD で 0 件確認
- (2) scripts 削除 + CLI entrypoint 不在確認
- (3) yaml key delete + caller 非参照確認
- (4) docs runbook 更新 (= 注意喚起、 旧 path 言及があれば warning)

これら 4 経路で **runtime 到達不能** を担保すれば「並走」 でなく「同居」 として許容、 切替コミット後は (1)-(3) で 0 件、 (4) は warning level。

### 7.3 collider bias non-goal (Round R1 [W6])

T075 module は以下を **判定しない**:
- holiday_markets / dst_transition_markets / schedule_status の stratified audit
- 因果解釈 (= "FM1 trigger は X が原因" 等)
- 比率差の有意性検定 (= bypass_ratio が前回比増加で有意か等)

これらは Phase 2 で T071 RunObservabilityReport 経由で別 caller (= manual review or 後段別 TODO) が判定。 T075 は evidence_class 単位の **観測事実** のみを report。

---

## 8. 不変条件 (invariant、 Round 2 改訂)

| ID | 不変条件 | 担保 |
|---|---|---|
| I1 | T058-T074 SSOT は T075 で touch しない | 新規 module、 既存 import なし |
| I2 | early gate ではない | T075 PR は selection 経路 touch しない |
| I3 | EvidenceClass 4 値 / Severity 3 値 / FailureModeKind 5 値 | __post_init__ |
| I4 | PerRunSmokeDoDResult.items は DoD1-DoD7 全網羅 (Round R1 [C2]) | __post_init__ |
| I5 | CrossRunSmokeDoDResult.item.dod_id == "DoD8" (Round R1 [C2]) | __post_init__ |
| I6 | FiveRunConsistencyResult.runs len == 5 (synthesis § 18.3) | __post_init__ |
| I7 | SmokeDoDItem は数値 field を持たない (T073/T074 SSOT 継承、 Round R1 [C5]) | dataclass field 列で構造的担保 |
| I8 | SmokeObservabilityProjection は typed (= Mapping[str, Decimal] 排除、 Round R1 [C5]) | dataclass field 構造 |
| I9 | T075 module で **数値 threshold (= FM*) を SSOT 化しない** (Round R1 [C3]) | 定数列 0 件、 grep DoD |
| I10 | enumerate_deletion_targets は synthesis § 12.1 / § 12.2 全網羅 (Round R1 [C6]) | docstring + 詳細設計で synthesis grep + yaml dump |
| I11 | DeletionTarget manifest schema 6 field (= path / category / source_section / source_clause / removal_mode / owner) | __post_init__ |
| I12 | dual-path 並走禁止 (Round R1 [W3] operational definition) | 切替コミット手順 + Phase 2 PR description |
| I13 | new_cascade 名前空間は採用しない (= synthesis Round 22 改訂候補) | docstring SSOT、 blocked-by 明示 |
| I14 | collider bias 判定しない (Round R1 [W6] non-goal) | docstring SSOT、 grep DoD |
| I15 | T075 は synthesis local projection、 親 SSOT を再定義しない (Round R1 [C1]) | docstring 明示 + Round 22 blocked-by |
| I16 | classify_smoke_outcome (事実認定) と decide_release_action (運用判断 hint) を分離 (Round R1 [C4]) | 関数 signature + docstring |
| I17 | observed_fms と rollback_relevant_fms を別軸 (Round R1 [W4]) | rollback_relevant_fms は T075 module 持たない、 synthesis Round 22 後に caller で実装 |
| I18 | 1 cycle = run cadence (Round R1 [W2]、 数値定数廃止) | docstring SSOT、 ROLLBACK_DELAY_CYCLE_DAYS 不在 |
| I19 | scaffold 数値 field なし (T073 / T074 SSOT 継承) | SmokeDoDItem.detail は文字列のみ |

---

## 9. リスクと緩和

| リスク | 影響 | 緩和 |
|---|---|---|
| F1 synthesis § 12.1 / § 12.2 削除対象網羅漏れ (Round R1 [C6]) | 切替後旧 code 残存 | 詳細設計で synthesis grep + default.yaml dump 手順 + manifest CI lint |
| F2 親 SSOT 改訂 (synthesis Round 22) 不在で T075 が evidence-only mode 固定 | 自動判定不可、 manual review 負荷高 | Round 22 改訂を T075 PR の blocked-by 依存として明示、 改訂後別 TODO で rollback_relevant 判定実装 |
| F3 dual-path 並走の誤適用 (Round R1 [W3]) | 切替後の予期せぬ runtime 到達 | I12 + operational definition、 切替コミットで git rm + import 経路 grep DoD |
| F4 切替コミット削除漏れ (Round R1 [C6]) | 旧 code 残存 | DeletionTarget tuple を CI lint で照合 (= Phase 2 PR 必須 check) |
| F5 5 Run consistency caller adapter 不在 (Round R1 [C5]) | run_summaries 集計 ambiguity | Phase 2 で run_ga.py を唯一の SSOT adapter と申し送り (T074 / T073 と同 pattern) |
| F6 collider bias 規範違反 | 偏った smoke 判定 | I14 non-goal、 stratified audit は Phase 2 で T071 経由 |
| F7 T071 schema 変更で T075 互換性破壊 | smoke 検証 fail | SmokeObservabilityProjection に T071 schema_version 確認を caller 責務 |
| F8 synthesis Round 22 改訂が T075 PR と非同期 merge | T075 docstring の blocked-by が一時不整合 | PR description で同期 merge 推奨、 順序は synthesis 先 |
| F9 manual_review 負荷の運用定着 | 切替延期の慢性化 | synthesis Round 22 改訂で rollback_relevant 自動化を別 TODO 化 |

---

## 10. テスト計画 (概要、 詳細は detailed-design.md で)

### 10.1 enumerate_deletion_targets tests

- F1: 全 4 category (= 並走機構 / 旧 config キー / 旧 script / 全面置換) が含まれる
- F2: synthesis § 12.1 全 bullet が網羅 (= 詳細設計で count 一致 lint)
- F3: synthesis § 12.2 全 bullet が網羅
- F4: 縮退保持対象 (synthesis § 12.3) が DeletionTarget に含まれない (= factor_shadow / aux / dataset / backtest / live_criteria を grep で除外)
- F5: DeletionTarget manifest 6 field 全網羅 (Round R1 [C6])

### 10.2 SmokeDoDItem / PerRunSmokeDoDResult / CrossRunSmokeDoDResult tests

- F6: SmokeDoDItem.dod_id が DoD1-DoD7 (per-run) または DoD8 (cross-run)
- F7: PerRunSmokeDoDResult.items が DoD1-DoD7 全網羅
- F8: PerRunSmokeDoDResult.overall_evidence_class 集約: hard_fail 1 個でも → hard_fail / 全 ok → ok
- F9: CrossRunSmokeDoDResult.item.dod_id == "DoD8"
- F10: SmokeDoDItem に数値 field なし (= dataclasses.fields(SmokeDoDItem) で int/Decimal 不在を test)

### 10.3 SmokeObservabilityProjection tests (Round R1 [C5] typed projection)

- F11: 各 *_class field が EvidenceClass 4 値
- F12: dataset_epoch_id_present は bool
- F13: report_ref non-empty
- F14: SmokeObservabilityProjection は Mapping を持たない (= dataclass field で typed projection、 untyped dict 排除を test)

### 10.4 FiveRunConsistencyResult tests

- F15: runs len != 5 → ValueError
- F16: epoch_pollution_observed=True → overall_severity in {"hard_fail", "warning"}
- F17: 全 OK → overall_severity == "ok"

### 10.5 classify_smoke_outcome / decide_release_action tests (Round R1 [C4] [S5])

- F18: classify は事実認定のみ (= recommended_action 不在)
- F19: decide は manual_review hint を返す、 自動切替指示しない
- F20: overall_severity="ok" + observed_fms=∅ → recommended_action="proceed"
- F21: overall_severity="warning" + observed_fms=∅ → recommended_action="delay"
- F22: overall_severity="hard_fail" OR FM 観測 → recommended_action="manual_review"
- F23: requires_manual_review == (recommended_action == "manual_review")

### 10.6 既存 SSOT 整合 tests (Round R1 [C1] local projection)

- F24: synthesis § 18.3 8 項目と DoD1-DoD8 1 対 1 対応、 synthesis_text は原文 quote
- F25: synthesis § 16 Risk Top 5 と FailureModeKind FM1-FM5 の **enum 紐付けのみ** (= 数値 threshold は T075 不在)
- F26: synthesis § 12.4 ロールバック条件 「FM1/FM4」 文言は T075 で「synthesis Round 22 改訂後に rollback_relevant 確定」 の blocked-by として記述

### 10.7 invariant tests

- F27: T075 module 内に数値 threshold 定数なし (= grep DoD、 Round R1 [C3])
- F28: T075 module 内に ROLLBACK_DELAY_CYCLE_DAYS 等 cycle 数値定数なし (Round R1 [W2])
- F29: collider bias 関連参照なし (= holiday / DST / observability_flags / stratified、 AST 解析、 T072-T074 同 pattern)
- F30: T075 module は archive.py / swim_lane.py / cross_pair.py を import しない (= grep DoD)

### 10.8 dual-path operational definition tests (Round R1 [W3])

- F31: 「同居」 (= source tree に残るが import 不在) を許容するルール明文化
- F32: 「並走」 (= 二経路同時到達可能) を禁止するルール明文化

### 10.9 manifest schema tests (Round R1 [C6] [S4])

- F33: DeletionTarget の 6 field 全網羅
- F34: source_section ∈ {"12.1", "12.2"}
- F35: removal_mode ∈ {"git_rm", "yaml_key_delete", "yaml_value_replace"}

---

## 11. Phase 1 / Phase 2 分離

### 11.1 Phase 1 (T075 PR、 純ライブラリ + evidence collection only)

含む:
- `src/alpha_factory/smoke.py` 新規 (上記 SSOT 群)
- `tests/alpha_factory/test_smoke.py` 新規 (F1-F35)
- 単体テストのみで runtime 未組込
- **synthesis Round 22 改訂 PR を blocked-by として PR description 明記**

含まない (Phase 2):
- 既存 src の **実削除コミット**
- 既存 config の **実書換コミット**
- T071 RunObservabilityReport.smoke_dod field 配線
- run_ga.py で smoke 関数呼出
- 5 Run smoke の実施
- 自動 rollback / proceed 判定 (= manual review に委ねる)
- **rollback_relevant_fms 自動判定** (synthesis Round 22 後に別 TODO)
- collider bias 判定
- new_cascade 名前空間

### 11.2 Phase 2 (別 TODO、 cascade port 切替時)

- T071 RunObservabilityReport.smoke_dod field 追加
- run_ga.py で smoke 関数呼出 + SmokeRunSummary 構築
- **synthesis Round 22 改訂 (= new_cascade 採用しない / FM SSOT / DoD 機械検証形式) merge**
- **切替コミット (= big-bang 1-shot)**:
  - smoke 5 Run + classify_smoke_outcome → release_action_recommendation 確認
  - manual review (= reviewer 承認) 後に切替
  - 全 17 件 (T058-T074) Phase 2 PR を merge + 旧 src/scripts/config を **同日削除**

### 11.3 申し送り (詳細設計で明文化)

- T071 詳細設計改訂: RunObservabilityReport に `smoke_dod: PerRunSmokeDoDResult` field 追加
- run_ga.py 詳細設計改訂申し送り: 唯一の SSOT adapter として archive 集計 → SmokeRunSummary 構築
- synthesis Round 22 改訂候補:
  - § 12.4「new_cascade 名前空間」 文言を「採用しない、 直接 src/alpha_factory/* で実装」 に修正
  - § 12.4 ロールバック条件「FM1/FM4」 を T075 FailureModeKind enum と紐付けて確定 (= rollback_relevant_fms 集合定義)
  - § 18.3 Smoke DoD 8 項目を per-run / cross-run 分離形式 (= DoD1-DoD7 / DoD8) で明文化
  - § 16 Risk Top 5 と FM1-FM5 の数値 threshold を別 TODO で確定 (= smoke 後再校正)
- 別 TODO (synthesis Round 22 改訂後): rollback_relevant_fms 自動判定 + 数値 threshold 確定

---

## 12. 設計判断 SSOT (synthesis 確定値 vs T075 設計判断値)

### 12.1 synthesis 確定値 (= 厳密準拠)

- 削除対象 (synthesis § 12.1)
- 全面置換対象 (synthesis § 12.2)
- 縮退保持対象 (synthesis § 12.3)
- 切替戦略 (synthesis § 12.4): smoke + 5 Run → 切替コミット → 旧実装同日削除
- smoke DoD 8 項目 (synthesis § 18.3)
- 5 Run 連続検証 (synthesis § 18.3)
- Risk Top 5 (synthesis § 16) → FailureModeKind enum 紐付け

### 12.2 T075 設計判断値 (Round 1 [C1] [C3] 反映で削減)

- DoD 二層分離 (= DoD1-DoD7 per-run / DoD8 cross-run、 Round R1 [C2])
- EvidenceClass / Severity 4/3 値 (Round R1 [C3] threshold-free)
- DeletionTarget manifest 6 field (Round R1 [C6])
- dual-path operational definition (Round R1 [W3])
- classify / decide 2 段階分離 (Round R1 [C4])
- typed projection (Round R1 [C5])
- collider bias non-goal (Round R1 [W6])
- 「1 cycle = run cadence」 (= 数値定数廃止、 Round R1 [W2])
- synthesis Round 22 改訂 blocked-by (Round R1 [C1])

**T075 で SSOT 化しない** (= 別 TODO / synthesis Round 22 で確定):
- FM1-FM5 数値 threshold
- rollback_relevant_fms 集合
- 自動 rollback / proceed 判定
- 1 cycle の日数

---

## 13. T075 完了後の cascade port 全体完了

T075 完了で **cascade port v2 設計 18 件 (T058-T075) 完了**。 Phase 2 (= 配線) 実装フェーズへ移行。 Phase 2 完了 + synthesis Round 22 改訂 + 切替コミット後に big-bang cascade port 完了。

---

## 14. open questions (詳細設計で解消)

1. **synthesis Round 22 改訂 PR の merge 順序**: T075 PR と同期 merge or T075 先 merge (= blocked-by 状態で実装) の trade-off
2. **enumerate_deletion_targets 全件列挙生成手順**: synthesis grep + yaml dump + T058-T074 申し送り集約の自動化
3. **decide_release_action の reviewer 規約**: manual_review 時の review 人数 / 期間 / SLA
4. **DoD8 の cross-run 集計実装**: 5 Run の dataset_epoch_id 列から prev_epoch 比率算出ロジック
5. **synthesis Round 22 改訂候補 4 件の優先順位**: new_cascade 採用しない > FM SSOT > DoD 機械検証 > rollback_relevant 確定
6. **rollback_relevant_fms 自動判定の Phase 2 別 TODO 化**: synthesis Round 22 で SSOT 確定後、 別 TODO で実装
7. **EvidenceClass の T071 metric → class マッピング**: ab_divergence 値 (T071) を「hard_fail / warning / ok」 にマップする規則は T075 範囲外、 別 TODO
8. **collider bias non-goal の AST grep DoD**: T072-T074 同 pattern で実装、 詳細設計で AST 検出語を確定

---

## 15. references / cross-cut

| 項目 | 場所 |
|---|---|
| synthesis § 12 / § 16 / § 18.2 T918 / § 18.3 | `devnotes/20260428-2300-cascade-port-debate/synthesis.md` |
| T058-T074 全 17 設計 | `devnotes/20260429-1912-todo-T058-*` 〜 `devnotes/20260501-0023-todo-T074-*` |
| T071 RunObservabilityReport (Phase 2 拡張先) | `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 4.2 |
| T072 / T073 / T074 collider bias 規範 | 各 detailed-design |
| T073 / T074 scaffold SSOT (= 数値 field なし) | 各 conceptual-design § 4.3 |

---

## 16. 学術文献 (参考、 Round R1 補足)

- Bailey, D. H., Borwein, J. M., López de Prado, M. M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* (= 切替後 overfitting 監査参照、 5 Run smoke を性能評価に流用しない牽制)
- Lo, A. W. (2002). *The Statistics of Sharpe Ratios.* Financial Analysts Journal 58(4). (= 5 Run smoke を性能保証に使わない牽制、 HAC 補正)
- Site Reliability Engineering (Beyer et al. 2016) Chap. 8 Release Engineering / Chap. 27 Reliable Product Launches at Scale (= big-bang vs canary、 manual review 規約参考)

---

## 17. Round 1 → Round 2 対応マトリクス

| Round R1 | Round 2 対応 |
|---|---|
| C1 親 SSOT 再定義 | T075 を local projection に下げる、 synthesis Round 22 改訂 blocked-by 明示 (§ 1.2) |
| C2 DoD8 責務破綻 | PerRunSmokeDoDResult (DoD1-7) / CrossRunSmokeDoDResult (DoD8) 分離 |
| C3 FM threshold SSOT 不適切 | EvidenceClass threshold-free 4 値、 数値 threshold T075 不在 (I9)、 別 TODO |
| C4 rollback truth table 硬すぎ | classify_smoke_outcome (事実認定) / decide_release_action (運用判断 hint) 2 段階分離、 自動 rollback 廃止 |
| C5 untyped dict 漏れ | SmokeObservabilityProjection typed projection、 Mapping[str, Decimal] 排除 |
| C6 削除対象代表例のみ | DeletionTarget manifest 6 field SSOT、 全件列挙生成手順を § 1.3 / § 11.3 で明記 |
| W1 new_cascade 非採用理由 | § 1.2 で synthesis Round 22 blocked-by として記述 |
| W2 1 cycle = 7 days 早すぎ | ROLLBACK_DELAY_CYCLE_DAYS 削除、 「1 cycle = run cadence (Phase 2 確定)」 (I18) |
| W3 dual-path / 同居の境界 | § 7.2 operational definition: 並走 = runtime 到達 OR feature flag OR 二経路出力、 同居 = source tree のみ |
| W4 RollbackTrigger と trigger_fms 粒度混在 | observed_fms (T075) / rollback_relevant_fms (synthesis Round 22 後) 分離 (I17) |
| W5 Literal["DoD1"-"DoD8"] 表記 | DoDIdPerRun / DoDIdCrossRun に分離、 各 Literal 値完全列挙 |
| W6 collider bias 継承だけでは弱い | § 7.3 non-goal を 3 項目明記 (= stratified / 因果解釈 / 比率差) |
| S1 synthesis projection 表現 | § 1.2 で「Requires synthesis Round 22 before merge」 と明示 |
| S2 DoD 二層分離 | 採用 (= C2 と同義) |
| S3 evidence_class 開始 | EvidenceClass 4 値採用 (= C3 と同義) |
| S4 deletion manifest 規約 | DeletionTarget 6 field schema 採用 (= C6 と同義) |
| S5 classify / decide 2 段階 | 採用 (= C4 と同義) |

---

これで T075 概念設計 Round 2 改訂は完成。 Round 1 で出た 6 Critical / 6 Warning / 5 Suggestion を全反映、 T075 を synthesis local projection に下げ + DoD 二層分離 + threshold-free + 2 段階判定 + typed projection + manifest schema に再設計。 Codex Round 2 review で更に falsification を試みる。
