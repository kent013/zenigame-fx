# 概念設計: B Phase 2 Integration Program — step 2.1 (stage_bc_evaluator shadow integration)

**作成日時**: 2026-05-04 10:26 JST (Round 2: 案 B 採用 + step 2.1 scope 化、 Round 3: 2.1a/2.1b 内部分割、 Round 4: sidecar timing + skip event 必須化、 Round 5 改訂: 2026-05-04 11:03 JST、 StageBCShadowContext 導入 + run-level collector 分離 + schema 完全反映 + 文言全統一)
**起源**: B Phase 2 切替コミット step 1.8 (= Stage C cross_pair (ii-lite) dual-path 拡張、 main commit c3ee70a) 完了後の本丸統合 (= Phase 2 integration program 開始)
**性質**: Codex Round 1 review で **案 B (= 段階分割)** が確定。 全体 program は **B Phase 2 Integration Program** と命名し、 配下に **step 2.1 (shadow integration LOG_ONLY)** / **step 2.2 (switch)** / **step 2.3 (deprecation)** を配置。 本設計は **step 2.1 のみ** を scope 対象とし、 2.2 / 2.3 への exit criteria を同時定義する。
**位置付け**: cascade port v2 Phase 2 切替コミット 7 step segmentation の **step 2 = Phase 2 integration program**。 program は段階分割で完結 (= 2.1 → 2.2 → 2.3)、 「Phase 2 切替コミット完了」 という呼称は **step 2.2 完了時にのみ** 使用。
**status**: **概念設計 Round 5 APPROVED** (= 案 B 採用維持、 Codex Round 1-5 全反映、 Warning 5 件 + Suggestion 3 件 は詳細設計前のテキスト修正で取込済、 詳細設計フェーズへ進行可)

---

## 0. 改訂対応マトリクス

### 0.-3 Round 4 → Round 5 改訂対応マトリクス

| Round 4 指摘 | 対応 |
|---|---|
| § [Critical 1] stage_gate.evaluate_stage_c 内配置で `legacy_b_result / bars_b / folds` 供給経路消失 | **`StageBCShadowContext` (新規 dataclass)** を `evaluate_stage_c` に新引数として渡す。 caller (parallel_eval / swim_lane) で context を構築 (= legacy_b_result / bars_b / folds / run_id / generation_no / individual_index 等を集約) して渡す。 § 2.2.1 で StageBCShadowContext 設計、 § 2.2.2 で wrapper signature 確定 |
| § [Critical 2] 「caller 完全不変」 と § 4.1 の caller 変更候補が矛盾 | caller 完全不変方針は **撤回**。 caller (parallel_eval / swim_lane) は **context 構築 + 1 行追加** に変更。 § 2.2 / § 4.1 で表記統一、 acceptance A1 を「既存判定経路完全不変 (= shadow_enabled=False default で fitness 不変)」 に修正 (= caller 構造の変更は許容) |
| § [Critical 3] skip event 契約と C2 矛盾 | acceptance C2 を **「shadow_enabled=True で ok/degraded/failed/skipped いずれも per genome 1 event、 shadow_enabled=False のみ 0 event」** に明確化 |
| § [Critical 4] shadow_run_summary を run 終端で emit する場所が無い | run-level summary collector を **`run_ga` / GenomeEvaluator 上位層** に配置 (= 新規 module `bc_evaluator_shadow_collector.py` で per-genome event を集約、 run 終端で `stage_bc_evaluator.shadow_run_summary` emit)。 § 2.2.3 で collector 設計、 acceptance C6 を「collector が run 終端で run_summary を emit」 に修正 |
| § [Warning] bounded recomputation 文言統一未完了 | § 2.1 docstring / § 5.2 / § 7 リスク表 全件 `uncontrolled full backtest 禁止` に統一 (= Round 5 修正で全文搜索 + 一括置換) |
| § [Warning] schema v1 に genome_serialization_version / n_genomes_attempted / skip_rate_by_reason 未反映 | § 2.3 schema v1 を全件反映: per genome event に `genome_serialization_version: 1` 追加、 shadow_run_summary に `n_genomes_attempted` + `skip_rate_by_reason` (= dict) + `failure_rate` + `degraded_rate` 追加 |
| § [Warning] 2.1a success criteria の fixture 構築確認 反映不十分 | § 1.5 success criteria に **「fixture 1 件以上で anchor_bundle / shadow_pairs を実構築できる」** を明示、 acceptance C7 (= 新設) で固定 |
| § [Warning] failed を skip_rate 分子に入れるか failure_rate と分けるか揺れ | 3 rate 分離: `skip_rate` (= shadow_skipped=True / 件数 比率) + `failure_rate` (= status=failed / 件数 比率) + `degraded_rate` (= status=degraded / 件数 比率)、 `n_genomes_attempted` を分母に統一 |
| § [Suggestion] StageBCShadowContext 最小 field | `run_id`, `generation_no`, `individual_index`, `genome`, `legacy_b_result`, `bars_b`, `bounded_recompute_mode: bool` を最小 field として § 2.2.1 で固定 |
| § [Suggestion] stage_gate.evaluate_stage_c は shadow 実行のみ、 集計は外部 aggregator | 採用、 § 2.2.3 collector で対応 |
| § [Suggestion] § 7 リスク表 古い表現残る | § 7 表全件更新 (= bounded recomputation / uncontrolled full backtest / StageBCShadowContext 最新化) |

### 0.-2 Round 3 → Round 4 改訂対応マトリクス

| Round 3 指摘 | 対応 |
|---|---|
| § [Critical 1] `_shadow_sidecar_inputs` 再利用 vs sanitize 完全不変 衝突 | shadow 配線の **配置場所を変更**: parallel_eval / swim_lane の Stage C 後 → **stage_gate.evaluate_stage_c 内、 sanitize の直前** (= step 1.8 try-finally 構造の try 末尾で実行)。 これにより `cp_result._shadow_sidecar_inputs` が non-empty な状態で bundle 構築可能、 sanitize SSOT 完全維持。 § 2.2 配線設計を全面改訂、 acceptance B5 で「sanitize 直前に shadow 走り、 sanitize 後 sidecar が空 dict」 を test 固定 |
| § [Critical 2] builder skip が無観測 | wrapper return 経路を修正、 **shadow_enabled=True で `ok / degraded / failed / skipped` 全件 1 event emit 必須** (= acceptance C2 / C5 修正)。 shadow_enabled=False のときのみ 0 event。 builder None 時も skipped event emit |
| § [Critical 3] bounded recomputation vs 「新規 backtest 絶対禁止」 矛盾 | 全文統一: 禁止対象は **`uncontrolled full backtest`** のみ、 bounded recomputation の発火条件 / 上限 / metadata / **専用検証 run 限定** を § 5.2 制約 + § 2.1 builder 設計で明文化。 通常 run では bounded recomputation 不可 |
| § [Warning] stage_c_lite_periods 「時系列均等分割」 が T064 と一致しない可能性 | acceptance C4 拡張: `stage_c_holdout_days < 180`、 端数、 営業日 / 暦日、 bar 欠損時 derive rule を明示、 1対1 対応の test fixture で fixedensure |
| § [Warning] evaluate_bc_safe outcome.result 型曖昧 | wrapper 仕様に明記: `evaluate_bc_for_a_pass` は `dict[int, BCEvaluationResult]` を返す、 wrapper では `outcome.result.get(individual_index)` で unwrap、 None 時は skipped event emit (= § 2.2 wrapper 仕様) |
| § [Warning] skip_rate 全体だけでなく per skip_reason / pair / generation 別集計 | shadow_run_summary schema 拡張: `skip_rate_total` + `skip_rate_by_reason` (= dict) + (post-hoc 分析用に skip_reason / pair / generation を per genome event に保持) |
| § [Warning] genome_serialization_version 追加 | schema v1 に `genome_serialization_version: int = 1` 追加、 sha256 の入力 source version を明示 |
| § [Suggestion] 2.1a 完了条件に「少なくとも 1 fixture で anchor_bundle / shadow_pairs 構築」 | § 1.5 step 2.1a success criteria に追記 |
| § [Suggestion] shadow_run_summary に `n_genomes_attempted` | schema v1 に `n_genomes_attempted` 追加、 観測の分母を固定 |
| § [Suggestion] § 8 進捗表を 2.1a / 2.1b に更新 | § 8 表更新 |

### 0.-1 Round 2 → Round 3 改訂対応マトリクス

