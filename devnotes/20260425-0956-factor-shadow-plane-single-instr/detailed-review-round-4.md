## 前提（本レビューの前提条件）
- 反証先行（C9）で、まず「壊れる経路」を優先して確認しました。
- 本レビューは提示された設計本文のみを対象にしています（実コード・実テスト結果は未確認）。
- 事実と解釈を分離して記載します（C6）。
- conditioning set は本文記載の `all_bars_all_individuals` と、因子欠損日の `dropna` 除外を前提に評価しています（C3）。

## Critical（対応必須）
- なし

## Warning（対応推奨）
- `skipped_conditioning_mismatch` の永続化責務が本文で不明確です。  
事実: Step A/Step B のサンプルは mismatch 検知後に `return` しており、当該行へ `fsp_runtime_mode` を書いて保存する処理が明示されていません。  
解釈: 実装次第で `runtime_mode` が `null` のまま残ると、H1 分母・再実行挙動・障害可観測性が崩れます。  
対応: mismatch 経路でも「どの行に何を書いて atomic write するか」を明文化してください。

- 4段接続の最終接続（`AlphaFactoryConfig.fsp` → `run_fsp_updater` 引数）がサンプル上で曖昧です。  
事実: integration 例は `fsp_cfg=fsp_cfg` となっており、`load_config()` からの受け渡しが明示されていません。  
解釈: 設定伝搬漏れ（デフォルト固定化）のリスクがあります。  
対応: `cfg = load_config(...); run_fsp_updater(..., fsp_cfg=cfg.fsp, ...)` を本文とテストで固定してください。

## Suggestion（任意改善）
- `close_time` の UTC 正規化を仕様に1行追加すると安全です（`tz_convert("UTC").normalize()` 相当）。
- `dropna` 後の有効サンプル日数をログに出すと、`window_days` 未満で rolling が空になる事象の説明が容易です。

## Round 3 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| `TARGET_ROWS` 化で全体重複キー検知が抜ける | 解消（概ね） | Step A 全件重複チェック + Step B TARGET_ROWS 整合で設計上は是正。 |
| `target_df.empty -> "active"` の意味論混線 | 解消 | `fsp_updater.no_op` と `rows_processed=0` を分離しており、可観測性は改善。 |
| H1 分母に `skipped_conditioning_mismatch` を含む C3 懸念 | 解消 | 補助指標 `evaluate_key_integrity_failure_rate()` を追加し、解釈分離ができています。 |

## 総評と判定
CONDITIONAL_APPROVED

理由:
- Round 3 の Critical は設計レベルで解消されています。
- Phase 1 diagnostic-only との整合、DoD D1-D8 の本文対応、dispatch 6パスの網羅方針は妥当です。
- ただし上記 Warning 2件（特に mismatch 時の書き戻し責務）は、運用時の可観測性と集計整合に直結するため、明文化してから実装に入るのが安全です。