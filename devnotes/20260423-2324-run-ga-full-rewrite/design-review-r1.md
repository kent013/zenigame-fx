**判定**: NEEDS_REVISION

**コメント**:
- [ブロッカー:detailed-design.md:1055] `best_name` は全世代 cache から選ぶのに、`best_row` を最終世代固定で引いており不整合です（`best.metrics`/`live_criteria` が空化）。修正指示: `cache` に `generation` を保持して同じキーで `get_row_snapshot` 参照してください。
- [ブロッカー:detailed-design.md:613,analyze_run.py:43] `-math.inf` を `summary/history` に文字列化すると `Decimal("-inf")` で既存 consumer が落ちます。修正指示: `best.fitness`/`history.best_fitness` は必ず Decimal 互換の有限値に制限し、失敗状態は別キーで表現してください。
- [ブロッカー:detailed-design.md:1024,swim_lane.py:345] `strict_for_graduation=False` が実昇格ロジックに効かず、`effective_graduation_count` だけ増える設計です。修正指示: `graduation_criteria` 側へ設定を渡して実際の `mark_graduated` 条件を切り替えるか、表示上の擬似件数を廃止してください。
- [設定整合:detailed-design.md:252,default.yaml:104] `cross_pair_integration.strict_for_graduation` を新設していますが既存 SSOT `swim_lane.graduation_criteria.require_cross_pair_pass` を読んでいません。修正指示: 既存キーを一次ソースにして互換マッピングを明示してください。
- [Validation:detailed-design.md:92] `GAConfig` が `elite_count < 0` を許容しています。修正指示: `elite_count >= 0` を追加し、未対応の `fitness_metric!=sharpe` も reject するか実装方針を固定してください。
- [Bars分割:detailed-design.md:662] holdout fallback が `stage_a_n_bars` を再利用しており `stage_c_holdout_days` と一致しません。修正指示: holdout 用バー数を別計算し、fallback はその長さで切ってください。
- [契約維持:run_ga.py:270,detailed-design.md:734] 現行 `summary` の top-level `population_size` が設計例で消えています。修正指示: 「追加のみ」方針なら既存キーを残してください。
- [テスト妥当性:detailed-design.md:1131] DB mock の call順依存は実装変更に脆く、誤検知しやすいです。修正指示: 少なくとも `CurrencyPair`/`PriceBarM1` を stmt で判別し、holdout取得経路と fallback有無を個別に assert してください。
- [後方互換(良好+補強):detailed-design.md:457,test_swim_lane.py:493] `Tier1Lane.provenance` 追加自体は default 空dictで後方互換です。修正指示: `collect_stage_a(parent_a,parent_b)` 伝搬を検証する回帰テストを1件追加してください。
- [registry bridge(概ね妥当):detailed-design.md:378,random_gen.py:77] category射影と `ParamSpec.is_int` 判定は現契約に整合しています。修正指示: 将来カテゴリ追加時のドリフト防止として `slot_from_category` 再利用を推奨します。

**ブロッカー**:
1. `best_row` を最終世代固定で引く不整合（best metrics/live_criteria が壊れる）。
2. `-inf` 文字列が `summary/history` に出ると `analyze_run.py`/`generate_run_report.py` の Decimal 解釈が破綻する。
3. `strict_for_graduation` が実昇格ロジックに反映されず、`graduation_count` と `effective_graduation_count` の意味が乖離している。