| Round 2 指摘 | 対応 |
|---|---|
| § [Critical] BCEvaluationInput 構築方針が新 API 評価意味論を満たすか未証明 | step 2.1 を **2.1a (input feasibility) + 2.1b (shadow logging)** に内部分割 (= § 1.4 拡張)。 2.1a で各 input field の `source / copy_or_reference / semantic_validity / skip_reason` 対応表を作成、 構築可能性を明示検証 |
| § [Critical] 「追加 full backtest 禁止」 絶対化で shadow 偽観測リスク | 禁止対象を **`uncontrolled full backtest`** に限定。 専用検証 run 内では **`bounded recomputation`** (= 必要な per-fold backtest を bounded 回数 + 観測 metadata 付で許可) を許容。 § 5.2 制約 + § 2.1 builder 設計に明記 |
| § [Critical] builder skip 多発で n>=30 でも有効観測不足 | 2.2 exit criteria に **「`shadow_skipped=False` の有効観測 n>=30」 + 「skip_rate 上限 (例: 30%)」** を追加 (= § 1.5 exit criteria 拡張) |
| § [Critical] stage_c_lite_periods / stage_c_period derive rule が T064 確定式と一致根拠不足 | derive rule を § 5.2 で明文化、 T064 window 定義 (= synthesis § 5.3 / § 5.4) と 1対1 対応することを **acceptance に追加** (= § 5.3 acceptance C4 新設) |
| § [Warning] mission_pass_diff 単純比較は危険 | shadow event の `diffs` を **`descriptive_diff`** に明記 (= 同等性判定ではなく乖離パターン分析に限定)、 § 2.4 schema 修正 |
| § [Warning] peak_rss_delta / wall_clock_delta は run-level metric、 別 event 分離 | 2 event 分離: **`stage_bc_evaluator.shadow`** (= genome-level) + **`stage_bc_evaluator.shadow_run_summary`** (= run-level RSS / wall-clock)、 § 2.4 schema 拡張 |
| § [Warning] 通常 run shadow_enabled=True による wall-clock timeout / log I/O 間接影響 | shadow_enabled=True は **専用検証 run のみ**、 通常 run への有効化は **step 2.2 以降に限定** (= § 1.7 切替誘因ガード明示) |
| § [Warning] genome_hash SSOT 曖昧 | schema v1 に **`genome_hash` の serialization source + hash algorithm を明示固定** (= sha256(canonical_serialization(genome))、 § 2.4) |
| § [Suggestion] 2.1a feasibility / 2.1b shadow logging 分離 | § 1.4 / § 1.5 で 2.1a / 2.1b を正式に分離 |
| § [Suggestion] BCEvaluationInput 各 field の対応表 | § 2.1 builder 設計に「BCEvaluationInput 9 fields の source / copy_or_reference / semantic_validity / skip_reason 対応表」 を新設 |
| § [Suggestion] bc_summary.status = ok/degraded/failed/skipped | schema v1 に **`bc_summary.status: Literal["ok", "degraded", "failed", "skipped"]`** を追加 (= § 2.4) |

### 0.0 Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 |
|---|---|
| § 1 [Critical] case C 単独完結は North Star 進捗を生まない、 案 B 採用 + step 2.1 / 2.2 / 2.3 正式化 | **案 B 採用**。 program 名「B Phase 2 Integration Program」、 配下に 2.1 / 2.2 / 2.3 を § 1.4 で正式定義。 本設計は **step 2.1 (shadow integration LOG_ONLY) のみ**、 2.2 / 2.3 の exit criteria を § 1.5 に明記。 「Phase 2 切替コミット完了」 呼称は 2.2 完了時のみ |
| § 3 [Critical] `BCEvaluationInput` を main flow から組めるか核心前提未検証、 builder は既存成果物再利用 + 追加 full backtest 禁止 | § 2.1 builder 設計制約を「**既存成果物再利用のみ、 追加 full backtest 禁止**」 と明記。 入力は既存 backtest 結果 (= GenomeStageResult.stage_b/c の trades / equity_curve) を **adapter 経由で再利用**、 新規 backtest は cross_pair の anchor / shadow pair に限り既存 cross_pair_evaluator の結果を再利用 |
| § 4 [Critical] `(genome, individual_index)` join 契約弱 | identifier 契約強化: **`run_id + generation_no + genome_hash + individual_index`** を log SSOT。 `genome_hash` は既存 (= digest) を再利用 |
| § 5 [Critical] メモリ超過リスク主論点が「実測必須」 止まり | `shadow_enabled=True` は **default off** (= production 通常 run では off)、 **専用検証 run** で別建て、 通常 run へ載せるのは B4 (= sampled_max_worker_rss < 3 GB) 達成後。 § 4.4 / acceptance に明記 |
| § 6 [Critical] step 2 本丸 と 案 C 最小完結 が scope 自己矛盾 | scope 名称分離: 全体 program = `B Phase 2 Integration Program`、 本設計対象 = `step 2.1 shadow integration`。 「Phase 2 切替コミット」 という呼称は 2.2 完了時のみ |
| § 7 [Critical] 5-10x で 6 worker 3 GB 制約に楽観できない | acceptance B4 を **worker 数別 RSS 計測表** (= 1 / 2 / 4 / 6 workers) に拡張、 専用検証 run で実測を必須化。 § 12 メモリ実測手順に追加 |
| § 8 [Critical] `stage_c_lite_periods` / `stage_c_period` の SSOT 未確定 | § 5 制約に「**既存 config (= StageGateConfig) 再利用、 新規 field 追加禁止**」 と明記。 stage_bc_evaluator の input は既存 stage_c_holdout_days 等から builder 内で derive |
| § 1 [Warning] shadow log で切替判断証拠が弱い | shadow event `stage_bc_evaluator.shadow` に **schema version** + **必須 field 事前固定** (= § 2.4 schema 表)。 切替判定で使う観測項目を pre-register |
| § 2 [Warning] 1/10 sampling は collider bias 危険 | 1/10 sampling は撤回、 **専用検証 run** (= shadow_enabled=True で別建て、 全 genome を観測) のみ採用 |
| § 3 [Warning] parallel_eval / swim_lane 分岐重複 | shadow 配線 wrapper を **共通 helper** (= 新規 `bc_evaluator_shadow.py` に集約)、 parallel_eval / swim_lane 双方から同 wrapper を呼ぶ |
| § 4 [Warning] 観測項目 pre-register | 必須 field: `mission_pass_diff` / `b_gate_pass_diff` / `c_pass_depth` / `peak_rss_delta` / `wall_clock_delta` を schema に固定 (= § 2.4) |
| § 5 [Warning] log volume / I/O backpressure リスク未整理 | shadow event は **最小 field に絞る**、 **1 genome 1 event 上限** (= per genome 1 entry of `stage_bc_evaluator.shadow`、 § 2.4 / acceptance C2 で固定) |
| § 7 [Warning] shadow_pairs を copy で持つのは設計時点で危険 | **参照共有 / lazy materialization 原則**、 builder は既存 BarEquitySeries / TradeRecord tuple をそのまま渡す (= deep copy 禁止)、 § 2.1 制約に追記 |
| § 8 [Warning] `bc_result=None` 経路が常に走っている「可能性」 は Fact ではない | 次 round で grep + Read で Fact 確定 (= § 9 Round 2 独立検証成果として記載) |
| § 9 [Warning] T064/T065 と今回の step 2 名称対応表不足 | § 1.6 に対応表を追加 |
| § 4 [Suggestion] 同一 event に旧/新 API 要約並列 (= join より安定) | shadow event に **旧 API 要約 (= legacy_summary)** + **新 API 要約 (= bc_summary)** を並列で含める (= post-hoc join 不要、 § 2.4 schema) |
| § 5 [Suggestion] 切替不能時の rollback ではなく `2.1 継続` を正規状態として認める基準 | § 1.5 に「2.1 継続条件」 を明記 (= B4 不達成 → 2.2 移行不可、 2.1 専用検証 run で観測継続) |
| § 8 [Suggestion] 未検証項目を 2.1 exit criteria に直結 | § 1.5 で 2.1 success criteria + 2.2 exit criteria を分けて明記 |

---

## 1. 背景・課題

### 1.1 step 1.8 完了時点の状態

step 1.8 (= main commit c3ee70a) で:
- Stage A / B_IS / B_fold / C_base / C_stress / C_cross_pair の **6 系列で dual-path 観測点を確立** (= mission 必須軸 ii-lite observability 完成)
- helper / adapter 凍結、 `_PairSidecarInputs` / `_shadow_sidecar_inputs` field / sanitize 経路 (= try-finally) で multiprocessing pickle 互換 + IPC sidecar 漏洩防止 を確立

### 1.2 着手前調査 (= Verified Fact)

`zenigame-fx-codex-review` C1 Design-first 順守で grep + Read で確認:

#### (a) stage_bc_evaluator.py は実装済だが **dormant code**
- `stage_bc_evaluator.py:1-1419` 実装済 (synthesis § 5.2-5.4 / § 6.7 / § 8.3 確定式)
- 公開 API: `evaluate_stage_b` / `evaluate_stage_c_lite` / `evaluate_stage_c` / `evaluate_bc_for_a_pass` / `BCEvaluationInput` / `BCEvaluationResult` 他
- T064 PR1 docstring (= `stage_bc_evaluator.py:14-16`): 「stage_gate.py / swim_lane.py / cross_pair.py への置換は **Phase 2 (別 PR、 T065 統合と同時)** で実施」
- `BCEvaluationInput(...)` を **production code で構築する箇所は皆無** (= grep src/ で 0 件)
- `failure_handling.evaluate_bc_safe` (= wrapper) も dormant、 caller 無し

