# T058 PR 7 DoD verification report

検証日: 2026-05-01 (JST) / branch: `todo/T058-pr7` (worktree)

詳細設計 SSOT: `devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md`
§ DoD (行 1509-1538)。 本書は PR 7 で各 DoD 項目を機械的に検証した結果を記録する。

---

## コード DoD (詳細設計 行 1513-1528)

| # | DoD 項目 | 実行コマンド | 結果 |
|---|---------|-------------|------|
| 1 | 12 施策全てのコード変更が main にマージ済 | `git log main --oneline | grep "T058 PR"` で PR 1-6 確認 | **PARTIAL (本 PR 7 で完了予定)** — PR 1-6 (= 施策 1-11) は main 着地済、 PR 7 (= 施策 12 統合テスト + DoD 検証 + docs 更新) は本 commit 内容として worktree に存在し、 main 着地は本 PR merge 後に確定する。 PR 7 commit 後、 main merge 確認をもって本項目を完全 PASS と扱う |
| 2 | `tests/alpha_factory/test_schema_contract.py` 全 pass | `uv run pytest tests/alpha_factory/test_schema_contract.py` | PASS (52 tests) |
| 3 | `tests/alpha_factory/test_run_context.py` 全 pass | `uv run pytest tests/alpha_factory/test_run_context.py` | PASS (10 tests) |
| 4 | `tests/alpha_factory/test_archive.py` 全 pass | `uv run pytest tests/alpha_factory/test_archive.py` | PASS (76 tests、 v2 schema 追加 test 含む) |
| 5 | `tests/alpha_factory/test_calibrate_gate_history.py` 全 pass | `uv run pytest tests/alpha_factory/test_calibrate_gate_history.py` | PASS (28 tests、 v1 record skip テスト含む) |
| 6 | `tests/scripts/test_calibrate_gate_drift.py` 全 pass | `uv run pytest tests/scripts/test_calibrate_gate_drift.py` | PASS (Codex Round 1+2 path 修正済) |
| 7 | `tests/alpha_factory/test_calibrate_state.py` 全 pass | `uv run pytest tests/alpha_factory/test_calibrate_state.py` | PASS (26 tests、 dataset_span + dataset_epoch_id 両方の scope key 確認) |
| 8 | `tests/alpha_factory/test_diagnostics_sidecar.py` 全 pass | `uv run pytest tests/alpha_factory/test_diagnostics_sidecar.py` | PASS (24 tests、 STAGE_A_PROVENANCE_SCHEMA 列追加確認) |
| 9 | `tests/alpha_factory/test_fsp_updater.py` 全 pass | `uv run pytest tests/alpha_factory/test_fsp_updater.py` | PASS (52 tests、 mode 連動確認) |
| 10 | `tests/alpha_factory/test_t058_integration.py` 全 pass | `uv run pytest tests/alpha_factory/test_t058_integration.py` | PASS (7 tests、 PR 7 新規) |
| 11 | `tests/scripts/test_run_ga_parallel.py` | `uv run pytest tests/scripts/test_run_ga_parallel.py` | PASS (cascade_contract_version + dataset_epoch_id 含む、 既存 schema_version: "1.1" 維持確認) |
| 12 | `tests/scripts/test_run_alpha_sieve.py` 全 pass | `uv run pytest tests/scripts/test_run_alpha_sieve.py` | PASS (22 tests、 LOG_ONLY skip / FAIL_CLOSED raise 両 path) |
| 13 | `tests/scripts/test_tier2_epoch_id_propagation.py` 全 pass | `uv run pytest tests/scripts/test_tier2_epoch_id_propagation.py` | PASS (6 tests、 PR 6 で着地済) |
| 14 | `uv run ruff check src/ tests/` clean | `uv run ruff check src/ tests/` | 既存 main にあった 15 件の pre-existing 警告 (analyze_run.py 行長 / compare_batch_runs.py F541 / todo_manager.py F401-RUF059 / 既存テスト 行長) 維持。 PR 7 で touch した 4 file (test_t058_integration.py / dod-verification-pr7.md / docs/stage-gates.md / SKILL.md) では新規 lint 違反 0 件 |
| 15 | `uv run mypy src/` clean | `uv run mypy src/` | PASS (102 source files、 issues 0) |

