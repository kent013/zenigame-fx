# Run 60 — run_20260509_173346

**Generated**: 2026-05-09T17:33:47.775285+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.5812577635019968 / threshold 1.0
- ❌ **total_pnl**: 36030.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 33 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 45

## Best 個体

- name: `g34_i33`
- generation: 34
- fitness: **0.5417577635019968**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 33
- total_pnl: 36030.0
- sharpe: 0.5812577635019968
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 226
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 226 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 226 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4705, median=1.0000, std=0.5063, min=0, max=2
- n_nodes: n=5856, mean=2.8379, median=3.0000, std=1.4708, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=226, mean=0.0194, median=0.0000, std=0.0446, min=0.0000, max=0.2424
- dsr: n=0
- n_fold_effective (Stage A pass): n=226, mean=11.0044, median=4.0000, std=12.2256, min=2, max=34
- positive_fold_ratio_effective (Stage A pass): n=226, mean=0.0208, median=0.0000, std=0.0479, min=0.0000, max=0.2333

## Stage B failure reason 集計

- Stage A pass = 226, Stage B pass = 0, failures = 226 (primary_sum = 226)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 226 |
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
| `median_oos_sharpe<min` | 226 |
| `positive_fold_ratio<min` | 226 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 5.4% (314/5856)
- best 個体 trade_count: 33
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=226, stage_a_only=5630
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5630, mean=-812274.9059, median=-1000130.0000, std=369344.9383, min=-1009220.0000, max=30260.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5316): n=5316, mean=-860253.5214, median=-1000150.0000, std=321246.9007, min=-1009220.0000, max=30260.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=226): n=226, mean=-64478.4513, median=32890.0000, std=291853.8972, min=-1000550.0000, max=36030.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g34_i33` | 34 | tier1_EUR_JPY | EUR_JPY | 0.5418 | 0.5813 | ✅ | ❌ | ❌ | 33 | — |
| 2 | `g35_i0` | 35 | tier1_EUR_JPY | EUR_JPY | 0.5418 | 0.5813 | ✅ | ❌ | ❌ | 33 | — |
| 3 | `g36_i0` | 36 | tier1_EUR_JPY | EUR_JPY | 0.5418 | 0.5813 | ✅ | ❌ | ❌ | 33 | — |
| 4 | `g36_i62` | 36 | tier1_EUR_JPY | EUR_JPY | 0.5418 | 0.5813 | ✅ | ❌ | ❌ | 33 | — |
| 5 | `g37_i0` | 37 | tier1_EUR_JPY | EUR_JPY | 0.5418 | 0.5813 | ✅ | ❌ | ❌ | 33 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.039453155784594116 |
| 1 | -0.030874652545325752 |
| 2 | -0.005828384566978751 |
| 3 | -0.005828384566978751 |
| 4 | -0.005828384566978751 |
| 5 | -0.005828384566978751 |
| 6 | -0.005828384566978751 |
| 7 | 0.4970981623425602 |
| 8 | 0.4970981623425602 |
| 9 | 0.4970981623425602 |
| 10 | 0.4970981623425602 |
| 11 | 0.4970981623425602 |
| 12 | 0.4970981623425602 |
| 13 | 0.4970981623425602 |
| 14 | 0.4970981623425602 |
| 15 | 0.4970981623425602 |
| 16 | 0.4970981623425602 |
| 17 | 0.4970981623425602 |
| 18 | 0.4970981623425602 |
| 19 | 0.4970981623425602 |
| 20 | 0.4970981623425602 |
| 21 | 0.4970981623425602 |
| 22 | 0.4970981623425602 |
| 23 | 0.4970981623425602 |
| 24 | 0.4970981623425602 |
| 25 | 0.4970981623425602 |
| 26 | 0.4970981623425602 |
| 27 | 0.4970981623425602 |
| 28 | 0.4970981623425602 |
| 29 | 0.4970981623425602 |
| 30 | 0.4970981623425602 |
| 31 | 0.4970981623425602 |
| 32 | 0.4970981623425602 |
| 33 | 0.4970981623425602 |
| 34 | 0.5417577635019968 |
| 35 | 0.5417577635019968 |
| 36 | 0.5417577635019968 |
| 37 | 0.5417577635019968 |
| 38 | 0.5417577635019968 |
| 39 | 0.5417577635019968 |
| 40 | 0.5417577635019968 |
| 41 | 0.5417577635019968 |
| 42 | 0.5417577635019968 |
| 43 | 0.5417577635019968 |
| 44 | 0.5417577635019968 |
| 45 | 0.5417577635019968 |
| 46 | 0.5417577635019968 |
| 47 | 0.5417577635019968 |
| 48 | 0.5417577635019968 |
| 49 | 0.5417577635019968 |
| 50 | 0.5417577635019968 |
| 51 | 0.5417577635019968 |
| 52 | 0.5417577635019968 |
| 53 | 0.5417577635019968 |
| 54 | 0.5417577635019968 |
| 55 | 0.5417577635019968 |
| 56 | 0.5417577635019968 |
| 57 | 0.5417577635019968 |
| 58 | 0.5417577635019968 |
| 59 | 0.5417577635019968 |
| 60 | 0.5417577635019968 |

