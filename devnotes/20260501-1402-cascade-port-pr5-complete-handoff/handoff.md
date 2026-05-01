# Selection Cascade Port — Session Handoff (T058 Phase 2 配線 PR 1-5 完了、 残 PR 6-7)

**作成日時**: 2026-05-01 14:02 JST
**Session**: cascade port v2 設計フェーズ完了後の Phase 2 配線実装着手、 T058 schema v2 contract 全 7 PR のうち PR 1-5 完了 (= 主要 caller の RunContext 注入完成)
**前セッション**: cascade port v2 設計 18 件 (T058-T075) 全件完了 (handoff: `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md`)
**次セッション**: **T058 残 PR 6 (Tier 2 軽量ガード) + PR 7 (統合テスト + DoD 全項目確認) 着地**、 続いて T059 Phase 2 配線 or T076 synthesis Round 22 改訂

---

## 0. 現在地 (Where we are)

### 完了済 (cascade port v2 Phase 1 設計 + Phase 2 配線着手)

```
Phase 1 設計 18 件 (T058-T075)        ████████████████████ 100%
Phase 2 配線 T058 (7 PR 構成)
  ├─ PR 1: schema_contract 基盤層    ████████████████████ 100% (a4bf1bf)
  ├─ PR 2: archive.py v2 schema       ████████████████████ 100% (f810c24)
  ├─ PR 3: calibrate_gate_history     ████████████████████ 100% (2a75de8)
  ├─ PR 4: diagnostics_sidecar / fsp  ████████████████████ 100% (a9733f3)
  ├─ PR 5: run_ga RunContext 完成     ████████████████████ 100% (ba11aaa) ✨
  ├─ PR 6: Tier 2 軽量ガード          ░░░░░░░░░░░░░░░░░░░░ 0%
  └─ PR 7: 統合テスト + DoD 確認      ░░░░░░░░░░░░░░░░░░░░ 0%
Phase 2 配線 T059-T075 (依存順、 並行可能)  ░░░░░░░░░░░░░░░░░░░░ 0%
synthesis Round 22 改訂 (T076)              ░░░░░░░░░░░░░░░░░░░░ 0%
```

**全体進捗**: 設計 100%、 実装 T058 PR 5/7 (= 71%) 完了。 PR 6+7 で T058 完了後、 T059-T075 Phase 2 配線へ。

### 本セッションで実装した PR (5 件、 全 ff-merge 済)

