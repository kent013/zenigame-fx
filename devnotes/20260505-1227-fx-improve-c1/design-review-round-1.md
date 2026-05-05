# Round 1 Design Review

## C1 (partition 監査) 判定
REQUEST_CHANGES  
- [Critical] `run-34` を T087 監査の根拠に使う前提が未検証です。`run-34` の `summary.json` は `bars_stage_b_excludes_stage_a`/`stage_b` がなく、現行 T087 出力契約と不整合です（旧経路の可能性大）。  
  参照: [summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/summary.json:8), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:954)
- [Warning] `holdout=60日 ≒ 86400 bars` 前提は 24/7 仮定で過剰です。FX は 24/5 欠損があるため、期待本数は「実測 cadence 基準」で算出すべきです。
- [Suggestion] `non-empty` だけでなく「必要 coverage 比率」の guard を別途定義してください（現状は empty のみ fail）。  
  参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:476), [stage_partition_guard.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_partition_guard.py:53)

## C2 (PnL 経路) 判定
REQUEST_CHANGES  
- [Critical] 調査手順が主経路を外しています。`total_pnl` は `canonical_metrics` ではなく `backtest.metrics -> stage_gate payload -> archive -> summary` 経路です。  
  参照: [metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py:156), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:865), [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:409), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:766)
- [Critical] `best_genome.json` から `generation/metrics` は取れません。再現キーの取得元が誤りです（`summary.json` or archive が必要）。  
  参照: [best_genome.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/best_genome.json)
- [Warning] Case B（trade-level Sharpe 設計で total_pnl 常時0）は優先度を下げるべきです。`total_pnl` は Sharpe と独立計算です。  
  参照: [metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py:156)
- [Suggestion] 先に sidecar と archive を同一個体キーで突合してください（最短反証）。`g54_i35` は sidecar で `total_pnl_stage_a=50360.0`、summary は `0.0` を確認済み。

## W3 (observability) 判定
REQUEST_CHANGES  
- [Critical] `archive_role/source_stage/fsp_* non-null` を success criterion に置くのは現行契約違反です。これらは現時点で nullable/後段更新前提です。  
  参照: [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:176), [test_archive.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_archive.py:1121)
- [Warning] `median_fitness_pen`/`population_diversity`/`stage_X_pass_count` は現行 `per_generation` schema に存在しません。観測対象定義がズレています。  
  参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:903), [summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-34/summary.json:48)
- [Warning] `dsr` は Stage B payload で明示的に `None`（Phase 4 予定）なので、NaN/None を即欠陥扱いにしない方がよいです。  
  参照: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1227)

## 全体判定
CHANGES_REQUESTED

## 主要指摘 (Critical 1-2 / Warning 2-4)
- [Critical] C2 の主因仮説は既に「Stage A `total_pnl` の archive 未伝搬」側が濃厚で、調査手順が遠回り。  
- [Critical] W3 の success criterion が現行契約（nullable）と矛盾。  
- [Warning] C1 の holdout本数前提が 24/7 仮定。  
- [Warning] run-34 を T087 検証に使う前に artifact バージョン整合チェックが必要。  
- [Warning] C3 collider bias: `best` 1個体だけで因果判断しない（最低でも stage_a_pass 群で比較）。

## 保留・推奨事項
- Q1（手順の欠落/過剰）: 欠落あり。`artifact互換性確認`、`sidecar↔archive突合`、`compute_metrics経路確認` を先に。`canonical_metrics深掘り` は過剰。  
- Q2（Case B）: **cycle 1 では実施しない**（持ち越し）。まず Case A（記録経路バグ）を潰すべきです。  
- Q3（テスト網羅）: 不十分。`collect_stage_a` の `total_pnl` 伝搬回帰、`partial holdout`、`run_gaでguard実行` の3点が不足。  
- Q4（波及変更）: `docs` は妥当。追加で `summary schema`（W3観測項目定義）と `test fixture`（holdout coverage契約）も明示した方がよいです。  
- 収束案（1仮説+1最小変更）:  
  仮説 `H1`: 「`total_pnl=0` は Stage A payload→archive 伝搬欠落が原因」。  
  最小変更 `M1`: `collect_stage_a` で `total_pnl` を保存し、回帰テスト1本追加。  
