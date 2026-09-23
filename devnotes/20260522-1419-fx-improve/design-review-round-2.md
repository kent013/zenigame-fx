**判定**
設計レビューとしては **APPROVE** です。Round1 の Critical/Warning は、提示された反映内容で解消されています。

ただし、現在のワークツリー実装はまだ旧T115のままです。実装レビューとしては **REQUEST_CHANGES** です。

[Critical] 実装未反映  
現在の [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:282) はまだ `cp_pref=int(margin > threshold)`、[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1667) はまだ `v3_4_cross_pair_pressure`、[cross_pair.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:119) は threshold fail-closed 未実装です。archive も `cross_pair_mean_sharpe` 等の新列が未追加です。

最小変更:
1. `_selection_key` を `cp_val` 連続値に置換。
2. `selection_key_schema` を `v3_5_cross_pair_pressure_continuous` に変更。
3. `CrossPairConfig.__post_init__` に `selection_pressure and threshold != 0.0` の `ValueError` を追加。
4. archive に `cross_pair_mean_sharpe` / `cross_pair_min_sharpe` / `cross_pair_target_ratio` / `cross_pair_pair_failure_count` を追加。
5. `test_cross_pair_selection_pressure` と `test_archive` の期待値を更新。

設計そのものに残Critical/Warningはありません。  
【収束】設計は **APPROVED**、実装は未反映のため上記最小変更が必要です。

テストは未実行です。