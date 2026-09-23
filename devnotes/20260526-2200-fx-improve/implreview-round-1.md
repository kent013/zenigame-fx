**Critical**
1. `OFFで32本固定` が「同一プロセス内の連続実行」で破れます。`register_experimental()` はグローバル registry に F15 を永続追加し、OFF実行時に除去されません。  
[directional_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/directional_generic.py):742  
[run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py):2213  
[_registry_bridge.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/_registry_bridge.py):52  
[_registry.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_registry.py):86  
事実確認: `ensure_registered()`→32、`register_experimental()`→33、再度`ensure_registered()`でも33のまま。  
修正案: `run_ga.main()` 冒頭で registry を `clear()` して毎回 `ensure_registered()` し、flag ON 時のみ `register_experimental()`（毎runで状態を再構築）にしてください。

**Warning**
1. look-aheadテストが NaN 遷移を検知できません。`np.isfinite(arr1)` マスク比較のみで、`NaN -> finite` のリークを見逃します。  
[test_directional_generic.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_directional_generic.py):504  
修正案: `np.testing.assert_allclose(..., equal_nan=True)` で全要素比較し、週末ギャップ（bucket不連続）ケースと単一bucketケースも追加。

**Nit**
1. `htf_open` が未使用です（可読性ノイズ）。  
[directional_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/directional_generic.py):685

**確認結果（問題なし）**
- look-ahead本体ロジック（`completed = pos - 1` で B-1のみ参照）は設計どおりで、`reduceat`集約自体も現在bucketを参照しない限りリークしません。  
[directional_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/directional_generic.py):697
- 空配列/単一bucketは `n_buckets < 2` で全NaN返却、`[-1,+1]` bounded・`_EPS` によるゼロ除算回避・純粋numpyでの決定性も妥当です。  
[directional_generic.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/directional_generic.py):679

総合判定: **要修正(Critical 1件)**