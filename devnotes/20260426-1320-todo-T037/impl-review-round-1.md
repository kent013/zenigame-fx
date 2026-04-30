**所見**
- [Critical] `compute_composite` のガードを inline 展開時に落としているため、`clauses` が空の個体が ValueError ではなく `0.0` を返すようになっています。旧実装では `clauses must not be empty` 例外で Stage A が `system_failure` 判定になりましたが、現状は `no_trades` として処理・archive に書き込まれ、観測値も変わるため設計ドキュメントの「composite 数値不変」契約に反します。`src/dsl/strategy.py:316-329` に `if not clauses: raise ValueError` など元のガードを復活させるか、単純に `compute_composite` を再利用して完全に同じ挙動を維持してください（参考: `src/dsl/composite.py:90-104`）。

全体判定 CHANGES_REQUESTED

補足:
- defensive に 0 を返す fallback は archive スキーマ制約上やむを得ませんが、測定不能ケースは StageResult の `reason_codes`（例: `system_failure`）で区別する想定になります。archive 側だけで判別したい場合は別カラム（例: 測定失敗フラグ）を検討すると安心です。