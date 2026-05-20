**全体判定**

`CHANGES_REQUESTED`

この概念設計の方向性自体は使命に整合しています。評価内容を変えずに wall-time を縮め、同一予算での探索試行回数を増やす、という狙いは妥当です。  
ただし現時点の記述では、**GA 結果完全不変**を担保するための設計契約が不足しています。とくに **数値表現の厳密一致契約**, **event-driven 分岐の完全列挙**, **同値性検証計画の粒度** が未確定なので、このままでは承認できません。

**前提検証 (C4)**

- `verified`
  - 提案文上の目的は「評価基準を変えずに速度改善」であり、禁止事項 1, 2, 3, 4, 6, 7 には直接触れていません。
  - 提案文上、メモリ問題は本件の主論点ではないと整理されています。
  - 提案文上、backtest は path-dependent であり、逐次ループの高速化が主眼です。

- `unverified`
  - 最新コードで本当に `Decimal` の丸め規約が全経路で一貫しているか。
  - `mid`, `spread_bps`, `margin_level`, `holding_cost` の計算式と丸めタイミングがどこで定義されているか。
  - `margin call / session close / EOD close / negative-equity drop / pending fill` の優先順位が現行実装でどう固定されているか。
  - `engine.run_backtest` の public 契約を保ったまま broker/strategy の内部意味論も保てるか。
  - Run 82 単発と profile 1 ケースだけで、期待速度向上を一般化してよいか。

**Fact (観察事実)**

- 本文は、現状の主要ボトルネックを `Decimal` を伴う pure Python の per-bar ループと整理しています。
- 本文は、改善案を「path 依存シミュレーション全体を 1 つの `@njit` kernel に畳む」と定義しています。
- 本文は、数値表現の候補を `scaled-int` と `float64` に限定して比較しています。
- 本文は、成功条件として `seed=9999` smoke の一致、best individual 一致、A/B pass count と pass/fail vector 一致を置いています。
- 本文は、評価期間延長や閾値緩和をスコープ外と明示しています。

**Interpretation (解釈)**

- 方向性は mission-aligned です。速度改善は探索回数を増やしうるため、live_criteria 達成確率に間接的に寄与します。
- ただし、速度改善の提案で最も重要なのは「速いこと」ではなく「**選抜順序を 1 bit も動かさないこと**」です。
- 現在の文書はその点を理解している一方、**不変性を保証する設計粒度まで落ちていません**。
- したがって、問題は方針ではなく、**設計契約の未定義**です。

**観点別レビュー**

1. 使命との整合性  
[Suggestion] 整合しています。評価の中身を変えず探索効率だけを上げる案として妥当です。  
修正提案: 文書の冒頭に「本件は selection pressure を一切変更しない performance-only change」と 1 文で明記してください。

2. 禁止事項違反の有無  
[Suggestion] 提案文の範囲では明示的違反はありません。  
修正提案: 「trade_count を減らして速くする設計は採らない」「session/EOD 強制クローズは完全維持」を非機能要件として明文化してください。

3. 実現可能性  
[Critical] `scaled-int` で Decimal と一致させるための**丸め契約**が未定義です。`mid=(bid+ask)/2`, `spread_bps`, `margin_level`, `holding_cost` は、整数化した瞬間に「どの単位で」「どのタイミングで」「どの丸め規則で」商を取るかが結果を変えます。ここが曖昧なままでは feasibility は未成立です。  
修正提案: 各演算について `入力単位 / 中間単位 / 出力単位 / 丸めモード / 丸めタイミング / 例外時処理` を表形式で固定してください。

[Critical] `1 つの njit kernel に畳む` としつつ、**event ordering contract** が書かれていません。event-driven 系は「何を表現できるか」より「どの順序で適用するか」が重要です。  
修正提案: `fill_pending -> mark_to_market -> holding_cost -> margin_call -> forced_session_close -> strategy_eval -> eod_close -> snapshot` のように、現行順序を列挙し、各イベントの read/write state を定義してください。

[Warning] `public 契約は可能な限り保つ` は弱いです。本件は API 互換より **意味論互換** が本体です。  
修正提案: 「public signature 維持」ではなく「observable behavior contract 維持」を主契約にしてください。

4. 期待効果の妥当性  
[Warning] `10〜数十×` は根拠の外挿が強いです。提示されている数値は Run 82 と 1 profile ケース中心で、C7 的には性能一般化のサンプルが不足しています。  
修正提案: 期待値を「Stage B 支配の run で大幅短縮を狙う」に留め、正式 KPI は `A/B/C 各 stage の median wall reduction` として複数 run で測る形に下げてください。

[Suggestion] ただし「Stage B が wall の大半を占めるなら、そこを速くするのが最も mission-aligned」という大枠の判断は妥当です。

