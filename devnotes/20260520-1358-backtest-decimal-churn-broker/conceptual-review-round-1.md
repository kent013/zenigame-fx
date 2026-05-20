**全体判定: CHANGES_REQUESTED**

この概念設計は、`main RSS` ではなく `worker RSS` に焦点を移した点、`float` を避けて正確性を守ろうとしている点、`B0 spike -> B1 本実装` の段階分けを置いた点は妥当です。  
ただし、現状のままでは「Decimal churn が支配要因」という因果が未確定で、しかも **24GB×6worker 制約に対する必要削減量の見積りが不足**しています。設計として通すには、**B0 の前に memory attribution を 1 段追加**し、さらに **scaled-int の厳密性契約**を明文化する必要があります。

**Fact**
- 設計文書上、`worker per-worker RSS = 9.5GB`、`main RSS = 2.3GB`、`primitives は float64 numpy cache 化済`、`MockBroker / DslStrategy / Trade` に `Decimal` が残っている、という整理は一貫しています。
- 設計文書自身も、`Decimal churn が worker RSS 9.5GB の支配要因` を **unverified hypothesis** と明示しており、この点は誠実です。
- `B0 profiling spike` を本実装の前提に置き、効果がなければ `REJECT` する設計になっており、Falsification-first の姿勢は入っています。
- `live_criteria` への直接寄与ではなく、OOM 回避の前提整備だと明示しており、使命との関係整理はできています。

**Interpretation**
- 問題は「仮説を置いている」ことではなく、**仮説の反証順序**です。現状案は `prototype を作って RSS を見る` に寄っていますが、その前に **live retained memory と transient churn のどちらが支配的か** を切り分けないと、`B0 の不成功` も `B0 の成功` も解釈が荒くなります。
- `scaled-int` は `Decimal` より軽くなる可能性は高いですが、**Python int もヒープオブジェクト**なので、「これで RSS が大きく下がる」はまだ言えません。特に path-dependent backtest では、演算コストより **Trade 蓄積・bars 保持・task recycle 前の残留メモリ**が支配している可能性があります。
- `24GB×6worker` を前提にするなら、`1GB/worker 削減` は成功条件として弱いです。現在値が本当に 9.5GB/worker なら、6worker 同居は設計上ほぼ成立しません。**必要なのは“有意差”でなく“運用可能域への到達”です。**

**観点別レビュー**

1. 使命との整合性  
[Warning] 整合しています。これは live_criteria 直接改善ではなく、探索を完走させるための基盤整備です。  
修正提案: 成果判定に `探索完走率` または `OOM なしで所定 worker 数を維持できること` を追加してください。`RSS が下がった` だけでは使命への接続が弱いです。

2. 禁止事項違反  
[Suggestion] 文面上の明確な違反はありません。`評価期間延長`、`live_criteria 緩和`、`取引回数削減`、`オーバーナイト` に触れていない点は良いです。  
注意点: 将来この施策の効果を評価するときに、`完走率改善` を `戦略品質改善` と混同しないでください。

3. 実現可能性  
[Critical] **B0 の前に B-1: memory attribution を入れるべきです。**  
現状は `Decimal churn 支配仮説` が未検証のまま prototype に進みます。これだと、効果が薄かった場合に「scaled-int が悪い」のか「触った箇所が支配的でなかった」のか判別できません。  
修正提案:
- `B-1 attribution` を追加する
- 計測対象は `peak RSS` だけでなく、`task 終了直前/GC 後/child recycle 後` の差分、`live Trade 件数`、`Decimal 系オブジェクトの残留量`、`bars 保持量`
- `tracemalloc 単独` ではなく、`RSS 実測 + Python object census + recycle 前後差` の併用にする  
[Critical] **scaled-int の厳密性契約が不足しています。**  
`scaled-int は exact` は一般論としては強すぎます。exact なのは「固定スケールで表現可能な量」に限られます。FX の `price / spread / swap / pnl / notional / account currency` それぞれでスケール定義が必要です。  
修正提案:
- `価格`, `数量`, `bps`, `損益`, `スワップ` の固定スケールを明記
- `丸め規則`, `境界変換点`, `オーバーフロー上限` を設計に追加
- `Trade.pnl + holding_cost == raw_pnl` に加え、`ロング/ショート`, `spread`, `swap`, `cross-currency` の golden case を列挙

4. 期待効果の妥当性  
[Warning] `>=1GB` は統計的にも運用的にも根拠が弱いです。  
C7 の観点では、Run 82 単発の 9.5GB を基準に閾値を置くのは粗いです。  
修正提案:
- 同一 seed・同一条件で複数回測定し、`median peak RSS` で比較
- 成功条件を `24GB / 想定同居 worker 数 / main RSS / headroom` から逆算する
- もし 6worker 前提なら、`1GB削減で足りるのか` を先に数式で示す