#### (b) main flow は **stage_gate.py 旧 API を呼んでいる**
- `parallel_eval.py:319` `evaluate_stage_b(...)` (= 旧 API)
- `parallel_eval.py:357` `evaluate_stage_c(..., cross_pair_evaluator=cp_evaluator, ...)` (= 旧 API、 step 1.8 拡張済)
- `swim_lane.py:635, 670` 同型
- `run_ga.py:1483` GenomeEvaluator 起動

#### (c) post-evaluation 経路は `BCEvaluationResult` を type 利用
- `loop_closure.py:74` / `nsga2_selection.py:45` / `cpps_archive.py:49` で import
- `nsga2_selection.py:123` docstring: 「`bc_result`: T064 `evaluate_bc_for_a_pass` の出力。 a_pass のみ非 None、 a_fail は」 → **GA selection は新評価結果を期待する設計**
- 現時点では caller が無く `bc_result=None` 経路が常に走っている可能性 → **Round 2 で grep + Read 確認** (= § 9 Round 2 独立検証成果)

#### (d) 新旧評価設計の根本的差異 (= step 1.8 同表 維持)
| 軸 | stage_gate.py 旧 API | stage_bc_evaluator.py 新 API |
|---|---|---|
| Stage B 評価 | 単一 IS + WF fold | per-fold rolling-origin pooled OOS (= synthesis § 5.2) |
| Stage C 評価 | base + stress + cross_pair shadow | 12w main + spread stress + cross-pair shadow + Stage C-lite (= 3 windows × 15 セル worst) |
| 入力 | `bars / meta / backtest_config / primitive_evaluator` | `BCEvaluationInput` (= 9 fields) |
| 戻り値 | `StageResult(stage="B"/"C", passed, metrics, reason_codes)` | `BCEvaluationResult(individual_index, b_result, c_lite_result, c_result, mission_pass, b_pooled_cf, pareto_axis_usable, c_pass_depth)` |
| dual-path SSOT | step 1.5-1.8 で 6 系列確立 | 未対応 (= legacy BacktestMetrics 経由しない) |

#### (e) 既存 dual-path log の継続観測可能性
- 新 API は `CanonicalFiveResult` を直接生成、 legacy `BacktestMetrics` 経由しない
- 現在の `_log_canonical_dual_path` は legacy + canonical の比較を SSOT 化
- step 2.1 (= shadow integration) では既存 dual-path log は **完全保持** (= 6 系列不変)、 新 API observation は **別 event** (= `stage_bc_evaluator.shadow`) で並列観測

### 1.3 課題 (= step 2.1 scope 限定)

- **builder の構築コスト**: 既存成果物再利用のみで `BCEvaluationInput` を組めるか
- **メモリ overhead**: shadow 配線の peak RSS が 3 GB / worker budget 内か (= 専用検証 run で実測必須)
- **observability schema**: 切替判断 (= step 2.2) に必要な観測項目を 2.1 で pre-register
- **物理隔離**: shadow 経路の例外で main flow 判定経路を絶対巻き込まない

### 1.4 B Phase 2 Integration Program の正式分割 (= 案 B 採用)

| sub-step | 名称 | scope | 完了条件 |
|---|---|---|---|
| **2.1a** | **input feasibility** (本設計対象 前半、 Round 2 [Critical] 反映で内部分割) | BCEvaluationInput 9 fields の意味論的構築可能性を明示検証、 各 field について `source / copy_or_reference / semantic_validity / skip_reason` 対応表を確立 (= § 2.1)、 builder の skeleton 実装 + skip パス確認 | 全 fields の対応表確定、 builder skeleton で skip 経路含めた基本動作 PASS、 構築不能 fields は skip_reason を pre-register |
| **2.1b** | **shadow logging** (本設計対象 後半) | builder で BCEvaluationInput 構築 → evaluate_bc_for_a_pass shadow 呼出 → schema v1 イベント emit (= LOG_ONLY)、 既存 dual-path SSOT 完全保持、 BCEvaluationResult は post-evaluation に流さない | acceptance A1-A4 + B1-B4 + C1-C5 + D1-D2 + E1-E2 全 PASS、 専用検証 run で worker 数別 RSS 計測表 (= 1/2/4/6) 確認 |
| 2.2 | switch (= 「Phase 2 切替コミット完了」 と呼ぶのはここ) | shadow 観測 data で新旧 descriptive_diff 分析 (= 乖離パターン、 collider bias 注記)、 GA Pareto 軸を `b_pooled_cf` に切替、 mission 判定を新 API で実行 | 有効観測 (= shadow_skipped=False) n>=30 かつ skip_rate <= 30%、 切替後 fitness regression が許容範囲内、 通常 run での shadow_enabled=True 安定運用確認 |
| 2.3 | deprecation | stage_gate.py 旧 evaluate_stage_b/c の deprecation marker、 dual-path SSOT の新 API 対応 (= legacy BacktestMetrics 不在経路) | 旧 API caller 0 件、 新 API SSOT が docs / archive / GA 全経路で確立 |

「**Phase 2 切替コミット完了**」 という呼称は **step 2.2 完了時にのみ** 使用 (= Round 1 [Critical] 反映)。

**本設計対象 = step 2.1 = 2.1a + 2.1b**。 2.1a は 2.1b の前提として **設計フェーズで feasibility 表を完成**、 実装フェーズで 2.1a の skeleton を先行実装し、 動作確認後に 2.1b の本体実装に進む内部段階運用とする。

### 1.5 step 2.1 success criteria + step 2.2 exit criteria の事前定義

#### step 2.1a success criteria (= input feasibility、 設計確定 + skeleton)
- C7 (= 新設、 Round 4 [Warning] 反映): **少なくとも 1 件の fixture で `anchor_bundle / shadow_pairs` を実構築完了** (= 9 fields 対応表 § 2.1 の skip_reason / semantic_validity を test 固定)
- builder skeleton で skip 経路 (= cp_result/sidecar 不在) と構築成功経路の両方が動作確認

#### step 2.1b success criteria (= shadow logging 本体)
- A1-A4: 既存判定経路完全不変 (= regression 0、 alpha_factory 全 2208 PASS 不変、 shadow_enabled=False default で fitness 不変)
- B1-B5: shadow 配線 emit + 物理隔離 + 専用検証 run でメモリ実測 (= worker 数別 RSS 表) + sanitize 順序契約 (= shadow 後 sanitize で sidecar 空)
- C1-C7: shadow event schema 確立 + identifier 契約 (= run_id + generation_no + genome_hash + individual_index) + status 区別 + run_summary + fixture 構築
- D1-D2: 例外隔離契約
- E1-E2: dormant 維持 (= bc_result が GenomeStageResult / archive に絶対漏れない)

#### step 2.2 exit criteria (= 切替を許可する条件、 Round 2 [Critical] 反映で skip_rate 上限追加)
1. **有効観測 n>=30**: shadow_enabled=True で **`shadow_skipped=False` かつ `bc_summary.status=ok`** の有効観測 N >= 30 genome
2. **invalid_observation_rate 上限** (= Round 5 [Warning] 反映で名称明確化): `invalid_observation_rate = skip_rate + failure_rate + degraded_rate <= 30%`、 各 rate の分母は `n_genomes_attempted` 統一 (= 観測 base が偽観測で歪まないため)
3. **descriptive_diff 分析**: `mission_pass_descriptive_diff` / `b_gate_pass_descriptive_diff` / `c_pass_depth 分布差` の **乖離パターン分析** (= 同等性判定ではない、 collider bias / conditioning set 明示、 Round 2 [Warning] 反映)
4. **メモリ / wall-clock**: 通常 run で `sampled_max_worker_rss < 3 GB` + step 1.7 比 ±20% 以内 (= shadow_enabled=True の通常 run 有効化が前提条件)
5. **GA Pareto 軸の整合**: `b_pooled_cf` を Pareto 軸に切替えても従来 fitness 軸 (= base sharpe / total_pnl) が retire しない (= live_criteria 整合)
6. **archive 互換**: `BCEvaluationResult` を archive Parquet schema に書き込む経路が確立

#### 2.1 継続条件 (= 2.2 移行不可時の正規状態)
- B4 (= メモリ 3 GB / worker budget) 不達成 → 2.2 移行不可、 2.1 専用検証 run で観測継続 (= 設計再考、 shadow_pairs lazy materialization 等の最適化検討)
- 観測 data n>>30 の整合不達 → 2.1 観測継続、 2.2 へ進まない

### 1.6 既存計画名称と今回 segmentation の対応表 (= Round 1 [Warning § 9] 反映)

