## 前提（本レビューの前提条件）
- [Fact] レビュー対象は提示された「詳細設計テキスト」のみで、実装コード・概念設計本文・既存 `archive.py` 実装本体は未確認です。  
- [Fact] 反証優先（C9）で、まず「設計通りでも壊れる経路」を探索しました。  
- [Fact] conditioning set は `all_bars_all_individuals` を採用する設計です。  
- [Interpretation] `collect_stage_*` 不変・flush 整合・旧schema読込互換は、現時点では **INCONCLUSIVE**（設計記述上は意図あり、実装確認不足）です。  

## Critical（対応必須）
- [Fact] `rolling().corr(..., method="spearman")` は pandas の Rolling API と整合しない可能性が高く、設計例のままだと実装時に破綻し得ます。  
- [Interpretation] 「rolling Spearman 実装方針」が未成立。`rank` 化して Pearson を取る等の明示が必要です。

- [Fact] `_check_key_integrity()` は `archive_df` 全件キーと `fsp_results` 全件キーの完全一致を要求しています。  
- [Fact] 一方で冪等性方針は「`fsp_runtime_mode` が null の行のみ再計算対象」です。  
- [Interpretation] 再実行時に対象が部分集合になると `skipped_conditioning_mismatch` に倒れる設計矛盾があります（キー結合設計の破綻）。

- [Fact] `evaluate_h1()` の `eligible` 定義が仕様コメントと不一致です。実装案は `skipped_multi_pair_run / skipped_disabled` しか除外せず、`no_factor_data` や `window_too_short` を母集団に残します。  
- [Interpretation] H1 指標が歪み、設計判断を誤らせます。

- [Fact] atomic write のコード例は「tmp -> rename」のみで、説明にある `fsync` が未実装です（ファイル・親ディレクトリ）。  
- [Interpretation] 原子的置換は概ね満たしても、クラッシュ耐性（durability）要件を満たしません。

## Warning（対応推奨）
- [Fact] 4段接続は記述上 `config -> FspConfig -> AlphaFactoryConfig -> run_fsp_updater` まで見えますが、統合例が `if fsp_cfg.enabled:` で呼び出し自体を抑止します。  
- [Interpretation] `skipped_disabled` の実運用観測ができず、6モード監査の一貫性が落ちます。

- [Fact] archive 4点セットのうち「flush 出力整合」は設計文中に意図はあるが、旧/混在 schema の補完ロジック位置が未明確です。  
- [Interpretation] old/new/mixed 互換で列欠落時の補完責務を明記しないと実装差異が出ます。

- [Fact] `aligned = concat(...).dropna()` により、因子欠損日の除外が発生します。  
- [Interpretation] conditioning set は「全bar全個体」でも、因子欠損を介した選別が入るため collider 的バイアス混入リスクがあります（欠損処理方針の明文化推奨）。

- [Fact] `idio_ratio = 1 - R^2` は `R^2 < 0` で 1 を超えます。  
- [Interpretation] 指標名として直感に反するため、レンジ定義（未拘束か [0,1] か）を設計で固定すべきです。

## Suggestion（任意改善）
- キー結合を関数化し、`TARGET_ROWS`（再計算対象）と `ALL_ROWS`（監査対象）を明示的に分離してください。  
- dispatch は「判定関数で6値を完結」か「5値+整合チェック由来1値」に整理し、テストも同じ責務境界で分割してください。  
- テストに以下を追加すると堅くなります。  
- `test_rerun_with_partially_active_rows`（部分再計算）  
- `test_timezone_boundary_utc_daily_aggregation`（UTC日境界）  
- `test_schema_backfill_on_old_archive_missing_fsp_columns`（旧schema補完）

## 総評と判定
**NEEDS_REVISION**

理由: 主要ロジックに設計矛盾（rolling Spearman 実装方針、冪等性とキー整合、H1母集団定義、atomic write durability）があり、現状のまま実装に進むと誤判定または運用不整合を高確率で招きます。  
一方で、FSPを post-RUN 独立層として分離し、archive 4点セットを意識している方向性自体は妥当です。