# T074 — Graduation lane batch evaluator scaffold (概念設計)

**作成日時**: 2026-05-01 00:23 JST (Round 2 改訂: 01:05 JST、 Round 3 改訂: 01:30 JST)
**Round 2 反映**: C1-C3 / W1-W4 / S1-S4 全反映:
- Round R2 [C1]: `contributing_run_ids` を **`observed_run_ids` + `mission_pass_run_ids` の 2 field 分離** に修正 (= mission fail epoch でも観測 run は非空、 mission pass run のみが has_mission_pass を決定)
- Round R2 [C2]: empty archive を業務不足状態として扱う、 `archive_epoch_id_active: str | None`、 `distinct_dataset_epoch_ids` 非空時のみ invariant 適用
- Round R2 [C3]: `recent_epoch_summaries` を **recent-first head N** に修正、 「tail」 表記廃止、 `[0] == active` SSOT 厳密化
- Round R2 [W1]: Phase 2 で config missing 時に fail-closed (= 暗黙 default 置かない)
- Round R2 [W2]: `has_recent_mission_pass` を「実際に直近 N epoch が pass したか」 (= 早期 return 時は False、 status と独立) と SSOT 化
- Round R2 [W3]: Phase 2 adapter contract で「同一 archive snapshot から n_graduates と epoch summary を構築」 を明記、 連続 read の揺らぎは adapter contract violation
- Round R2 [W4]: `MultiPairAggregationKind` を Phase 1 では `worst_pair | mean` に閉じる、 robust 系は「synthesis 再確認後の追加候補」 と Phase 4 申し送り
- Round R2 [S1]: `GraduationEpochSummary` を 3 field 化 (= dataset_epoch_id / observed_run_ids / mission_pass_run_ids)
- Round R2 [S2]: `recent_epoch_summaries` contract docstring 強化 (= active/current から古い順、 epoch 単位 unique、 [0] が active)
- Round R2 [S3]: grep DoD 検索語明示 (= archive / swim_lane / cross_pair / ANCHOR_PAIRS / holiday / DST / observability_flags)
- Round R2 [S4]: T064 集合等価 test は test 側のみで T064 constants import、 production module 不変
**親 TODO**: T074 (synthesis § 18.2 T917 — Graduation lane batch evaluator scaffold: 起動条件 (graduates>=24 + 3 epoch + mission 連続) + multi-pair 集約 sketch (詳細実装は Phase 4 別 TODO))
**Milestone**: M6 中盤 (T073 完了済、 T075 残)
**前提 commit**: `main@323055b` (T073 commit 後)
**Round 1 反映**: C1-C3 / W1-W8 / S1-S5 全反映
- Round R1 [C1]: `GRADUATION_RECENT_*` の数値を Phase 1 では定数化しない、 caller 引数で受け渡し (= 数値操作禁止規範整合、 smoke 後 / synthesis Round 22 で SSOT 確定)
- Round R1 [C2]: 「直近 N Run」 → **「直近 N epoch」** に SSOT 修正 (= synthesis § 11.1 「直近 epoch で mission_pass が連続観測」 厳密従属)
- Round R1 [C3]: anchor_pairs の SSOT を **frozenset 等価** に変更 (= 順序は実装詳細)、 tuple SSOT は廃止
- Round R1 [W1] [S3]: `archive_epoch_id_active` の入力契約強化 (= recent_epoch_summaries[0].dataset_epoch_id 一致 invariant)
- Round R1 [W2]: caller adapter SSOT を Phase 2 申し送りで明文化 (= run_ga.py が SSOT adapter)
- Round R1 [W3]: 入力異常は status 拡張せず ValueError (= 業務上の不足状態 vs 入力 contract 違反の責務分離)
- Round R1 [W4]: scaffold 互換性戦略 (= 1.1.0 で optional field 追加、 旧 reader は status のみ参照) を明文化
- Round R1 [W5] [S4]: GraduationBatchInput / GraduationBatchReport を Phase 4 申し送りに格下げ (= Phase 1 では evaluate_graduation_trigger SSOT 固定のみ、 死蔵 risk 排除)
- Round R1 [W6]: graduates は **snapshot count** SSOT、 単調増加前提しない (= rollback / 再構築の余地保持)
- Round R1 [W7] [S2]: GRADUATION_ANCHOR_PAIRS → **GRADUATION_BATCH_PAIRS** rename (= cross_pair.ANCHOR_PAIRS との命名衝突排除)
- Round R1 [W8]: collider bias 責務境界 1 文固定 (= T074 は判定しない、 Phase 2 で T071 経由)
- Round R1 [S1]: GraduationRunSummary → **GraduationEpochSummary** に置換 (= run_id は監査 payload に降格、 trigger は epoch 基準)
- Round R1 [S5]: Phase 4 multi-pair aggregation 候補拡張 (= worst-case / CVaR 等)、 概念設計に追記