| 既存計画 / docs 名称 | 今回 segmentation 名称 | 役割 |
|---|---|---|
| T064 PR1 (= stage_bc_evaluator 単体実装) | (完了) | 新 API 単体実装 |
| T065 (= GA selection 統合) | step 2.2 (= switch) | GA Pareto 軸を b_pooled_cf に切替 |
| Phase 2 切替コミット (= synthesis 文脈) | B Phase 2 Integration Program 全体 (2.1 + 2.2 + 2.3) | 段階分割で完結 |
| T064 PR1 docstring「Phase 2 で main flow 反映」 | step 2.1 + step 2.2 | 反映本体 |

### 1.7 切替誘因のガード (= step 2.1 採用前提)

step 2.1 完了後、 shadow 観測 data を切替判断の根拠にしないこと (= 2.2 exit criteria 達成までは停止):
- `stage_bc_evaluator.shadow` event は **descriptive observation only**
- mission 判定 (= `evaluate_stage_c.passed` / `live_criteria_pass`) には旧 API のみ使用
- shadow 経路の bc_result は **post-evaluation (= GA selection / archive) に絶対流さない** (= step 2.2 まで dormant 維持)
- collider bias 注記: shadow 経路で観測した「新 API mission_pass / 旧 API passed の差」 は専用検証 run の集計でのみ評価 (= n>>30 + conditioning set 明示)
- 通常 run では `shadow_enabled=False` (= default off、 § 4.4 / acceptance B4 反映)
- step 2.1b では shadow_enabled=True は **専用検証 run のみ** (= Round 2 [Warning] 反映、 通常 run への有効化は wall-clock timeout / log I/O 間接影響回避のため step 2.2 以降に限定)

---

## 2. 改善アイデア (= step 2.1 shadow integration、 LOG_ONLY)

### 2.1 builder: main flow 入力 → BCEvaluationInput 変換 (= 2.1a feasibility 表)

#### BCEvaluationInput 9 fields の意味論的構築可能性 (= Round 2 [Critical] / [Suggestion] 反映)

| field | source (= 旧 API 経路の何から構築するか) | copy_or_reference | semantic_validity | skip_reason (= 構築不能時) |
|---|---|---|---|---|
| `individual_index` | caller (= GenomeEvaluator) が連番付与 | (新規) | OK (= identifier 用、 意味論なし) | n/a |
| `trades` | 既存 evaluate_stage_b 内 `run_backtest(bars_b)` の `BacktestResult.trades` を **adapter 経由で TradeRecord に変換** | reference (= adapter は既存 trade を deep copy せず変換) | OK (= step 1 で確立済の adapter pattern) | `b_result_trades_unavailable` (= legacy_b_result.passed=False の payload に trades 不在) |
| `bars` | 既存 evaluate_stage_b 内の equity_curve を **adapter 経由で BarEquitySeries に変換** | reference | OK (= step 1 で確立済) | `b_result_equity_curve_unavailable` |
| `business_day_universe` | bars_b から `compute_business_day_universe_from_bars` (= step 1 helper) | (新規 dict) | OK (= step 1 で確立済) | `bars_b_unavailable` |
| `folds` | 既存 `make_wf_folds(bars_b, ...)` の出力 (= step 1.6 で再利用済) を T060 `Fold` tuple に変換 | reference (= 既存 fold tuple をそのまま) | OK (= 既存 stage 1.6 と同型) | `folds_construction_failed` |
| `stage_c_lite_periods` | **既存 stage_c_holdout_days から derive** (= synthesis § 5.3 確定式の 3 windows × 60d / 60d / 60d を holdout_days 内で時系列分割) | (新規 tuple) | **2.1a feasibility 検証必要** (= synthesis § 5.3 と 1対1 対応の derive rule、 acceptance C4 で固定) | `stage_c_lite_window_split_failed` |
| `stage_c_period` | **既存 stage_c_holdout_days から derive** (= holdout 全体を 1 period として T060 Period に変換) | (新規) | OK (= 既存 holdout と完全一致) | `stage_c_period_construction_failed` |
| `anchor_bundle` | 既存 cross_pair_evaluator 内 anchor pair backtest 結果 (= step 1.8 で sidecar 保持) を `PairBacktestBundle` に変換 | **reference (= step 1.8 _shadow_sidecar_inputs を再利用)** | OK (= step 1.8 で per-pair sidecar 確立済) | `anchor_pair_sidecar_unavailable` (= cross_pair が走っていない / pair_failure) |
| `shadow_pairs` | 同上、 anchor 以外の per-pair sidecar を `dict[str, PairBacktestBundle]` に変換 | reference (= 参照共有 + lazy materialization、 deep copy 禁止) | OK (= step 1.8 で多 pair sidecar 確立) | `shadow_pair_sidecar_unavailable` |

**設計判断 (= Round 2 [Critical 1, 2, 4] 反映)**:
1. **追加 full backtest 禁止 → uncontrolled full backtest 禁止に修正**: 通常運用での無制御な再 backtest は禁止。 ただし **専用検証 run** 内では **bounded recomputation** (= 必要な per-fold backtest を bounded 回数で許可、 観測 metadata 付き) を許容。 step 2.1b 通常 run では既存成果物再利用のみ
2. **意味論妥当性検証**: 各 field が「stage_bc_evaluator が確定式 (synthesis § 5.2-5.4) を観測する」 ための input として意味的に正しいかを 2.1a で feasibility 表で固定
3. **skip 経路の明示**: 構築不能時は `skip_reason` を `bc_summary.status="skipped"` で記録、 偽観測を排除 (= acceptance C5 / Round 2 [Critical 3])
4. **stage_c_lite_periods derive rule**: synthesis § 5.3 の「3 windows × 60d」 を `stage_c_holdout_days` 内で **時系列均等分割** (= 例: 180d holdout → 60d × 3 windows) で構築。 derive rule は § 5.3 acceptance C4 で T064 window 定義との 1対1 対応を固定検証

#### builder 関数 (= bc_evaluator_shadow.py 内)

**配置先**: 新規 module `src/alpha_factory/bc_evaluator_shadow.py` に集約 (= Round 1 [Warning § 3] 反映、 parallel_eval / swim_lane 分岐重複防止)

```python
# bc_evaluator_shadow.py に集約
def build_bc_evaluation_input_from_legacy(
    *,
    individual_index: int,
    genome: Genome,
    legacy_b_result: StageResult,        # 既存 evaluate_stage_b 結果 (= 再利用)
    legacy_c_result: StageResult,        # 既存 evaluate_stage_c 結果 (= 再利用)
    bars_b: list[PriceBar],
    bars_holdout: list[PriceBar],
    cp_inputs: CrossPairLaneInputs | None,
    stage_gate_cfg: StageGateConfig,
) -> BCEvaluationInput | None:
    """既存成果物 (= legacy_b/c_result の payload に含まれる trades / equity_curve)
    から BCEvaluationInput を構築する。

    制約 (Round 1 [Critical § 3] 反映):
    - **既存成果物再利用のみ、 `uncontrolled full backtest` 禁止** (= Round 5 文言統一)
    - **shadow_pairs は cp_inputs から参照共有、 lazy materialization 原則**
    - 構築不能時 (= 必須 input 不在) は None 返り (shadow skip)
    """
    ...
```

**設計判断**:
- 新規 backtest は **絶対走らせない** (= 既存 evaluate_stage_b/c の trades / equity_curve を adapter 経由で TradeRecord / BarEquitySeries に変換するのみ)
- shadow_pairs 構築は cp_inputs.pair_bars_map から **参照共有** (= deep copy 禁止)
- folds は make_wf_folds の既存出力を T060 Fold tuple に変換するだけ
- stage_c_lite_periods / stage_c_period は **既存 config (= stage_c_holdout_days 等) から derive** (= 新規 config 追加禁止、 Round 1 [Critical § 8] 反映)

### 2.2 shadow 配線: stage_gate.evaluate_stage_c 内 sanitize 直前 + StageBCShadowContext + collector (= Round 3 [Critical 1] + Round 4 [Critical 1-4] 反映)

#### 2.2.1 StageBCShadowContext (= 新規 dataclass、 caller から artifacts を渡す)

```python
# bc_evaluator_shadow.py
@dataclass(frozen=True)
class StageBCShadowContext:
    """step 2.1 shadow 配線用の context (= caller から artifacts を渡す).

    Round 4 [Critical 1] 反映: stage_gate.evaluate_stage_c 単独では Stage B 側の
    artifacts (= legacy_b_result / bars_b / folds) を持てないため、 caller
    (parallel_eval / swim_lane) で集約した context を `evaluate_stage_c` に渡す。

    field:
        run_id: run 識別子 (= shadow event identifier 必須)
        generation_no: GA 世代番号
        individual_index: 個体 index (= GenomeEvaluator が連番付与)
        genome: 評価対象 Genome (= genome_hash 生成 + builder 入力 SSOT、
            Round 5 [Warning] 反映)
        legacy_b_result: 既存 evaluate_stage_b 結果 (= trades / equity_curve source)
        bars_b: Stage B 評価窓 bars (= folds / business_day_universe source、
            tuple 化推奨で参照安全性向上、 Round 5 [Suggestion] 反映)
        bounded_recompute_mode: 専用検証 run のみ True (= bounded recomputation 許可)、
            通常 run は False (= uncontrolled full backtest 禁止維持)
    """
    run_id: str
    generation_no: int
    individual_index: int
    genome: Genome  # Round 5 [Warning] 反映で必須 field 追加
    legacy_b_result: StageResult  # 既存 stage_gate.StageResult
    bars_b: tuple[PriceBar, ...]  # Round 5 [Suggestion] 反映で tuple 化
    bounded_recompute_mode: bool = False
```

