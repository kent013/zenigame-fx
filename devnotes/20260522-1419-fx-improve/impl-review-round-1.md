[Critical]  
- なし

[Warning]  
- なし

[Suggestion]  
- `_selection_key` の docstring が T115 bool 記述のままなので、実装（連続値）に合わせて更新すると誤読を防げます。  
  [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/scripts/alpha_factory/run_ga.py:272)
- テストは主要動作を押さえていますが、`selection_pressure=True && threshold!=0.0` の fail-closed を直接検証する1ケースを追加すると回帰に強くなります。  
  [test_cross_pair.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/tests/alpha_factory/test_cross_pair.py:185)
- `cp_val` の `+inf/-inf` ガードは実装済みなので、`inf` 入力の明示テストも追加すると境界網羅が完成します。  
  [test_cross_pair_selection_pressure.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/tests/alpha_factory/test_cross_pair_selection_pressure.py:67)

ファイルごと判定  
- `run_ga.py`: APPROVED  
  default OFF で 10-tuple 不変、ON 時のみ `cp_val` 連続値挿入、`selection_key_schema` も `v3_5` 識別に更新済み。  
  [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/scripts/alpha_factory/run_ga.py:282)  
  [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/scripts/alpha_factory/run_ga.py:290)  
  [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/scripts/alpha_factory/run_ga.py:1671)
- `cross_pair.py`: APPROVED  
  連続値経路で死に設定になる threshold を fail-closed して一貫性あり。  
  [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/src/alpha_factory/cross_pair.py:121)
- `archive.py`: APPROVED  
  4観測列の schema/template/書込が揃っており、skipped/None 時も全Noneで整合。`pair_failure_count` も reason prefix 集計で妥当。  
  [archive.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/src/alpha_factory/archive.py:116)  
  [archive.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/src/alpha_factory/archive.py:272)  
  [archive.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/src/alpha_factory/archive.py:864)  
  [cross_pair.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/src/alpha_factory/cross_pair.py:326)
- `tests`: APPROVED  
  OFF bit-exact / 連続値順序 / None・NaN→`-inf` / schema 66→70 は確認できています。  
  [test_cross_pair_selection_pressure.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/tests/alpha_factory/test_cross_pair_selection_pressure.py:29)  
  [test_archive.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T116/tests/alpha_factory/test_archive.py:169)

全体判定  
- 実装は設計意図（gen0飽和回避の連続値圧、観測列での監視、default OFF bit-exact）と整合しており、selection非影響境界も維持されています。

【収束】APPROVED