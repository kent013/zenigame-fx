# Run 31 — run_20260504_065916

**Generated**: 2026-05-04T06:59:16.985158+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.004640911397074999 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 2966 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 15
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 42

## Best 個体

- name: `g14_i21`
- generation: 14
- fitness: **-0.008859088602925001**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 2966
- total_pnl: 0.0
- sharpe: 0.004640911397074999
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 640
- Stage A pass: 2
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 640 | 2 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 640 | 2 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=640, mean=0.9969, median=1.0000, std=0.0558, min=0, max=1
- n_nodes: n=640, mean=2.5219, median=3.0000, std=0.9696, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2, mean=9, median=9.0000, std=0.0000, min=9, max=9
- positive_fold_ratio_effective (Stage A pass): n=2, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000

## Stage B failure reason 集計

- Stage A pass = 2, Stage B pass = 0, failures = 2 (primary_sum = 2)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2 |
| `positive_fold_ratio<min` | 2 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=640

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 3.0% (19/640)
- best 個体 trade_count: 2966
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 640
- metric_stage 分布: stage_a_evaluated=2, stage_a_only=638
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=638, mean=-883532.0690, median=-1000260.0000, std=306823.1592, min=-1008930.0000, max=3600.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=619): n=619, mean=-910651.7932, median=-1000280.0000, std=268948.7600, min=-1008930.0000, max=3600.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2): n=2, mean=-1000450.0000, median=-1000450.0000, std=0.0000, min=-1000450.0000, max=-1000450.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g14_i21` | 14 | tier1_EUR_JPY | EUR_JPY | -0.0089 | 0.0046 | ✅ | ❌ | ❌ | 2966 | — |
| 2 | `g15_i0` | 15 | tier1_EUR_JPY | EUR_JPY | -0.0089 | 0.0046 | ✅ | ❌ | ❌ | 2966 | — |
| 3 | `g15_i4` | 15 | tier1_EUR_JPY | EUR_JPY | -0.0213 | -0.0018 | ❌ | ❌ | ❌ | 2964 | — |
| 4 | `g3_i9` | 3 | tier1_EUR_JPY | EUR_JPY | -0.0253 | -0.0118 | ❌ | ❌ | ❌ | 2964 | — |
| 5 | `g4_i0` | 4 | tier1_EUR_JPY | EUR_JPY | -0.0253 | -0.0118 | ❌ | ❌ | ❌ | 2964 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.047990806784814155 |
| 1 | -0.032737951153762324 |
| 2 | -0.03155054208186555 |
| 3 | -0.025327011422860125 |
| 4 | -0.025327011422860125 |
| 5 | -0.025327011422860125 |
| 6 | -0.025327011422860125 |
| 7 | -0.025327011422860125 |
| 8 | -0.025327011422860125 |
| 9 | -0.025327011422860125 |
| 10 | -0.025327011422860125 |
| 11 | -0.025327011422860125 |
| 12 | -0.025327011422860125 |
| 13 | -0.025327011422860125 |
| 14 | -0.008859088602925001 |
| 15 | -0.008859088602925001 |