#### 2.2.2 wrapper signature の確定 (= Round 4 [Warning] 反映で型明記)

```python
# bc_evaluator_shadow.py
def evaluate_stage_bc_shadow_safe(
    *,
    shadow_context: StageBCShadowContext,  # caller から渡す
    cp_result_with_sidecar: CrossPairResult | None,  # sanitize 前 cp_result
    cross_pair_payload: dict,                          # 旧 API 要約 source
    stage_c_payload_legacy: dict,                      # legacy stage_c payload (= live_criteria_pass / stress 等)
    bars_holdout: list[PriceBar],
    stage_config: StageGateConfig,
    event_collector: BCShadowEventCollector | None = None,  # run-level 集約 (= None 時は emit のみ)
) -> None:
    """shadow 配線 wrapper. shadow_enabled=True で ok/degraded/failed/skipped 全件
    1 event emit、 shadow_enabled=False で 0 event (= acceptance C2)."""
```

#### 2.2.3 BCShadowEventCollector (= 新規 module、 run-level 集約)

```python
# bc_evaluator_shadow_collector.py
class BCShadowEventCollector:
    """per-genome event を集約し、 run 終端で shadow_run_summary を emit する.

    Round 4 [Critical 4] 反映: stage_gate.py 内では run-level 集計を出せない (=
    生存期間が genome 単位) ため、 run_ga / GenomeEvaluator 上位層に配置する.
    """
    def __init__(self, run_id: str) -> None: ...
    def record_event(self, event_payload: dict) -> None:
        """per-genome event 受け取り (= status / skip_reason / RSS 等を集計)."""
        ...
    def emit_run_summary(self, *, sampled_max_worker_rss: int | None,
                        wall_clock_total: float) -> None:
        """run 終端で stage_bc_evaluator.shadow_run_summary を emit:

        - n_genomes_attempted: shadow_enabled=True で wrapper が呼ばれた件数
        - n_genomes_observed_ok / degraded / failed / skipped: status 別件数
        - skip_rate / failure_rate / degraded_rate: それぞれ /n_attempted
        - skip_rate_by_reason: dict[reason, rate]
        - sampled_max_worker_rss_bytes / process_tree_peak_rss_max_bytes
        - wall_clock_total_seconds
        """
        ...
```

#### 2.2.4 stage_gate.evaluate_stage_c 内の配線

```python
# stage_gate.evaluate_stage_c 内 (= step 1.8 try-finally 末尾)
def evaluate_stage_c(
    ...,
    *,
    cross_pair_evaluator: CrossPairEvaluator | None = None,
    cross_pair_inputs: Mapping[str, object] | None = None,
    bc_shadow_context: StageBCShadowContext | None = None,  # Round 5 新規
    bc_shadow_collector: BCShadowEventCollector | None = None,
) -> StageResult:
    try:
        # ... step 1.8 dual-path 配線 (= 既存、 完全不変) ...

        # === step 2.1 shadow 配線 (= sanitize 直前、 sidecar 利用可能) ===
        if (
            stage_config.phase2_bc_evaluator_shadow_enabled
            and bc_shadow_context is not None
        ):
            evaluate_stage_bc_shadow_safe(
                shadow_context=bc_shadow_context,
                cp_result_with_sidecar=cp_result_local,
                cross_pair_payload=cross_pair_payload,
                stage_c_payload_legacy=metrics_envelope_payload,
                bars_holdout=bars_holdout,
                stage_config=stage_config,
                event_collector=bc_shadow_collector,
            )
    finally:
        # === step 1.8 sanitize 経路 (= 完全不変) ===
        ...
```

#### 2.2.5 caller (parallel_eval / swim_lane) の変更 (= Round 5 で caller 完全不変方針撤回)

```python
# parallel_eval._evaluate_genome_steps 内
# (= 既存 evaluate_stage_c の呼出を 1 行修正)
if stage_gate_cfg.phase2_bc_evaluator_shadow_enabled:
    bc_shadow_context = StageBCShadowContext(
        run_id=ctx.run_id, generation_no=ctx.generation_no,
        individual_index=ctx.individual_index,
        legacy_b_result=b_result,  # 既存 evaluate_stage_b 結果
        bars_b=list(ctx.bars_b),
        bounded_recompute_mode=ctx.bounded_recompute_mode,  # 通常 run False
    )
else:
    bc_shadow_context = None

c_result = evaluate_stage_c(
    genome, list(ctx.bars_holdout), ctx.meta, ctx.bt_cfg, ev_c, stage_gate_cfg,
    cross_pair_evaluator=cp_evaluator,
    cross_pair_inputs=cp_inputs_dict,
    bc_shadow_context=bc_shadow_context,
    bc_shadow_collector=ctx.bc_shadow_collector,  # GenomeEvaluator が保持
)
```

#### 設計判断
- `StageBCShadowContext` で Stage B artifacts を caller から渡す (= Round 4 [Critical 1] 解消)
- caller は `bc_shadow_context` 構築 + 既存 `evaluate_stage_c` 呼出に 2 引数追加 のみ (= 完全不変ではないが最小変更)
- `BCShadowEventCollector` を `GenomeEvaluator` (= run_ga 上位層) で保持、 run 終端で summary emit (= Round 4 [Critical 4] 解消)
- shadow_enabled=False は context 構築不要 (= overhead 0)
- step 1.8 sanitize SSOT は **完全維持** (= shadow 配線後 finally で sidecar 空 dict 化)
- `failure_handling.evaluate_bc_safe` で degraded / failed handling、 wrapper return path で全 4 status (= ok/degraded/failed/skipped) で 1 event emit 必須

### 2.3 shadow event schema の事前固定 (= Round 1 [Warning § 4] + Round 2 [Warning] / [Suggestion] 反映)

#### Event 1: `stage_bc_evaluator.shadow` (= genome-level)

per genome 1 entry、 schema v1:

```python
{
    "schema_version": 1,
    # === identifier 契約 (Round 1 [Critical § 4] + Round 2 [Warning] 反映) ===
    "run_id": "<run_id>",
    "generation_no": int,
    # genome_hash の SSOT 固定 (= Round 2 [Warning]):
    # serialization source = canonical_serialization(genome) (= JSON-stable repr)
    # algorithm = sha256
    "genome_hash": "<sha256_hex>",
    # Round 4 [Warning] 反映: serialization source の version 明示
    "genome_serialization_version": 1,
    "individual_index": int,
    # === 旧 API 要約 (= Round 1 [Suggestion § 4] 反映、 同一 event に並列) ===
    "legacy_summary": {
        "b_passed": bool,
        "c_passed": bool,
        "c_live_criteria_pass": bool,
        "c_stress_pass": bool,
        "c_cross_pair_pass": bool,
    },
    # === 新 API 要約 + status (= Round 2 [Suggestion] 反映で status 追加) ===
    "bc_summary": {
        # status: degraded を ok と区別、 偽観測排除のため必須
        "status": Literal["ok", "degraded", "failed", "skipped"],
        "mission_pass": str | None,        # status=ok のみ非 None
        "b_gate_pass": bool | None,
        "c_pass_depth": float | None,      # [0.0, 1.75]
        "c_lite_mission_pass": str | None,
        "c_lite_n_pass_windows": int | None,
        "c_stress_pass": str | None,
        "c_cross_pair_pass": str | None,
    },
    # === descriptive_diff (= Round 2 [Warning] 反映、 同等性判定ではなく乖離パターン分析用) ===
    "diffs": {
        # descriptive_ prefix で同等性判定ではないことを明示
        "mission_pass_descriptive_diff": str,  # "agree" / "legacy_only_pass" / "bc_only_pass" / "both_fail" / "n/a"
        "b_gate_pass_descriptive_diff": str,
        "interpretation_note": "descriptive_observation_only_no_equivalence_claim",
    },
    # === 観測 metadata ===
    "shadow_skipped": bool,            # builder None / shadow_enabled=False で True
    "shadow_skip_reason": str | None,  # "config_disabled" / "<field>_unavailable" / None (= feasibility 表参照)
    "interpretation_note": "shadow_observation_only_phase2.1",
}
```

#### Event 2: `stage_bc_evaluator.shadow_run_summary` (= run-level、 Round 2 [Warning] 反映で分離)

per run 1 entry (= run 終端で emit)、 schema v1:

