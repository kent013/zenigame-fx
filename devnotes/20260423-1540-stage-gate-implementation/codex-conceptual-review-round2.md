**Findings**

- **重大**: `reason_codes` の canonical 語彙と Stage C の失敗理由が食い違っています。`§3.2` では `spread_stress.trade_count<min` / `spread_stress.total_pnl<0` / `spread_stress.sharpe<0` を canonical code に固定していますが、`§3.5 step 4` では失敗時に `reason="spread_stress_fail"` と書かれています。これは Round 1 の `StageResult schema drift` 対応を崩しており、consumer 側で再び文字列解釈が必要になります。

- **重大**: `CrossPairEvaluator` の interface 修正が文書内で一貫していません。`§3.5 step 5` と `§4` では `CrossPairResult` / `pair_bars_map` / `meta_map` / `target_pair` に更新されていますが、`§6.5` に古い `evaluate(self, genome, target_bars, meta, backtest_config) -> dict` が残っています。Round 1 指摘 #5 への修正が文書全体として完了していません。

- **中程度**: `max_spread_bps=None` の fail-closed 方針とテスト方針が矛盾しています。`§3.5 step 4` では `reason="spread_stress_skipped"` で不通過と明記していますが、`§5` のテスト項目は「stress スキップ + skipped flag」のみで、不通過を期待値に含めていません。Round 1 指摘 #4 は設計本文では修正されていますが、検証仕様へ落ち切っていません。

- **中程度**: Stage A の failure reason も canonical 化が最後まで揃っていません。`§3.2` の語彙は `"system_failure"` と `"metric_unavailable"` に分離されていますが、`§3.3` では `_FAILURE_FITNESS` 時に `reason_if_failed="system_failure_or_metric_unavailable"` としています。Round 1 指摘 #9 の schema drift 対応としては未完です。

**解消を確認できた点**

- `§3.6` の observed-day index ONLY 化で、Round 1 指摘 #1 は概念レベルで解消しています。
- `§3.5 step 3` の `overnight_violations` 追加で、指摘 #2 は解消しています。
- `§3.5 step 4` の hard gate 化と `spread_stress_skipped` fail-closed で、指摘 #3 と #4 の方向性自体は妥当です。
- `§3.4` の unavailable fold を 0 扱い・母数に含める方針で、指摘 #6 は解消しています。
- `§3.4` の責務再定義で、指摘 #7 は解消しています。
- `§3.5` の drawdown fraction 統一で、指摘 #8 は解消しています。
- `§3.7` の `# monitor_only` 明示で、指摘 #10 は解消しています。
- `§3.6` / `§9` の 396 観測日修正で、指摘 #11 は解消しています。

**判定**

`REQUEST_CHANGES`

Round 1 の主要論点はほぼ正しい方向に修正されていますが、`reason_codes` の canonical 化、`CrossPairEvaluator` interface、`fail-closed` を反映したテスト期待値の3点で文書内不整合が残っています。詳細設計へ進む前に、少なくともこの整合性だけは潰すべきです。