**関連設計 (前提)**:
- `devnotes/20260428-2300-cascade-port-debate/synthesis.md` § 11 (= Graduation Lane Batch 仕様、 T917 担当) / § 18.2 T917
- `devnotes/20260429-1912-todo-T058-schema-v2-contract/` (= dataset_epoch_id / archive_role / source_stage)
- `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md` § (`STAGE_C_ANCHOR_PAIR = "EUR_JPY"` + `STAGE_C_SHADOW_PAIR_LIST` 5 pair)
- `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 4.2 (= RunObservabilityReport)
- 既存 swim_lane: `src/alpha_factory/swim_lane.py:79` (`GraduationLane` / `Tier1Lane` / `SwimLaneRegistry`)、 `swim_lane.py:361` (Phase 2 で `run_generation` NotImplementedError)
- 既存 archive: `src/alpha_factory/archive.py:83` (`graduated: bool` field) / `archive.py:561` (`mark_graduated`)
- 既存 cross_pair: `src/alpha_factory/cross_pair.py:63` (`ANCHOR_PAIRS` mapping は別概念、 target→(anchor1,anchor2) cross-pair shadow validation 用)

---

## 0. 結論 (TL;DR、 Round 2)

T074 は新規 graduation lane 実装ではなく、 **既存 swim_lane の上に「graduation 起動条件判定 helper」 を純ライブラリで載せる scaffold** (Round R1 [S4] で batch 系 dataclass は Phase 4 申し送り):

1. **新規 module (純ライブラリ)**: `src/alpha_factory/graduation.py`、 Phase 1 は library + 単体テストのみ、 既存 swim_lane / archive / cross_pair に touch しない
2. **起動条件 SSOT (Round R1 [C2] 反映で epoch 基準に修正)** (synthesis § 11.1 厳密準拠): `evaluate_graduation_trigger(archive_summary, recent_epochs_with_mission_pass_required)` で 3 条件 (graduates>=24 / distinct epoch>=3 / **直近 N epoch すべてで mission_pass 観測**) を判定。 `recent_epochs_with_mission_pass_required` は **caller 引数** (= Phase 1 で定数化しない、 Round R1 [C1] 反映)
3. **6 batch pair SSOT** (Round R1 [W7] [S2] [C3] 反映): `GRADUATION_BATCH_PAIRS: Final[frozenset[str]] = frozenset({"EUR_JPY", "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR"})` (= synthesis § 11.2 厳密準拠、 T064 STAGE_C_ANCHOR_PAIR ∪ STAGE_C_SHADOW_PAIR_LIST と整合、 frozenset で順序非依存 SSOT)
4. **multi-pair 集約 scaffold**: `MultiPairAggregationKind = Literal["worst_pair", "mean"]` + `MultiPairAggregationSketch` dataclass (= status="not_implemented" 固定 / 数値 field なし、 T073 と同 SSOT)
5. **batch 単位実行 SSOT** (synthesis § 11.2): `LANE_PARALLELISM: Final[int] = 1` を invariant 化。 既存 GraduationLane.run_generation は Phase 4 まで NotImplementedError 維持
6. **early gate ではない / read-only**: graduation 起動条件判定は **archive read-only**、 selection 経路 (= Stage A/B/C / GA / archive admission) に touch しない (synthesis § 11.2 「初版は scaffold (起動条件判定) のみ」)
7. **status field 方式継承** (T071 / T073): `GraduationTriggerStatus = Literal["ready", "insufficient_graduates", "insufficient_epochs", "no_recent_mission_pass"]` で None 経路完全排除
8. **入力異常は ValueError** (Round R1 [W3] 反映): recent_epoch_summaries 未 sort / archive_epoch_id_active 不整合 / epoch 重複 等は status 拡張せず __post_init__ ValueError で reject (= 業務不足状態 vs 入力 contract 違反の責務分離)
9. **collider bias 責務境界** (Round R1 [W8] 反映): 「T074 は collider bias 判定しない、 stratified audit は Phase 2 で T071 RunObservabilityReport 経由」 を 1 文 SSOT
10. **graduates の snapshot count SSOT** (Round R1 [W6] 反映): archive 内 `graduated=True` field の **評価時点 snapshot count** (= 単調増加前提しない、 rollback / 再構築の余地保持)
11. **GraduationEpochSummary 中心** (Round R1 [S1] 反映): trigger は epoch 基準 (= dataset_epoch_id / has_mission_pass / contributing_run_ids)、 run_id は監査 payload に降格
12. **archive 配線は Phase 2** (Round R1 [W2] 反映): T071 RunObservabilityReport.graduation field 配線 + run_ga.py が **唯一の SSOT adapter** で archive 集計 → GraduationArchiveSummary 構築
13. **batch 系 dataclass を Phase 4 申し送り** (Round R1 [W5] [S4] 反映): GraduationBatchInput / GraduationBatchReport を Phase 1 で導入せず Phase 4 まで遅延、 死蔵 risk 排除
14. **Phase 4 申し送り**: multi-pair 集約計算実装 + GraduationLane.run_generation 実装 + Phase 4 集約候補は worst_pair / mean に加えて worst-case CVaR 等の robust portfolio 系も比較対象 (Round R1 [S5])
15. **scaffold 互換性戦略** (Round R1 [W4] 反映): MultiPairAggregationSketch は Phase 4 で 1.1.0 MINOR bump (= optional field 追加、 旧 reader は status のみ参照)

---

## 1. T074 が解決する問題

### 1.1 synthesis § 11 / § 18.2 T917 で確定済の責務

| 項目 | synthesis 文言 | T074 対応 (Round 2) |
|---|---|---|
| 起動条件 | graduates>=24 + 3 epoch + 直近 epoch で mission_pass 連続 | `evaluate_graduation_trigger` で archive read-only 判定、 直近 N epoch (= caller 引数) すべてで has_mission_pass=True を条件とする |
| 評価ロジック (Phase 4) | tier1 graduates の union を 6 anchor pair で再 backtest + multi-pair 集約 (worst-pair / mean) + live_criteria 全達成で graduation_pass | T074 では schema scaffold + sketch のみ、 計算は Phase 4 別 TODO |
| batch 単位 | tier1 と並列せず (lane_parallelism=1 維持) | `LANE_PARALLELISM: Final[int] = 1` SSOT 化 |
| 配置 | 「初版は scaffold (起動条件判定) のみ」 | Phase 1 で起動条件判定 + scaffold dataclass、 計算ロジックは未実装 |

### 1.2 既存 swim_lane との整合 (= 重要)

zenigame-fx には既に GraduationLane 関連実装あり:
- `src/alpha_factory/swim_lane.py:79` (`GraduationLane`、 `Tier1Lane`、 `SwimLaneRegistry` 等)
- `swim_lane.py:94` `GRADUATION_LANE_ID = "graduation"`
- `swim_lane.py:361` `GraduationLane.run_generation` は **NotImplementedError raise** (= "Phase 2 では未実装")
- `swim_lane.py:403` `promote_graduates` (= seed_graduates append + archive.mark_graduated)
- `swim_lane.py:939` `_mark_for_graduation` (= 冪等性 guard 付き promotion)
- `archive.py:83` `graduated: bool` field、 `archive.py:561` `mark_graduated`

→ T074 は **既存実装を touch しない**:
- 既存 GraduationLane は Phase 4 まで `run_generation` NotImplementedError 維持 (= 既存 docstring と整合)
- T074 は **archive read-only の起動条件判定** + **scaffold dataclass** を別 module に置く
- Phase 2 で T071 RunObservabilityReport.graduation field 配線時に `evaluate_graduation_trigger` を呼出

### 1.3 6 batch pair の SSOT 整合 (T064 と整合、 Round R1 [W7] [S2] [C3] 反映)

synthesis § 11.2 「6 anchor pair (EUR_JPY/USD_JPY/EUR_USD/AUD_JPY/USD_CAD/USD_ZAR)」 は T064 と整合:
- T064: `STAGE_C_ANCHOR_PAIR: Final[str] = "EUR_JPY"` (= 単独)
- T064: `STAGE_C_SHADOW_PAIR_LIST = ("USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR")` (= 5 pair)
- 計 6 pair = STAGE_C_ANCHOR_PAIR ∪ STAGE_C_SHADOW_PAIR_LIST

T074 SSOT (Round R1 [C3] 反映、 frozenset 等価):
- `GRADUATION_BATCH_PAIRS: Final[frozenset[str]] = frozenset({"EUR_JPY", "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR"})`
- 命名は `BATCH_PAIRS` で `cross_pair.ANCHOR_PAIRS` (mapping、 別概念) との衝突排除 (Round R1 [W7] [S2])
- 順序は実装詳細 (= deterministic iteration 用に sorted tuple を内部生成)、 SSOT は frozenset

### 1.4 「直近 epoch で mission_pass が連続観測」 の意味論 (Round R1 [C2] 厳密化)

synthesis § 11.1 文言は「直近 epoch で mission_pass が連続観測」。 T074 SSOT:
- **直近 N epoch すべてで has_mission_pass=True** (= run_id ベースではない、 epoch ベース)
- 「N」 (= `recent_epochs_with_mission_pass_required`) は **caller 引数** (Round R1 [C1] 反映)
- Phase 1 では定数化しない、 caller (= Phase 2 で run_ga.py) が config から渡す
- 詳細設計で「caller の default 推奨値」 (= Phase 2 config SSOT) を別途規定する余地あり
- smoke 後 / synthesis Round 22 改訂 で SSOT を確定

入力 (= GraduationEpochSummary、 Round R1 [S1] 反映):
- dataset_epoch_id
- has_mission_pass (= この epoch で mission_pass を持つ genome が >=1 つ存在)
- contributing_run_ids (= mission_pass を持つ run_id 集合、 監査 payload)

GraduationArchiveSummary.recent_epoch_summaries:
- archive 内 distinct dataset_epoch_id の **直近 N+ 個** (= run order 降順 で epoch 単位重複除去後 tail)
- caller responsibility で集計、 順序は archive_epoch_id_active 降順
- T074 trigger は最初の N 個 (= caller 引数) すべてで has_mission_pass=True を条件

### 1.5 graduates の snapshot count SSOT (Round R1 [W6] 反映)

T074 SSOT:
- archive 内の `graduated=True` field の **評価時点 snapshot count** (= 単調増加前提しない)
- rollback / 再構築 (= archive 部分削除や schema migration) の余地を保持
- caller (= Phase 2 で run_ga.py) が trigger 判定時に archive snapshot を取って count

---

## 2. 設計の SSOT 原則

### 2.1 不変 (T058 / T064 / T071 / T072 / T073 / 既存 SSOT)

- T058 schema v2: archive_role / source_stage / dataset_epoch_id (= graduated field と並んで存在)
- T064 STAGE_C_ANCHOR_PAIR / STAGE_C_SHADOW_PAIR_LIST (= GRADUATION_BATCH_PAIRS と integration test で集合等価担保)
- T071 RunObservabilityReport (= status field 方式)
- T072 collider bias 規範 (= holiday_markets 単独 drop 禁止、 Phase 2 で stratified audit)
- T073 audit early-gate ではない / status field SSOT / scaffold は数値 field なし
- 既存 swim_lane: GraduationLane / Tier1Lane / mark_graduated / promote_graduates (= touch しない)
- 既存 archive: graduated field / dataset_epoch_id (= touch しない)

### 2.2 T074 で新設 (SSOT、 Round 2)

#### 型・定数

- `GraduationTriggerStatus = Literal["ready", "insufficient_graduates", "insufficient_epochs", "no_recent_mission_pass"]` (4 値、 業務不足状態のみ。 入力 contract 違反は ValueError)
- `MultiPairAggregationKind = Literal["worst_pair", "mean"]`
- `MultiPairAggregationStatus = Literal["not_implemented"]` (= T073 AuditScaffoldStatus と同 SSOT、 1 値)
- `GRADUATION_TRIGGER_MIN_GRADUATES: Final[int] = 24` (synthesis § 11.1)
- `GRADUATION_TRIGGER_MIN_EPOCHS: Final[int] = 3` (synthesis § 11.1)
- `GRADUATION_BATCH_PAIRS: Final[frozenset[str]] = frozenset({"EUR_JPY", "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR"})` (synthesis § 11.2)
- `LANE_PARALLELISM: Final[int] = 1` (synthesis § 11.2)
- `GRADUATION_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"`
- `GRADUATION_TRIGGER_CALC_VERSION: Final[str] = "v1"`
- `GRADUATION_AGGREGATION_CALC_VERSION: Final[str] = "scaffold-v1"`

