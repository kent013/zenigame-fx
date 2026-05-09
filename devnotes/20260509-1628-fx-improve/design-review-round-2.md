## Q1 / Q2 / Q3 への回答

- **Q1**: `dataset.start=2025-04-01` は妥当です。`extended_start=2023-10-09` で DB min 2023-04-23 から約 5.5 ヶ月余裕があり、Round 1 Critical は解消と判断します。さらに `2025-07-01` へ詰めると Stage B 情報量を削る副作用が大きく、preflight が実測で 50% 閾値を十分超えるなら不要です。
- **Q2**: fold 急増 Warning は実質解消です。46 folds は `wf_min_safe_folds=5` を十分超え、Run 56 比 2.4 倍程度なら性能リスクは監視対象に下げてよいです。ただし fold 数は calendar days ではなく実際の `n_unique_dates(bars_stage_b)` ベースで Run 57 ログに残してください。
- **Q3**: 「pytest 確認 + 必要なら同期更新」だけより、事前に grep して用途分類する方が安全です。一律同期は不要ですが、production default を模倣する fixture / docs / devnotes は同期、独立 fixture は維持、という triage を実装手順に入れるのが望ましいです。

## Critical 指摘 (該当時)

なし。

## Warning 指摘 (該当時)

なし。Round 1 の Critical / Warning は今回の v2 方針で解消と判断します。

## Suggestion (該当時)

- `coverage ≒ 85%` は、実コードの分母が calendar minutes ならやや高く見積もっている可能性があります。SQL 実測値をそのまま記載するのが安全です。
- `preflight extended period` の終端は実装上 `dataset.end + 60d = 2026-04-20T00:00:00Z` です。DB max 2026-04-21 でカバーできる、という表現に揃えると誤読が減ります。
- Run 57 の acceptance に `stage_b_fold_count`, `stage_b_unique_dates`, `pair coverage pct` のログ確認を追加すると、反証可能性が明確になります。

## 全体判定: APPROVED