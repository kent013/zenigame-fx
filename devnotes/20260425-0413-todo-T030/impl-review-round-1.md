前提を明示します（C4/C6準拠）。

- 事実: コマンド実行禁止のため、提示テキスト（抜粋diff・設計要約・テスト結果）を根拠にレビューしました。
- 事実: 設計制約（selection invariance, P9 import境界, lockstep, id再利用ガード）に対応する実装・テスト項目は提示上そろっています。
- 解釈: フル実装本文を直接読めていないため、呼び出し側の「配列不変（非破壊）」契約は追加確認余地があります。

[src/alpha_factory/primitives/_bars_cache.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T030/src/alpha_factory/primitives/_bars_cache.py)

- [Critical] なし
- [Warning] キャッシュが `np.ndarray` をそのまま共有返却するため、呼び出し側が in-place 変更すると後続計算へ汚染が伝搬します（旧実装は毎回新規配列生成）。現状テスト名からはこの退行検知が見えません。
- [Suggestion] `bars_to_mid_ohlc` の返却配列を read-only 化する回帰テスト（または「呼び出し側は不変利用」の明文化）を追加すると、selection invariance の保証が強化されます。
- [Suggestion] 稀な key 再利用パスで `OrderedDict` の再代入時に順序が更新されないケースを考慮し、miss時にも `move_to_end(key)` を入れると LRU 厳密性が上がります。

[src/alpha_factory/primitives/directional_generic.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T030/src/alpha_factory/primitives/directional_generic.py)

- [Critical] なし
- [Warning] なし
- [Suggestion] `_bars_to_mid_ohlc` のローカルalias維持は妥当です。既存呼び出しを書き換えず移行できており設計一致。

[src/alpha_factory/primitives/modulator_generic.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T030/src/alpha_factory/primitives/modulator_generic.py)

- [Critical] なし
- [Warning] なし
- [Suggestion] alias移行は妥当です。重複削除コメントの削除自体は問題ありませんが、設計トレーサビリティ目的でコミットメッセージかdevnotes側に理由が残っていれば十分です。

[src/alpha_factory/primitives/pair_specific.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T030/src/alpha_factory/primitives/pair_specific.py)

- [Critical] なし
- [Warning] なし
- [Suggestion] 中間変数化（`bo, ao` 等）は演算順序が同一で、提示条件下では bit-identical と判断してよいです（selection invariance観点で許容）。

[tests/alpha_factory/primitives/test_bars_cache.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T030/tests/alpha_factory/primitives/test_bars_cache.py)

- [Critical] なし
- [Warning] なし
- [Suggestion] 既存9件は要点を押さえています。追加するなら「返却配列の不変性（in-place変更が起きた場合の期待挙動）」の1件があると安全性が上がります。

全体判定: **APPROVED**

補足:
- P9 import境界、LRU lockstep invariant、id再利用ガード、alias rename は提示情報上いずれも成立。
- 禁止事項（閾値緩和・評価期間延長・GAハック等）に抵触する変更は見当たりません。