| PR | commit | 内容 | tests pass | Codex Round |
|---|---|---|---|---|
| **PR 1** | `a4bf1bf` | schema v2 contract 基盤層 (`src/alpha_factory/schema_contract.py` 新規 + `run_context.py` 新規 + `config.py` SchemaContractConfig 追加 + `default.yaml` schema_contract block) | 910 (alpha_factory) / 1489 全体 | 2 round APPROVED (F-001 = grammar 違反 log 専用化を反映) |
| **PR 2** | `f810c24` | archive.py GENOMES_SCHEMA に v2 4 field 追加 + `_create_row_template` 既定値 + GenomeArchive `__init__` に run_context/enforcement_mode kwarg + flush() で `assert_genome_entry_v2` lint 連動 + schema_lint_summary log | 924 (alpha_factory) / 1489 全体 | 2 round APPROVED (W1: lint counter reset / W2: 47 col 列順序検証 / W3: load 拡張は PR 5 持越し) |
| **PR 3** | `2a75de8` | calibrate_gate_history.py HistoryRecord に `calibrate_history_schema_version=2` + `dataset_epoch_id` 追加 + `from_dict_or_none` classmethod + read_history で v1 record skip + warning + calibrate_state.py SCHEMA_VERSION=2 + load_calibrated_threshold に dataset_epoch_id 引数 (AND 結合、 dataset_span は T067 まで残す) + caller (calibrate_gate.py / run_ga.py) の append_record/load 呼出更新 + tests/scripts/test_calibrate_gate_drift.py path 修正 | 939 (alpha_factory) / 173 (scripts) / 1504 全体 | 2 round APPROVED (Critical 1: from_dict_or_none で SchemaContractError 明示 / Critical 2: grammar violation skip test 追加) |
| **PR 4** | `a9733f3` | diagnostics_sidecar.py STAGE_A_PROVENANCE_SCHEMA に v2 2 field (diagnostics_schema_version + dataset_epoch_id) 追加 + build_sidecar_table/write_stage_a_provenance に optional run_context/mode kwargs + fsp_updater.py `_detect_archive_schema_version` helper + `_read_archive_with_fsp_compat`/`_atomic_write_parquet` mode kwarg + 内部 caller 5 箇所の mode 伝搬 + `runtime_mode` rename (衝突回避) | 966 (alpha_factory) / 173 (scripts) / 1504 全体 | 1 round APPROVED + Suggestion 2 件 commit 前反映 |
| **PR 5** ✨ | `ba11aaa` | **中核 PR**: run_ga.py 起動初期で `RunContext` 生成 + 全 artifact (summary.json / history.json / best_genome.json / population.jsonl / run cache JSON) に dataset_epoch_id propagate + `assert_run_report_v2` 呼出 + `cascade_contract_version=2` (int) + `schema_version="1.1"` (string) 両立 + GenomeArchive(run_context=, enforcement_mode=) 注入 + write_stage_a_provenance(run_context=, mode=) 伝搬 + load_calibrated_threshold(dataset_epoch_id=run_context.dataset_epoch_id) + run_alpha_sieve.py で `GenomeArchive.load(..., return_schema_version=True)` tuple 受取 + LOG_ONLY warning skip / FAIL_CLOSED raise + GenomeArchive.load(path, *, mode=LOG_ONLY, return_schema_version=False) 拡張 (1-arg 旧 caller 完全互換) + `generate_epoch_id_stub(DatasetConfig) -> "epoch_legacy"` (T059 で deterministic 置換予定) | 1546 全体 (regression 0、 1 skipped pre-existing) | 1 round APPROVED + Warning 1 反映 (test 追加) |

合計 **5 commit、 全 fast-forward merge、 regression 0 件**。 Codex impl-review **gpt-5.3-codex / xhigh** で **計 7 round** (PR 1: 2 / PR 2: 2 / PR 3: 2 / PR 4: 1 / PR 5: 1)。

### 本セッションの T064 Follow-up 設計改訂 (cascade port Phase 1 範囲、 commit `874e287`)

T058 Phase 2 配線着手前に、 T066 Phase 0 dependency 解消として T064 詳細設計に `BCEvaluationResult.c_pass_depth: float` field + `StageCLiteResult.n_pass_windows: int` field + `compute_c_pass_depth` helper を追加. Codex 詳細レビュー (gpt-5.3-codex / high) で 2 round APPROVED. 主要規範:
- StagePassStatus 3 値明示分岐 + 未知値 ValueError raise (Round 2 反映)
- StageCLiteResult.__post_init__ で n_pass_windows ∈ [0, 3] + len(per_window_results) 整合二重検証
- compute_c_pass_depth は IEEE 754 exact (整数 × 0.25 + 整数定数 のみ)
- collider bias 独立性 (T072 規範継承): `c_pass_depth` / `n_pass_windows` は holiday/DST/observability_flags 系に依存しない
- T066/T067/T068 Phase 2 配線 PR より先 merge 必須の順序契約

### 本セッション 序盤の運用 commit 2 件

| commit | 内容 |
|---|---|
| `9718663` | chore(stage_a): threshold 0.0 復元 (Run-26 で Stage A pass=0 完全崩壊、 並走 T054 で 0.15 になっていた yaml seed を variance 確認用に revert、 T054 history > yaml 優先順位は維持) |
| `58782fd` | chore(skill): zenigame-fx-codex-vscode モデル名を gpt-5.5 系に更新 (skill ドキュメント更新のみ、 ただし `gpt-5.5-codex` は OpenAI 側未登録のため実呼び出しは `gpt-5.3-codex` 継続) |

---

## 1. 全体ロードマップ (T058 完了時点 + 残作業)

