**全体判定: CHANGES_REQUESTED**

**Fact**
- 現行 `compute_bucket_for_bar` は「24h ループ」ではなく、`BLOCK_BUCKET_RANGES_UTC.items()` の **3 要素走査**です。[session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L304)
- 実測 profile は `1,777,180 calls / tottime 0.703s / cumtime 0.905s` です。入力値としては妥当です。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2022-session_block_lookup_table/conceptual-design.md#L5)
- `BLOCK_BUCKET_RANGES_UTC` は `tokyo/london/ny` の 3 区間で、既存 test は 24h covering と no-overlap を検証済みです。[session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L74) [test_session_block.py](/Users/ishitoya/repository/zenigame-fx/tests/backtest/test_session_block.py#L446)
- `calendar.py` は top-level で `session_block` を import しています。一方 `session_block.py` から `calendar.py` への参照は現状 lazy import です。[calendar.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/calendar.py#L43) [session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L88)
- 現行設計・実装上の契約は、`compute_bucket_for_bar` 自体が partition violation 時に `RuntimeError` を送出する形です。[session_block.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/session_block.py#L304) [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260430-1810-todo-T070-backtest-engine-extension/detailed-design.md#L255)
- T088 は「hot path を局所最適化しつつ parity を厳格に置く」パターンで、今回の 1-file/SSOT 派生という方向性自体は近いです。[detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/detailed-design.md#L1)

**Interpretation**
- 使命整合性、スコープ、メモリ制約、禁止事項 5「過度な複雑化」の観点では概ね良いです。1 ファイル内の局所最適化で、探索量への間接寄与という位置づけも妥当です。
- ただし、期待効果の見積もりは強すぎます。残る `tzinfo` / `utcoffset()` validation と Python 関数呼び出しコストがあるため、`0.40 -> 0.05 μs` は現時点では未立証です。しかも現行は 3 要素走査なので、設計文書の前提がやや過大評価です。
- import 時 validation は、**builder が local data のみを使う限り**循環 import リスクは低いです。ただし「per-call RuntimeError と同等」は厳密には誤りで、失敗タイミングの契約は変わります。

**[Critical] 期待効果の仮説が強すぎる**
- 反証可能仮説: ボトルネックの主因は 3 要素走査ではなく、`utcoffset()` を含む validation と Python call overhead であり、lookup table 化だけでは `0.05 μs/call` までは下がらない。
- 最小変更: 概念設計の効果見積もりを「`0.05 μs` 断定」から「microbenchmark で要確認」に格下げし、DoD に `compute_bucket_for_bar` 単体 benchmark と profile 再計測を追加してください。RUN 全体効果も暫定値として保守的に置くべきです。

**[Warning] import 時 RuntimeError 化は厳密には契約変更**
- `compute_bucket_for_bar` が `RuntimeError` を投げる現契約を、module import failure に移すなら「同等」ではありません。
- 修正提案: 「startup invariant への変更」と明記し、既存 docstring/設計文書も更新してください。互換を厳密維持したいなら、import 時検証とは別に関数側の defensive path を残す設計にしてください。

**[Suggestion] C4 前提検証をもう一段明文化**
- `_build_hour_to_bucket()` の検証対象は「covering」だけでなく、`0<=start<end<=24`、重複なし、24 要素すべて充足を明記した方がよいです。
- 修正提案: `BLOCK_BUCKET_RANGES_UTC` を SSOT としつつ、builder の責務を「派生 + 構造検証」に限定すると T088 流用パターンとして綺麗です。

質問への回答です。
1. 循環 import リスクは低いです。現状の top-level 依存は `calendar -> session_block` で、builder が `session_block` 内の定数だけを使うなら新規循環は増えません。
2. 契約 break かという意味では、**厳密には yes** です。運用上は許容可能ですが、「同等」とは書かない方がよいです。
3. 75-87% は未立証です。特に `0.05 μs` は CPython では楽観的です。
4. 判定は `CHANGES_REQUESTED` です。上の 1 仮説 + 1 最小変更に絞れば、次ラウンドで収束可能です。