```python
{
    "schema_version": 1,
    "run_id": "<run_id>",
    "shadow_enabled": bool,
    # === per-status counts + 分母 (= Round 4 [Suggestion] 反映で attempted 追加) ===
    "n_genomes_attempted": int,        # shadow_enabled=True で wrapper が呼ばれた件数 (= 分母 SSOT)
    "n_genomes_observed_ok": int,      # status=ok
    "n_genomes_skipped": int,          # status=skipped
    "n_genomes_failed": int,           # status=failed
    "n_genomes_degraded": int,         # status=degraded
    # === 3 rate 分離 (= Round 4 [Warning] 反映、 分母は n_genomes_attempted) ===
    "skip_rate": float,                # n_skipped / n_attempted
    "failure_rate": float,             # n_failed / n_attempted
    "degraded_rate": float,            # n_degraded / n_attempted
    "skip_rate_by_reason": dict,       # {reason: rate} per skip_reason
    # === 観測 metadata ===
    "process_tree_peak_rss_max_bytes": int | None,
    "sampled_max_worker_rss_bytes": int | None,  # psutil sampling SSOT (= step 1.8)
    "wall_clock_total_seconds": float,
    "wall_clock_overhead_vs_baseline": float | None,  # baseline 不在で None
    "interpretation_note": "shadow_run_summary_for_step2.2_exit_criteria",
}
```

#### 設計判断
- schema version 1 を明示 (= 後続 step で拡張可能)
- 旧 API 要約 + 新 API 要約を **同一 event に並列** (= post-hoc join 不要、 解釈安定)
- descriptive_ prefix で「同等性判定ではない」 ことを field 名で明示 (= Round 2 [Warning] 反映、 collider bias 抑止)
- bc_summary.status (= ok/degraded/failed/skipped) で degraded を ok と区別、 偽観測排除
- 1 genome 1 entry の上限 (= acceptance C2)
- run-level metric (= RSS / wall-clock) は別 event に分離 (= Round 2 [Warning] 反映、 genome-level event 肥大化防止)

### 2.4 stage_label / 識別子契約 SSOT 拡張 (= 案 B step 2.1 採用前提)

step 1.5-1.8 で確立した dual-path log SSOT は **完全不変** (= 6 系列維持、 acceptance A2)。 shadow 配線は別 event 名前空間:

| event name | 出所 | step | identifier 契約 |
|---|---|---|---|
| `stage_gate.canonical_five.dual_path` | `_log_canonical_dual_path` (step 1-1.8) | step 1-1.8 | (stage, genome) + 必要に応じ fold / pair |
| `stage_gate.canonical_five.skipped` | `_try_evaluate_canonical_five_safe` | step 1-1.8 | (stage, genome) |
| **`stage_bc_evaluator.shadow`** | bc_evaluator_shadow.py 共通 wrapper (= genome-level) | **step 2.1b** | **(run_id, generation_no, genome_hash, individual_index)** |
| **`stage_bc_evaluator.shadow_run_summary`** | run 終端 emit (= run-level RSS / wall-clock) | **step 2.1b** | **(run_id)** |
| `stage_bc_evaluator.shadow_failure` | shadow 例外 | step 2.1b | (run_id, generation_no, genome_hash, individual_index) |

### 2.5 step 1.5-1.8 で確立した sanitize 経路 / `_shadow_sidecar_inputs` の整合

shadow 配線で:
- 既存 `cross_pair_payload["result"]._shadow_sidecar_inputs` の sanitize 経路 (= step 1.8 try-finally) **完全不変**
- shadow 経路は別 evaluator (= stage_bc_evaluator) を別 event で起動、 既存 sidecar 経路は通らない
- → step 1.8 sanitize SSOT は破壊せず、 別 evaluator 経路として併存

---

## 3. 期待効果 (= step 2.1 採用前提、 descriptive observation only)

### 3.1 直接的 (= shadow 観測のみ)

- main flow が新 API (= `stage_bc_evaluator`) を **shadow で呼出可能** に (= production caller 0 件 → 1 件、 dormant code 解消)
- step 1.5-1.8 の dual-path log SSOT (= 6 + n_fold entries / genome) を **完全保持** したまま、 新 API 出力 (= `BCEvaluationResult`) を観測可能
- 旧 / 新 API 要約を同一 event に並列出力、 切替判断 (= step 2.2 exit criteria) のための constituent data を集約

### 3.2 間接的 (= step 2.2 切替前提条件)

- `BCEvaluationInput` 構築経路の確立 (= 切替時に新 API caller がそのまま使える)
- shadow 観測 data の蓄積 (= 切替判断 n>>30 に必要)
- 共通 wrapper `bc_evaluator_shadow.py` 確立 (= 2.2 で本配線に再利用可能)

### 3.3 live_criteria 達成への寄与

- **直接寄与**: なし (= shadow only、 判定ロジック完全不変、 GA fitness 不変、 acceptance A1-A4)
- **間接寄与**: 中 (= 新 API observability の確立、 切替判断 data の蓄積、 ただし「使う」 のは step 2.2 以降)

---

## 4. 実装方針 (= step 2.1 shadow integration)

### 4.1 変更ファイル候補

1. `src/alpha_factory/bc_evaluator_shadow.py` (= 新規 module、 Round 1 [Warning § 3] 反映で集約):
   - `StageBCShadowContext` (= dataclass、 § 2.2.1)
   - `build_bc_evaluation_input_from_sidecar` (= builder、 § 2.1)
   - `evaluate_stage_bc_shadow_safe` (= shadow wrapper、 LOG_ONLY、 § 2.2.2)
   - `_log_bc_evaluator_shadow` (= shadow event emit、 schema v1 SSOT)
2. `src/alpha_factory/bc_evaluator_shadow_collector.py` (= 新規 module、 Round 4 [Critical 4] 反映):
   - `BCShadowEventCollector` クラス (= run-level 集約、 run 終端で `stage_bc_evaluator.shadow_run_summary` emit、 § 2.2.3)
3. `src/alpha_factory/stage_gate.py`:
   - `StageGateConfig` に `phase2_bc_evaluator_shadow_enabled: bool = False` field 追加 (= default off)
   - `evaluate_stage_c` に新引数 `bc_shadow_context: StageBCShadowContext | None = None` + `bc_shadow_collector: BCShadowEventCollector | None = None` 追加
   - try-finally の try 末尾に shadow 配線 1 ブロック追加 (= sanitize 直前、 § 2.2.4)
4. `src/alpha_factory/parallel_eval.py` (= Round 5 [Warning] 反映で 「Stage C 後 1 行」 から訂正):
   - `_evaluate_genome_steps` で `StageBCShadowContext` 構築 + `evaluate_stage_c` の呼出に `bc_shadow_context / bc_shadow_collector` 引数を追加 (= § 2.2.5)
   - `GenomeEvaluator` に `BCShadowEventCollector` を保持、 run 終端で `emit_run_summary` を呼ぶ
5. `src/alpha_factory/swim_lane.py`:
   - 同型修正 (= `evaluate_stage_c` 呼出に bc_shadow_context / bc_shadow_collector 引数追加、 LaneManager に collector 保持)
6. `src/alpha_factory/run_ga.py` (= caller 上位層):
   - `BCShadowEventCollector` instantiation + GenomeEvaluator / LaneManager に注入、 run 終端で `emit_run_summary`
7. テスト追加:
   - `tests/alpha_factory/test_bc_evaluator_shadow.py` (= builder + wrapper + StageBCShadowContext + log emit 単体)
   - `tests/alpha_factory/test_bc_evaluator_shadow_collector.py` (= collector の record_event + emit_run_summary 単体)
   - `tests/alpha_factory/test_parallel_eval_bc_shadow.py` (= caller integration、 既存 main flow 不変確認、 sanitize 順序契約)
8. ドキュメント更新候補: `docs/alpha_factory/stage-gates.md` (= step 2.1 shadow integration SSOT 追記)

### 4.2 影響範囲

- main flow 計算量 +1 evaluate_bc_safe call / genome (= shadow_enabled=True のとき)
- shadow_enabled=False (= default、 通常 run) では overhead 0
- archive Parquet schema 不変 (= shadow log のみ、 BCEvaluationResult は post-evaluation に流さない)
- helper / adapter 凍結 (= step 1-1.8 helper 改変なし)
- main flow shadow_enabled=False で既存 2208 PASS 完全不変 (= regression 0)

### 4.3 LOG_ONLY 維持

step 2.1 では LOG_ONLY 維持 (= shadow 配線のみ、 既存判定経路完全不変)。 切替は step 2.2、 deprecation は step 2.3。

### 4.4 メモリ概算 (= acceptance B4 worker 数別、 専用検証 run で実測必須)

shadow 配線で `BCEvaluationInput` を構築 (= 既存成果物の **参照共有**) → `evaluate_bc_for_a_pass` で per-fold canonical 計算が走る:
- `BCEvaluationInput.trades` / `bars`: 既存 stage_b/c 結果の参照 (= 追加 deep copy なし)
- `shadow_pairs`: cp_inputs.pair_bars_map の参照 (= 同)
- per-fold canonical: stage_bc_evaluator が canonical_metrics を直接計算 → 評価窓内の sharpe / pnl / dd 算出 cost
- 6 worker 並列 worst case: **概算 + 50-150 MB / 全体 vs step 1.8** (= 参照共有なので copy overhead 無し、 計算 overhead のみ)