**Round R1 [C1] 反映**: `GRADUATION_RECENT_*` 系の数値定数は Phase 1 で**定数化しない**。 `evaluate_graduation_trigger` の引数 `recent_epochs_with_mission_pass_required: int` で受け渡し。 Phase 2 caller (= run_ga.py) が config 値から渡す。 smoke 後 / synthesis Round 22 改訂で SSOT 確定。

#### dataclass (frozen)

- `GraduationEpochSummary` (Round R1 [S1] 新設): dataset_epoch_id / has_mission_pass / contributing_run_ids
- `GraduationArchiveSummary` (Round R1 [S1] [S3] [W1] [W6] 反映): n_graduates (= snapshot count) / distinct_dataset_epoch_ids / recent_epoch_summaries (epoch 単位 sort) / archive_epoch_id_active (= recent[0] と一致 invariant)
- `GraduationTriggerEvaluation`: status / n_graduates / n_distinct_epochs / recent_mission_pass_epoch_ids / has_recent_mission_pass / calc_version (= "v1")
- `MultiPairAggregationSketch` (scaffold): kind / status (= "not_implemented") / calc_version (= "scaffold-v1") / **数値 field なし** (T073 SSOT 継承)

**Round R1 [W5] [S4] 反映**: `GraduationBatchInput` / `GraduationBatchReport` を Phase 1 で導入しない (= Phase 4 直前まで遅延)。 Phase 1 では `evaluate_graduation_trigger` + `compute_multi_pair_aggregation_sketch` の 2 関数 + 上記 4 dataclass に閉じる。

#### 関数

- `evaluate_graduation_trigger(*, archive_summary, recent_epochs_with_mission_pass_required) -> GraduationTriggerEvaluation`: archive read-only で 3 条件判定
- `compute_multi_pair_aggregation_sketch(*, kind) -> MultiPairAggregationSketch`: scaffold

注: `GraduationArchiveSummary` (= archive read-only の集計入力) を **caller (= Phase 2 で run_ga.py) が事前構築** して T074 に渡す。 archive.py 直 import は不可 (= 純ライブラリ + early gate ではない、 SSOT)。

### 2.3 T074 で扱わない (Phase 2 / Phase 4)

- 既存 swim_lane.GraduationLane.run_generation の実装 (= Phase 4 まで NotImplementedError 維持)
- 既存 archive.py touch (= read-only)
- multi-pair 集約計算ロジック (= worst-pair / mean / Phase 4 で worst-case / CVaR 等も検討、 Round R1 [S5])
- T071 RunObservabilityReport.graduation field 配線 (= Phase 2)
- run_ga.py で `evaluate_graduation_trigger` 呼出 (= Phase 2、 唯一の SSOT adapter)
- 6 batch pair 再 backtest 経路 (= Phase 4)
- selection 経路への接続 (= 永久に不在)
- GraduationBatchInput / GraduationBatchReport dataclass (= Phase 4 で導入)
- collider bias の T074 enforce (= 判定しない、 Phase 2 で T071 経由 stratified audit)

---

## 3. アーキテクチャ概観

```
src/alpha_factory/
├── swim_lane.py                  [既存、 T074 で touch しない]
│   ├── GraduationLane            (= run_generation は Phase 4 まで NotImplementedError)
│   ├── Tier1Lane / SwimLaneRegistry / promote_graduates / _mark_for_graduation
│
├── archive.py                     [既存、 T074 で touch しない]
│   ├── GENOMES_SCHEMA             (= "graduated" field / dataset_epoch_id 既存)
│   └── mark_graduated
│
├── cross_pair.py                  [既存、 T074 で touch しない]
│   └── ANCHOR_PAIRS (target → (anchor1, anchor2) mapping、 T074 BATCH_PAIRS と別概念)
│
└── graduation.py                  [T074 新規]
    ├── GraduationTriggerStatus / MultiPairAggregationKind / MultiPairAggregationStatus  [SSOT]
    ├── GRADUATION_TRIGGER_MIN_GRADUATES = 24                                              [SSOT]
    ├── GRADUATION_TRIGGER_MIN_EPOCHS = 3                                                  [SSOT]
    ├── GRADUATION_BATCH_PAIRS = frozenset(6 pair)                                         [SSOT]
    ├── LANE_PARALLELISM = 1                                                               [SSOT]
    ├── GRADUATION_REPORT_SCHEMA_VERSION = "1.0.0"                                         [SSOT]
    ├── GRADUATION_TRIGGER_CALC_VERSION = "v1"                                             [SSOT]
    ├── GRADUATION_AGGREGATION_CALC_VERSION = "scaffold-v1"                                [SSOT]
    ├── GraduationEpochSummary    [新設、 epoch 中心]
    ├── GraduationArchiveSummary  [入力契約、 caller responsibility]
    ├── GraduationTriggerEvaluation                                                         [SSOT]
    ├── MultiPairAggregationSketch  [scaffold、 T073 SSOT 継承]
    ├── evaluate_graduation_trigger
    └── compute_multi_pair_aggregation_sketch
```

### 3.1 T074 が touch する既存ファイル

| ファイル | 改造内容 | 既存挙動への影響 |
|---|---|---|
| (なし) | T074 PR は新規 module + 単体テストのみ | 既存ファイルへの影響なし |

### 3.2 T074 で新設するファイル

| ファイル | 内容 | 行数概算 |
|---|---|---|
| `src/alpha_factory/graduation.py` | 上記 SSOT 群 | +180 |
| `tests/alpha_factory/test_graduation.py` | F1-F22 + happy path | +250 |

---

## 4. データ構造 SSOT

### 4.1 GraduationTriggerStatus (4 値、 業務不足状態のみ)