| Milestone | TODO | 進捗 |
|---|---|---|
| **設計フェーズ (Phase 1)** | T058-T075 全 18 件 | ✅ 100% (cascade port v2 全 18 件 APPROVED) |
| **T064 Follow-up** | c_pass_depth field 追加 (T066 Phase 0 解消) | ✅ 完了 (874e287) |
| **T058 Phase 2 配線** | 7 PR (PR 1-5 完了、 PR 6-7 残) | 71% |
| **T059 Phase 2 配線** | dataset_epoch_id 値生成 (`generate_epoch_id_stub` を deterministic に置換) | 0% |
| **T060-T075 Phase 2 配線** | 依存順、 並行可能 | 0% |
| **T076 synthesis Round 22 改訂** | new_cascade 採用しない / FM SSOT / DoD 分離 / threshold / stable clause anchor | 0% |
| **T075 切替コミット** | big-bang 1-shot (= LOG_ONLY → FAIL_CLOSED + 旧 v1 archive 物理削除等) | 0% |

---

## 2. T058 残作業 (PR 6 + PR 7)

### 2.1 PR 6: Tier 2 軽量ガード (施策 11)

**スコープ**: scripts 側で v2 schema 適合を最低限確認する軽量ガード追加. 詳細設計 行 1443-1469.

**変更対象**:
- `scripts/alpha_factory/calibrate_gate.py` 等 (詳細設計の各スクリプト)
- 各スクリプト entry point で `cfg.schema_contract.to_mode()` を取得 → archive load / history read を mode 連動に切替
- 既存 caller との完全互換 (= mode default LOG_ONLY)

**テスト**:
- `tests/scripts/test_tier2_epoch_id_propagation.py` 新規 (詳細設計 行 1526)

**想定実装時間**: 30 min

### 2.2 PR 7: 統合テスト + DoD 全項目確認 (施策 12)

**スコープ**: 詳細設計 行 1474-1483 の統合テスト + DoD 全項目 (詳細設計 行 1509-1538) を機械検証.

**変更対象**:
- `tests/alpha_factory/test_t058_integration.py` 新規 (詳細設計 行 1523)
  - smoke RUN シミュレーション (= RunContext → archive flush → calibrate read → diagnostics → fsp → sieve の end-to-end)
  - LOG_ONLY mode で全経路で warning なしで通る
  - FAIL_CLOSED mode + v1 artifact で適切に raise
- DoD 機械検証 (pytest test 数 / mypy / ruff)
- `docs/alpha_factory/stage-gates.md` § "T054: state file 経由の自動適用" を更新 (詳細設計 行 1537)
- `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md:99` 付近の T058 反映 (詳細設計 行 1538)

**想定実装時間**: 1 h

### 2.3 PR 6+7 完了後の作業

1. T058 全 7 PR 完了 → `docs/alpha_factory/TODO.md` で T058 を Closed に移動 (`zenigame-fx-todo-close` skill)
2. handoff 文書更新 (= T058 完了 + T059 着手準備)

---

## 3. T058 完了後のロードマップ (T059-T075 Phase 2 配線)

T058 完了後、 cascade port v2 設計 18 件のうち残り 17 件 (T059-T075) を Phase 2 配線実装. 依存関係 (synthesis § 18.1):

```
先行必須 (T058 完了後): T059 → T060
  T059: dataset_epoch_id 値生成 (= generate_epoch_id_stub を deterministic 関数に置換)
  T060: Partition + Fold generator
評価系: T061 → T062 → T063 → T064 (T060 完了後)
  T061: canonical 5 engine
  T062: mission_inf_gap engine
  T063: Stage A evaluator
  T064: Stage B/C evaluator (本セッションで follow-up 設計済、 Phase 2 で T065 統合と同時実装)
GA 中核: T065 → T066 (T058 / T064 完了後)
  T065: NSGA-II core + main selection
  T066: CPPS 2-state FSM + CA/DA archive
運用制御: T067 → T068 → T069 (T065 / T066 完了後)
  T067: Loop closure (calibrate_state の dataset_span 撤廃 + LOG_ONLY → FAIL_CLOSED 切替)
  T068: Failure handling
  T069: Calibrate-gate scope (3 Run freeze)
基盤拡張: T070 → T071 → T072 (T064 完了後)
  T070: Backtest engine 拡張 (SessionBlock)
  T071: Observability layer (RunObservabilityReport)
  T072: DST/holiday boundary contract
監査/展開: T073 → T074 → T075 (T071 完了後)
  T073: Audit layer (DSR + PBO/SPA scaffold)
  T074: Graduation lane scaffold
  T075: Big-bang cleanup + smoke (切替コミット = 全 17 件 Phase 2 完了 + synthesis Round 22 改訂後)
```

