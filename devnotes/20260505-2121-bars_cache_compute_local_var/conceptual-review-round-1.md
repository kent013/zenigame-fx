全体判定: CHANGES_REQUESTED

**Fact**
- 現行 `_compute` は [`_bars_cache.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_bars_cache.py#L59) の単純な pure compute で、T030 の本契約は `bars_to_mid_ohlc()` 側の read-only cache 返却です。[`_bars_cache.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_bars_cache.py#L87)
- T030 では cache correctness と `_compute` 直呼びの値一致が既にテストされています。[`test_bars_cache.py`](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_bars_cache.py#L72)
- `PriceBar.bid/ask` と `Ohlc.open/high/low/close` は property ではなく frozen dataclass の通常属性です。[`price.py`](/Users/ishitoya/repository/zenigame-fx/src/domain/price.py#L8)
- 現設計案は `bid/ask` の local 化に加えて、`enumerate(bars) -> range(len(bars))` という別最適化も混ぜています。[`conceptual-design.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2121-bars_cache_compute_local_var/conceptual-design.md#L46)
- bytecode 観点では、`bid/ask` local 化で削れるのは主に `b.bid` / `b.ask` の再読込で、各 bar あたりの `LOAD_ATTR` は大きく減りますが、`float(Decimal)` 8 回と ndarray 代入 4 回はそのまま残ります。つまり「効く方向」は正しいですが、支配項が完全に消える設計ではありません。

**Interpretation**
- 使命との整合性は良いです。1 ファイルの局所変更で、selection invariance を崩さず hot path を削る方向は妥当です。
- ただし、期待効果 `20-35%` と benchmark gate `15%+` はやや強すぎます。今回の改善は T089 lookup table より弱く、主因が `float(Decimal)` 側なら局所効果は single-digit から low-teens に留まる可能性があります。
- また、`range(len(bars))` まで入れると「attribute access 削減の検証」から外れ、T030 が `Sequence[PriceBar]` を受ける設計とも少しズレます。Round 1 は最小変更に絞るべきです。

[Critical] 効果見積もりとスコープがまだ広い  
修正提案:
- 反証可能仮説を 1 つに絞ってください。  
  `主因は float(Decimal) 8 回であり、bid/ask local 化の局所改善は 20-35% ではなく 5-15% かそれ未満である`
- 最小変更も 1 つに絞ってください。  
  `_compute` は `bid = b.bid; ask = b.ask` の local 化のみに限定し、`enumerate -> range(len)` は外す
- DoD は `ratio<0.85 必須` ではなく、`microbenchmark で非退行 + 改善確認` と `profile 再計測で _compute tottime が減ること` に下げるのが妥当です。

[Warning] `range(len(bars))` は T030 の抽象境界と相性が悪い  
修正提案:
- `_compute` の引数は `Sequence[PriceBar]` です。[`_bars_cache.py`](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_bars_cache.py#L59)  
  ここで index access 前提の最適化を混ぜるより、`enumerate` を維持して今回の仮説を純化した方が design-first です。

[Suggestion] メモリ効果は価値主張から外してよい  
修正提案:
- 「stack 軽量化」は事実としては微差ですが、意思決定を支える論点ではありません。[`conceptual-design.md`](/Users/ishitoya/repository/zenigame-fx/devnotes/20260505-2121-bars_cache_compute_local_var/conceptual-design.md#L81)  
  この施策の価値は純粋に CPU 時間短縮だけで十分です。

**質問への回答**
1. 20-35% は楽観的です。方向は正しいですが、T089 と違って支配項を丸ごと潰していません。`float(Decimal)` が残るので、まずは low-teens 以下を第一仮説に置くのが保守的です。
2. 中間変数削除の効果は微差です。効くのは `bo...ac` を消すこと自体ではなく、`b.bid` / `b.ask` の再読込を減らす点です。
3. `15%+` を pass/fail gate にするのは強すぎます。upside 目標にはよいですが、概念設計の必須条件には向きません。
4. 大きな副作用リスクはありません。数値同値性も保ちやすいです。注意点は `range(len)` を混ぜて別要因を入れないことです。
5. 残 blocker は 1 点だけです。  
   「仮説を保守化し、変更を `bid/ask local 化のみ` に絞る」  
   これが入れば次ラウンドで APPROVED に寄せられます。