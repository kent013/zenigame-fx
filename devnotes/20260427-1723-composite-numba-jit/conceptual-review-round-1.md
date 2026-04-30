**前提**

- `verified`: 提供 profile では `evaluate_stage_a` と `run_backtest` がともに 16 回で、観測対象は Stage A のみです。
- `verified`: 観測された 1 backtest あたりの bar 数は 14,351 です。したがって profile 時の Stage A 実行は 60 日ではなく、CLI で与えた短い dataset 長に制約されています。
- `verified`: 現行 prepared path は [`src/dsl/strategy.py`](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py) で `(name, params)` 単位に ndarray を共有キャッシュしています。
- `verified`: 現行の T037 semantics は [`src/dsl/composite.py`](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py) の `compute_clause_score(...) != 0.0` を bar ごとに評価した集合です。
- `verified`: 提供 config では `dataset` は約 6 ヶ月なのに、`stage_b.window_months` は 18 ヶ月です。
- `unverified`: 将来の Stage A 実行が本当に 60 日相当の実 bar 数で `run_backtest` されること。
- `unverified`: 実行環境が概念設計どおり `Python 3.13 + NumPy 2.x + Numba 0.61+` で安定動作すること。
- `unverified`: clause 間で同一 primitive の再利用が少なく、提案 2D 行列化でメモリ重複が問題化しないこと。

**主要 findings**

1. `[High]` Stage B/C への主張が強すぎます。  
事実: profile は Stage A しか観測しておらず、しかも提供 config の `dataset` は約 6 ヶ月しかありません。にもかかわらず概念設計は Stage B 18 ヶ月前提の外挿とメモリ見積りを置いています。  
解釈: 「同じ engine 経路を通るので線形に効く」は方向としては妥当でも、倍率主張としては未検証です。現状の default config では Stage B 18 ヶ月自体が成立していない可能性があります。  
修正案: Stage B/C は `INCONCLUSIVE` を維持し、「kernel 再利用により同方向の改善は期待できるが、効果量は未検証」に下げるべきです。

2. `[High]` `bars_scale_a = 60d / 14d = 4.29x` は雑で、根拠としては弱いです。  
事実: 観測された 14,351 bars/backtest は、CLI で与えた短い dataset 上の Stage A 実行結果です。FX は週末が欠けるため、calendar day 比はそのまま cost 比になりません。  
解釈: 4.29x は方向感としては大きく外していない可能性がありますが、「妥当」と言い切るには bar 比で置き換える必要があります。  
修正案: `actual_stage_a_bar_count / 14351` に置換してください。60 日という日数比ではなく、実際の Stage A slice の bar 数比で外挿すべきです。

3. `[High]` 提案している `dir_value_arrs[total_dir, n_bars]` / `gate_value_arrs` は、現行よりメモリ回帰する設計です。  
事実: 現行 [`src/dsl/strategy.py`](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py) は同一 `(name, params)` の ndarray を共有しています。概念設計の flat 2D 行列は signal occurrence ごとに並べる前提なので、同じ primitive が複数 clause に出るとコピーが増えます。  
解釈: 現在のメモリ見積りは「unique signal 数」ではなく「出現回数」を持つ実装になるなら過小評価です。しかも 18 ヶ月の minute bar は 39 万より多くなりやすく、見積りはさらに甘いです。  
修正案: 2D 行列は `n_unique_signals x n_bars` にし、clause 側は index 配列で参照する形にした方がよいです。

4. `[Medium]` `on_bar` の 1.165s と composite 関連 tottime 0.473s の差分を、そのまま dict/loop overhead と見なすのは立証不足です。  
事実: [`src/dsl/strategy.py`](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py) の `on_bar` には warmup 判定、prepared 分岐、T037 集計、その後段のヒステリシスや発注ロジックも含まれます。profile 上も `compute_gate` 単体は切り出されていません。  
解釈: Numba 化でかなり削れる可能性は高いですが、0.69s 全額を削れる前提で 60-75% 削減を書くのは強すぎます。  
修正案: 期待効果は一段弱めるか、`values_per_clause` 構築だけを別計測してから書くべきです。

5. `[Medium]` 数値契約の書き方が矛盾しています。  
事実: 概念設計は「bit-identical」と書きつつ、判定条件は `np.allclose(atol=1e-6, rtol=0)` です。これは同じ意味ではありません。`fastmath=False` だけで bitwise equality は保証できません。  
解釈: 防衛可能なのは tolerance-based equivalence です。bit-identical を残すと、レビューで簡単に崩れます。  
修正案:  
- aggregate metrics / archive diff: `allclose(atol=1e-6, rtol=0)`  
- T037 の zero/non-zero semantics: 別途 exact parity test  
に分離してください。

6. `[Medium]` Numba 導入コストの扱いがまだ甘いです。  
事実: 提供 profile には import コストが大きく出ています。Numba を入れると import と初回 compile が追加されます。worker 並列時の cold start も未検証です。  
解釈: 長い本番 run では償却できても、短い検証 run や CI では悪化し得ます。  
修正案: warm cache / cold cache / `--max-workers 6` の 3 条件を分けて benchmark しないと、導入後評価がぶれます。

7. `[Low]` T037 の不変性は再現可能ですが、条件を明文化すべきです。  
事実: kernel が clause score を毎 bar 全 clause 分上書きし、Python 側で `score != 0.0` をそのまま使えば semantics は維持できます。  
解釈: ここは大きな設計リスクではありません。リスクは `abs(score) > eps` などに変えてしまうことです。  
修正案: 「全 clause 毎 bar 上書き」「判定は exact `!= 0.0`」を詳細設計に固定してください。

**論点別結論**

1. `bars_scale_a=4.29x`  
結論: 方向としてはあり得ますが、現状は `verified` ではありません。日数比ではなく実 bar 比に直すべきです。

2. `on_bar` 差分 0.69s  
結論: dict/loop が主因候補なのは妥当ですが、証明は不足しています。削減見込みは書けても、差分全額を Numba 対象とみなすのは危険です。

3. Numba の隠れコスト  
結論: 懸念は正当です。特に cold start と multi-worker 初回 compile は設計書の現在の記述だけでは足りません。

4. `fastmath=False` と数値同値性  
結論: `allclose` 契約なら妥当、bit-identical は言い過ぎです。

5. T037 active clause  
結論: exact `!= 0.0` を維持する限り再現可能です。ここは設計で縛ればよいです。

6. Stage B/C INCONCLUSIVE  
結論: その扱い自体は妥当です。ただし「線形に効く」は削るか弱めるべきです。

7. メモリ概算  
結論: 現状は楽観寄りです。特に dense 2D 化で duplicate signal を複製するなら見積りが崩れます。

**総評**

設計の方向自体は妥当です。反証で崩れたのは「Stage B/C への線形外挿」「bit-identical の表現」「2D 行列化のメモリ見積り」の 3 点です。  
このまま進めるなら、まず Stage A 限定の高速化として主張を絞り、データ表現は「unique signal matrix + index indirection」に修正するのが筋です。