各 TODO は **T058 と同じ 7 PR 分割スタイル** (= 段階導入) を採用するか、 各 TODO の詳細設計の「実装モード」 / 「実装順序」 に従う. T058 経験で確立したフロー:

1. worktree (`./worktrees/todo-T{NNN}-pr{M}/`) 作成 + uv sync
2. subagent (general-purpose) に worktree 内実装を依頼 (= prompt に背景 / スコープ / DoD / Codex review 指示を inline で詳細記述)
3. subagent: 実装 + tests + ruff + mypy + Codex impl-review (gpt-5.3-codex / xhigh) + commit
4. main conversation: 結果確認 → main へ ff-merge → worktree cleanup
5. 次 PR へ進む

### 3.1 T058 で確立した規範 (T059-T075 でも継承)

- **incremental モード**: 大規模 TODO は 5-7 PR に分割、 各 PR で main merge して段階導入
- **既存 signature 完全維持**: 新 kwarg は default 付き (LOG_ONLY etc.)、 既存 caller は変更不要
- **schema_version 二層**: 個別 schema (genome_entry_schema_version=2 / calibrate_history_schema_version=2 / diagnostics_schema_version=2) と RunContext 一段上 (cascade_contract_version=2、 dataset_epoch_id) を分離
- **summary.json 互換**: `schema_version: "1.1"` (string) は既存維持、 v2 系は `cascade_contract_version: 2` (int) で別 key
- **mode 連動 helper**: 各経路 (archive / calibrate / diagnostics / fsp / sieve) で `assert_*_v2(record, *, mode)` + LOG_ONLY warning / FAIL_CLOSED raise の 2 経路統一
- **stub fallback**: dataset_epoch_id は T058 段階で `"epoch_legacy"` literal 統一 (= archive template / RunContext / calibrate-gate / diagnostics_sidecar 全て)、 T059 で deterministic 値に一括置換
- **Codex model 厳守**: `gpt-5.3-codex` (xhigh = impl-review、 high = design-review、 medium = conceptual-review)。 `gpt-5.5-codex` は OpenAI 側未登録 (= 404)
- **Phase 0 dependency**: 詳細設計時に他 TODO で必要な field を明文化、 follow-up 設計改訂で SSOT 確定 (= 本セッション T064 で実施した手順を T065-T075 でも適用)
- **regression 0 必須**: 各 PR で全テスト pass (= ~1500+ tests)、 既存 schema_version="1.1" string test 等を壊さない
- **5 段階 grep DoD**: PR スコープ外ファイルへの touch を構造的に防止

### 3.2 synthesis Round 22 改訂 (T076、 タイミング判断)

T075 PR の blocked-by 5 件 (旧 handoff 記載) を解消する別 TODO. T058-T074 Phase 2 配線とは並行可能. T075 PR (= 切替コミット = big-bang 1-shot) より先 merge or 同期 merge が推奨.