```python
GraduationTriggerStatus = Literal[
    "ready",                          # 全 3 条件達成 (= batch 起動可)
    "insufficient_graduates",         # graduates < 24
    "insufficient_epochs",            # distinct dataset_epoch_id < 3
    "no_recent_mission_pass",         # 直近 N epoch すべてで has_mission_pass を満たさない
]
```

**Round R1 [W3] 反映**: 入力 contract 違反 (= recent_epoch_summaries 未 sort / archive_epoch_id_active 不整合 / epoch 重複) は status 拡張せず __post_init__ ValueError raise。 業務不足状態 (= 上記 4 値) と区別。

### 4.2 MultiPairAggregationKind / MultiPairAggregationStatus

```python
MultiPairAggregationKind = Literal["worst_pair", "mean"]   # synthesis § 11.2 2 軸
MultiPairAggregationStatus = Literal["not_implemented"]     # T073 SSOT 継承、 1 値
```

### 4.3 GraduationEpochSummary (Round R1 [S1] 新設)

```python
@dataclass(frozen=True)
class GraduationEpochSummary:
    """1 epoch 単位の集約 (= 直近 N epoch mission_pass 判定の入力).

    SSOT (Round R1 [C2] [S1] / Round R2 [C1] [S1] 反映): 3 field 分離で意味論明確化.
        - dataset_epoch_id: epoch 識別子
        - observed_run_ids: この epoch で観測された全 run_id (= mission fail / pass 問わず)
        - mission_pass_run_ids: mission_pass を持つ run_id の集合 (⊂ observed_run_ids)
    has_mission_pass は property で `bool(mission_pass_run_ids)` から導出.
    """

    dataset_epoch_id: str
    observed_run_ids: frozenset[str]             # この epoch の全観測 run (mission_pass / fail 問わず)
    mission_pass_run_ids: frozenset[str]         # mission_pass を持つ run のみ (⊂ observed_run_ids)

    def __post_init__(self) -> None:
        # invariant:
        #   dataset_epoch_id non-empty
        #   observed_run_ids non-empty (= 空 epoch は GraduationEpochSummary を生成しない)
        #   mission_pass_run_ids ⊂ observed_run_ids
        ...

    @property
    def has_mission_pass(self) -> bool:
        """Round R2 [C1] 反映: mission pass run の有無で導出 (= 観測 run 全体ではない)."""
        return bool(self.mission_pass_run_ids)
```

### 4.4 GraduationArchiveSummary (Round R1 [W1] [W6] [S3] 反映)

```python
@dataclass(frozen=True)
class GraduationArchiveSummary:
    """archive read-only の評価時点 snapshot 集計 (Round R1 [W6] / Round R2 [C2] [C3] [S2] / [W3]、 caller responsibility).

    SSOT:
        - n_graduates: archive 内 graduated=True の **評価時点 snapshot count** (= 単調増加前提しない)
        - distinct_dataset_epoch_ids: archive 内 distinct dataset_epoch_id 集合 (= 空集合許容、 empty archive は業務不足)
        - recent_epoch_summaries: 直近 N+ epoch の GraduationEpochSummary 列
          **recent-first head N order** (Round R2 [C3]):
            - active/current epoch から古い順 (= [0] が active、 [-1] が最古)
            - epoch 単位 unique
            - 全要素の dataset_epoch_id ∈ distinct_dataset_epoch_ids
        - archive_epoch_id_active: str | None (Round R2 [C2])
          - non-None なら recent_epoch_summaries[0].dataset_epoch_id と一致
          - None なら distinct_dataset_epoch_ids 空 + recent_epoch_summaries 空 (= empty archive)

    adapter contract (Round R2 [W3]、 Phase 2 申し送り):
        Phase 2 caller (= run_ga.py) は **同一 archive snapshot** から
        n_graduates / distinct_dataset_epoch_ids / recent_epoch_summaries / archive_epoch_id_active を
        単一 transaction 内で構築する責務. 連続 read の揺らぎは adapter contract violation
        (= T074 module ではなく adapter 側の問題).
    """

    n_graduates: int
    distinct_dataset_epoch_ids: frozenset[str]
    recent_epoch_summaries: tuple[GraduationEpochSummary, ...]
    archive_epoch_id_active: str | None     # Round R2 [C2]: None で empty archive

    def __post_init__(self) -> None:
        # invariant:
        #   n_graduates >= 0
        #   recent_epoch_summaries は epoch 単位重複なし (= dataset_epoch_id がユニーク)
        #   全 recent_epoch_summaries[i].dataset_epoch_id ∈ distinct_dataset_epoch_ids
        #
        # archive_epoch_id_active 整合 (Round R2 [C2] 反映):
        #   None case (= empty archive):
        #     distinct_dataset_epoch_ids が空集合
        #     recent_epoch_summaries が空 tuple
        #   non-None case:
        #     archive_epoch_id_active ∈ distinct_dataset_epoch_ids
        #     recent_epoch_summaries が non-empty なら [0].dataset_epoch_id == archive_epoch_id_active
        #
        # 入力 contract 違反 (= 上記 invariant 違反) は ValueError raise (status 拡張しない)
        ...
```

### 4.5 GraduationTriggerEvaluation

```python
@dataclass(frozen=True)
class GraduationTriggerEvaluation:
    """3 条件判定結果 (Round R1 [C2] 反映で epoch 基準).

    SSOT (synthesis § 11.1):
        status="ready" 条件:
            n_graduates >= GRADUATION_TRIGGER_MIN_GRADUATES (= 24)
            len(distinct_dataset_epoch_ids) >= GRADUATION_TRIGGER_MIN_EPOCHS (= 3)
            直近 recent_epochs_with_mission_pass_required epoch すべてで has_mission_pass=True
        失敗時 status:
            n_graduates 不足 → "insufficient_graduates" (最優先)
            epoch 不足 → "insufficient_epochs"
            recent epoch mission_pass 不足 → "no_recent_mission_pass"

    優先順位 (status 排他、 disjoint):
        1. n_graduates 不足 → "insufficient_graduates"
        2. epoch 不足 → "insufficient_epochs"
        3. recent epoch mission_pass 不足 → "no_recent_mission_pass"
        4. 全達成 → "ready"
    """

    status: GraduationTriggerStatus
    n_graduates: int                             # snapshot count、 status != "ready" でも実測値保持
    n_distinct_epochs: int                       # 実測値
    recent_mission_pass_epoch_ids: tuple[str, ...]   # mission_pass を持つ直近 N epoch の dataset_epoch_id (= status="ready" 時のみ完全集計、 早期 return では空 tuple)
    has_recent_mission_pass: bool                # **Round R2 [W2] 反映**: 「実際に直近 N epoch すべてで mission_pass か」 = (len(recent_mission_pass_epoch_ids) == recent_epochs_required AND status == "ready")
    recent_epochs_required: int                   # 入力した「N」 を保持 (audit 用)
    calc_version: str                            # = "v1"

    def __post_init__(self) -> None:
        # invariant:
        #   calc_version == GRADUATION_TRIGGER_CALC_VERSION
        #   n_graduates >= 0
        #   n_distinct_epochs >= 0
        #   recent_epochs_required >= 1
        #   has_recent_mission_pass invariant (Round R2 [W2]):
        #     status == "ready" → has_recent_mission_pass == True かつ len(recent_mission_pass_epoch_ids) == recent_epochs_required
        #     status != "ready" → has_recent_mission_pass == False
        #     (= 早期 return 時は False、 status と独立計算しない)
        #   status 別 invariant (= "ready" → 全 3 条件達成、 "insufficient_*" → 該当条件不充足)
        ...
```

### 4.6 MultiPairAggregationSketch (scaffold、 T073 SSOT 継承)

