## 前提（本レビューの前提条件）
- 前提1: 本レビューは提示された Round 2 設計テキストのみを対象にした反証優先レビューです（Verified）。
- 前提2: `docs/alpha_factory/*`・`devnotes/*`・`git log` の実ファクト照合（C1）は未実施です（Not Verified）。よって実装済み可否の一部は `INCONCLUSIVE` を含みます。
- 前提3: 事実（設計文に明記された内容）と解釈（そこからの不具合リスク推論）を分離して記載します（Verified）。

## Critical（対応必須）
1. `skipped_disabled` 記録要件と統合コードが矛盾
- Facts: 統合例が `if fsp_cfg.enabled:` で updater 呼び出しを抑止しています（[scripts/run_alpha_factory.py](/Users/ishitoya/repository/zenigame-fx/scripts/run_alpha_factory.py) 想定、設計 §11）。
- Interpretation: `enabled=false` 時に `skipped_disabled` が記録されず、Round 1 Warning の「対応済み」主張と不整合です。`fsp_runtime_mode` が `null` のまま残り、H1 集計母集団も歪みます。

2. rolling Spearman の定義が統計的に不正確
- Facts: `pnl.rank()` / `factor.rank()` を全期間で一度だけ作って rolling Pearson を計算する設計です（[fsp_updater.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/fsp_updater.py) 想定、設計 §6-3）。
- Interpretation: これは「各窓で順位付けした Spearman」と一致しません。API整合問題は解消していますが、指標意味がズレます。診断層の根幹指標なので Critical 相当です。

3. TARGET_ROWS 分離の冪等性仕様が未確定
- Facts: `_check_key_integrity(target_df, fsp_results)` への変更はある一方、`target_df.empty` 時の挙動と `fsp_results` のキー集合を TARGET_ROWS に限定する規約が明記されていません（設計 §5）。
- Interpretation: 再実行時に `target_df` が空でも `fsp_results` が全件なら `skipped_conditioning_mismatch` へ誤遷移し得ます。冪等性要件に対して仕様が不足しています。

## Warning（対応推奨）
1. D8 互換補完の実装責務がテスト記述先行
- Facts: old/new/mixed テスト方針はあるが、旧Parquet読込時に FSP列を `None` 補完する本体責務の記述が薄いです（[test_archive_schema.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive_schema.py) 想定、設計 §8）。
- Interpretation: テストはあっても実装側の責務位置が曖昧で、将来の回帰点になります。

2. D7「dispatch 6パス」と実装境界の表現が曖昧
- Facts: `skipped_conditioning_mismatch` は `_decide_runtime_mode()` ではなく後段の整合チェックで発生します（設計 §5, §9）。
- Interpretation: 「dispatch matrix 6パス」の言葉が実装境界を誤解させ、テストが関数単位で崩れるリスクがあります。

## Suggestion（任意改善）
- `run_fsp_updater` を常時呼び出しに固定し、`enabled` 判定は updater 内 dispatch のみに一本化。
- rolling Spearman は「窓ごと rank」実装に変更（例: rolling windowごとに `scipy.stats.spearmanr`。参考: Spearman, 1904 要確認）。
- 冪等性仕様を明文化:  
  `if target_df.empty: return "active"`（rows_processed=0 をログ）  
  `fsp_results` は必ず `target_keys` のみ生成  
  この2点を unit test に追加。

## Round 1 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| Critical-1 rolling Spearman API不整合 | 部分解消 | API不整合は解消。ただし統計定義としては未解消（窓内 rank でない）。 |
| Critical-2 冪等性とキー整合矛盾 | 部分解消 | TARGET_ROWS 導入は前進。`target_df.empty` と `fsp_results` スコープ規約が不足。 |
| Critical-3 H1 eligible定義不一致 | 解消 | 4つの non-eligible mode 列挙は整合。 |
| Critical-4 atomic write fsync欠如 | 解消 | file fsync + dir fsync が設計に反映。 |
| Warning-1 `skipped_disabled` 呼び出し抑止 | 未解消 | 統合例が依然 `if fsp_cfg.enabled:`。 |
| Warning-2 flush互換補完責務 | 要確認 | テスト設計はあるが本体責務の明記が弱い。 |
| Warning-3 `dropna()` 方針の明文化 | 解消 | コメントで明記済み。 |
| Warning-4 `idio_ratio` レンジ未定義 | 解消 | unclipped/R²<0記録を明記。 |

## 総評と判定
**NEEDS_REVISION**

理由: Critical が 3 件（統合矛盾、rolling Spearman 定義、冪等性仕様不足）残っています。Round 1 の主要論点は多く反映されていますが、「対応済み」と言うにはまだ設計上の矛盾が残っています。