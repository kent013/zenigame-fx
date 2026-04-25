## 前提（本レビューの前提条件）
- 本レビューは提示された Round 3 テキストのみを対象に実施（実コード・実テスト未確認）。
- `C9 Falsification-first` に従い、まず「Round 2 指摘が実質未解消となる反例」を探索。
- `C6 Fact/Interpretation` を分離して記載。
- `C3 Collider bias` 観点では、`H1` の conditioning set 定義と分母構成を重点確認。

## Critical（対応必須）
1. `TARGET_ROWS` 化で「全体重複キー検知」が抜ける可能性
- 事実: 設計では `_check_key_integrity()` を `target_df` に対して呼び出す運用へ変更。重複検知も同関数内で `len(archive_df) != len(archive_keys)` 判定。
- 事実: `target_df` は `fsp_runtime_mode.isna()` 行のみで、既処理行は除外される。
- 解釈: 「既処理行と未処理行にまたがる重複キー」は `target_df` 単体では検知漏れしうる。D5（キー結合の健全性）に対する回帰リスク。
- 必要対応: 重複キー検知だけは常に `full archive_df` で先行実施し、`target_df` では「不足/超過キー整合」のみ判定する2段構成に分離。

## Warning（対応推奨）
1. `target_df.empty -> "active"` は意味論が混線
- 事実: 全行既処理時に `rows_processed=0` でも返却値は `"active"`。
- 解釈: 実運用ログ/監視で「計算実行成功」と「再計算不要(no-op)」が区別できない。
- 推奨: 返却値を増やせない制約があるなら、少なくとも `rows_processed==0` を一次判定キーとして運用指標を分離。

2. `evaluate_h1()` の分母に `skipped_conditioning_mismatch` を含める設計の解釈注意
- 事実: `H1_NON_ELIGIBLE_MODES` から `skipped_conditioning_mismatch` は除外されていない。
- 解釈: H1 が「データ整合失敗率」も含む複合KPIになる。dispatch健全性と整合性障害が混ざるため、因果解釈時に混線しやすい（C3注意）。
- 推奨: H1補助指標として `key_integrity_failure_rate` を別出し。

## Suggestion（任意改善）
- rolling Spearman は現在の実装（窓ごと rank → Pearson）なら実質 Spearman 定義に一致しうるため、「近似」表現は誤解を招きやすい。  
  参考: Spearman, 1904, *The Proof and Measurement of Association between Two Things*（要確認）。
- `trades_df["pnl"]` がスプレッド・スワップ控除後の純利益かを設計文で明示すると、North Star/絶対制約との整合監査がしやすくなる。

## Round 2 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| `skipped_disabled` 統合矛盾 | 解消 | `if fsp_cfg.enabled:` ガード撤去方針は妥当 |
| rolling Spearman 定義不整合 | 概ね解消 | 窓内 rank-corr に修正済み。表現上の「近似」注記は再整理推奨 |
| TARGET_ROWS 冪等性仕様未確定 | 部分解消 | `empty` 挙動とスコープ規約は明文化。ただし全体重複キー検知の抜け穴が新規発生 |
| D8 補完責務未明記 | 解消 | `_read_archive_with_fsp_compat()` で責務が明確 |
| D7 dispatch 境界曖昧 | 解消 | `_decide_runtime_mode` と `_check_key_integrity` の境界明示は良い |

## 総評と判定
**NEEDS_REVISION**

理由: Round 2 の主要論点はほぼ潰せていますが、`TARGET_ROWS` 化に伴う**全体重複キー検知の抜け**はデータ整合性に直結し、`skipped_conditioning_mismatch` 系の信頼性を落とすため Critical と判断します。これを解消できれば、設計全体は `CONDITIONAL_APPROVED` 以上に上げられる水準です。