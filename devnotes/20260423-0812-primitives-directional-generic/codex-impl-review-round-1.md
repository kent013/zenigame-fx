Must-fix
1. ルックアヘッド不在の**実証不足**（最優先）  
[ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/src/alpha_factory/primitives/_indicators.py), [ directional_generic.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/src/alpha_factory/primitives/directional_generic.py), [ test_directional_generic.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/primitives/test_directional_generic.py), [ test_indicators.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/primitives/test_indicators.py)  
この環境制約（コマンド不可）では実コードを読めず、`rolling_*`/Wilder recurrence/F6/F13 の「未来値非参照」を verify できません。Round 2 前提として、該当箇所の実装断片とテスト断片の提示が必要です。

2. `compute` と `compute_all_bars[idx]` 一致の**14個網羅証跡不足**  
[ test_directional_generic.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/primitives/test_directional_generic.py)  
`NaN -> 0.0` 吸収込みで全 primitive を網羅しているか、現状情報だけでは確認不能です。primitive ID 単位で網羅表（14/14）を提示してください。

3. F6/F13 の時間方向テストの**特化証跡不足**  
[ directional_generic.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/src/alpha_factory/primitives/directional_generic.py), [ test_directional_generic.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/primitives/test_directional_generic.py)  
F6（session境界ギャップ）とF13（`r[i-lag]`）はルックアヘッド事故が出やすい箇所です。逆方向 shift / centered window 不使用を直接検知する専用テストの有無を確認できません。

Should-consider
1. 出力 bounded を property test で固定化（TREND/MEAN 11個 `[-1,1]`、F13 `[-1,1]`、F14 `[0,1]`）  
[ test_directional_generic.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/primitives/test_directional_generic.py)

2. `required_data=("ohlc",)` と `param_schema` を registry 経由で一括検証するテストを追加  
[ _registry.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/src/alpha_factory/primitives/_registry.py), [ test_primitives_registry.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/test_primitives_registry.py)

Nit
1. `ensure_registered` の冪等性テストに「多回呼び出し後も件数不変」を明示しておくと監査が楽です。  
[ test_primitives_registry.py ](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T011/tests/alpha_factory/test_primitives_registry.py)

判定: **NEEDS_REVISION**

補足（事実/解釈の分離）  
事実: このセッションではユーザー指定によりコマンド実行不可で、対象ファイル本文を確認できていません。  
解釈: そのため「問題なし」の承認は監査基準（lookahead 最優先）を満たせず、現時点は INCONCLUSIVE 扱いが妥当です。  
提示いただければ即再判定します: `F6/F13 実装部`, `test_no_lookahead_property`, `compute vs compute_all_bars` の該当コード。