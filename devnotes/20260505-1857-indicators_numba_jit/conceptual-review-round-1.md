全体判定: **CHANGES_REQUESTED**

絞り込みます。

- 反証可能仮説: **`_wilder_smooth` を「呼び出し側で NaN 除外済み」前提に寄せて `np.nanmean` を `np.mean` 相当に落とすと、`adx()` の現行 NaN/warmup 契約が壊れる。**
- 最小変更: **概念設計から `_wilder_smooth` の「NaN 除外契約依存」記述を外し、現行の NaN seed/skip semantics を保持する方針に修正する。加えて `adx` 経由の NaN parity テストを 1 本明記する。**

**Findings**
- [Critical] `_wilder_smooth` の NaN 契約が現行実装と不整合です。  
  Fact: 現行 `_wilder_smooth` は seed で `np.nanmean` を使い、途中の `NaN` 入力では前値維持を行っています。[ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L214) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L229) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L234) さらに `adx()` は `dx` の warmup 区間に `NaN` を作ったうえで `_wilder_smooth(dx, n)` を呼んでいます。[ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L468) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L471) 一方、概念設計は `_wilder_smooth` を「呼び出し側で NaN 除外」前提に寄せています。[ conceptual-design.md ](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/conceptual-design.md#L37) [ conceptual-design.md ](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/conceptual-design.md#L55) [ conceptual-design.md ](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/conceptual-design.md#L71)  
  Interpretation: ここをそのまま実装すると、最も重い `_wilder_smooth` の意味論を変える危険が高いです。速度改善の設計としては成立しますが、現状のままでは「数値同値性」を主張できません。  
  修正提案: `_wilder_smooth` は first scope に残してよいですが、「NaN seed/途中 NaN は現行互換を保持」と明記してください。もし Numba 実装が煩雑なら、Round 1 は `rolling_max/min` の 2 関数に限定し、`_wilder_smooth` は別設計に分ける方が安全です。

- [Warning] C1/C4 の根拠提示は一部不足しています。  
  Fact: profile 上で target line は整合しています。`_wilder_smooth` 1.000s、`rolling_max` 0.465s、`rolling_min` 0.463s、`ema` 0.262s が `sort=tottime` に出ています。参照は [profile_20260505_171107.txt](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/profile/profile_20260505_171107.txt) です。実装 line も一致します。[ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L116) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L137) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L191) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L214) ただし概念設計中のテスト参照は実在パスとずれており、line 番号もありません。実際の既存テストは [test_indicators.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_indicators.py#L77) と [test_indicators_causality.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_indicators_causality.py#L84) です。  
  Interpretation: 「既存 test を参照済」の主張は方向として正しいですが、設計書の証跡としては弱いです。  
  修正提案: 既存テストの正しいパスと line を設計書に明記し、特に `_wilder_smooth` 由来の `atr/adx` テスト箇所を根拠として足してください。[ test_indicators.py ](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_indicators.py#L168) [ test_indicators.py ](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_indicators.py#L261)

- [Warning] 効果見積りは「関数局所」と「RUN 全体」が少し混ざっています。  
  Fact: repo にはすでに `numba>=0.61` が入り、既存の `@numba.njit(cache=True, fastmath=False)` もあります。[pyproject.toml](/Users/ishitoya/repository/zenigame-fx/pyproject.toml) [composite.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py#L144) なので実現可能性は高いです。一方、今回 profile に出ている `ema` は 0.262s で、設計書の「推定 0.4s」より小さいです。[ conceptual-design.md ](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-indicators_numba_jit/conceptual-design.md#L12)  
  Interpretation: `zenigame` の 93% 削減は「同じ種類の loop/JIT パターン」という意味では参考になりますが、そのまま本件に移植できる証拠ではありません。50-70% を仮説として置くのは妥当ですが、5-8% の end-to-end 削減は benchmark で反証可能な仮説として書くべきです。  
  修正提案: 期待効果は「target 関数群で 50-70%」「RUN 全体で 3-6% を first hypothesis、5-8% は upside」と段階化すると堅いです。

- [Suggestion] `rolling_max/min` の circular buffer 化は feasible ですが、設計文言を少し正した方がよいです。  
  Fact: 現行実装は `<=` / `>=` で等値も drop しています。[ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L129) [ _indicators.py ](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_indicators.py#L148)  
  Interpretation: 値出力だけを見る限り等値保持/非保持の差は出にくいですが、「bit-identical」主張ならここは曖昧にしない方がよいです。  
  修正提案: 「等値は残す」を削除し、「現行 comparator をそのまま再現」と書いてください。あわせて bit-identical を言うなら `allclose(1e-12)` ではなく exact parity テストに寄せるか、主張を「numerically identical」に下げるのが適切です。

**Fact**
- target 層の選定自体は profile と整合しています。前回 reject の「層誤り」は今回は解消しています。[REJECTED.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-1857-dsl_evaluator_fused_jit/REJECTED.md)
- 実現可能性は高いです。repo 既存で Numba 採用済み、対象も ndarray 入出力の loop です。[composite.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py#L144)
- スコープは概ね適切です。`rolling_max/min` と `_wilder_smooth` は hot path として十分根拠があります。`ema` は optional 扱いが妥当です。

**Interpretation**
- 禁止事項 5「過度な複雑化」には、**現状の `_wilder_smooth` NaN 契約を変えない限り**抵触しません。`deque -> circular buffer` も 2 関数に閉じるなら許容範囲です。
- 最大リスクは性能ではなく意味論です。特に `adx()` を経由した NaN/warmup 契約が設計書上で過小評価されています。
- メモリ制約は実務上問題ありませんが、「増加なし」ではなく「追加 workspace は O(n) だが既存 deque より悪化しない見込み」と書く方が正確です。

**質問への回答**
1. **ターゲット層は整合しています。** 今回は `_indicators.py` の hot path を正しく見ています。前回の層誤りは解消済みです。  
2. **93% の直接類推は不可、50-70% の関数局所仮説は妥当です。** ただし RUN 全体 5-8% はまだ強めです。  
3. **`deque`→circular buffer 自体の値同値リスクは低いです。** ただし comparator の再現を曖昧にしないこと。  
4. **`_wilder_smooth` の `np.nanmean`→`np.mean` 置換は現状では不整合です。** `adx()` が現に NaN を含む入力で `_wilder_smooth` を使っています。  
5. **全体判定は CHANGES_REQUESTED です。** 修正点は 1 つで十分で、`_wilder_smooth` の NaN 契約を現行互換に明記できれば、次ラウンドで APPROVED に寄せられます。