```python
@dataclass(frozen=True)
class MultiPairAggregationSketch:
    """multi-pair 集約 scaffold (Phase 4 で実装).

    SSOT (synthesis § 11.2 / T073 AuditPBOMetric scaffold と同 SSOT):
        - status は "not_implemented" 固定
        - 数値 field なし (= status check 漏れで誤読 risk 排除、 fail-closed、 Round R1 [W4])
        - calc_version = "scaffold-v1"
        - kind は worst_pair / mean (Phase 4 候補は worst-case / CVaR 等も検討、 Round R1 [S5])

    Phase 4 で field 追加候補 (= 1.1.0 MINOR bump で後方互換、 Round R1 [W4]):
        - per_pair_results: tuple[PerPairCanonicalFiveResult, ...] (= 6 pair の canonical 5 worst)
        - aggregated_value: Decimal
        - graduation_pass: bool (= multi-pair worst で live_criteria 全達成)
        旧 reader は status field のみ参照、 unknown field を ignore する規約.
    """

    kind: MultiPairAggregationKind
    status: MultiPairAggregationStatus    # = "not_implemented" 固定
    calc_version: str                      # = "scaffold-v1"

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(
                f"MultiPairAggregationSketch.status must be 'not_implemented' (scaffold), got {self.status!r}"
            )
        if self.calc_version != GRADUATION_AGGREGATION_CALC_VERSION:
            raise ValueError(
                f"calc_version must be {GRADUATION_AGGREGATION_CALC_VERSION!r}, got {self.calc_version!r}"
            )
```

---

## 5. 主要関数 API SSOT (§ 11.2 SSOT 規約準拠)

```python
# src/alpha_factory/graduation.py

GraduationTriggerStatus = Literal["ready", "insufficient_graduates", "insufficient_epochs", "no_recent_mission_pass"]
MultiPairAggregationKind = Literal["worst_pair", "mean"]
MultiPairAggregationStatus = Literal["not_implemented"]

GRADUATION_TRIGGER_MIN_GRADUATES: Final[int] = 24
GRADUATION_TRIGGER_MIN_EPOCHS: Final[int] = 3
GRADUATION_BATCH_PAIRS: Final[frozenset[str]] = frozenset({
    "EUR_JPY", "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR"
})
LANE_PARALLELISM: Final[int] = 1
GRADUATION_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
GRADUATION_TRIGGER_CALC_VERSION: Final[str] = "v1"
GRADUATION_AGGREGATION_CALC_VERSION: Final[str] = "scaffold-v1"


@dataclass(frozen=True)
class GraduationEpochSummary: ...

@dataclass(frozen=True)
class GraduationArchiveSummary: ...

@dataclass(frozen=True)
class GraduationTriggerEvaluation: ...

@dataclass(frozen=True)
class MultiPairAggregationSketch: ...


def evaluate_graduation_trigger(
    *,
    archive_summary: GraduationArchiveSummary,
    recent_epochs_with_mission_pass_required: int,
) -> GraduationTriggerEvaluation:
    """archive read-only で 3 条件判定.

    SSOT (synthesis § 11.1、 Round R1 [C1] [C2] 反映):
        recent_epochs_with_mission_pass_required は **caller 引数** (= Phase 1 で定数化しない、
        Phase 2 で run_ga.py が config 値から渡す).

        優先順位 (disjoint):
            1. n_graduates < 24                                    → "insufficient_graduates"
            2. distinct epoch < 3                                  → "insufficient_epochs"
            3. 直近 N epoch すべてで has_mission_pass を満たさない   → "no_recent_mission_pass"
            4. 全達成                                                → "ready"

    Raises:
        ValueError: recent_epochs_with_mission_pass_required < 1 / 入力 contract 違反.
    """
    ...


def compute_multi_pair_aggregation_sketch(
    *,
    kind: MultiPairAggregationKind,
    calc_version: str = GRADUATION_AGGREGATION_CALC_VERSION,
) -> MultiPairAggregationSketch:
    """multi-pair 集約 scaffold (= status="not_implemented" 固定、 計算しない)."""
    ...
```

---

## 6. アルゴリズム詳細 (擬似コード)

### 6.1 evaluate_graduation_trigger (Round 2)

```python
def evaluate_graduation_trigger(*, archive_summary, recent_epochs_with_mission_pass_required):
    if recent_epochs_with_mission_pass_required < 1:
        raise ValueError(
            f"recent_epochs_with_mission_pass_required >= 1 required, "
            f"got {recent_epochs_with_mission_pass_required}"
        )

    n_graduates = archive_summary.n_graduates
    n_distinct_epochs = len(archive_summary.distinct_dataset_epoch_ids)

    # Step 1: graduates 不足 (最優先)
    if n_graduates < GRADUATION_TRIGGER_MIN_GRADUATES:
        return _make_trigger(
            status="insufficient_graduates",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=tuple(),
            recent_epochs_required=recent_epochs_with_mission_pass_required,
        )

    # Step 2: epoch 不足
    if n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS:
        return _make_trigger(
            status="insufficient_epochs",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=tuple(),
            recent_epochs_required=recent_epochs_with_mission_pass_required,
        )

    # Step 3: 直近 N epoch 連続 mission_pass 判定
    recent = archive_summary.recent_epoch_summaries[:recent_epochs_with_mission_pass_required]
    if len(recent) < recent_epochs_with_mission_pass_required:
        return _make_trigger(
            status="no_recent_mission_pass",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=tuple(),
            recent_epochs_required=recent_epochs_with_mission_pass_required,
        )

    mission_pass_epoch_ids = tuple(e.dataset_epoch_id for e in recent if e.has_mission_pass)
    if len(mission_pass_epoch_ids) < recent_epochs_with_mission_pass_required:
        return _make_trigger(
            status="no_recent_mission_pass",
            n_graduates=n_graduates,
            n_distinct_epochs=n_distinct_epochs,
            recent_mission_pass_epoch_ids=mission_pass_epoch_ids,
            recent_epochs_required=recent_epochs_with_mission_pass_required,
        )

    # Step 4: 全達成
    return _make_trigger(
        status="ready",
        n_graduates=n_graduates,
        n_distinct_epochs=n_distinct_epochs,
        recent_mission_pass_epoch_ids=mission_pass_epoch_ids,
        recent_epochs_required=recent_epochs_with_mission_pass_required,
    )


def _make_trigger(*, status, n_graduates, n_distinct_epochs, recent_mission_pass_epoch_ids, recent_epochs_required):
    return GraduationTriggerEvaluation(
        status=status,
        n_graduates=n_graduates,
        n_distinct_epochs=n_distinct_epochs,
        recent_mission_pass_epoch_ids=recent_mission_pass_epoch_ids,
        has_recent_mission_pass=(
            len(recent_mission_pass_epoch_ids) >= recent_epochs_required
        ),
        recent_epochs_required=recent_epochs_required,
        calc_version=GRADUATION_TRIGGER_CALC_VERSION,
    )
```

### 6.2 compute_multi_pair_aggregation_sketch

```python
def compute_multi_pair_aggregation_sketch(*, kind, calc_version=GRADUATION_AGGREGATION_CALC_VERSION):
    return MultiPairAggregationSketch(
        kind=kind,
        status="not_implemented",
        calc_version=calc_version,
    )
```

---

## 7. 既存挙動への影響 (C2 parallel-path verification)

### 7.1 直 import 経路

`src/alpha_factory/graduation.py` は **新規ファイル**。 既存ファイルの touch は **0 件** (= early gate 不在 SSOT、 synthesis § 11.2 厳密準拠)。 既存 swim_lane.py / archive.py / cross_pair.py は import しない (= 純ライブラリ、 caller (Phase 2 で run_ga.py) が archive 集計して `GraduationArchiveSummary` を構築)。

