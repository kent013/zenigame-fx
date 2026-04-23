## Verdict
NEEDS_REVISION

## 主要論点
- `per-pair home` 自体は最小変更として筋がよいが、**Sharpe 集約の正当化に必要な前提が 1 つ不足**している
- `Phase 4` への逃げ道は意図としてはあるが、**interface としてはまだ弱い**

## 必須修正（NEEDS_REVISION 時のみ）
- **前提を明文化して検証対象に追加すること**: `per-pair home` で cross-pair Sharpe 集約が成立するのは、「各 pair の return series が通貨単位の違いで歪まない」場合に限る。特に `initial_cash`、position sizing、margin 制約、spread/swap の反映が `JPY=1,000,000` と `USD=1,000,000` のような**数値スケール差で挙動を変えない**ことを前提として明記し、受け入れ基準に検証を入れるべき。
- **Phase 4 用の拡張点を interface として明示すること**: `home_currency` 引数を残すだけでは不十分。将来 `quote != home` を真に扱うための注入点（例: `fx_converter` / `quote_to_home_rate_provider` / `conversion_context` のいずれか）を「今回は未使用だが予約する」と設計に書くべき。

## 推奨修正（任意）
- `cross_pair` / shadow stats のログか結果構造に `evaluation_home_currency` もしくは `per_pair_home_mode=true` を残した方がよい。後で「Sharpe は出ているが通貨前提が不明」という記録漏れを防げる。
- 既存互換性の観点では、「引数無指定で `quote` 採用」と「明示 `home_currency="JPY"` の旧挙動維持」の両方をテストに固定した方がよい。
- `InstrumentMeta` に `pip_size` / `display_precision` を持たせるなら、`CurrencyPair` との SSOT 境界を 1 行でもよいので明記した方が将来の二重管理事故を減らせる。

## 根拠
- **Fact**: 現在の構造的失敗点として明示されているのは `MockBroker` の `quote_currency != home_currency` 制約であり、これを外せば `EUR_USD` / `USD_CAD` を broker 層で完走させられる可能性は高い。  
  **Interpretation**: `T016 cross-pair` の `pair_failure:…:NotImplementedError` を解消する最小変更として、broker 側だけを一般化する方針は妥当。
- **Fact**: `MockBroker` は single-instrument orientation で、`P&L` 式も quote 建てで自己完結している。`home=quote` なら既存式を変えずに済む。  
  **Interpretation**: 「backtest engine 本体に触れない」というスコープ判断は合理的で、USD_JPY / EUR_JPY の後方互換性も高い。
- **Fact**: 設計文書では「Sharpe は無次元だから pair 間集約してよい」としている。  
  **Interpretation**: この主張は**return の生成過程が home 通貨の数値スケールに依存しない**ことが確認されて初めて成立する。もし初期資金や注文量制御が通貨単位の絶対値に依存するなら、Sharpe は無次元でも比較対象の戦略運用条件が pair ごとに変わる。
- **Fact**: 受け入れ基準には `EUR_USD` / `USD_CAD` 完走と `pair_failure` 解消はあるが、`per-pair home` による資金スケール不変性の確認項目はない。  
  **Interpretation**: ここを入れないと、「NotImplementedError は消えたが、cross-pair 集約の意味が崩れている」状態を取り逃がす。
- **Fact**: 将来 Phase 4 のために `home_currency` 引数を残すと書かれている。  
  **Interpretation**: それだけだと将来の換算レート供給経路が設計上見えず、再度 broker 内部に ad hoc な分岐を足す危険がある。拡張点を今の段階で名前だけでも固定しておく方が退行防止になる。
- **Fact**: 既存 JPY-quote ペアは `meta.quote_currency == "JPY"` なので、`default=None -> meta.quote_currency` は挙動不変。  
  **Interpretation**: 798 passed baseline を壊さない見込みは高いが、これは「暗黙互換」であり、明示テストで固定した方が安全。