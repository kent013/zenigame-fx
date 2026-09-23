**判定**
残っていた1件を最小修正したうえで、T117 は **APPROVED** です。

**修正した残件**
[run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T117/scripts/alpha_factory/run_ga.py:875) の `require_holdout=False` 経路で `bars_holdout=[]` なのにログが `bars_holdout[0]` を参照して落ちる問題が残っていました。  
`require_holdout=True` のときだけ holdout first/last をログへ載せる形に修正し、anchor Stage A-only ロードが holdout 不在でも通るテストを追加しました: [test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T117/tests/scripts/test_alpha_factory_run_ga.py:495)。

**追加確認**
- `with_pair` 属性保持テスト追加: [test_multi_pair_training.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T117/tests/alpha_factory/test_multi_pair_training.py:48)
- `pairs` 重複 fail-closed テスト追加: [test_multi_pair_training.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T117/tests/alpha_factory/test_multi_pair_training.py:34)
- `base_config_hash` が multi-pair 切替で変わるテスト追加: [test_calibrate_state.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T117/tests/alpha_factory/test_calibrate_state.py:543)

**検証**
- `uv run pytest ... -q` 対象13件 pass
- `uv run ruff check ...` pass
- `uv run mypy --explicit-package-bases ...` pass

【収束】APPROVED