実測判断 (= acceptance B4):
- shadow_enabled=True で **専用検証 run** を 1 / 2 / 4 / 6 workers で実行
- 各 worker 数で `sampled_max_worker_rss` を計測
- 6 workers で `sampled_max_worker_rss < 3 GB` を確認 (= step 1.7 baseline 比 step 1.8 ±20% 以内 = step 2.1 でも維持)
- **shadow_enabled=True を通常 run に default on にするのは B4 達成後** (= step 2.2 exit criteria の一部)

### 4.5 stage_label 命名 (= step 2.1 採用前提)

dual-path log SSOT は不変 (= step 1-1.8 の 6 系列維持)。 shadow 配線は別 event 名前空間 (= § 2.4 表)。

---

## 5. 制約・前提

### 5.1 前提表 (= 4 段階分解、 step 1.8 と同型)

| 前提 | 状態 | 検証方法 / Out-of-scope 理由 |
|---|---|---|
| **(a) Verified** | | |
| stage_bc_evaluator.py は実装済 (1419 行)、 production caller 無し (= dormant code) | **Verified** | grep 確認 (= § 1.2 (a)) |
| main flow (parallel_eval / swim_lane) は stage_gate.py 旧 API を呼ぶ | **Verified** | grep 確認 (= § 1.2 (b)) |
| failure_handling.evaluate_bc_safe wrapper も dormant | **Verified** | grep 確認 |
| step 1.5-1.8 の dual-path SSOT (= 6 entries / genome) は stage_gate.py 経路で確立 | **Verified** | step 1.8 main commit c3ee70a で固定 |
| **(b) Inferred — step 2.1 で実証検証必要** | | |
| `BCEvaluationInput` を main flow 入力から **既存成果物再利用のみ** で構築可能 (= 通常 run、 専用検証 run では bounded recomputation 許可) | **To Verify in 2.1a** | builder 実装 + test (= acceptance C1 / C7)、 `uncontrolled full backtest` 禁止制約に基づく構築可能性、 9 fields 対応表の semantic_validity 検証 |
| shadow 配線で既存 dual-path log SSOT が完全不変 | **To Verify in 2.1** | acceptance A1-A4 で deep equality 比較固定 |
| shadow 配線のメモリ overhead が 3 GB / worker budget 内 (worker 数別) | **To Verify in 2.1** | acceptance B4 専用検証 run で実測 (= 1 / 2 / 4 / 6 workers) |
| **(c) Unverified — step 2.1 で検証** | | |
| `BCEvaluationInput.shadow_pairs` の参照共有で deep copy overhead 無し | **To Verify** | builder 実装で deep copy 禁止契約 + test |
| stage_c_lite_periods / stage_c_period の derive (= 既存 config から) で適合 | **To Verify** | builder 実装で既存 stage_c_holdout_days からの自動 derive |
| **(d) False / Out-of-scope — step 2.1 では達成しない** | | |
| 新 API への切替 (= 旧 API deprecation) | **Out-of-scope** | step 2.2 / 2.3 で対応 |
| GA Pareto 軸の b_pooled_cf 切替 (= T065 統合) | **Out-of-scope** | step 2.2 |
| 新 API mission_pass を mission 判定に使用 | **Out-of-scope** | step 2.2 |
| BCEvaluationResult を archive Parquet schema に書き込む経路 | **Out-of-scope** | step 2.2 / 2.3 |

### 5.2 制約

- helper / adapter 凍結 (= step 1-1.8 で確立、 改変なし)
- `_log_canonical_dual_path` シグネチャ完全不変 (= step 1.8 で確立)
- `stage_gate.evaluate_stage_b` / `evaluate_stage_c` 完全不変 (= 旧 API 経路維持、 acceptance A1)
- main flow の判定結果 (= passed / reason_codes / fitness) 完全不変 (= regression 0、 acceptance A4)
- BCEvaluationResult は post-evaluation に流さない (= dormant 維持、 acceptance C 整合)
- live_criteria 不変
- **`uncontrolled full backtest` 禁止** (= 通常 run では builder は既存成果物再利用のみ、 Round 1 [Critical § 3] + Round 3 [Critical 3] 反映で文言統一)
- **`bounded recomputation` 専用検証 run 限定** (= shadow_enabled=True かつ専用検証 run でのみ許可、 通常 run では発火不可、 発火条件 / 上限 / metadata は § 2.1 builder 設計で pre-register)
- **shadow_pairs deep copy 禁止** (= 参照共有 + lazy materialization、 Round 1 [Warning § 7] 反映)
- **既存 config 再利用** (= 新規 stage_c_lite_periods / stage_c_period field 追加禁止、 Round 1 [Critical § 8] 反映)
- **shadow_enabled=False default** (= 通常 run では off、 Round 1 [Critical § 5] 反映)

### 5.3 Acceptance Criteria

**A. 判定結果回帰 0 (必須、 deep dict comparison)**
- [A1] alpha_factory 全 2208 PASS 不変 (= regression 0、 既存 test 全件)
- [A2] dual-path log SSOT (= step 1.5-1.8 の 6 + n_fold entries / genome) 完全不変
- [A3] sanitize 経路 / `_shadow_sidecar_inputs` field / `_PairSidecarInputs` の挙動完全不変
- [A4] GA fitness 不変 (= shadow_enabled=False default で fitness 値が変化しない、 shadow_enabled=True でも main flow 経路は不変)

**B. shadow 配線確認**
- [B1] `phase2_bc_evaluator_shadow_enabled=True` で `stage_bc_evaluator.shadow` event が emit される (= per genome 1 entry、 schema v1 準拠、 ok/degraded/failed/skipped 全件)
- [B2] shadow_enabled=False (= default) で event が emit されない (= regression 0 default、 0 event)
- [B3] shadow 経路の例外で main flow が止まらない (= 物理隔離、 二重 try、 acceptance D1-D2)
- [B4] **専用検証 run** (= shadow_enabled=True、 1 / 2 / 4 / 6 workers) で `sampled_max_worker_rss < 3 GB` (= worker 数別計測表で実測、 step 1.7 baseline 比 ±20% 以内)
- [B5] **shadow 配線の sanitize 順序契約** (= Round 3 [Critical 1] 反映): shadow 配線が stage_gate.evaluate_stage_c 内 sanitize 直前 (= try 末尾) で走る、 sanitize 後 `cp_result._shadow_sidecar_inputs == {}` を test 固定。 shadow が走った後でも sanitize は完全実行される (= step 1.8 SSOT 維持)

**C. shadow 観測 data**
- [C1] schema v1 必須 field 全件 (= identifier 4 軸 + legacy_summary + bc_summary + descriptive_diffs + 観測 metadata) が log に出力
- [C2] **shadow_enabled=True で ok/degraded/failed/skipped いずれも per genome 1 event emit** (= Round 4 [Critical 3] 反映、 偽観測排除)、 **shadow_enabled=False のみ 0 event** (= regression 0 default)。 `bc_shadow_context is None` (= caller 構築失敗) のとき `status=skipped, skip_reason="context_missing"` で必ず emit (= Round 5 [Warning] 反映で context missing 経路も観測)
- [C3] identifier 契約: **`run_id + generation_no + genome_hash + individual_index`** で `(genome, run, generation)` 横断 join 可能、 `genome_hash = sha256(canonical_serialization(genome))` SSOT 固定 (= Round 2 [Warning] 反映)
- [C4] **stage_c_lite_periods derive rule の T064 一致** (= Round 2 [Critical 4] 反映): builder の derive rule が synthesis § 5.3 の「3 windows × 60d」 と 1対1 対応することを test で固定 (= 既存 stage_c_holdout_days からの分割が T064 window 定義と一致)
- [C5] **bc_summary.status 区別** (= Round 2 [Suggestion] 反映): builder skip / evaluate_bc_safe degraded / 例外 / 正常 の 4 ケースで status field が `ok/degraded/failed/skipped` 区別される、 deep equality test
- [C6] **run-level shadow_run_summary**: `BCShadowEventCollector` (= 上位層 GenomeEvaluator が保持) が run 終端で `stage_bc_evaluator.shadow_run_summary` event を emit (= shadow_enabled=True かつ ≥ 1 genome 観測時)、 schema v1 必須 field (= n_genomes_attempted + n_genomes_observed_ok/skipped/failed/degraded + skip_rate / failure_rate / degraded_rate + skip_rate_by_reason + RSS / wall_clock) 全件出力。 Round 4 [Critical 4] 反映で配置を上位層に移動
- [C7] **2.1a fixture 構築**: 少なくとも 1 件の test fixture (= 旧 API stage_b/c 経由の sidecar が存在する状態) で `anchor_bundle / shadow_pairs` を構築完了し、 `BCEvaluationInput` の 9 fields 全件が valid (= 9 fields 対応表の semantic_validity 列が OK / 構築不能 fields は skip_reason 明示) を test 固定 (= Round 4 [Warning] 反映)

