## Verdict
NEEDS_REVISION

## 主要論点
- `MockBroker` の `home_currency=None -> quote採用` と `quote!=home` fail-fast 方針自体は、Phase 2 制約下で妥当です。
- ただし、scale 不変性テスト設計に数理的不整合があります（`initial_cash` だけを変えて `equity returns` 同一を期待している点）。
- Phase 4 予約インターフェース名が文書内で不一致です（`fx_rate_provider` と `fx_converter`）。
- `pip_size/display_precision` は [tests/_helpers.py](/Users/ishitoya/repository/zenigame-fx/tests/_helpers.py) だけでなく、`InstrumentMeta` 直接生成箇所全体の伝搬確認が必要です。
- 影響範囲確認が `MockBroker(` grep 中心で、`InstrumentMeta(` 側の監査が不足しています。

## 必須修正（NEEDS_REVISION 時のみ）
- scale 不変性検証を修正すること。  
  `initial_cash` のみ変更ケースでは `equity returns` 同一を主張しない。  
  1) `compute_metrics` の trade-based Sharpe のみで検証する、または  
  2) `initial_cash` と `units` を同倍率で同時スケールして `equity returns` 比較する。
- Phase 4 予約名を統一すること。  
  [src/broker/mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py) と [src/broker/margin.py](/Users/ishitoya/repository/zenigame-fx/src/broker/margin.py) で `fx_rate_provider` / `fx_converter` を一本化。
- 呼び出し元監査を拡張すること。  
  `MockBroker(` だけでなく `InstrumentMeta(`・`home_currency=`・broker ファクトリ経由（[src/broker/__init__.py](/Users/ishitoya/repository/zenigame-fx/src/broker/__init__.py)）を対象に grep して、伝搬漏れゼロを確認。
- JPY ペアの `InstrumentMeta` 直接生成箇所で `pip_size=0.01` / `display_precision=3` を明示すること（`_dummy_meta` 含む）。
- [docs/alpha_factory/cross-pair.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/cross-pair.md) の「T019で解消」を限定表現に修正すること。  
  正確には「非JPY-quoteでの Phase 2 backtest 完走制約を解消、`home!=quote` 換算は未解消（Phase 4）」です。

## 推奨修正（任意）
- `MockBroker.__init__` の `home_currency` を keyword-only 化して、位置引数誤用リスクを下げる。
- `NotImplementedError` 文言の検証を 1 テストに集約し、エラーメッセージ変更耐性を高める。

## 根拠
- Fact: 詳細設計 6.2 では「`initial_cash` 10倍・`units`固定」で「`equity returns` 同一」を主張。  
- Interpretation: これは一般に成立せず、検証仮説と指標が不整合（C4/C9）。
- Fact: 詳細設計 3 で `fx_rate_provider`、5 で `fx_converter` を使用。  
- Interpretation: Phase 4 拡張時のインターフェース退行リスク（命名不一致）。
- Fact: 既存影響調査コマンド案は `MockBroker(` のみ。  
- Interpretation: 転記漏れ監査としては不十分で、`InstrumentMeta` 生成経路の網羅が必要（レビュー重点項目 1/3/5）。
- Fact: `pip_size/display_precision` は将来 slippage/log 用と明記。  
- Interpretation: 「今は未使用」でも値の明示伝搬を徹底しないと将来の静かな不整合を招く。