### 7.2 5 段階 grep 検証 (Phase 1 PR 内)

- 直 import: `from src.alpha_factory.graduation import ...` は Phase 1 では tests のみ
- alias / relative / 再エクスポート: なし
- runtime シンボル: T074 dataclass / 関数の caller は Phase 2 で T071 RunObservabilityReport 拡張から (= まだ実装されていない)

### 7.3 既存 cross_pair.ANCHOR_PAIRS との命名分離 (Round R1 [W7] [S2])

- 既存 `cross_pair.py:63` `ANCHOR_PAIRS: Mapping[str, tuple[str, str]]` (= target → (anchor1, anchor2) mapping、 cross-pair shadow validation 用)
- T074 `GRADUATION_BATCH_PAIRS: frozenset[str]` (= 6 pair flat、 graduation batch 用)
- 命名分離で C2 parallel-path 誤読防止、 docstring 明示

### 7.4 fail-closed 経路

- 入力 GraduationArchiveSummary が contract 違反 → __post_init__ ValueError
- recent_epoch_summaries が epoch 単位重複 / archive_epoch_id_active 不整合 → __post_init__ ValueError
- recent_epochs_with_mission_pass_required < 1 → evaluate_graduation_trigger ValueError
- MultiPairAggregationSketch の status / calc_version invariant 違反 → __post_init__ ValueError

---

## 8. 不変条件 (invariant)

| ID | 不変条件 | 担保 |
|---|---|---|
| I1 | 既存 swim_lane / archive / cross_pair の SSOT は T074 で touch しない | 新規 module、 既存 import なし |
| I2 | early gate ではない (= selection 経路に影響しない) | T074 PR は selection 経路に touch しない |
| I3 | GraduationTriggerStatus は 4 値のみ (= 業務不足状態) | __post_init__ で値検証 |
| I4 | GraduationTriggerEvaluation の status と数値 field の disjoint 整合 | __post_init__ |
| I5 | GraduationArchiveSummary の入力 contract 違反は ValueError (= status 拡張せず、 Round R1 [W3]) | __post_init__ |
| I6 | recent_epoch_summaries は epoch 単位ユニーク、 [0].dataset_epoch_id == archive_epoch_id_active | __post_init__ (Round R1 [W1] [S3]) |
| I7 | GRADUATION_TRIGGER_MIN_GRADUATES = 24 / GRADUATION_TRIGGER_MIN_EPOCHS = 3 (synthesis § 11.1 厳密準拠) | Final 定数 |
| I8 | recent_epochs_with_mission_pass_required は **caller 引数** (= Phase 1 で定数化しない、 Round R1 [C1]) | 関数 signature SSOT |
| I9 | GRADUATION_BATCH_PAIRS = frozenset 6 pair (= synthesis § 11.2 厳密準拠) | Final 定数、 T064 STAGE_C_ANCHOR_PAIR ∪ STAGE_C_SHADOW_PAIR_LIST と integration test で集合等価担保 |
| I10 | LANE_PARALLELISM = 1 (synthesis § 11.2) | Final 定数 |
| I11 | MultiPairAggregationSketch.status == "not_implemented" 固定 / calc_version == "scaffold-v1" | __post_init__ |
| I12 | scaffold は NotImplementedError raise しない (= status field 方式、 T073 と同 SSOT) | 関数 logic + 単体テスト |
| I13 | T074 module は archive.py / swim_lane.py / cross_pair.py を import しない (= 純ライブラリ) | grep DoD |
| I14 | graduates は archive snapshot count (= 単調増加前提しない、 Round R1 [W6]) | docstring SSOT |
| I15 | trigger 判定は epoch 基準 (= run 基準ではない、 Round R1 [C2]) | GraduationEpochSummary 中心、 関数 logic |
| I16 | collider bias は T074 で判定しない (Round R1 [W8]) | docstring SSOT、 Phase 2 申し送り |

---

## 9. リスクと緩和

| リスク | 影響 | 緩和 |
|---|---|---|
| F1 recent_epochs_with_mission_pass_required の SSOT 不在 | trigger 誤判定 | Phase 1 では caller 引数で受け渡し、 Phase 2 caller (run_ga.py) で config 値から渡す、 smoke 後 / synthesis Round 22 改訂で SSOT 確定 |
| F2 multi-pair 集約 scaffold で誤って Phase 4 実装と混同 | scaffold が caller に流入 | status="not_implemented" 固定 + calc_version="scaffold-v1" の二重 SSOT、 docstring 明示 |
| F3 既存 GraduationLane.run_generation が Phase 4 まで NotImplementedError | T074 PR で誤って実装される risk | T074 PR は touch しない、 既存 docstring と整合 |
| F4 6 batch pair の SSOT が T064 と乖離 | live_criteria 評価で不整合 | I9 整合性 test で T064 値との集合等価を検証 |
| F5 GraduationArchiveSummary の caller (= Phase 2 で run_ga.py) が archive を直接読む経路の SSOT 不在 (Round R1 [W2]) | 集計規則の複数化 | Phase 2 で run_ga.py を **唯一の SSOT adapter** に固定、 docstring + Phase 2 申し送り |
| F6 既存 cross_pair.py:63 の ANCHOR_PAIRS (= 別概念) と混同 (Round R1 [W7] [S2]) | 命名衝突 | T074 SSOT は GRADUATION_BATCH_PAIRS で命名分離、 docstring で別概念明示 |
| F7 lane_parallelism の SSOT 違反 (= 並列起動) | tier1 と graduation の干渉 | LANE_PARALLELISM = 1 invariant、 Phase 4 で GraduationBatchInput 導入時に __post_init__ で reject |
| F8 graduates の単調増加前提 (Round R1 [W6]) | rollback / 再構築で count 揺らぎ | docstring SSOT で「snapshot count」 明記、 archive 経路の rollback 余地保持 |
| F9 epoch 多様性判定で skip_frozen / drift 状態の epoch を誤計上 | trigger 誤判定 | archive_summary.distinct_dataset_epoch_ids は archive 内 distinct epoch_id 集合、 frozen state は別概念 (= T069 calibrate-gate scope) |
| F10 collider bias (T072 / T073 規範) graduates の holiday/DST 偏り (Round R1 [W8]) | trigger 判定の bias | T074 で判定しない、 Phase 2 で T071 経由 stratified audit を申し送り、 docstring 1 文 SSOT |
| F11 GRADUATION_REPORT_SCHEMA_VERSION の Phase 4 bump (Round R1 [W4]) | consumer breakage | 1.0.0 → 1.1.0 (MINOR、 optional field 追加で後方互換)、 旧 reader は status のみ参照する規約を Phase 4 申し送り |
| F12 「直近 epoch」 の解釈揺らぎ (Round R1 [C2]) | trigger 判定の意味論 | T074 SSOT で「epoch 基準」 と固定、 GraduationEpochSummary 中心、 docstring 明記 |

---

## 10. テスト計画 (概要、 詳細は detailed-design.md で)

### 10.1 pure function tests

- F1: `evaluate_graduation_trigger` happy path (= 全 3 条件達成、 status="ready")
- F2: n_graduates=23 → status="insufficient_graduates"
- F3: distinct epoch=2 → status="insufficient_epochs"
- F4: recent_epoch_summaries が required 未満 → status="no_recent_mission_pass"
- F5: recent N epoch 中 1 epoch のみ mission_pass → status="no_recent_mission_pass"
- F6: 直近 N epoch すべてで mission_pass → has_recent_mission_pass=True
- F7: 優先順位 (graduates → epoch → recent) 排他性
- F8: recent_epochs_with_mission_pass_required=0 → ValueError
- F9: recent_epochs_with_mission_pass_required を 1 / 2 / 3 で渡して結果が引数依存に変わる (= 定数化していない、 Round R1 [C1])

