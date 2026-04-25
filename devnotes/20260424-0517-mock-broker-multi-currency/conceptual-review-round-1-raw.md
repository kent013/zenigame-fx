## Verdict
APPROVED

## 主要論点
- `MockBroker` の single-instrument 前提に乗って `home=quote` を pair ごとに再定義する方針は、最小変更で T016 の構造的 `pair_failure` を外す設計として妥当
- `per-pair home` での Sharpe 集約は shadow screening 用の比較としては成立するが、将来の統合会計とは意味が違うため境界を明記し続ける必要がある

## 推奨修正（任意）
- `home_currency is not None and home_currency != meta.quote_currency` は Phase 4 まで明示的に fail-fast のまま維持する、と受け入れ基準かテスト名に書いておく
- `InstrumentMeta` へ `pip_size` / `display_precision` を足す理由は妥当だが、`CurrencyPair` との二重定義は将来 drift しやすいので、「現時点の SSOT はどちらか」を docs 上で一文固定しておく

## 根拠
- Fact: T016 の anchor 構成では全 target で少なくとも 1 つ非 JPY-quote pair を含むため、現状の `MockBroker` 制約は run 条件ではなく構造的 blocker になっている
- Fact: 設計文面上、`MockBroker` は 1 broker instance = 1 instrument の前提で閉じており、同一 instance 内で複数 home 通貨が混在しない
- Interpretation: この前提なら `EUR_USD` を USD 建て、`USD_CAD` を CAD 建てで完結させても、pair 単体の return series から計算する Sharpe 自体は意味を保つ。cross-pair で比較しているのは絶対 P&L ではなく無次元の risk-adjusted return だから
- Interpretation: ただしこれは「portfolio-level の共通 home 会計が不要な shadow 評価」に限って正当化される。Phase 4 の quote→home 換算とは別問題、という切り分けも設計上明確
- Fact: `(A1) home_currency=None なら meta.quote_currency` は、既存の `USD_JPY` / `EUR_JPY` では実効挙動が不変で、非 JPY-quote のみを新規に通すので後方互換の取り方として自然
- Fact: `home_currency` 引数を残す判断は、将来 Phase 4 で真の換算を入れるための interface 保持として正しい
- Interpretation: blocking な懸念は見当たらない。承認条件は「明示的な mismatched home はまだ未対応」という fail-fast 契約を実装・テストで固定することだけで十分です