5. リスク  
[Critical] `best individual 一致` と `pass/fail vector 一致` だけでは不十分です。途中世代で同点順位や tie-break が変わっても、最終 best が偶然一致する可能性があります。  
修正提案: 最低でも `全 genome の主要メトリクス`, `trade log`, `equity curve`, `constraint flags`, `selection input tensor` の一致を golden として比較してください。

[Critical] float64 を「条件付き次善」と残す書き方は危険です。本件の絶対制約は GA 結果完全不変です。float64 は feasibility 逆流の主要リスク源です。  
修正提案: 本設計レビューとしては **本線は scaled-int のみ** に限定し、float64 は別 investigation branch 扱いに分離してください。

[Warning] overflow リスクの扱いが薄いです。価格だけでなく `notional`, `PnL`, `cumulative equity`, `margin numerator/denominator`, `bps scaling` の合成で int64 範囲を超える可能性があります。  
修正提案: 最大価格、最大ロット、最大バー数、最大保有日数、最大 cumulative PnL を使った worst-case 上界計算を先に置いてください。

6. スコープの適切さ  
[Suggestion] スコープは概ね適切です。composite/primitive や worker 数に触れないのは良い切り分けです。  
修正提案: 初回スコープを「single pair / fixed config / single-thread reference parity」にさらに絞ると安全です。

7. メモリ制約  
[Suggestion] 本文の整理で十分です。本件の主争点ではありません。  
修正提案: なし。

8. 前提検証（C4）  
[Critical] 「Decimal と一致」「RNG 不使用」「current ordering 維持」はどれも本件の中核前提ですが、本文では assertion に留まっています。  
修正提案: 詳細設計では前提ごとに `source of truth` を明記してください。例: `丸め規約: broker.py の関数X`, `event順序: engine.py の関数Y`, `RNG不使用: 該当 call graph 調査結果`。

9. Design-first（C1）  
[Warning] 本文は profile と既存改善履歴を踏まえており、方向としては C1 に沿っています。  
修正提案: ただし承認には docs/devnotes 上で「現行 backtest の意味論契約」を先に書き出した 1 枚が必要です。コード高速化設計の前に、**何を不変とみなすか**を文書化してください。

**本件特有の重点論点**

A. 数値表現の選択  
[Critical] 主案は `scaled-int` が妥当です。理由は speed ではなく **selection invariance** です。`float64` は PnL や Sharpe の微差より、約定条件・margin 判定・trade_count の境界で危険です。そこが 1 回でもずれると feasibility 逆流で GA 選抜が変わります。  
修正提案: 設計として「本番採用候補は scaled-int のみ」「float64 は parity study 専用」と明記してください。

[Warning] ただし `scaled-int` でも「pip 整数」だけでは不足です。pip, pipette, quote-currency minor unit, bps, leverage ratio で必要スケールが異なる可能性があります。  
修正提案: 単一スケールではなく、`price_scale / cash_scale / ratio_scale` を分ける前提で設計してください。

B. njit kernel での実装可能性  
[Critical] Decimal と一致させるうえで最難所は除算です。`(bid+ask)/2` の 0.5 pip, bps 計算, holding cost の日割, margin_level の ratio は、整数化後に exact に扱うには**分子分母を保持したまま最後に丸める**設計が必要です。単純な `//` では一致保証になりません。  
修正提案: kernel 内部では `numerator, denominator` を持つか、演算ごとに固定小数点スケールを定めて「どこで丸めるか」を統一してください。

[Warning] overflow は price 自体より cross-multiplication で起きます。`equity * leverage_scale`, `notional * price_scale`, `bps * notional` が危険です。  
修正提案: worst-case 上界計算に加え、debug build では overflow sentinel を入れて reference 実行と比較してください。

C. path 依存ループを 1 つの njit に畳む妥当性  
[Critical] 表現自体は可能でも、**全分岐の漏れなき仕様化**が未記述です。とくに `margin call` と `session/EOD 強制クローズ` が同一 bar に競合する場合、どちらが先かで結果が変わります。  
修正提案: コーナーケース表を作ってください。最低限 `same-bar fill+stop`, `negative equity intrabar`, `session close and signal on same bar`, `spread filter hit`, `pending order then forced close`, `short holding_cost` を列挙すべきです。

[Warning] `strategy.on_bar` を kernel に吸収するなら、strategy の自由度をどこまで許すかを限定しないと設計が破綻します。  
修正提案: 今回の対象戦略を「columnar input から scalar signal を返す pure function 群」に限定し、stateful callback はスコープ外と明記してください。

**承認条件**

以下が揃えば再レビューで `APPROVED` を検討できます。

1. `scaled-int` 前提の数値契約表  
2. event ordering contract  
3. コーナーケース一覧と期待動作  
4. overflow 上界計算  
5. golden parity の比較粒度拡張  
6. `float64` を本線から外したスコープ明確化

現時点では、方針は良いが、**不変性の設計がまだ甘い**という評価です。