### 10.2 scaffold tests

- F10: compute_multi_pair_aggregation_sketch(kind="worst_pair") → status="not_implemented" / calc_version="scaffold-v1"
- F11: kind="mean" → 同上
- F12: scaffold は NotImplementedError raise しない

### 10.3 GraduationEpochSummary / GraduationArchiveSummary tests

- F13: GraduationEpochSummary(has_mission_pass=True, contributing_run_ids=frozenset()) → ValueError (= bool(contributing_run_ids) と整合)
- F14: GraduationArchiveSummary recent_epoch_summaries が epoch 単位重複 → ValueError
- F15: archive_epoch_id_active ∉ distinct_dataset_epoch_ids → ValueError
- F16: recent_epoch_summaries[0].dataset_epoch_id != archive_epoch_id_active → ValueError (Round R1 [W1] [S3])
- F17: n_graduates < 0 → ValueError

### 10.4 MultiPairAggregationSketch tests

- F18: status="ok" → ValueError
- F19: calc_version="v1" → ValueError

### 10.5 既存 SSOT 整合 tests

- F20: GRADUATION_BATCH_PAIRS の値が T064 STAGE_C_ANCHOR_PAIR ("EUR_JPY") + STAGE_C_SHADOW_PAIR_LIST (5 pair) と **集合等価** (= frozenset SSOT、 順序非依存)
- F21: GRADUATION_TRIGGER_MIN_GRADUATES=24 / MIN_EPOCHS=3 が synthesis § 11.1 と一致

### 10.6 collider bias 規範 tests (Round R1 [W8] 申し送り)

- F22: T074 内で holiday_markets / dst_transition_markets を参照する経路がない (= grep DoD)、 collider bias 判定は Phase 2 で T071 経由

---

## 11. Phase 1 / Phase 2 / Phase 4 分離

### 11.1 Phase 1 (T074 PR、 純ライブラリ)

含む:
- `src/alpha_factory/graduation.py` 新規 (上記 SSOT 群、 batch 系 dataclass は含まない)
- `tests/alpha_factory/test_graduation.py` 新規 (F1-F22)
- 単体テストのみで runtime 未組込

含まない (Round R1 [W5] [S4] 反映で Phase 4 申し送り強化):
- T071 RunObservabilityReport.graduation field 配線 (= Phase 2)
- run_ga.py で `evaluate_graduation_trigger` 呼出 + `GraduationArchiveSummary` 構築 (= Phase 2、 唯一の SSOT adapter)
- 既存 swim_lane / archive / cross_pair の touch (= Phase 4 まで run_generation NotImplementedError 維持)
- GraduationBatchInput / GraduationBatchReport dataclass (= **Phase 4 で導入**、 Phase 1 で死蔵 risk 排除)
- multi-pair 集約計算ロジック (= Phase 4 別 TODO)
- collider bias 判定 (= 永久に不在、 Phase 2 で T071 経由)

### 11.2 Phase 2 (別 TODO、 cascade port 切替時)

- T071 RunObservabilityReport に `graduation_trigger: GraduationTriggerEvaluation` field 追加
- **run_ga.py は唯一の SSOT adapter** (Round R1 [W2] 反映): archive 集計 → GraduationArchiveSummary 構築 → evaluate_graduation_trigger → log/report 出力
- collider bias 規範: T071 経由で graduation 関連の stratified audit 出力

### 11.3 Phase 4 (別 TODO、 multi-pair 集約実装)

- compute_multi_pair_aggregation_sketch を実装版に置換
- GraduationBatchInput / GraduationBatchReport dataclass 導入
- GraduationLane.run_generation の実装 (= 6 batch pair 再 backtest + worst_pair / mean 集約 + graduation_pass 判定)
- GRADUATION_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 (MINOR bump、 後方互換)
- Phase 4 集約候補の検討 (Round R1 [S5]): worst_pair / mean に加えて worst-case CVaR / robust portfolio 系も比較対象

### 11.4 申し送り (詳細設計で明文化)

- T071 詳細設計改訂: RunObservabilityReport に `graduation_trigger: GraduationTriggerEvaluation` field 追加
- T064 詳細設計改訂申し送り: STAGE_C_ANCHOR_PAIR / STAGE_C_SHADOW_PAIR_LIST と GRADUATION_BATCH_PAIRS の整合性は T074 PR で integration test、 T064 値変更時は同期改訂
- swim_lane.py 詳細設計改訂申し送り: GraduationLane.run_generation の Phase 4 実装は別 TODO、 NotImplementedError docstring 維持
- run_ga.py 詳細設計改訂申し送り: Phase 2 で archive read-only 集計 → GraduationArchiveSummary 構築の唯一の SSOT adapter

### 11.5 collider bias 責務境界 SSOT (Round R1 [W8] 1 文固定)

> T074 は collider bias を判定しない。 holiday_markets / dst_transition_markets / schedule_status の stratified audit は **Phase 2 で T071 RunObservabilityReport 経由**で出力する責務。 T074 module 内では observability_flags を参照しない (= grep DoD で確認)。

### 11.6 caller adapter SSOT (Round R1 [W2] / Round R2 [W1] [W3] 反映)

Phase 2 で `run_ga.py` を **唯一の SSOT adapter** とする:
- **同一 archive snapshot から単一 transaction で集計** (Round R2 [W3]): n_graduates / distinct_dataset_epoch_ids / recent_epoch_summaries / archive_epoch_id_active を一括取得、 連続 read の揺らぎは adapter contract violation
- archive read-only 集計 → `GraduationArchiveSummary` 構築
- **config missing 時は fail-closed** (Round R2 [W1]): `recent_epochs_with_mission_pass_required` の config キー (= Phase 2 で命名確定) が不在なら ValueError raise、 暗黙 default 不可
- `evaluate_graduation_trigger` 呼出
- `RunObservabilityReport.graduation_trigger` field に同梱
- log / report 出力

archive 集計ロジック (= n_graduates / distinct_dataset_epoch_ids / recent_epoch_summaries / archive_epoch_id_active の構築) は run_ga.py に集約し、 他 caller (= test 含む) は run_ga.py の helper を経由して構築。

---

## 12. 設計判断 SSOT (synthesis 確定値 vs T074 設計判断値)

### 12.1 synthesis 確定値 (= 厳密準拠)

- graduates >= 24 (synthesis § 11.1)
- distinct epoch >= 3 (synthesis § 11.1)
- 直近 epoch で mission_pass 連続観測 (synthesis § 11.1、 N は T074 で caller 引数化)
- 6 batch pair = EUR_JPY / USD_JPY / EUR_USD / AUD_JPY / USD_CAD / USD_ZAR (synthesis § 11.2)
- multi-pair 集約 = worst_pair / mean (synthesis § 11.2、 Phase 4 で robust 系も検討)
- graduation_pass = multi-pair worst で live_criteria 全達成 (synthesis § 11.2)
- batch 単位、 lane_parallelism=1 (synthesis § 11.2)
- 「初版は scaffold (起動条件判定) のみ」 (synthesis § 11.2)

### 12.2 T074 設計判断値 (= synthesis 未明示、 Phase 4 / smoke 後再校正)