5. リスク  
[Critical] **公開 API 不変**は良いですが、境界での `int <-> Decimal` 変換が hot path に漏れると効果が消えます。  
修正提案:
- `Decimal を作るのは report/archive/API 境界のみ` と明記
- `on_bar`, `mark_to_market`, `holding_cost`, `snapshot` など bar 単位経路では Decimal を禁止する  
[Warning] `bit-identical` 目標は高すぎる可能性があります。  
もし既存実装が `Decimal` の quantize/rounding に依存しているなら、`bit-identical` ではなく `設計上同値` の定義が必要です。  
修正提案: `同値` の判定軸を `trade ledger`, `PnL`, `drawdown`, `Sharpe`, `pass/fail` に分解してください。

6. スコープの適切さ  
[Warning] `B0 -> B1` だけだと少し荒いです。  
修正提案: `B-1 attribution -> B0 spike -> B0.5 recycle 比較 -> B1` の 4 段階にしてください。  
これは feasibility-first により合っています。

7. メモリ制約 24GB×6worker  
[Critical] 現行設計の成功条件は、この制約と整合していません。  
`main 2.3GB + worker 9.5GB×6` は成立しません。`>=1GB/worker` 削減でも成立しません。  
修正提案:
- 「本当に 6 concurrent worker が要求か」を先に固定する
- 必要なら `1 worker あたり許容 RSS 上限` を先に定義する
- もし短期運用が `2worker` なら、その前提を明文化する
- 6worker が絶対なら、scaled-int 単独ではなく `recycle / retained 削減 / representation 変更` の複合策前提に修正する

8. 前提検証  
[Critical] C4 観点では、前提がまだ足りません。  
不足している前提は `worker RSS の内訳`, `retained vs churn の比率`, `6worker 運用要件`, `fixed-point scale contract` です。  
修正提案: 前提表に以下を追加してください。  
- `6worker 同居が本当に必要か`  
- `peak RSS の主因は retained か churn か`  
- `各 monetary/price quantity の scale は固定可能か`

9. Design-first  
[Suggestion] 方向性は Design-first です。既存最適化の到達点 (`T030`, `T106`, `T107`) を踏まえて次のボトルネックに進んでいるのは良いです。  
ただし、設計として通すには「どの仮説をどの順で落とすか」をもっと厳密に書くべきです。

10. Falsification  
[Warning] 反証条件は入っていますが、まだ弱いです。  
修正提案:
- `RSS 改善なし` だけでなく `throughput 悪化が大きい`, `recycle 短縮で同等以上の改善`, `retained 支配判明` も REJECT 条件に入れる
- `scaled-int 導入で exactness 契約が破れる` は即 REJECT と明記する

**Q1-Q3 への回答**

**Q1: 「正確性最優先で scaled-int」は妥当か。Decimal churn 低減は本当に効くか。**  
[Interpretation] 方針自体は妥当です。ただし **条件付き妥当** です。  
`float` を避ける判断は使命に整合します。一方で、`scaled-int なら RSS が下がる` はまだ未立証です。`Decimal` より `int` の方が一般に軽いのは事実寄りですが、path-dependent backtest では **live retained memory が支配的なら効かない** 可能性があります。  
結論: **scaled-int は採用候補として妥当だが、本命と決め打ちする段階ではない** です。

**Q2: B0 profiling spike を必須先行にする設計は適切か。先に RSS 内訳実測をすべきか。**  
[Interpretation] **先に内訳実測を入れるべきです。**  
ただし `tracemalloc 単独` は不十分です。必要なのは `B-1 attribution` で、`RSS 実測`, `task 境界`, `recycle 前後`, `live object census` を合わせて見ることです。  
結論: **B0 は必須でよいが、その前に B-1 を追加してください。**

**Q3: worker recycle 間隔短縮の方が費用対効果が高くないか。**  
[Interpretation] **短期の費用対効果は高い可能性が高いです。**  
これは低リスクで、exactness も壊しません。少なくとも `運用上の即効薬` としては有力です。  
ただし根治ではなく、CPU/起動オーバーヘッドやスループット悪化を招く可能性があります。  
結論: **recycle 短縮は代替ではなく、比較対象兼ガードレールとして先に試す価値があります。** 概念設計には `baseline / recycle 短縮 / scaled-int prototype` の 3-arm 比較を入れるべきです。

**最小修正での承認条件**
- `B-1 attribution` を B0 の前に追加
- `24GB×6worker` に対する必要 RSS 予算を先に定義
- `scaled-int` の scale/rounding/overflow 契約を明文化
- 成功条件を `>=1GB` ではなく `運用可能域への到達` で再定義
- `recycle 短縮` を比較対象として設計に組み込む

この修正が入れば、概念設計としてはかなり筋が良くなります。