**D. 例外隔離契約**
- [D1] shadow 経路で例外発生しても main flow の `StageResult` 完全不変
- [D2] shadow 経路の例外は `stage_bc_evaluator.shadow_failure` WARN log のみ (= 既存 stage_c.cross_pair_failure 等を絶対 touch しない)

**E. dormant 維持契約**
- [E1] BCEvaluationResult が `GenomeStageResult` に絶対流れない (= deep snapshot 比較で固定)
- [E2] BCEvaluationResult が archive Parquet schema に絶対流れない (= 同)

---

## 6. スコープ外 (= step 2.1 採用前提)

1. **新 API への切替** (= 旧 evaluate_stage_b/c → 新 evaluate_stage_b/c_lite/c): step 2.2
2. **GA Pareto 軸の b_pooled_cf 切替** (= T065 統合): step 2.2
3. **mission 判定の新 API 採用**: step 2.2
4. **dual-path SSOT の新 API 対応**: step 2.3 (= legacy BacktestMetrics 不在経路への対応)
5. **archive Parquet schema 拡張**: step 2.2 / 2.3 (= BCEvaluationResult 永続化)
6. **stage_gate.py 旧 API の deprecation**: step 2.3
7. **shadow_enabled の通常 run default on**: step 2.2 exit criteria 達成後

---

## 7. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| shadow 経路の例外で main flow を巻き込む | 高 | step 1.5-1.8 同型 物理隔離 (= 二重 try、 default off flag、 acceptance D1-D2)、 `failure_handling.evaluate_bc_safe` を isolation boundary に再利用 |
| shadow 配線で peak RSS が 3 GB / worker budget 超過 | 高 | acceptance B4 で worker 数別 (1 / 2 / 4 / 6) 専用検証 run 実測、 default off で通常 run には影響しない、 超過時は 2.2 移行不可 → 2.1 継続 (= § 1.5 継続条件) |
| `BCEvaluationInput` 構築コストが per-genome で大きく overhead 過大 | 中 | builder 設計制約「**`uncontrolled full backtest` 禁止 + 通常 run 既存成果物再利用のみ**」 + shadow_pairs 参照共有、 構築不能時は skipped event emit (= shadow skip)、 専用検証 run 内では bounded recomputation 許可 (= Round 5 文言統一) |
| dual-path SSOT (= step 1.5-1.8 の 6 系列) が shadow 配線追加で意図せず変化 | 高 | acceptance A2 で deep equality 比較固定、 別 event 名前空間 (= `stage_bc_evaluator.shadow` は `stage_gate.canonical_five.*` と完全分離) |
| shadow 経路の `BCEvaluationResult` が post-evaluation に意図せず流れる | 高 | acceptance E1-E2 で deep snapshot 比較固定 (= GenomeStageResult / archive Parquet に絶対漏れない) |
| log volume / I/O backpressure | 中 | shadow event は最小 field (= schema v1)、 1 genome 1 event 上限 (= acceptance C2)、 default off で通常 run には影響しない |
| `BCEvaluationInput` の identifier 不安定 (= individual_index 単独では run/generation 跨ぎで不安定) | 中 | identifier 契約 (= run_id + generation_no + genome_hash + individual_index) を schema v1 必須 field に固定 (= acceptance C3) |

---

## 8. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path) | canonical_metrics | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS + Stage C base dual-path | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | (stage_gate.py のみ) | **完了** (commit 1dadc8b) |
| step 1.7 ✨ | Stage C stress dual-path | (stage_gate.py のみ) | **完了** (commit e3a428b) |
| step 1.8 ✨ | Stage C cross_pair (ii-lite) dual-path | (stage_gate.py + cross_pair.py) | **完了** (commit c3ee70a) |
| **step 2 = B Phase 2 Integration Program** | (本) | (= 段階分割) | **概念設計 Round 5 (= StageBCShadowContext + collector 分離 + schema 完全反映 + 文言統一)** |
| └ **step 2.1a (本設計対象 前半)** | input feasibility 検証 (= 9 fields 対応表) + fixture 構築 | (= 設計確定 + skeleton) | 概念設計 Round 5 |
| └ **step 2.1b (本設計対象 後半)** | shadow logging (= LOG_ONLY、 stage_gate 内 sanitize 直前 配置 + 上位層 collector) | (stage_gate.py 拡張 + 新 helper bc_evaluator_shadow.py + bc_evaluator_shadow_collector.py + caller context 構築) | 概念設計 Round 5 |
| └ step 2.2 | switch (= Phase 2 切替コミット完了) | (T065 統合 + Pareto 軸切替) | 後続 |
| └ step 2.3 | deprecation | (旧 API 廃止) | 後続 |
| step 3-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 9. この設計に効く事実 (= docs/devnotes 要点要約 + Round 2 独立検証成果)

### 9.1 step 1.8 完了 handoff (`devnotes/20260504-1018-B-step1.8-complete-handoff/handoff.md`)
- 6 系列で dual-path 観測点を確立、 mission 必須軸 ii-lite observability 完成
- step 2 着手前提条件達成、 規模 大の改修

### 9.2 stage_bc_evaluator.py 現行構造 (= 着手前調査)
- T064 PR1 docstring: 「stage_gate.py / swim_lane.py / cross_pair.py への置換は Phase 2 (別 PR、 T065 統合と同時) で実施」 = 本 program の起源
- `BCEvaluationInput`: stage_bc_evaluator.py:409 (= 9 fields)、 production caller 無し
- `BCEvaluationResult`: stage_bc_evaluator.py:429 (= 8 fields、 c_pass_depth 含む)

### 9.3 main flow 配線 (= 着手前調査)
- `parallel_eval.py:319, 357` 旧 API caller
- `swim_lane.py:635, 670` 同
- `failure_handling.evaluate_bc_safe`: 新 API isolation boundary (= 再利用可能)

### 9.4 step 1.5-1.8 確立 SSOT
- dual-path log: 6 系列 + n_fold entries / genome
- helper シグネチャ凍結
- adapter 凍結
- sanitize SSOT: `cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})` を try-finally で常時実行

### 9.5 Round 2 独立検証成果 (= Round 1 [Warning § 8] 反映)

#### (a) `BCEvaluationResult` post-evaluation 経路の現状
- `loop_closure.py` / `nsga2_selection.py` / `cpps_archive.py` で type 利用
- 現時点では **caller が無いため `bc_result=None` 経路が常に走っている** (= 詳細実装で確認すべき、 step 2.1 では post-evaluation に流さないので影響なし)

#### (b) `failure_handling.evaluate_bc_safe` の signature 確認
- `genome_id / run_id / generation_no / stage / evaluate_fn / **evaluate_kwargs` で受け取り、 `EvaluationOutcome[BCEvaluationResult]` を返す
- 4 段 wrapper: ValueError / Exception / finite check / state invariant check で degraded result を返す経路あり
- step 2.1 で再利用可能 (= shadow wrapper の isolation boundary に流用)

#### (c) `parallel_eval` / `swim_lane` の caller 同型性
- 両者で `evaluate_stage_b/c` の caller 構造が同型、 step 2.1 共通 wrapper で吸収可能

#### (d) `stage_c_lite_periods` / `stage_c_period` の SSOT 確定
- 既存 `StageGateConfig.stage_c_holdout_days` 等から builder 内で derive 可能
- 新規 config field 追加禁止 (= Round 1 [Critical § 8] 反映)

### 9.6 git log の関連
- `c3ee70a Merge branch 'todo/T086'` (= step 1.8)
- `e3a428b Merge branch 'todo/T085'` (= step 1.7)
- ... 以降 step 1-1.8 全 main commit

---

## 10. 参考資料

- step 1.8 完了 handoff: `devnotes/20260504-1018-B-step1.8-complete-handoff/handoff.md`
- step 1.8 概念設計 + 詳細設計 (Round 5 APPROVED): `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/`
- T064 stage_bc_evaluator 設計: `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/{conceptual,detailed}-design.md`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- stage_bc_evaluator.py (新 API): `src/alpha_factory/stage_bc_evaluator.py:1-1419`
- stage_gate.py (旧 API、 step 1.8 拡張済): `src/alpha_factory/stage_gate.py`
- parallel_eval.py (= main flow): `src/alpha_factory/parallel_eval.py:319, 357`
- swim_lane.py (= main flow): `src/alpha_factory/swim_lane.py:635, 670`
- failure_handling.evaluate_bc_safe (= dormant wrapper): `src/alpha_factory/failure_handling.py:525-622`
- Codex 概念設計 review Round 1: `devnotes/20260504-1026-B-phase2-step2-stage-bc-evaluator-main-flow-integration/conceptual-review-round-1.md`
