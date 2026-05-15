**全体判定**

CHANGES_REQUESTED

**前提検証（C4）**

- Verified（提供テキスト上）: 本設計の目的は `live_criteria` の直接改善ではなく、GA 探索基盤のメモリ制約を下げる間接改善です。これは North Star と矛盾しません。
- Verified（提供テキスト上）: 精度 load-bearing 領域を `Decimal` のまま残し、`equity_curve` を主対象にするスコープ切りは、禁止事項 #5 の観点では概ね妥当です。
- Unverified: `equity_curve` が churn の量的支配項であることは、提示文では仮説としては強いですが、最新コード実体と計測結果の再確認はできていません。
- Unverified: `trade_sharpe_raw` が `equity_curve` 非依存であること、`max_drawdown_pct` / `calmar` の現行 Decimal 計算契約、`equity` の小数桁上限は、今回はコード未確認です。
- Unverified: C1 Design-first は「提示された devnotes 要約を参照した」水準では満たしていますが、docs/devnotes/git log 実体の直接確認まではできていません。

**指摘**

- [Critical] `max_drawdown_pct` と `calmar` の「整数演算で bit-exact」という主張は、このままでは成立しません。  
Fact: `final_equity` と絶対額 `max_drawdown` は、`Decimal -> scaled-int64 -> Decimal` の往復が lossless なら一致可能です。  
Fact: `max_drawdown_pct = dd / peak * 100` は除算を含みます。`calmar` も比率計算を含みます。  
Interpretation: lossless なのは「保存表現」です。比率計算まで整数のままで bit-exact になるわけではありません。現行値と一致させるには、除算時点で現行と同じ `Decimal` 文脈・丸め規約を再現する必要があります。  
修正提案: 設計文の主張を「`final_equity` / `max_drawdown` は exact、`max_drawdown_pct` / `calmar` は scaled-int64 から `Decimal` を復元して現行と同じ演算経路で算出する限り exact」に修正してください。併せて、旧実装と新実装を同一入力で二重計算し、gate-feeding 指標の完全一致を検証する shadow test を必須化してください。

- [Critical] スケール係数 `k` を「dataset/instrument の Decimal 精度から決める」という記述は根拠不足です。  
Fact: `equity` は価格そのものではなく、約定価格、数量、スプレッド、holding cost、通貨換算、累積損益の結果です。  
Interpretation: `PriceBar` の桁数だけでは `equity` の必要小数桁上限を保証できません。ここを誤ると lossless 性が崩れます。  
修正提案: `k` の根拠を「`equity` が取りうる最小量子」に置き換えてください。最善は会計量子を明示することです。明示できないなら、移行期間は旧経路と並走し、各 bar で `equity == decode(encode(equity))` を fail-closed で検証してください。

- [Warning] `int64 overflow` は「guard を入れる」だけでは不十分で、設計上の確認方法を先に固定すべきです。  
Fact: `numpy.int64` は overflow 時に静かに壊れる経路を持ちます。  
Interpretation: 金額計算と L1/L2 契約の観点では、実行時に検知できても「途中で壊れた後に気づく」設計は弱いです。  
修正提案: `scaled` は一度 Python `int` で生成し、`abs(value) <= 2^63-1` を確認してから `np.int64` へ cast する手順を明記してください。さらに、上界確認式 `max_abs_equity_bound * 10^k < 2^63` を devnotes に残してください。`max_abs_equity_bound` は初期資金ではなく、設定上取りうる最大ポジション・最大有利変動・換算を含む保守上界で定義すべきです。

- [Warning] 「`equity_curve` が churn の量的支配項」という表現は、現時点では仮説として扱うべきです。  
Fact: retained object 数では `equity_curve` が有力です。  
Fact: 一方で、pymalloc 断片化は「大量に生まれて消える小オブジェクト」でも悪化します。`MockBroker` 内部の中間 `Decimal` churn は未計測です。  
Interpretation: `equity_curve` のみで十分かは、まだ falsification が終わっていません。  
修正提案: 設計文の表現を「第一候補」に落とし、受け入れ条件として「改修後に worker RSS と backtest throughput を再計測し、残差が大きければ Phase 1 で `MockBroker` 内部 churn 計測へ進む」を追加してください。Phase 0 後回しの判断自体は妥当です。

- [Warning] `BacktestResult.equity_curve` の公開型変更は、メモリ対策としては小さくない波及です。  
Fact: 設計文でも consumer 8 箇所追従を認識しています。  
Interpretation: ここは禁止事項 #5 には直ちに抵触しませんが、接続漏れと report 系の暗黙依存が主要リスクです。  
修正提案: `BacktestMetrics` は現状維持のまま、`equity_curve` は内部表現を包む専用型にして access API を限定するか、少なくとも追従対象一覧を設計書に固定してください。`paper_trading` 等の周辺経路は「未確認」と明記すべきです。

- [Suggestion] 期待効果の評価は、sample size を先に固定した方がよいです。  
Fact: 現行記述には性能検証の n と観測指標がありません。  
Interpretation: メモリ改善は run-to-run ばらつきがあります。  
提案: 同一 seed・同一 dataset・同一 worker 数で、改修前後それぞれ n>=5 の worker lifecycle を比較し、median/p95 RSS、swap 発生有無、genome/s を記録してください。

**観点別まとめ**

- 使命との整合性: [Suggestion] 間接寄与として妥当です。採否条件は「metric parity を壊さず、探索基盤制約を緩めること」に限定すべきです。
- 禁止事項違反: [Suggestion] 現状スコープなら #5 の過度な複雑化ではありません。ただし公開型変更の波及は最小化が必要です。
- 実現可能性: [Warning] 実装自体は可能です。lossless 条件と overflow 設計を先に固めないと危険です。
- 期待効果: [Warning] 方向性は妥当です。支配項断定はまだ早いです。
- リスク: [Critical] 比率指標の exactness と `int64` overflow が最大リスクです。
- スコープ: [Suggestion] `Trade` / `MockBroker` を今回外す判断は妥当です。Phase 0 計測条件を明文化すべきです。
- メモリ制約: [Suggestion] 24GB 制約に対しては意味があります。`maxtasksperchild` 依存を下げる補完策として整合的です。
- 前提検証: [Warning] 重要前提の一部はコード未確認です。設計書側で「verified / unverified」を明示してください。
- Design-first: [Warning] 提示テキスト上は devnotes 参照ありです。git log・実コード実体の直接確認までは到達していません。

この設計は方向としては良いです。却下理由は「numpy 化そのもの」ではなく、「lossless の定義が保存表現と比率計算で混線していること」と、「scale/overflow の根拠がまだ設計として弱いこと」です。ここを修正できれば APPROVED 寄りです。