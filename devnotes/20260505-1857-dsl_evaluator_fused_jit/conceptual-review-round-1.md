全体判定: `CHANGES_REQUESTED`

**Fact**
- 現在の profile で 5.236s を使っている `evaluate_all_bars` は、`DslStrategy.prepare()` 内で primitive 配列を前計算している経路です。[profile_20260505_171107.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_171107.txt#L32) [evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/evaluator.py#L187) [strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py#L243)
- `compute_composite_at_bar_jit` は `on_bar` の prepared path から bar ごとに呼ばれており、`evaluate_all_bars` からは呼ばれていません。[strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py#L391) [composite.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py#L145)
- profile の tottime 上、`compute_composite_at_bar_jit` 自体は 0.392s、`strategy.on_bar` 全体は 1.600s、`evaluate_all_bars` は 5.236s です。今回の概念設計はこの 3 つを同じボトルネックとして扱っています。[profile_20260505_171107.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_171107.txt#L79) [profile_20260505_171107.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_171107.txt#L101)
- `RegistryEvaluator.evaluate_all_bars()` は単一 `SignalConfig` の `spec.compute_all_bars(ctx)` を返す層で、clause weights や composite 用 buffer を持ちません。ここに composite kernel を入れる設計は現行責務と一致しません。[evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/evaluator.py#L187)
- clause 数の現行契約は `1-3 個` です。メモリ見積もりの `32 clauses` は現行契約と整合していません。[genome.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/genome.py#L102)
- T053 既存実装は、prepared/unprepared 同値と T037 exact parity をすでに強くテストしています。all-bars 化するならこの契約を壊さない設計が必要です。[tests/dsl/test_strategy.py](/Users/ishitoya/repository/zenigame-fx/tests/dsl/test_strategy.py#L603) [tests/dsl/test_composite_jit.py](/Users/ishitoya/repository/zenigame-fx/tests/dsl/test_composite_jit.py#L437)

**Interpretation**
- 使命との整合性自体はあります。速度改善なので live_criteria への直接寄与ではなく、探索量拡大への間接寄与です。
- ただし本案は C4 前提検証が不足しています。測れているのは「primitive 前計算」と「per-bar composite dispatch」と「その他 on_bar/engine コスト」の混在で、25.5 分削減の根拠がまだ立っていません。
- 禁止事項 1-4,6,7 への直接違反は見えません。最大の懸念は 5 の「過度な複雑化」で、`evaluator.py` まで触る案はそのリスクが高いです。

**指摘事項**
- `[Critical]` ボトルネックの層がずれています。概念設計は `evaluate_all_bars` の 5.236s を composite all-bars fused JIT の削減対象として扱っていますが、現行コード上それは primitive 前計算です。`compute_composite_at_bar_jit` の all-bars 化をやるなら対象は `DslStrategy.prepare/on_bar` 層であり、`RegistryEvaluator.evaluate_all_bars` 変更はスコープ誤りです。[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-dsl_evaluator_fused_jit/conceptual-design.md#L7) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-dsl_evaluator_fused_jit/conceptual-design.md#L40) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-dsl_evaluator_fused_jit/conceptual-design.md#L53)
  修正提案: 最小変更は 1 つです。設計を `DslStrategy.prepare()` で `composite_per_bar` を前計算し、`on_bar` は配列 lookup のみにする案へ限定してください。その前に、同一 `PreparedSignals` 入力で `for idx in range(n_bars): compute_composite_at_bar_jit(...)` と `compute_composite_all_bars_jit(...)` を比較する microbenchmark を追加し、「warm cache で Stage A 時間の 40%以上を削れる」を反証可能仮説として置くのが妥当です。
- `[Warning]` メモリ議論が現行契約とずれています。clause は `1-3` 個なので `86400 × 32 × 8B` は前提不整合です。さらに T037 が必要なのは最終的な active set であり、`out_clause_scores[n_bars, n_clauses]` 全保持は必須ではありません。
  修正提案: メモリ見積もりを `1-3 clause` 契約で再計算し、必要なら `active_any_by_clause` のような集約出力で full matrix を避けてください。
- `[Suggestion]` `compute_composite_at_bar_jit` の backward compat 維持は妥当です。現状でも unprepared path の挙動維持と oracle/test 比較に使われています。[strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py#L408) [tests/dsl/test_strategy.py](/Users/ishitoya/repository/zenigame-fx/tests/dsl/test_strategy.py#L603)

**質問への回答**
1. 妥当ではありません。概念設計だけでは判断不能で、実コードと profile を読むと `0.327s/eval` は primitive `evaluate_all_bars` 側です。composite per-bar dispatch 支配とは言えません。
2. そのままは類推できません。zenigame の 46s→18s は「未 fused な高水準演算を 1 JIT call にまとめた」実績ですが、こちらはすでに per-bar で fused kernel 化済みです。別ベンチが必要です。
3. メモリ局所性の主リスクは大きくありません。むしろ「不要な full matrix を持つ設計か」が論点です。現契約の 1-3 clause なら raw サイズ自体は重くありません。
4. backward compat 維持は残す方が良いです。unprepared path と数値 oracle の両方で価値があります。
5. 判定は `CHANGES_REQUESTED` です。

次ラウンドに向けた絞り込み:
- 反証可能仮説: `compute_composite_at_bar_jit` の per-bar dispatch は、warm cache 条件で Stage A 時間の少なくとも 40% を占める。
- 最小変更: `evaluator.py` には触れず、`DslStrategy.prepare()` 内だけで all-bars precompute を試す設計に修正する。