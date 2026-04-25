## 前提
- 反証優先（C9）で、まず「Round 4 の2警告が本当に閉じたか」「mismatch後の冪等性が壊れないか」を主軸に確認しました。
- conditioning set（C3）は設計上 `all_bars_all_individuals` と明記され、日次グリッド0埋め方針は確認しました。
- 以下は提示された設計文書のみを根拠にしたレビューです（実装コード未確認）。

## Critical（対応必須）
1. `duplicate mismatch` 経路の書き戻しフローが文書内で矛盾しています。  
事実: 「冪等性とTARGET_ROWSの分離」節では `dup_mismatch` 検知直後に `return`。一方「mismatch時の書き戻し責務」節では `dup_mismatch or key_mismatch` で `target_df` へ書き戻して保存。  
解釈: 実装者が前者を採ると `dup_mismatch` 時に null 行が残り、再実行で再び再計算対象になって冪等性要件（mismatch行を再計算対象から外す）を満たせません。Round 4 Warning 1 は未完了です。  
最小修正: `dup_mismatch` でも必ず `target_df` null 行へ `skipped_conditioning_mismatch` を書いて `_atomic_write_parquet()` 後に return する単一フローに統一してください。

## Warning（対応推奨）
1. `target_df.empty -> "active"` は運用ログ上の意味が弱いです。  
事実: 計算ゼロ件でも返り値が `active`。  
解釈: post-RUN の `fsp_post_run` だけ見ると「実計算active」と誤読されやすいです（特に再実行時）。`rows_processed=0` を必須ログキーに固定するか、`active_noop` 相当の識別を追加すると安全です。

2. conditioning set の実効母集団が `dropna()` で縮む点は、観測性をもう一段明示した方がよいです。  
事実: 因子欠損日は OLS/rolling から除外。  
解釈: C3観点で「all bars」設計意図と実計算母集団の差を後から監査しづらいです。`aligned_n` / `dropped_factor_na_n` を行単位で記録推奨です。

## Suggestion（任意改善）
1. `run_fsp_updater(..., run_id=...)` を受けるなら、読み込んだ archive の `run_id` 一貫性チェック（全行一致）を1行入れると設計の自己防衛が上がります。

## Round 4 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| mismatch 時の書き戻し責務が不明確 | **未解消（文書矛盾あり）** | 書き戻す記述は追加されたが、別節に早期 `return` が残り、`dup_mismatch` 経路で実施保証が崩れている |
| 4段接続の最終接続が曖昧 | **解消** | `cfg = load_config(...); run_fsp_updater(..., fsp_cfg=cfg.fsp, ...)` と D1-D3+統合点の明示は妥当 |

## 総評と判定
**NEEDS_REVISION**  
理由: Critical が 1 件（`duplicate mismatch` 経路の書き戻し責務と冪等性保証の不整合）。  
ここだけ単一フローに明文化できれば、Phase 1 diagnostic-only の整合性は全体として高い水準です。