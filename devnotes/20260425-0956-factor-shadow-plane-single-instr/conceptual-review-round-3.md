## 前提（本レビューの前提条件）
- 反証先行（C9）として「破綻しうる点」を先に探索した（Verified）。
- 評価対象は提示された Round 3 文書本文のみで、実コード実装は未照合である（Verified）。
- Fact / Interpretation を分離して判定した（Verified）。
- INCONCLUSIVE を CONFIRMED / REJECTED と同格で扱った（Verified）。

## Critical（対応必須）
1. archive 4段接続の実装完了条件が監査可能な粒度で未定義  
Facts:
- DoD D1〜D7 は `config`、`FspConfig`、`genome.meta`、`flush` を含む。
- 重点チェックで要求された 4 点セット（`GENOMES_SCHEMA`、`_create_row_template`、`collect_stage_*`、`flush`）が DoD 上で個別明示されていない。  
Interpretation:
- 「どこで値が欠落したか」を設計段階で特定できず、過去の転記漏れ再発防止要件を満たし切れていない。  
必要対応:
- DoD を 4 点セットで分解して明記（少なくとも D4 を `schema/template/collect/flush` の検証項目に分離）。

## Warning（対応推奨）
1. H1 の判定条件に `bars >= window_days` 前提が欠けている  
Facts:
- dispatch matrix では `bars < window` は `skipped_window_too_short`。  
- H1 は「single instrument + DXY data 存在」で `active > 90%` を要求。  
Interpretation:
- データ長不足時に設計良否と無関係に H1 が偽化する。  
対応:
- H1 の前提に `eligible_rows = bars>=window_days` を追加し、分母定義を固定。

2. H3 は INCONCLUSIVE 許容で健全だが、反証可能性が弱く残る  
Facts:
- 「3 RUN 全出現で判定、未出現は INCONCLUSIVE」。  
Interpretation:
- INCONCLUSIVE が連続し続ける可能性があり、仮説が長期未判定化する。  
対応:
- 期限付き運用ルール（例: N ラウンド連続 INCONCLUSIVE で検証設計を再定義）を追加。

3. 件数不一致時の `runtime_mode="skipped_*"` が曖昧  
Facts:
- 5b で不一致時 `skipped_*` に倒すと記載（具体値未特定）。  
Interpretation:
- データ欠損と整合性異常が同じカテゴリに混在し、原因追跡が弱くなる。  
対応:
- `skipped_conditioning_mismatch` 追加、または別エラーフィールドを必須化。

## Suggestion（任意改善）
1. UTC 日次境界と因子 `as-of` 時刻の定義を列として保存（例: `fsp_factor_asof_ts_utc`）。  
2. H3 の安定性指標は標準偏差に加えてロバスト指標（MAD など）を併記。  
3. 過学習監査の補助として文献ベースの検証 TODO を追加（例: White, 2000, *A Reality Check for Data Snooping*／Bailey et al., 2014, *The Probability of Backtest Overfitting*、要確認）。

## Round 2 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| H3 同一個体識別キー・判定不能規則 | 概ね解消 | `genome_hash` + INCONCLUSIVE は妥当。長期 INCONCLUSIVE の運用規則は未記載（Warning）。 |
| dispatch matrix 不完全網羅 | 解消 | 5行化され、`runtime_mode` 5種と対応。 |
| conditioning set 実装担保 | 概ね解消 | 件数整合 assert は追加済み。異常時の mode 分類が曖昧（Warning）。 |
| 因果時点整合の曖昧さ | 解消 | `factor_asof_lag=1` の式展開で look-ahead 回避を明文化。 |
| メモリ見積もり不整合 | 解消 | 60日×120個体に整合。 |
| 4段接続 DoD 不在 | 未解消（Critical） | DoD が監査要件（schema/template/collect/flush）の個別確認になっていない。 |

## 総評と判定
**NEEDS_REVISION**

理由:
- Critical が 1 件（4段接続の監査可能性不足）残っているため。  
- それ以外は Round 2 指摘の大半が解消され、設計方向は妥当。上記 Critical を潰せば、次ラウンドは `CONDITIONAL_APPROVED` 以上を狙える状態。