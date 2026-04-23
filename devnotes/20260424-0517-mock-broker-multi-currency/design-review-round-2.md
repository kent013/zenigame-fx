## Verdict
APPROVED

## 主要論点
- 前回の必須修正5点は、改訂版 [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260424-0517-mock-broker-multi-currency/detailed-design.md) で実質的に解消されています。
- とくに `S2`（`initial_cash × units` 同時スケール）と `S3`（同時スケール時の equity returns 一致）への再定式化は妥当です。
- Phase 4 予約名は `fx_rate_provider` に統一され、[src/broker/mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py) / [src/broker/margin.py](/Users/ishitoya/repository/zenigame-fx/src/broker/margin.py) の将来契約が揃っています。
- 呼び出し元監査は `MockBroker(` / `InstrumentMeta(` / `home_currency=` の3軸に拡張され、転記漏れ対策として `_dummy_meta` / `_stub_meta` / `_make_stage_c_inputs` 更新方針も明示されています。
- docs の「T019で解消」表現は、解消範囲と未解消範囲（Phase 4）に分離され、過大主張が解消されています（[docs/alpha_factory/cross-pair.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/cross-pair.md)）。

## 必須修正（NEEDS_REVISION 時のみ）
- なし

## 推奨修正（任意）
- 文書内の件数表記を実検索結果と一致させること（`MockBroker(` は31ヒット、`InstrumentMeta(` は11ヒット）。網羅自体はできていますが、件数の整合だけ直すと監査性が上がります。

## 根拠
- Fact: §6.2 で「`initial_cash` 単独変更では returns 不変でない」を明示し、S2/S3へ置換済み。  
- Fact: §5 および関連箇所で `fx_rate_provider` へ命名統一済み（`fx_converter` 記述なし）。  
- Fact: §3.1/§3.2 で `MockBroker(` と `InstrumentMeta(` の棚卸し、および test/scripts の伝搬方針が明文化済み。  
- Interpretation: Round 1 の必須修正は設計レベルで満たされており、実装着手可。