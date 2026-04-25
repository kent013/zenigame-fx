## 前提（本レビューの前提条件）
- `C4` 前提明示: 本レビューは**提示された Round 5 概念設計テキストのみ**を対象にし、実コード・実ログ・実 Parquet 実装は未確認。
- `Verified (文書内確認)`:
  - Round 4 の 2 Critical 修正（`collect_stage_*` は null 初期化のみ / `assert` 廃止）は文書上で反映済み。
  - enum 6値の単一定義、H1 分母定義の明示は反映済み。
- `Assumed`:
  - post-RUN updater は archive 行への値割当を「件数一致 + 行順」で行う可能性がある（キー結合規約が未記載）。
  - Parquet 書き戻しは単純上書き（原子的置換・ロック・再実行規約が未記載）。
- `C8` INCONCLUSIVE:
  - 「全呼び出し元での引数確認」は設計文書だけでは完全検証不可。

## Critical（対応必須）
1. 行対応の整合性が「件数一致」だけで保証されていない  
Fact: D5 は `len(archive_rows) == len(fsp_target_individuals)` の確認のみ記載。  
Interpretation: 件数が同じでも順序ずれで**別個体に FSP 値を誤付与**し得る。これは `genome.meta -> consumer` 接続のサイレント破壊。  
必要対応: `genome_hash`（+ 必要なら run 内一意キー）で**キー結合**し、`missing/duplicate/unmatched` を検出したら `skipped_conditioning_mismatch` に倒す。

2. Parquet 書き戻しの耐障害性・冪等性規約が未定義  
Fact: 「Parquet に書き戻し」はあるが、原子的置換・部分失敗時の回復・再実行時の一貫性が未記載。  
Interpretation: 部分書き込み failure でファイル破損/不整合、再実行で stale 値混在のリスク。  
必要対応: `tmp書き出し -> fsync -> atomic rename`、排他ロック、`fsp_update_version` 等の更新マーカー、`skipped_*` 時の FSP 値クリア規約を明記。

## Warning（対応推奨）
1. 指標定義に不整合が残存  
Fact: 本文に `fsp_partial_corr` の列名記載がある一方、schema 拡張列には含まれていない。  
Interpretation: 転記漏れ再発ポイント。D4a〜D4d/consumer 実装時に齟齬化しやすい。  
推奨: Phase 1 で使う列を 1 箇所に固定し、未採用指標名を削除。

2. collider 対策の設定固定が config 反映まで閉じていない  
Fact: `conditioning_set` を config レベル固定するとあるが、D6 の config 追加一覧に明示されていない。  
Interpretation: 実装時に暗黙値化され、将来変更で C3 再発リスク。  
推奨: `factor_shadow.conditioning_set` を明示キーとして DoD に追加。

## Suggestion（任意改善）
1. updater の状態遷移を 1 枚の state table に明記（`active/skipped_*` 遷移条件、優先順位、再実行時挙動）。
2. `D7` テストに「件数一致だがキー不一致」の反証ケースを追加（C9 強化）。
3. run_report に `fsp_rows_total / eligible / active / skipped_by_reason` を定型出力し、運用監査を容易化。

## Round 4 指摘の解消状況
| 指摘 | 状態 | コメント |
|---|---|---|
| D4c ライフサイクル矛盾（collect_stage_* で値書き込み問題） | 解消（文書上） | `collect_stage_*` は null 初期化のみ、値埋めは post-RUN updater に統一。 |
| D5 assert vs graceful degradation 矛盾 | 解消（文書上） | `assert` 廃止、`skipped_conditioning_mismatch` へフォールバックに変更。 |
| enum 一覧の不整合 | 解消（文書上） | 6値を計測内容で一元定義し D6/D7 の参照先化。 |
| H1 分母定義の曖昧さ | 解消（文書上） | `eligible_rows` 条件が追加され、評価母集団が明確化。 |

## 総評と判定
**NEEDS_REVISION**

理由: Round 4 指摘は文書上ほぼ解消されていますが、C9 観点で最も失敗確率が高い経路として  
- 「件数一致のみでの誤マッピング」  
- 「Parquet 書き戻しの耐障害性/冪等性未定義」  
の2点が残っています。  
この2点はどちらも `config -> GaConfig -> genome.meta -> consumer` の信頼性を直接損なうため、Phase 1 着手前に設計へ明文化するのが妥当です。