- recent_epochs_with_mission_pass_required: **caller 引数化** (= Phase 1 で定数化しない、 Round R1 [C1])
- GraduationArchiveSummary の入力契約 (= caller responsibility で archive 集計、 Phase 2 で run_ga.py が唯一の SSOT adapter)
- GraduationTriggerStatus 4 値 (= 業務不足状態のみ、 入力 contract 違反は ValueError)
- 優先順位 (graduates → epoch → recent) の disjoint 化
- GraduationEpochSummary 中心 (= run 基準ではない、 Round R1 [C2] [S1])
- GRADUATION_BATCH_PAIRS は frozenset (= 順序非依存、 Round R1 [C3])
- MultiPairAggregationSketch を T073 AuditPBOMetric scaffold と同 SSOT (= 数値 field なし)
- GRADUATION_REPORT_SCHEMA_VERSION = "1.0.0" / GRADUATION_TRIGGER_CALC_VERSION = "v1" / GRADUATION_AGGREGATION_CALC_VERSION = "scaffold-v1"

---

## 13. T075 / Phase 4 への申し送り

- **T075 smoke**: recent_epochs_with_mission_pass_required の caller 引数化を smoke 5 Run で実運用、 妥当性検証、 synthesis Round 22 改訂候補で値を明文化
- **Phase 4 multi-pair 集約**: GRADUATION_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 MINOR bump で field 追加、 既存 caller は status のみ参照
- **Phase 4 GraduationLane.run_generation 実装**: 既存 swim_lane.py:361 の NotImplementedError を実装に置換、 6 batch pair 再 backtest + worst_pair / mean 集約
- **Phase 4 集約候補**: synthesis § 11.2 の worst_pair / mean に加えて worst-case CVaR / robust portfolio 系の比較検討 (Round R1 [S5])

---

## 14. open questions (詳細設計で解消)

1. **`recent_epochs_with_mission_pass_required` の caller default 推奨値**: Phase 2 config SSOT で「2」 等を推奨するか、 完全に caller 自由か (= synthesis Round 22 改訂候補)
2. **GraduationArchiveSummary の caller 集計 SSOT (Round R1 [W2])**: Phase 2 run_ga.py の helper API 設計
3. **GRADUATION_AGGREGATION_CALC_VERSION = "scaffold-v1"**: T073 AUDIT_SCAFFOLD_CALC_VERSION と同値、 共通定数化するか別定数で SSOT 維持か
4. **GraduationLane (既存) との接続点**: T074 module は GraduationLane を import しないが、 Phase 4 で GraduationLane.run_generation 内で T074 関数を呼出する経路の SSOT
5. **詳細設計で固定すべき items**:
   - GraduationEpochSummary の bool / frozenset invariant 順序
   - `_make_trigger` keyword-only call SSOT (T073 と同パターン)
   - error message prefix (= invariant order test 用)
6. **collider bias 規範の T074 enforce 強化**: T071 経由で stratified audit を出力する Phase 2 申し送りで十分か / T074 schema にも flag 集計を入れるか
7. **Phase 4 集約候補の比較研究**: Round R1 [S5] の worst-case CVaR / robust portfolio 系を Phase 4 で実装する優先順位

---

## 15. references / cross-cut

| 項目 | 場所 |
|---|---|
| synthesis § 11 (= Graduation Lane Batch 仕様) | `devnotes/20260428-2300-cascade-port-debate/synthesis.md` |
| synthesis § 18.2 T917 (= 本 TODO の親条文) | 同上 |
| 既存 GraduationLane / swim_lane | `src/alpha_factory/swim_lane.py:79` (= GraduationLane / SwimLaneRegistry) / `swim_lane.py:361` (= run_generation NotImplementedError) |
| 既存 archive `graduated` field | `src/alpha_factory/archive.py:83` (= field) / `archive.py:561` (= mark_graduated) |
| T058 dataset_epoch_id / archive_role | `devnotes/20260429-1912-todo-T058-schema-v2-contract/` |
| T064 STAGE_C_ANCHOR_PAIR / STAGE_C_SHADOW_PAIR_LIST | `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md` § |
| T071 RunObservabilityReport (Phase 2 拡張先) | `devnotes/20260430-1925-todo-T071-observability/conceptual-design.md` § 4.2 |
| T072 collider bias 規範 | `devnotes/20260430-2036-todo-T072-dst-holiday-boundary/detailed-design.md` § 9.6 |
| T073 audit scaffold (= AuditPBOMetric / AuditScaffoldStatus 同 SSOT) | `devnotes/20260430-2301-todo-T073-audit-layer/conceptual-design.md` § 4.3 |
| 既存 cross_pair `ANCHOR_PAIRS` (別概念、 命名分離) | `src/alpha_factory/cross_pair.py:63` |

---

## 16. 学術文献 (Round R1 [S5] / Phase 4 検討用)

- Kim, W., Kim, J. H., & Fabozzi, F. J. (2018). *Robust Portfolio Optimization: A Survey.* Journal of Optimization Theory and Applications. (Phase 4 worst-case 集約検討)
- Boudt, K., et al. (2022). *Worst-case mean-CVaR portfolios for international FX.* European Journal of Operational Research. (Phase 4 通貨横断 robust 集約)
- Bailey, D. H., Borwein, J. M., López de Prado, M. M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* Journal of Computational Finance 20(4). (PBO / CSCV、 Phase 4 multi-pair 集約 + graduation 判定品質管理)
- Kahn, R. N. (1992). *Quantitative Aggregation of Asset-Specific Forecasts.* (mean 集約参考)

---

## 17. Round 1 → Round 2 対応マトリクス

| Round 1 | Round 2 対応 |
|---|---|
| C1 GRADUATION_RECENT_RUNS_WITH_MISSION_PASS=2 仮置き | 定数化廃止、 caller 引数 (recent_epochs_with_mission_pass_required) で受け渡し |
| C2 「直近 epoch」 を「直近 N Run」 に読み替え危険 | epoch 基準に修正、 GraduationEpochSummary 中心 |
| C3 anchor_pairs 順序 SSOT | frozenset 等価 SSOT、 GRADUATION_BATCH_PAIRS rename |
| W1 archive_epoch_id_active 未使用 | recent_epoch_summaries[0] 一致 invariant 化 (S3 と同義) |
| W2 caller adapter SSOT 不明 | Phase 2 で run_ga.py を唯一の SSOT adapter と明示 (§ 11.6) |
| W3 入力異常を status 拡張で扱う | __post_init__ ValueError 化、 業務不足状態 vs contract 違反の責務分離 |
| W4 scaffold 互換性戦略 | 1.1.0 MINOR bump で optional field 追加、 旧 reader は status のみ参照規約 (§ 4.6 docstring) |
| W5 GraduationBatchInput Phase 1 死蔵 | Phase 4 で導入、 Phase 1 では evaluate_graduation_trigger + scaffold のみ (S4 と同義) |
| W6 graduates 単調増加前提 | snapshot count SSOT (= rollback / 再構築の余地保持) |
| W7 cross_pair.ANCHOR_PAIRS 命名衝突 | GRADUATION_BATCH_PAIRS rename + docstring 明示 (S2 と同義) |
| W8 collider bias 責務境界 | § 11.5 で 1 文 SSOT 固定、 Phase 2 申し送り |
| S1 GraduationEpochSummary | 採用 (= C2 と同義) |
| S2 GRADUATION_BATCH_PAIRS rename | 採用 |
| S3 archive_epoch_id_active invariant 強化 | 採用 (= W1 と同義) |
| S4 batch 系 dataclass を Phase 4 遅延 | 採用 (= W5 と同義) |
| S5 Phase 4 集約候補拡張 | § 13 / § 16 で worst-case CVaR / robust portfolio 系を Phase 4 申し送り |

---

これで T074 概念設計 Round 2 改訂は完成。 Round 1 で出た 3 Critical / 8 Warning / 5 Suggestion を全反映、 batch 系 dataclass を Phase 4 申し送り + epoch 中心 + frozenset SSOT + caller 引数化に再設計。 Codex Round 2 review で更に falsification を試みる。
