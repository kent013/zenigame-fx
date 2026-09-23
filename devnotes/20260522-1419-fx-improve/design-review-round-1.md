施策判定: **REQUEST_CHANGES**

[Critical] 実験識別が壊れる（bool版と連続値版を区別できない）  
修正案: `selection_key_schema` を `v3_4` から連続値専用に bump してください（例: `v3_5_cross_pair_pressure_continuous`）。  
事実: 現行は pressure有効時に常に `v3_4_cross_pair_pressure` を出力する実装です。[run_ga.py:1666](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1666)  
解釈: R88(bool) と R89(continuous) の比較で schema 識別不能になり、A/B検証と監査が崩れます。

[Warning] `selection_pressure_margin_threshold` が連続値化後に死に設定になる  
修正案: 連続値経路では `threshold!=0` を fail-closed で拒否するか、設定キー自体を削除してください。  
事実: 現行 `_selection_key` は threshold を使う bool tie-break 前提です。[run_ga.py:260](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:260)  
解釈: 「設定したのに効かない」サイレント挙動は運用事故要因です。

[Warning] 天井判定を単一seed中心で確定するのは早い  
修正案: 天井判定は最低でも複数seedで `max(mean_sharpe_cross)` を確認してから確定にしてください。  
事実: pass条件は `mean/min/ratio` の3条件です。[cross_pair.py:352](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/cross_pair.py:352)  
解釈: 1 run の未達だけで「単一ペア学習の天井」を断定すると誤判定リスクがあります。

[Suggestion]  
- 観測列追加方針（aggregate + mean + min + ratio）は妥当です。`selection` が読むのは現状 `cross_pair_aggregate_fitness` のみで、観測専用化は守りやすいです。[run_ga.py:1303](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1303) [archive.py:853](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:853)  
- 追加で `pair_failure` 系（count/flag）を archive 観測列に持つと、aggregate上昇の偽陽性監視が強くなります。  
- テスト更新範囲は少なくとも `test_cross_pair_selection_pressure` と schema列数/nullable確認系です。[test_cross_pair_selection_pressure.py:45](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_cross_pair_selection_pressure.py:45) [test_archive.py:188](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:188)

全体判定: 方向性は正しいですが、**識別子バージョン管理と死に設定の扱い**を閉じるまで承認不可です。

【収束】  
反証可能仮説: `selection_pressure=True` で continuous化すると、世代ごとの `cross_pair_aggregate_fitness` 上昇に対して `cross_pair_mean_sharpe` も同方向に上昇する（同時に `cross_pair_target_ratio` が劣化しない）。  
最小変更: `selection_key_schema` を連続値版に bump し、`selection_pressure_margin_threshold!=0` を fail-closed にする。