候補内容 (旧 handoff から引用):
1. § 12.4 「new_cascade 名前空間」 文言 → 「採用しない、 直接 src/alpha_factory/* で実装」 と明文化
2. § 12.4 「FM1/FM4」 ロールバック条件 → T075 FailureModeKind enum と紐付けて確定
3. § 18.3 Smoke DoD 8 項目 → per-run / cross-run 分離形式 (DoD1-DoD7 / DoD8) で明文化
4. § 16 Risk Top 5 と FM1-FM5 の数値 threshold → 別 TODO で確定 (smoke 後再校正)
5. stable clause anchor 体系 → synthesis 全文に `synthesis_schema_version: 22` 冒頭 metadata block 追加 + 旧 1-21 round の遡及付与

T076 を「いつ着手するか」 はユーザ判断。 T058 完了後に T059 着手と並行で T076 概念設計から進めるのが効率的.

---

## 4. 次セッションの開始手順

### 4.1 まず読むもの (15 分)

1. **本ハンドオフ** (`devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md`)
2. **設計フェーズ完了時点ハンドオフ** (前セッション、 `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md`) — 全体ロードマップ、 設計 18 件の詳細
3. **T058 詳細設計 残施策** (`devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md`)
   - 施策 11 (Tier 2 軽量ガード): 行 1443-1469
   - 施策 12 (統合テスト): 行 1474-1483
   - DoD: 行 1509-1538
4. **本セッションの impl-review log** (= PR 1-5 の Codex review):
   - `devnotes/20260429-1912-todo-T058-schema-v2-contract/impl-review-pr{1,2,3,4,5}-round-{N}.md`

### 4.2 次セッション着手フロー

**A. T058 完遂優先 (推奨)**

```
1. PR 6 着手: 
   git -C /Users/ishitoya/repository/zenigame-fx worktree add ./worktrees/todo-T058-pr6 -b todo/T058-pr6 main
   cd worktrees/todo-T058-pr6 && uv sync
   subagent に T058 PR 6 (Tier 2 軽量ガード) 実装依頼
   → ff-merge → worktree cleanup

2. PR 7 着手:
   同フロー、 統合テスト + DoD 全項目確認 + docs / SKILL.md 更新

3. T058 close + handoff 更新
```

**B. T058 / T076 並行**

```
- メインラインで T058 PR 6+7 を継続 (本ハンドオフ 4.2 A の手順)
- 別途 T076 synthesis Round 22 改訂を概念設計から着手 (zenigame-fx-alpha-design skill)
```

**C. PR 6+7 軽量なら 1 セッションで T058 完遂 + T059 着手**

T059 は `generate_epoch_id_stub` を deterministic 値生成関数に置換 (詳細設計参照)。 T059 単独 PR は比較的軽量.

### 4.3 重要 docs / devnotes

| 場所 | 内容 |
|---|---|
| `devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md` | **本ハンドオフ (= T058 PR 1-5 完了時点、 canonical な引き継ぎ)** |
| `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md` | 前セッション handoff (= 設計 18 件全件完了時点) |
| `devnotes/cascade-port-handoffs-historical/` | 過去 handoff (履歴参照のみ) |
| `devnotes/20260428-2300-cascade-port-debate/synthesis.md` | cascade port v2 設計上位文書 (Round 21 改訂後、 Round 22 候補は T076 で改訂予定) |
| `devnotes/20260429-1912-todo-T058-schema-v2-contract/` | T058 詳細設計 + 概念設計 + 全 6 round Codex APPROVED 履歴 + 本セッション impl-review-pr1-5 履歴 |
| `devnotes/20260430-0230-todo-T064-stage-bc-evaluator/` | T064 詳細設計 + 本セッション follow-up 改訂 (c_pass_depth、 commit `874e287`) |
| `devnotes/20260430-{時刻}-todo-T0{59-75}-*/` | 各 cascade port v2 TODO の詳細設計 (= Phase 2 配線時の SSOT) |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T075 全 18 件 Open に登録済、 T058 PR 6+7 完了後に Closed へ) |
| `AGENTS.md` | プロジェクト全体規約 |

### 4.4 Codex 呼び出し方 (T058 で確立、 T059-T075 でも踏襲)

- 概念レビュー: `gpt-5.3-codex` / `medium`、 label `conceptual-review`
- 詳細レビュー: `gpt-5.3-codex` / `high`、 label `design-review`
- 実装レビュー: `gpt-5.3-codex` / `xhigh`、 label `impl-review`
- skill: `zenigame-fx-codex-review`
- prompt: file 経由 stdin (Write で `.codex-prompt-{label}.md` 作成 → `scripts/codex exec --sandbox read-only -m gpt-5.3-codex -c 'model_reasoning_effort="..."' --json -o {output} - < {prompt}`)
- セッションモード: Round 1 で thread_id 取得 → Round N で `scripts/codex exec resume "$SESSION_ID"`
- **重要**: `gpt-5.5-codex` は OpenAI 側未登録 (model_not_found 404)、 `gpt-5.3-codex` 継続使用. 本セッション初頭の skill SKILL.md 更新 (commit `58782fd`) は文書のみで実 model 切替なし.

### 4.5 重要原則 (本セッションで継続適用、 T059-T075 でも踏襲)

- **Phase 1 / Phase 2 分離**: 各 TODO の Phase 1 (= 設計) + Phase 2 (= 実装) を分離、 設計 commit と実装 commit を独立
- **Phase 0 dependency**: 他 TODO で消費される field を follow-up 設計改訂で SSOT 確定 (= T064 で実施済、 T070-T075 でも該当箇所あれば適用)
- **status field 方式**: None 経路完全排除、 Optional に逃げない、 enum は明示分岐 + 未知値 ValueError raise
- **scaffold 数値 field なし**: scaffold dataclass は status + calc_version のみ、 数値 field 追加は Phase 2 実装 PR で MINOR bump
- **collider bias 規範継承**: holiday_markets / dst_transition_markets / observability_flags 系を condition variable として直接参照しない、 stratified audit は T071 RunObservabilityReport 経由
- **dual-path operational definition**: 並走 (= runtime 到達 OR feature flag OR 二経路出力) は禁止、 同居 (= source tree のみ) は許容、 切替コミット (T075 Phase 2) で big-bang 1-shot
- **synthesis local projection**: 親 SSOT (synthesis / 上位 TODO) を再定義しない、 子 TODO は参照のみ、 改訂は別 PR (= T076 等)
- **既存 caller signature 完全維持**: 新 kwarg は default 付き、 既存 test 互換、 既存運用 (history.jsonl 等) を壊さない
- **T058 の段階導入経験を継承**: 大規模 TODO は 5-7 PR 分割、 各 PR で main merge

---

## 5. 未解決事項 / 次セッション最初に確認

1. **T058 PR 6+7 の着手** (= 推奨パス、 残 ~1.5 h で T058 完遂)
2. **T058 完了後の TODO close 処理** (= zenigame-fx-todo-close skill 経由 or 直接 todo_manager.py で close)
3. **T076 synthesis Round 22 改訂タイミング**: T058 並行 / T058 完了後 / T059 並行 / T075 PR 直前 のいずれ
4. **T059 着手判断**: T058 完了後即着手 (= generate_epoch_id_stub の deterministic 置換) / 一旦様子見
5. **Run-26 崩壊原因の調査**: 本セッションで yaml threshold revert (commit `9718663`) のみ実施、 根本原因は未調査. 次 RUN で Stage A pass=0 が再発しないか確認、 再発なら variance 内、 再発なら別 TODO で根本原因調査
6. **untracked reports (本セッション開始時から残置)**:
   - `reports/calibrate-gate/history.jsonl` (Run-26 周辺)
   - `reports/run-reports/run-1/diagnostics/`
   - `reports/run-reports/run-24/`、 `run-25/`、 `run-26.md`、 `run-26/`
   - これらは別系統の運用 RUN artifact。 commit するか .gitignore 追加するか判断必要
7. **T058 完了後の cascade port 全体監査**: T076 と並行で「全 18 TODO の Phase 2 申し送り集約 + 依存関係グラフ + collider bias 規範整合性 + scaffold SSOT 整合性」 を実施する選択肢 (旧 handoff section 7.3 の選択肢 C)

---

## 6. 進捗状況サマリー

```
設計 (Phase 1)            ████████████████████ 100% (T058-T075 全 18 件 APPROVED)
T064 follow-up            ████████████████████ 100% (c_pass_depth、 874e287)
T058 Phase 2 配線         ██████████████░░░░░░  71% (5/7 PR、 PR 6+7 残)
T059-T075 Phase 2 配線    ░░░░░░░░░░░░░░░░░░░░   0%
T076 synthesis Round 22   ░░░░░░░░░░░░░░░░░░░░   0%
T075 切替コミット (最終)  ░░░░░░░░░░░░░░░░░░░░   0%
```

**全体進捗** (実装フェーズ全体): ~10% (T058 が 71%、 T058 全体は 18 TODO 中 1 つだから ~ 4%、 ただし T058 は基盤層で他依存多いので相対的重み大). T059-T075 を T058 と同様の段階アプローチで進めれば、 全 17 TODO × 平均 3-5 PR = 50-80 PR で Phase 2 配線完了予測.

---

## 7. 次セッションの最初の指示テンプレート

### 7.1 T058 PR 6+7 で完遂 (= 推奨)

> 引き継ぎは `devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md` 読んで。 T058 PR 6 (Tier 2 軽量ガード) から着手、 完了したら PR 7 (統合テスト + DoD 全項目確認) で T058 完遂。 worktree + subagent + Codex impl-review (gpt-5.3-codex / xhigh) + ff-merge のフローを継承。

### 7.2 T058 / T076 並行

> 引き継ぎは `devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md` 読んで。 メインラインで T058 PR 6+7 を進めつつ、 別途 T076 synthesis Round 22 改訂を概念設計から起こす (zenigame-fx-alpha-design skill)。

### 7.3 T058 完了後 T059 着手

> 引き継ぎは `devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md` 読んで。 T058 PR 6+7 で完遂したら即座に T059 (dataset_epoch_id 値生成 = generate_epoch_id_stub を deterministic 置換) を着手。 設計は `devnotes/20260430-0500-todo-T059-epoch-window-manager/` 等。

### 7.4 全体監査優先

> 引き継ぎは `devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md` 読んで。 T058 PR 6+7 完了後、 T059 着手前に「cascade port v2 全体整合性監査」 を実施。 全 18 TODO の Phase 2 申し送り集約 + 依存関係グラフ + collider bias 規範整合性 + scaffold SSOT 整合性を Codex で全件 review。

---

## 8. Codex review 累積統計 (本セッション、 T064 follow-up + T058 PR 1-5)

| 区分 | Round 数 | model | reasoning |
|---|---|---|---|
| T064 follow-up 詳細レビュー | 2 | gpt-5.3-codex | high |
| T058 PR 1 impl-review | 2 | gpt-5.3-codex | xhigh |
| T058 PR 2 impl-review | 2 | gpt-5.3-codex | xhigh |
| T058 PR 3 impl-review | 2 | gpt-5.3-codex | xhigh |
| T058 PR 4 impl-review | 1 | gpt-5.3-codex | xhigh |
| T058 PR 5 impl-review | 1 | gpt-5.3-codex | xhigh |
| **合計** | **10 round** | gpt-5.3-codex | |

10 round 全 APPROVED. 累積 token は概算で 4 - 6 M tokens (= xhigh 1 round ~50K-100K × 8 + high 1 round ~50K × 2).

---

## 9. T058 全 7 PR の見取り図 (= 次セッションでの参照用)

```
PR 1 (a4bf1bf): schema_contract.py 新規 + run_context.py 新規 + config.py SchemaContractConfig + default.yaml
PR 2 (f810c24): archive.py GENOMES_SCHEMA v2 4 field + flush lint
PR 3 (2a75de8): calibrate_gate_history v2 + calibrate_state scope key 拡張 + caller (calibrate_gate / run_ga) 呼出更新
PR 4 (a9733f3): diagnostics_sidecar v2 + fsp_updater v2 propagate
PR 5 (ba11aaa): run_ga.py RunContext 生成 + 全 artifact propagate + run_alpha_sieve mode 連動 + GenomeArchive.load 拡張 ← 中核 PR
PR 6 (未着手): Tier 2 軽量ガード (scripts 側 mode 連動)
PR 7 (未着手): 統合テスト + DoD 全項目確認 + docs / SKILL.md 更新
```

---

これで T058 PR 1-5 完了時点の handoff は以上. 次セッションで PR 6+7 着地 → T058 完遂 → T059 着手 → ... と進めて cascade port v2 Phase 2 配線完了へ。 PR 1-5 の段階導入経験は T059-T075 でも継承される.
