**前提検証**

対象設計、Round 1 レビュー、前提コード `genome.py` / `enforce.py` / `strategy.py` / `composite.py`、primitive docs を先に確認しました。以下、観察事実と解釈を分けて書きます。

**主要指摘**

1. mutate の `rate=1` 契約はまだ曖昧で、Round 1 指摘 2 は未解消です。事実として、本文は `n_edits ~ Binomial(K, mutation_rate)` により `rate=1 -> K 回編集確定` と書く一方、仮説は `少なくとも 1 編集` に留まり、テスト計画も `少なくとも 1 回の編集` という表現に後退しています。[conceptual-design.md:28](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L28) [conceptual-design.md:104](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L104) [conceptual-design.md:123](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L123) [conceptual-design.md:344](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L344) 解釈として、これでは「K 回の mutation step を試行する」のか「K 個の有効差分を保証する」のかが確定していません。後者を狙うなら、各 mutation kernel が必ず状態差分を生むまで再抽選する契約を追加すべきです。現状のままだと `rate=0` は明確ですが `rate=1 必ず K 編集` は設計だけでは保証しきれません。

2. dummy registry の docs 整合はまだ崩れています。事実として、§2.1 は primitive ID が `primitives.md` の name 準拠だと述べていますが、例示された `SessionTimeGate` / `VolRegimeGate` / `TrendStrengthMod` は docs 側の `SessionGate` / `ATRRegimeGate` / `TrendStrengthGate` と一致していません。[conceptual-design.md:51](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L51) [conceptual-design.md:231](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L231) [conceptual-design.md:232](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L232) [conceptual-design.md:233](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L233) [primitives.md:53](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/primitives.md#L53) [primitives.md:54](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/primitives.md#L54) [primitives.md:58](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/primitives.md#L58) 解釈として、Round 1 指摘 4 の「docs 整合」は category だけでなく ID 命名も含めて揃えた方が後続 T010 への置換境界が明確です。

3. crossover の fallback 条件は設計上ほぼ到達不能です。事実として、operator 表には `position_swap` と `risk_swap` が `always` で含まれているため、候補集合が空になる条件が定義されていません。それでも §2.2 は「候補集合が空なら parent-choice fallback」としています。[conceptual-design.md:79](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L79) [conceptual-design.md:80](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L80) [conceptual-design.md:91](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L91) 解釈として、`parent-choice` を正式 operator に入れるか、fallback を削除して「空にならない」前提にした方が実装とテストが明確です。

**観点別回答**

1. Round 1 指摘 1-8 への対応は、1/3/5/6/8 は概ね十分、2/4/7 はまだ不十分です。2 は上記 mutate 契約の曖昧さ、4 は dummy 名称の docs 非整合、7 はテストが `rate=1` の意味論と crossover 候補集合の境界条件をまだ直接固定できていない点が残っています。

2. crossover operator 集合の前提条件判定は大筋妥当です。ただし fallback 条件だけは漏れというより矛盾で、`always` operator を残す限り空集合になりません。[conceptual-design.md:73](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L73) [conceptual-design.md:91](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L91)

3. mutate の Binomial 定式化で `rate=0 必ず no-op` は実装可能です。`rate=1 必ず K 編集` は、`K mutation step を試行` なら可能ですが、`K 個の有効差分` まで保証する設計にはなっていません。ここは契約文言を固定してください。

4. `EvaluationResult.meta: Mapping[str, float]` は将来の後悔が出やすいです。`trades_count` のような整数は実務上ほぼ問題ありませんが、今後 `reason`, `pair`, `regime`, `fold_id`, `warnings` のような非 float 情報を載せたくなる可能性があります。[conceptual-design.md:172](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1552-clause-ga-operators/conceptual-design.md#L172) 最小限でも `Mapping[str, object]`、もう少し絞るなら `Mapping[str, int | float | str | bool]` くらいの方が安全です。

5. 新しいテストケースは前進していますが、まだ十分ではありません。追加推奨は 2 点です。1 つは「この親条件では利用可能 operator 集合が何になるか」を直接検証するテストです。もう 1 つは `rate=1` で検証したい対象を「attempted edits 数」なのか「effective diffs 数」なのか先に固定し、それに一致するテストにすることです。今の `構造比較で検証` だと lossy enforce や相殺で不安定になります。

6. 実装順序は概ね依存関係順です。`random_gen -> _dummy_registry -> complexity -> operators -> runner -> tests` で大きな破綻はありません。ただし上の 3 点を直さないまま `operators` と `test_operators` に入ると、契約曖昧さがそのままコードとテストに持ち込まれます。

REVISE