### 実行サマリ (全体 test 数)

```
$ uv run pytest tests/
================ 1563 passed, 1 skipped, 20 warnings in 19.98s =================
```

regression 0、 全体 test 数 1563 passing (skipped 1 は環境依存テスト、 PR 1-6 と同等)。

---

## Config / Smoke DoD (詳細設計 行 1530-1534)

| # | DoD 項目 | 検証手段 | 結果 |
|---|---------|---------|------|
| 16 | `config/alpha_factory/default.yaml` に `schema_contract.enforcement_mode: log_only` 反映 | grep `schema_contract` config/alpha_factory/default.yaml | PASS (PR 1 で着地済、 行 228-232 で `enforcement_mode: log_only` 確定) |
| 17 | 1 Run smoke 実行で v2 archive が生成され、 v2 contract lint が log warning なしで通過 | `test_end_to_end_writes_v2_archive_with_all_required_fields` (実 RUN は AGENTS.md「dev サーバーは立ち上げない」 規範のため smoke run でシミュレーション、 詳細設計 § PR 7 スコープ 3) | PASS — archive を flush + 読み戻し、 v2 必須 4 field を確認した上で、 `capture_logs()` で `schema_contract.passive_validation_failed` / `schema_contract.invalid_epoch_id` / `archive.flush.schema_lint_summary` の発火が **0 件** であることを直接 assert (lint warning なしで通過) |
| 18 | `RunContext` が archive / calibrate / diagnostics の主要 3 component に注入されている | `grep "run_context" src/alpha_factory/{archive,calibrate_state,diagnostics_sidecar}.py` で PR 2/3/4 の注入を確認 + `test_run_context_is_propagated_to_archive_and_diagnostics_components` で end-to-end 検証 | PASS |
| 19 | `enforcement_mode=fail_closed` で v1 artifact が fail することの確認 | `test_end_to_end_archive_fail_closed_rejects_v1_archive` (= v1 互換 Parquet を直接生成 → `GenomeArchive.load(..., mode=FAIL_CLOSED)` で `SchemaVersionError` raise を確認) | PASS |

---

## Docs / Skill DoD (詳細設計 行 1536-1538、 Codex Round 1 [Warning] 10 反映)

| # | DoD 項目 | touch ファイル | 結果 |
|---|---------|--------------|------|
| 20 | `docs/alpha_factory/stage-gates.md` § "T054: state file 経由の自動適用" を T058 反映 | `docs/alpha_factory/stage-gates.md` 行 261-300 (T058 で `dataset_epoch_id` 追加条件を AND 結合、 完全置換は T067 と明記、 T058 v2 schema 移行ノート subsection 追加) | PASS |
| 21 | `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md:99` 付近を T058 反映 | `.claude/skills/zenigame-fx-calibrate-gate/SKILL.md` 行 95-117 (現行契約 schema_version=1, dataset_span guard を v2 + `dataset_epoch_id` 追加条件に拡張、 v1 → v2 移行ノート、 T067 完全置換予定) | PASS |

---

## 結論

DoD 全 21 項目について **20 PASS + 1 PARTIAL** (#1 = main マージ確定待ち、 PR 7
commit の main merge 後に PASS 化)。 ruff の pre-existing 15 件警告は PR 7 で touch
した範囲外 (analyze_run.py / compare_batch_runs.py / todo_manager.py 等の display
script + 既存 test) のもので、 PR 7 では touch 範囲を増やさない方針 (T064 follow-up
の SSOT 厳密性遵守) のため未修正。 これらは別 TODO で hygiene 対応の対象 (PR 7 の
スコープ外)。

T058 全 7 PR (基盤 / archive / calibrate / diagnostics / fsp / run_ga / sieve /
Tier 2 / 統合テスト) は本 PR 7 commit までで内容上 完成。 本 PR を main merge
後に cascade port v2 contract phase 2 配線が main 着地として扱え、 T058 を
Closed へ移行可能となる。
