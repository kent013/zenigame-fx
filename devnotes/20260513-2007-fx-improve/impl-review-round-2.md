**Findings**
- [Warning] T099 追加テストに ruff 違反があります。`uv run ruff check ...` で `F401` と `I001` が出ています。未使用の `import_module` は削除、関数内 import は ruff の並びに合わせる必要があります。該当: [test_generate_run_report_stage_b_reason.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T099/tests/scripts/test_generate_run_report_stage_b_reason.py:192), [test_stage_gate.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T099/tests/alpha_factory/test_stage_gate.py:2010)
- [Warning] [history.jsonl](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T099/reports/calibrate-gate/history.jsonl) に smoke/test 由来らしい record が追加されています。T099 実装差分としては不要で、null hash の calibration 履歴をコミット対象に含めるべきではありません。

**Round 1 指摘対応**
- `#1 effective fold のみ PnL 集計`: `RESOLVED`。`fold_pnl_candidate` は `try` 内で取得され、`oos_total_pnls.append` は `fold_sharpe is not None` の `else` 節だけで実行されています。legacy の `fold_sharpe` / `fold_reason` / `reason_counts` 経路は汚染していません。該当: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T099/src/alpha_factory/stage_gate.py:1498)
- `#2 CLI override と base_config_hash 順序`: `RESOLVED`。`stage_b_gate_kind` override は `_resolve_stage_a_threshold` 呼び出し前に移動されており、history guard の `compute_base_config_hash(cfg)` は override 後 cfg を見ます。該当: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T099/scripts/alpha_factory/run_ga.py:1443)
- `#3 known_codes 契約テスト`: `PARTIAL`。reason code 追加と routing テストは入っていますが、追加テスト自体が ruff clean ではありません。

**テスト確認**
- `uv run pytest tests/alpha_factory/test_stage_gate.py -k 'T099' tests/scripts/test_generate_run_report_stage_b_reason.py -q`
- 結果: `20 passed, 90 deselected`

**全体判定**
- `CHANGES_REQUESTED`
- Round 1 の Critical 2件は解消済みです。ただし、T099 追加テストの ruff 違反と不要な `history.jsonl` 差分が残っているため、この状態では `APPROVED` にはしません。