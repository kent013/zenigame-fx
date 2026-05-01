# Selection Cascade Port — Session Handoff (T058 全 7 PR 完了 + Closed 移動、 残 T059-T075 + T076)

**作成日時**: 2026-05-01 15:35 JST
**Session**: cascade port v2 Phase 2 配線実装、 T058 schema v2 contract 全 7 PR 完了 → main merge → TODO Closed 移動完了
**前セッション**: 設計 18 件全件完了 (`devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md`) → 本セッション PR 1-5 完了 (`devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md`) → PR 6+7 で T058 完遂
**次セッション**: **T059 (dataset_epoch_id 値生成 = generate_epoch_id_stub の deterministic 置換) または T076 (synthesis Round 22 改訂) 着手**

---

## 0. 現在地 (Where we are)

### 完了済 (cascade port v2 Phase 1 設計 + Phase 2 配線 T058 完了)

```
Phase 1 設計 18 件 (T058-T075)        ████████████████████ 100%
Phase 2 配線 T058 (7 PR 構成、 完了) ████████████████████ 100% ✨
  ├─ PR 1: schema_contract 基盤層    ████████████████████ 100% (a4bf1bf)
  ├─ PR 2: archive.py v2 schema       ████████████████████ 100% (f810c24)
  ├─ PR 3: calibrate_gate_history     ████████████████████ 100% (2a75de8)
  ├─ PR 4: diagnostics_sidecar / fsp  ████████████████████ 100% (a9733f3)
  ├─ PR 5: run_ga RunContext 完成     ████████████████████ 100% (ba11aaa)
  ├─ PR 6: Tier 2 軽量ガード          ████████████████████ 100% (2bd339a)
  └─ PR 7: 統合テスト + DoD 確認      ████████████████████ 100% (15f3ab6)
T058 TODO close (Open → Closed)       ████████████████████ 100%
Phase 2 配線 T059-T075 (依存順、 並行可) ░░░░░░░░░░░░░░░░░░░░ 0%
synthesis Round 22 改訂 (T076)            ░░░░░░░░░░░░░░░░░░░░ 0%
T075 切替コミット (最終)                  ░░░░░░░░░░░░░░░░░░░░ 0%
```

**全体進捗**: 設計 100%、 Phase 2 実装 T058 完了 (= cascade port v2 18 TODO 中 1 つ完了、 ただし基盤層なので相対重み大)。 残り 17 TODO (T059-T075) + T076 で全完了. 実装フェーズ全体は ~6% (T058 完了で実装基盤確立、 後続 TODO の段階導入経験を継承可能).

### 本セッション (= PR 6 + PR 7) で完了した内容

