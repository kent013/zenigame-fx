C9（Falsification-first）として先に反証を探しましたが、**性能・仕様面でのブロッカーは見当たりません**。  
結論は **APPROVED（軽微 Warning 1 件）** です。

**本レビューの前提**

- `verified`
- 提案は per-bar の `logger.*` 呼び出し 3 箇所を削除し、`run_backtest` のサマリ集計へ寄せる内容。
- 進捗観測 INFO（`backtest.finished` など）は維持する方針。
- `if session_closed_bar and signal.kind in ("open_long", "open_short")` は drop 仕様そのもので、比較演算はロジック上必要。

- `unverified`
- [`mock.py`](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:172) のログを完全削除した場合に、backtest 以外の将来呼び出しで監査ログが不要かどうか。
- structlog 設定依存での実 overhead（提案方向は妥当だが、削減量の厳密値は未実測）。

**Findings（重大度順）**

- [Critical] なし。
- [Warning] [`drop_pending_open`](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:172) 側ログを完全削除すると、呼び出し元が backtest 以外に増えた時にイベント痕跡が消えるリスクがあります。  
  修正提案: 現状の削除方針は維持しつつ、V7 に「`drop_pending_open` 呼び出し元一覧の固定化（grep）」を追加し、将来呼び出し増加時は呼び出し元側で集計ログを持つ運用ルールを明記。
- [Suggestion] `first_drop_open_bar_time` と対になる `first_drop_pending_bar_time` も必要なら追加すると、pending 側だけ多いケースでも時系列手がかりを残せます（必須ではありません）。

**Fact / Interpretation**

- Fact: per-bar logger 削除は event_dict 構築・kwargs 展開・`isoformat()` 評価の呼び出しを確実に消せる。
- Fact: 比較分岐は drop 制御仕様に必須で、削除対象ではない。
- Interpretation: 「DEBUG 降格」より「完全削除」の方が hot path 最適化として一貫している。進捗観測も `backtest.finished` で維持可能。

**各観点**

1. 使命整合性: [Critical]なし [Warning]なし [Suggestion]妥当。  
2. 禁止事項違反: [Critical]なし [Warning]なし [Suggestion]数値ロジック非変更を維持。  
3. 実現可能性: [Critical]なし [Warning]なし [Suggestion]局所変更で実装容易。  
4. 期待効果妥当性: [Critical]なし [Warning]なし [Suggestion]効果量は実測で確定。  
5. リスク: [Critical]なし [Warning]1件（`mock.py` 将来呼び出し元の可観測性） [Suggestion]上記対応。  
6. スコープ適切性: [Critical]なし [Warning]なし [Suggestion]適切。  
7. メモリ制約: [Critical]なし [Warning]なし [Suggestion]影響ほぼなし。  
8. 前提検証: [Critical]なし [Warning]なし [Suggestion]V7 で呼び出し元固定化を追加。  
9. Design-first: [Critical]なし [Warning]なし [Suggestion]設計意図は明確。

**確認依頼への回答**

1. 方向性（DEBUG 降格 → 完全削除）は運用上妥当です。  
2. 比較演算を残す判断は妥当です（drop 仕様に必須）。  
3. 新規 Critical はなし、Warning は 1 件（将来の `mock.py` 呼び出し元可観測性）。  
4. 総合判定は **APPROVED** です。