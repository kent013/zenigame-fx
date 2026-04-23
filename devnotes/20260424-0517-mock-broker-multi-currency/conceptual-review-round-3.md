## Verdict
APPROVED

## 主要論点
- 必須修正 2 点（`initial_cash` スケール不変性、`units` スケール不変性）の検証が、Sharpe 直接比較 `abs(diff) < ε` に置き換わっており、反証可能性を満たしています。
- Phase 4 契約（`home != quote` かつ `fx_rate_provider is None` で fail-fast）も明示され、将来拡張時の退行防止インターフェースが確保されています。

## 推奨修正（任意）
- `margin 非拘束` の成立をテスト内でも明示確認（例: 期間中 `margin_call` 未発生）すると、P1/P2 検証の解釈がさらに強くなります。

## 根拠
- Fact: §9.2 に Sharpe 不変性の直接 assert（`initial_cash` と `units` の両方）が追加された。
- Fact: §8 に fail-fast 規約が明文化され、エラーメッセージ方針も更新された。
- Interpretation: Round 1/2 の必須指摘は充足しており、現時点で設計承認可能です。