| PR | commit | 内容 | tests pass | Codex Round |
|---|---|---|---|---|
| **PR 6** | `2bd339a` | Tier 2 軽量ガード = `assert_epoch_id_present_for_display(record, *, artifact)` を schema_contract.py に追加 (warning ベース、 fail-open) + 4 display scripts (extract_batch_metrics / generate_run_report / compare_batch_runs / analyze_run) に呼出追加 + 4 scripts で `dataset_epoch_id` を markdown header / batch_summary.json / Per-run table に display 追加 | 1164 (alpha_factory + scripts) | 1 round APPROVED + Critical 0 / Warning 2 (Codex INCONCLUSIVE) / Suggestion 2 |
| **PR 7** ✨ | `15f3ab6` | **最終 PR** = `tests/alpha_factory/test_t058_integration.py` 新規 (4 end-to-end ケース + 既存 7 ケース 計 7 件) + DoD 全 20 項目チェックリスト (`devnotes/20260429-1912-todo-T058-schema-v2-contract/dod-verification-pr7.md`) + `docs/alpha_factory/stage-gates.md` § T054 を T058 反映 (dataset_epoch_id AND 結合 + T067 移行 3 点セット) + `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md:99` を T058 反映 | 1563 全体 (regression 0、 1 skipped pre-existing) | 2 round APPROVED (Round 1: REQUEST_CHANGES = T067 移行 3 点セット未統一 / DoD #17 直接 assert 不在 → Round 2 で blocker 全解消、 NIT のみ commit 内解消) |

### 本セッションの T058 全 7 PR 完了 + close 処理サマリ

```
本セッションで実施した作業:
- 前セッションの T058 PR 1-5 main 着地分を確認 (a4bf1bf〜ba11aaa)
- PR 6 worktree → subagent → ff-merge → cleanup
- PR 7 worktree → subagent → ff-merge → cleanup
- todo_manager.py close T058 → Open → Closed (TODO.md: Open リストから削除、 TODO-closed.md に追加)
- 本ハンドオフ作成 (= T058 完了時点 canonical handoff)
```

T058 main commit は計 7 個、 全 fast-forward merge.

---

## 1. T058 完了で確立した規範 (T059-T075 で継承)

T058 全 7 PR の実装経験から確立した規範を整理。 T059-T075 Phase 2 配線でこのまま踏襲する.

### 1.1 段階導入 (incremental モード)

- 大規模 TODO (= 12 施策超 / 1500+ tests に影響) は **5-7 PR に分割**
- 各 PR で main fast-forward merge、 段階的に runtime に投入
- 各 PR スコープ外への touch を **5 段階 grep DoD** で構造的に防止
- PR 1 は基盤層 (新規 module 追加のみ、 既存 caller 影響なし)、 PR 中盤は既存 API 拡張、 PR 終盤 (= PR 5 = 中核 PR) で主要 caller 配線、 PR 6+7 で軽量ガード + 統合テスト
- T058 例: PR 1 (基盤) → PR 2 (archive) → PR 3 (calibrate) → PR 4 (diagnostics + fsp) → PR 5 (run_ga + sieve、 中核) → PR 6 (Tier 2 ガード) → PR 7 (統合テスト + DoD + docs)

### 1.2 既存 caller signature 完全維持

- 新 kwarg は default 付き (LOG_ONLY etc.)、 既存 caller は変更不要
- `GenomeArchive(run_id, run_number)` 旧呼出 → `run_context=None, enforcement_mode=LOG_ONLY` default で旧挙動維持
- `GenomeArchive.load(path)` 旧呼出 → `*, mode=LOG_ONLY, return_schema_version=False` default で `pa.Table` 単独返却 (旧 caller 完全互換)
- `load_calibrated_threshold(*, history_path, base_config_hash, dataset_span, ...)` 旧呼出 → `dataset_epoch_id` 引数追加 (default なし、 ただし caller 側で明示的に渡すよう修正、 全 caller を同 PR 内で更新)
- summary.json `schema_version: "1.1"` (string) は **既存維持必須** (= test 互換性)、 v2 系は `cascade_contract_version: 2` (int) で別 key

### 1.3 schema_version 二層

- 個別 schema (genome_entry_schema_version=2 / calibrate_history_schema_version=2 / diagnostics_schema_version=2) を各 dataclass / Parquet schema に持つ
- RunContext 一段上で `cascade_contract_version=2` + `dataset_epoch_id` を artifact 横断 propagate
- 二層分離により、 個別 schema の version bump (2 → 3) と全体 contract bump (2 → 3) を独立に進められる

### 1.4 mode 連動 helper

- 各経路 (archive / calibrate / diagnostics / fsp / sieve / display) で統一パターン:
  ```python
  result = assert_*_v2(record, *, mode=SchemaEnforcementMode.LOG_ONLY)
  # LOG_ONLY: warning + result.ok=False / result.missing=...
  # FAIL_CLOSED: SchemaContractError raise
  ```
- Tier 2 軽量ガード (= display 系) は fail-open のみ: `assert_epoch_id_present_for_display(record, *, artifact)` (mode kwarg なし、 常に warning level、 raise しない)

### 1.5 stub fallback (epoch_legacy)

- T058 段階で `dataset_epoch_id = "epoch_legacy"` literal 統一 (archive template / RunContext / calibrate-gate / diagnostics_sidecar 全て)
- `generate_epoch_id_stub(DatasetConfig) -> "epoch_legacy"` を `src/alpha_factory/run_context.py` に配置
- T059 で deterministic 値生成関数に **一括置換** (= 1 関数の置き換えで全経路に伝搬)
- T067 切替コミットで `enforcement_mode=fail_closed` に切替時、 v1 archive (epoch_legacy なし) は schema_contract.py で raise

### 1.6 Codex impl-review (gpt-5.3-codex / xhigh) フロー

- model: `gpt-5.3-codex` 厳守 (`gpt-5.5-codex` は OpenAI 側未登録 = 404)
- reasoning effort: `xhigh` (実装レビュー)、 `high` (詳細設計レビュー)、 `medium` (概念設計レビュー)
- prompt: file 経由 stdin (Write で `.codex-prompt-{label}.md` 作成 → `scripts/codex exec --sandbox read-only -m gpt-5.3-codex -c 'model_reasoning_effort="..."' --json -o {output} - < {prompt}`)
- セッションモード: Round 1 で thread_id 取得 → Round N で `scripts/codex exec resume "$SESSION_ID"`
- prompt 先頭に `zenigame-fx-codex-review` SKILL.md の使命・禁止事項ブロック必須
- APPROVED まで Round (= 通常 1-3 round)、 修正対応 round では prompt は対応マトリクスのみ

### 1.7 worktree + subagent 委譲

- 各 PR で `git worktree add ./worktrees/todo-T{NNN}-pr{M} -b todo/T{NNN}-pr{M} main` 作成
- `cd worktree && uv sync` で依存セットアップ
- subagent (general-purpose) に worktree 内実装を委譲、 prompt に「背景 / スコープ / DoD / Codex review 指示」 を inline で詳細記述
- subagent: 実装 + tests + ruff + mypy + Codex impl-review + commit (= main merge は **しない**、 main conversation の判断)
- main conversation: 結果確認 → `git merge --ff-only` → `git worktree remove --force` → `git branch -d` で cleanup
- 各 subagent invocation 結果は ~130-200K tokens (= context window への負荷)。 連続 5-7 PR 進めると context 圧迫. 区切りでハンドオフ更新 + 次セッション継続が現実的.

### 1.8 regression 0 件必須

- 各 PR で全テスト pass: PR 1 で 1489 → PR 7 で 1563 (新規 74 tests 追加、 regression 0)
- 既存 schema_version="1.1" string test、 既存 GenomeArchive 旧 1-arg load 呼出、 既存 load_calibrated_threshold 旧 caller pattern 等を **絶対に壊さない**
- mypy / ruff clean (= PR touch 範囲のみ、 pre-existing 違反は触らない)

### 1.9 Phase 0 dependency (T064 follow-up 経験)

- 上流 TODO の詳細設計時に下流 TODO で消費される field を予測
- follow-up 設計改訂 PR で SSOT 確定 (= T064 で `c_pass_depth: float` 追加して T066 CA eviction lex key #4 を解消)
- T065-T075 でも該当箇所あれば適用 (= 詳細設計改訂のみで src 実装は Phase 2 PR で)

### 1.10 collider bias regulation 継承

- holiday_markets / dst_transition_markets / observability_flags 系を condition variable として直接参照しない
- stratified audit は T071 RunObservabilityReport 経由 (= T065-T075 Phase 2 配線でも踏襲)

---

## 2. 全体ロードマップ (T058 完了後の残作業)

| Milestone | TODO | 依存 | 進捗 |
|---|---|---|---|
| **T058 schema v2 contract** | 完了 | - | ✅ 100% |
| **T059 epoch / window manager** | dataset_epoch_id 値生成 (= generate_epoch_id_stub の deterministic 置換) | T058 | 0% |
| **T060 partition + fold generator** | T060 Period / Fold dataclass 実装 | T058 / T059 | 0% |
| **T061 canonical 5 engine** | canonical 5 metric 計算 | T058-T060 | 0% |
| **T062 mission_inf_gap engine** | mission_inf_gap 計算 (Pareto f3) | T061 | 0% |
| **T063 Stage A evaluator** | Stage A pass 判定 + StageAControllerState | T058-T062 | 0% |
| **T064 Stage B/C evaluator** | Stage B/C-lite/C 評価 + cross-pair shadow | T058-T063 (PR 1 の `c_pass_depth` 含む) | 0% |
| **T065 NSGA-II core** | NSGA-II 主選抜 + Pareto 3 軸 + breeding | T058 / T064 | 0% |
| **T066 CPPS FSM + archive** | CPPS 2-state FSM + CA/DA archive admission/eviction (lex key #4 = c_pass_depth、 T064 follow-up 解消済) | T058 / T064 / T065 | 0% |
| **T067 Loop closure** | warmstart + emergency + LOG_ONLY → FAIL_CLOSED 切替 + dataset_span 撤廃 | T065 / T066 | 0% |
| **T068 Failure handling** | graceful failure 伝搬 | T065 / T066 / T067 | 0% |
| **T069 Calibrate-gate scope** | 3 Run freeze 規範 | T065 / T066 / T067 | 0% |
| **T070 Backtest engine 拡張** | SessionBlock + spread_cost field | T064 | 0% |
| **T071 Observability layer** | RunObservabilityReport (audit / graduation_trigger / smoke_dod 等) | T064 | 0% |
| **T072 DST/holiday boundary** | BrokerTradingSchedule + MarketHolidayCalendar | T071 | 0% |
| **T073 Audit layer** | DSR + PBO/SPA scaffold | T071 | 0% |
| **T074 Graduation lane** | batch evaluator scaffold | T071 / T073 | 0% |
| **T075 Big-bang cleanup + smoke** | 切替コミット = 全 17 件 Phase 2 完了 + synthesis Round 22 改訂後の 1-shot | T067-T074 / T076 | 0% |
| **T076 synthesis Round 22 改訂** | 5 改訂候補 (new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor) | - (T075 PR より先 merge or 同期 merge) | 0% |

### 2.1 推奨着手順序 (= 旧 handoff section 4.6 + 本 T058 完了で再整理)

**Phase A: 基盤拡張 (T059 → T060 → T070 → T071 → T072)**
- T059 で dataset_epoch_id 値生成 (= T058 で stub 化した generate_epoch_id_stub を deterministic に置換)
- T060 で Period / Fold generator
- T070 / T071 / T072 は基盤拡張系 (T064 完了後並行可、 ただし T058 / T060 完了後は単独着手可)

**Phase B: 評価系 (T061 → T062 → T063 → T064)**
- T061-T062-T063 は線形依存
- T064 は T063 完了後 (本セッションで follow-up 設計済、 Phase 2 で T065 統合と同時実装)

**Phase C: GA 中核 (T065 → T066)**
- T065 NSGA-II core
- T066 CPPS FSM + archive (lex key #4 c_pass_depth は T064 follow-up で SSOT 確定済)

**Phase D: 運用制御 (T067 → T068 → T069)**
- T067 Loop closure (calibrate_state の dataset_span 撤廃 + LOG_ONLY → FAIL_CLOSED 切替)
- T068 Failure handling
- T069 Calibrate-gate scope

**Phase E: 監査/展開 (T073 → T074 → T075)**
- T071 完了後並行可
- T075 切替コミット = **全 17 件 Phase 2 完了 + synthesis Round 22 改訂後** の big-bang 1-shot

**Phase F: synthesis Round 22 改訂 (T076)**
- T058-T074 並行可、 T075 PR より先 merge or 同期 merge 推奨

### 2.2 各 TODO の Phase 2 PR 数予測

T058 が 7 PR 構成 (12 施策) だったが、 他 TODO は規模が異なる:
- 軽量 (= T059 epoch generation、 T072 DST table、 T076 synthesis 改訂): 1-2 PR
- 中規模 (= T060-T063, T067-T069, T070-T074): 2-4 PR
- 大規模 (= T064 + T065 + T066 統合 = 主要評価層 / GA 中核 / archive admission): 5-7 PR (T058 と同等)
- T075 切替コミット: **1 PR** (big-bang 1-shot)

合計 PR 数予測: ~50-80 PR (= T058 と同様 incremental モード前提).

---

## 3. T076 synthesis Round 22 改訂のタイミング

旧 handoff section 3.2 で T075 PR の blocked-by 5 件を整理済 (= new_cascade 採用しない / FM SSOT / DoD 分離 / threshold / stable clause anchor).

T076 着手タイミングの選択肢:
- **A**: T058 完了直後 (= 本セッション完了直後) に着手、 設計のみで src は触らない → T076 完了後に T059 着手
- **B**: T058 / T076 並行 (= 本セッションで両方着手済かのように) → T059 と並行可
- **C**: T058-T074 完了 → T075 PR 直前に T076 着手 (= 最も late)
- **D**: T058 完了 → T059 + T060 着手 → 並行で T076 概念設計開始 (推奨、 T076 設計と src 実装作業を並行)

旧 handoff section 8.2 推奨は「先 merge」 (= T075 PR より先 merge)、 ただし他 TODO PR との並行は柔軟. **D が現実的に最も効率的**:
- T076 は設計のみで src 触らないため、 T059-T074 Phase 2 配線と並行可
- T075 切替コミット直前に T076 改訂が完了していればよい

---

## 4. 次セッションの開始手順

### 4.1 まず読むもの (15 分)

1. **本ハンドオフ** (`devnotes/20260501-1535-cascade-port-T058-complete-handoff/handoff.md`)
2. **T058 PR 1-5 完了時点ハンドオフ** (`devnotes/20260501-1402-cascade-port-pr5-complete-handoff/handoff.md`) — T058 全体の経緯、 段階導入経験
3. **設計フェーズ完了時点ハンドオフ** (`devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md`) — 全体ロードマップ、 設計 18 件の詳細
4. **T058 詳細設計** (`devnotes/20260429-1912-todo-T058-schema-v2-contract/`) — Phase 2 配線の SSOT、 PR 1-7 の impl-review log を含む
5. **T058 DoD verification** (`devnotes/20260429-1912-todo-T058-schema-v2-contract/dod-verification-pr7.md`) — 完了確認チェックリスト

### 4.2 次セッション着手フロー

**A. T059 (dataset_epoch_id 値生成、 = generate_epoch_id_stub の deterministic 置換) 着手 (推奨)**

```
1. T059 詳細設計を Read (devnotes/20260{時刻}-todo-T059-epoch-window-manager/)
2. PR 数予測 (T058 経験から: 軽量 = 1-2 PR 想定)
3. PR 1 worktree 作成: git worktree add ./worktrees/todo-T059-pr1 -b todo/T059-pr1 main
4. uv sync
5. subagent invocation で実装 (= T058 で確立した worktree + subagent + Codex impl-review (gpt-5.3-codex / xhigh) + commit パターン継承)
6. ff-merge → worktree cleanup
7. T059 全 PR 完遂 → todo_manager.py close T059 → handoff 更新
```

**B. T076 (synthesis Round 22 改訂) 並行着手**

```
- メインラインで T059 を進めつつ、 別途 T076 概念設計から起こす (zenigame-fx-alpha-design skill)
- T076 は設計のみで src 触らないため T059-T074 と並行可
- T075 PR より先 merge を維持
```

**C. cascade port 全体整合性監査優先**

```
- T058 完了で実装基盤確立、 T059 着手前に「cascade port v2 全体整合性監査」 を実施
- 全 18 TODO の Phase 2 申し送り集約 + 依存関係グラフ + collider bias 規範整合性 + scaffold SSOT 整合性を Codex で全件 review
- T058 経験 (= incremental モード / signature 維持 / mode 連動 / stub fallback / 段階導入) が他 TODO で同様適用可能か確認
```

### 4.3 次セッションの最初の指示テンプレート

#### T059 着手 (推奨)
> 引き継ぎは `devnotes/20260501-1535-cascade-port-T058-complete-handoff/handoff.md` 読んで。 T059 (dataset_epoch_id 値生成 = generate_epoch_id_stub の deterministic 置換) から着手。 詳細設計は `devnotes/20260{時刻}-todo-T059-epoch-window-manager/`、 T058 で確立した worktree + subagent + Codex impl-review (gpt-5.3-codex / xhigh) + ff-merge のフローを継承。

#### T076 synthesis Round 22 改訂
> 引き継ぎは `devnotes/20260501-1535-cascade-port-T058-complete-handoff/handoff.md` 読んで。 T076 synthesis Round 22 改訂を概念設計から起こす (zenigame-fx-alpha-design skill)。 5 改訂候補 (new_cascade 採用しない / FM SSOT / DoD 分離 / threshold / stable clause anchor) を synthesis に反映。

#### 全体整合性監査
> 引き継ぎは `devnotes/20260501-1535-cascade-port-T058-complete-handoff/handoff.md` 読んで。 cascade port v2 全 18 TODO の Phase 2 配線着手前に「全体整合性監査」 を実施。 各 TODO の Phase 2 申し送り集約 + 依存関係グラフ + collider bias 規範整合性 + scaffold SSOT 整合性 + T058 経験から確立した規範の他 TODO 適用性を Codex で全件 review。

---

## 5. 未解決事項 / 次セッション最初に確認

1. **次に着手する TODO 選択**: T059 (推奨) / T076 / 全体整合性監査
2. **Run-26 崩壊原因の調査**: 本セッション開始時に yaml threshold 0.0 revert (commit `9718663`) のみ実施、 根本原因は未調査
3. **untracked reports (本セッション開始時から残置)**:
   - `reports/calibrate-gate/history.jsonl`
   - `reports/run-reports/run-1/diagnostics/`
   - `reports/run-reports/run-24/`、 `run-25/`、 `run-26.md`、 `run-26/`
   - これらは別系統の運用 RUN artifact。 PR 7 の Codex review で「test isolation 不備で pytest 実行時に再生成される副産物」 と指摘あり、 別 TODO で .gitignore 候補として扱う方針.
4. **TODO.md / TODO-closed.md の uncommitted 変更**: T058 close 操作で TODO.md / TODO-closed.md が更新されているが本セッションでは未 commit. 次 commit で取り込む or 即 commit.
5. **過去 handoff の historical archive 移動**: `devnotes/20260501-0253-...-design-complete/` と `devnotes/20260501-1402-...-pr5-complete/` を `devnotes/cascade-port-handoffs-historical/` に移動するか判断 (= 旧 handoff 慣習に従えば移動).

---

## 6. 進捗状況サマリー

```
設計 (Phase 1)            ████████████████████ 100% (T058-T075 全 18 件 APPROVED)
T064 follow-up            ████████████████████ 100% (c_pass_depth、 874e287)
T058 Phase 2 配線         ████████████████████ 100% (全 7 PR 完了 ✨)
T058 TODO close           ████████████████████ 100%
T059-T075 Phase 2 配線    ░░░░░░░░░░░░░░░░░░░░   0%
T076 synthesis Round 22   ░░░░░░░░░░░░░░░░░░░░   0%
T075 切替コミット (最終)  ░░░░░░░░░░░░░░░░░░░░   0%
```

---

## 7. T058 全 7 PR 一覧 (完了)

```
PR 1 (a4bf1bf): schema_contract.py 新規 + run_context.py 新規 + config.py SchemaContractConfig + default.yaml
PR 2 (f810c24): archive.py GENOMES_SCHEMA v2 4 field + flush lint
PR 3 (2a75de8): calibrate_gate_history v2 + calibrate_state scope key 拡張 + caller (calibrate_gate / run_ga) 呼出更新
PR 4 (a9733f3): diagnostics_sidecar v2 + fsp_updater v2 propagate
PR 5 (ba11aaa): run_ga.py RunContext 生成 + 全 artifact propagate + run_alpha_sieve mode 連動 + GenomeArchive.load 拡張 ← 中核 PR
PR 6 (2bd339a): Tier 2 軽量ガード追加 (display 系 4 scripts に assert_epoch_id_present_for_display + dataset_epoch_id display)
PR 7 (15f3ab6): 統合テスト + DoD 全項目確認 + docs / SKILL.md 更新 ← 最終 PR
```

合計 7 commit、 全 main fast-forward merge、 regression 0 件 (1563 tests passing).

---

## 8. Codex review 累積統計 (本セッション、 T058 全 7 PR + T064 follow-up)

| 区分 | Round 数 | model | reasoning |
|---|---|---|---|
| T064 follow-up 詳細レビュー | 2 | gpt-5.3-codex | high |
| T058 PR 1 impl-review | 2 | gpt-5.3-codex | xhigh |
| T058 PR 2 impl-review | 2 | gpt-5.3-codex | xhigh |
| T058 PR 3 impl-review | 2 | gpt-5.3-codex | xhigh |
| T058 PR 4 impl-review | 1 | gpt-5.3-codex | xhigh |
| T058 PR 5 impl-review | 1 | gpt-5.3-codex | xhigh |
| T058 PR 6 impl-review | 1 | gpt-5.3-codex | xhigh |
| T058 PR 7 impl-review | 2 | gpt-5.3-codex | xhigh |
| **合計** | **13 round** | gpt-5.3-codex | |

13 round 全 APPROVED (= 設計 follow-up 2 round + 実装 PR 11 round). 累積 token は概算で 6 - 8 M tokens.

---

## 9. T058 完了で確立した「次 TODO 着手テンプレート」

T059-T075 Phase 2 配線で各 TODO 着手時に以下のフローを再利用:

```
1. 詳細設計を Read (devnotes/{timestamp}-todo-T{NNN}-{topic}/)
2. PR 数予測 (= 12 施策超なら 5-7 PR、 中規模なら 2-4 PR、 軽量なら 1-2 PR)
3. PR 分割案を整理 (T058 PR 分割案を参考、 基盤層 → 既存拡張 → 中核配線 → 軽量ガード → 統合テスト)
4. 各 PR で:
   a. git worktree add ./worktrees/todo-T{NNN}-pr{M} -b todo/T{NNN}-pr{M} main
   b. cd worktree && uv sync
   c. subagent invocation (general-purpose) で実装委譲 (背景 / スコープ / DoD / Codex review 指示を inline で詳細記述)
   d. subagent: 実装 + tests + ruff + mypy + Codex impl-review (gpt-5.3-codex / xhigh) + commit (main merge は subagent では行わない)
   e. main conversation: 結果確認 → git merge --ff-only todo/T{NNN}-pr{M} → git worktree remove --force → git branch -d
5. 全 PR 完了後:
   a. uv run python scripts/alpha_factory/todo_manager.py close T{NNN} --closed-at "{JST}"
   b. handoff 更新 (= 本ハンドオフ書式)
```

特に重要な inline 制約 (= subagent prompt に必ず含める):
- AGENTS.md / CLAUDE.md / zenigame-fx-codex-review SKILL.md の使命・禁止事項を遵守
- Codex model `gpt-5.3-codex` 厳守 (gpt-5.5-codex は OpenAI 側未登録 = 404)
- 既存 caller signature 完全維持 (= default 値、 既存 test 互換)
- T064 follow-up 規範継承: status field 方式、 collider bias 独立性、 SSOT 厳密性
- 5 段階 grep DoD: PR スコープ外ファイルを構造的に touch 禁止
- summary.json の `schema_version: "1.1"` (string) 既存維持必須
- main merge は subagent では行わない (= main conversation の判断)
- 想定外問題は INCONCLUSIVE で明記

---

これで T058 全 7 PR 完了 + Closed 移動時点の handoff は以上. 次セッションで T059 着手 or T076 synthesis Round 22 改訂 or 全体整合性監査. T058 経験で確立した段階導入規範を T059-T075 で継承し、 全 17 TODO を完遂すれば cascade port v2 Phase 2 配線完了 → T075 big-bang 切替コミット → cascade port v2 完了へ.
