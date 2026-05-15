**全体判定: APPROVED**

Round 1 の Critical 2 件は、概念設計レベルでは解消されています。特に `lossless` を「保存表現」と「比率計算」に分離した点、`max_drawdown_pct` / `calmar` を `decode` 後の現行 Decimal 経路で計算する点、`encode` の整数性・overflow fail-closed guard を入れた点は妥当です。

参照すべき先人の知恵としては、David Goldberg, 1991, “What Every Computer Scientist Should Know About Floating-Point Arithmetic” と、Paul R. Wilson et al., 1995, “Dynamic Storage Allocation: A Survey and Critical Review” が本件の数値表現・ allocator fragmentation の背景に対応します。

**Fact**

- `final_equity` / `max_drawdown` 絶対額は、`Decimal -> scaled-int64 -> Decimal` が lossless なら同値にできます。
- `max_drawdown_pct` / `calmar` は除算を含みます。
- 修正版設計は、比率指標を整数演算ではなく `decode` 後の Decimal 経路で計算すると明記しています。
- `encode` は整数性と `int64` 範囲を fail-closed で検証する設計です。
- `equity_curve` 支配項説は、修正版で仮説に降格されています。

**Interpretation**

- Round 1 Critical 1 は解消済みです。保存表現の lossless と比率計算の bit-exact を分けたため、論理の混線は消えています。
- Round 1 Critical 2 も概念設計としては解消済みです。`k=10` の根拠そのものより、fail-closed guard によって silent precision loss を禁止している点が load-bearing です。
- 本設計は `live_criteria` を直接改善しません。探索基盤の制約解除として North Star への間接寄与に留まる、という自己認識は適切です。

**残存指摘**

- [Warning] `k=10` の overflow 上界式は、詳細設計でさらに具体化が必要です。  
  Fact: `max_abs_equity_bound × 10^k < 2^63` という形は正しいです。  
  Fact: 「最大ポジション notional × 最大有利変動 + 初期資金」は、FX の `units * price_diff`、通貨換算、複数ポジション可否によって定義が変わります。  
  Interpretation: 現状の式は方向性として妥当ですが、まだ単位系が曖昧です。  
  修正提案: 詳細設計では `units`、quote/home currency、同時保有数、dataset 内 max/min price から `max_abs_equity_bound` を導出してください。実行時 guard は最後の防壁として残してください。

- [Warning] `Decimal` の textual / archive 表現の bit-exact は、数値 equality とは別に確認が必要です。  
  Fact: `Decimal("1.23") == Decimal("1.2300000000")` は数値として真です。  
  Fact: 文字列化や JSON 出力では表現が変わる可能性があります。  
  Interpretation: gate 判定は不変でも、archive diff や L1/L2 の比較で差分が出るリスクがあります。  
  修正提案: shadow test は `BacktestMetrics` の数値 equality だけでなく、summary/archive に出る serialized value も比較対象にしてください。必要なら既存出力フォーマットへ正規化してください。

- [Warning] `bar_time_epoch ns` の lossless 性は、変換実装に依存します。  
  Fact: float 経由の timestamp 変換は丸めを持ちます。  
  Fact: timezone 情報の同一性は epoch 整数だけでは保持されません。  
  Interpretation: UTC aware datetime 前提なら問題は小さいですが、L1/L2 契約上は明文化が必要です。  
  修正提案: epoch 変換は整数 arithmetic で行い、入力は UTC aware / monotonic / non-null を guard してください。復元 API が必要なら UTC datetime として復元する契約を明記してください。

- [Suggestion] `holding_cost_per_day_bps > 0` を fail-closed に留める扱いは、今回スコープでは許容できます。  
  Fact: 絶対制約にはスワップ・スプレッドの fitness 反映があります。  
  Fact: 本設計は holding cost 経路自体を変更しません。  
  Interpretation: T105 の承認を止める理由ではありませんが、将来 swap を有効化する時にこの実装が即座に設計課題になります。  
  提案: 詳細設計の前提に「AF 現行設定では holding cost 0。非ゼロ化時は encode guard が fail-closed し、T105 の追加設計が必要」と明記してください。

- [Suggestion] `equity_curve` 改修後の効果検証は、n≥5 に加えて metric parity と性能を同じ run artifact に残すとよいです。  
  Fact: RSS 改善と throughput 改善は別の指標です。  
  Interpretation: numpy 化で retained 小オブジェクトは減りますが、`compute_metrics` の transient decode による churn は残ります。  
  提案: `median/p95 RSS`、`genome/s`、`stage pass-fail 完全一致`、`archive serialized diff` を同一レポートで確認してください。

結論として、Round 2 設計は実装設計へ進めてよいです。承認条件は「serialized parity」「overflow bound の単位系確定」「UTC epoch 変換契約」の 3 点を詳細設計で落とさないことです。