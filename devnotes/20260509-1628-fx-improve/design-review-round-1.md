## Q1 / Q2 / Q3 への回答
- **Q1**: 設計本文で「DB 最小日付との差は 5 日」と記載されていますが、`config/alpha_factory/default.yaml:11-12` の変更候補と前提「DB EUR_JPY range 2023-04-23〜2026-04-21」を突き合わせると実際のカレンダー差は 344 日あります。一方で `src/alpha_factory/aux_preflight.py:49-71` が Stage B 18 ヶ月分を遡及して aux / ペアバーを検査するため、今回の start=2024-04-01 では拡張開始日が 2022-10-09 になります。`HARD_REQUIRED_PAIRS`（EUR_USD, USD_JPY）が 2022-10-09 以降を 50% 以上カバーできているか、`preflight_check_aux_data` もしくは SQL で実測確認してください。ギャップが残る場合は start の再設定か ingest 補填が必要です。
- **Q2**: Stage B 区間が 4.5 ヶ月→約 20 ヶ月に伸びると、`src/alpha_factory/walk_forward.py:48-69` の `compute_max_folds` が算出する fold 数は約 5〜6 倍に増えます。`scripts/alpha_factory/run_ga.py:462-548` で生成する Stage B bars のユニーク観測日 ≈630 日を前提にすると、(20+1+18) 日構成×step=5 日で概算 118 fold 程度になり、Stage B 評価の backtest 呼び出し数・memory footprint・壁時計時間が大幅に増えます。Run 57 の試走前に Stage B seconds / peak RSS を観測し、ワーカー 6 × 3GB 制約内で収まるか検証する必要があります。さらに 2024-04〜2025-12 を含むことで regime 変化をまたぐため、Stage B median/dsr/positive_fold の分布が過去 RUN と非連続になる点も留意してください。
- **Q3**: `tests/alpha_factory/test_config.py:116-218` や `tests/alpha_factory/test_config_schema_contract.py:46-86` などに旧日付のベース YAML がベタ書きされています。実装では default.yaml だけを変える予定とのことですが、この差分が残るとテストが「旧想定の複製」を続けて将来の同期忘れを誘発します。`rg "2025-10-01"` で洗い出して、最低でも default を模倣しているテストフィクスチャは新日付へ更新してください。

## Critical 指摘
- `compute_extended_period` が導く拡張期間（2022-10-09〜2026-04-20）に対し、`HARD_REQUIRED_PAIRS`（EUR_USD / USD_JPY）が 50%以上のカバレッジを持つか未検証です。ここが 50% を割ると `preflight_check_aux_data` が `hard_missing` を返して RUN が fail-closed します。start を決める前に、該当 pair の `PriceBarM1` と aux series の `effective_from_utc` を実データで確認し、不足があれば start 再調整またはデータ補填をお願いします。（参照: `config/alpha_factory/default.yaml:11-12`, `src/alpha_factory/aux_preflight.py:33-97`）

## Warning 指摘
- Stage B fold 数の急増に伴う性能リスクが大きいです。最低でも Run 56→Run 57 の `summary.json` に含まれる `stage_b_seconds_total`・`peak_rss_mb_per_worker` を比較し、必要なら `stage_b_window_months` の分割適用や fold 数上限のガードを検討してください。（`src/alpha_factory/walk_forward.py:48-163`, `scripts/alpha_factory/run_ga.py:462-548`）
- Run 56 以前との指標比較が成り立たなくなります。Stage B の本数・regime が別物になるため、`reports/run-reports/` の評価ログや calibrate 系統の解析は「start変更後専用ベースライン」に作り替える計画を事前に整理してください。（関連: `reports/` 系運用、`devnotes/20260509-1628-fx-improve/`）
- C4 前提のうち `stage_b_window_months=18`・`stage_a_window_days=60`・`stage_c_holdout_days=60` は `config/alpha_factory/default.yaml:117-177` で確認できましたが、DB range（2023-04-23〜2026-04-21）は提示資料だけで実測確認ができていません。SQL などで一次情報を残し、前提検証を完了させてください。

## Suggestion
- default.yaml のコメントに記載予定の「DB から 60 日遡る」等の根拠を、実計算値（例: holdout span 60 日, Stage B coverage 85% 程度）に差し替えると保守負担が下がります。（`config/alpha_factory/default.yaml`）
- テスト YAML の新日付反映後に `tests/scripts/test_alpha_factory_run_ga.py` 等の smoke fixtureで Stage B / holdout の境界を再確認し、最小限のゴールデン差分（例: stage_partition_guard ログ）を更新しておくと回帰チェックが楽になります。

## 全体判定: REQUEST_CHANGES