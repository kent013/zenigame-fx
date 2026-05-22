# Run 92 — run_20260522_164949

**Generated**: 2026-05-22T16:49:49.742228+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 3.551781553543725 / threshold 1.0
- ✅ **total_pnl**: 57140.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.5020997596266263 / threshold 20.0
- ✅ **trade_count**: 57 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 133 (= Stage C 単独通過数)
- **mission_candidate_count**: 133 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 48
- generations: 20
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g20_i35`
- generation: 20
- fitness: **0.052858187254554004**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 57
- total_pnl: 57140.0
- sharpe: 0.08574522251389521
- sortino: —
- calmar: —
- max_drawdown_pct: 1.5020997596266263

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 1008
- Stage A pass: 356
- Stage B pass: 286
- Stage C pass: 133

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 133 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 2 | 1.5% |
| 51 | 2 | 1.5% |
| 52 | 7 | 5.3% |
| 53 | 5 | 3.8% |
| 54 | 77 | 57.9% |
| 55 | 6 | 4.5% |
| 56 | 23 | 17.3% |
| 57 | 5 | 3.8% |
| 58 | 1 | 0.8% |
| 59 | 1 | 0.8% |
| 61 | 2 | 1.5% |
| 62 | 1 | 0.8% |
| 67 | 1 | 0.8% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 2 | 131 |
| median total_pnl | 57665.0000 | 53770.0000 |
| median trade_sharpe_stage_c | 0.2487 | 0.2291 |
| median max_drawdown_pct | 1.8543 | 1.5068 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 1008 | 356 | 286 | 133 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 1008 | 356 | 286 | 133 |

## active_clause / n_nodes 分布

- active_clause: n=1008, mean=1.2381, median=1.0000, std=0.4282, min=0, max=2
- n_nodes: n=1008, mean=3.6012, median=3.0000, std=1.6225, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=276, mean=0.9290, median=0.9738, std=0.0935, min=0.3433, max=0.9829
- best mission_score: **0.9829** (`g0_ws0`, gen=0, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=356, mean=0.2593, median=0.3030, std=0.0786, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=356, mean=31.5983, median=34.0000, std=6.3519, min=5, max=34
- positive_fold_ratio_effective (Stage A pass): n=356, mean=0.5499, median=0.5882, std=0.1345, min=0.0769, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 356, Stage B pass = 286, failures = 70 (primary_sum = 70)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 40 |
| `median_oos_total_pnl<min` | 19 |
| `sum_oos_total_pnl<min` | 6 |
| `n_fold_effective_below_profit_safe_min` | 5 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 40 |
| `median_oos_total_pnl<min` | 59 |
| `sum_oos_total_pnl<min` | 65 |
| `n_fold_effective_below_profit_safe_min` | 23 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=286, None=722

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.3% (23/1008)
- best 個体 trade_count: 57
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 1008
- metric_stage 分布: stage_a_evaluated=70, stage_a_only=652, stage_b_evaluated=153, stage_c_evaluated=133
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=652, mean=-315759.4018, median=-44450.0000, std=429182.7756, min=-1001810.0000, max=30620.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=629): n=629, mean=-327305.4531, median=-49360.0000, std=432613.1575, min=-1001810.0000, max=30620.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=356): n=356, mean=22770.9551, median=25640.0000, std=12601.5403, min=-4120.0000, max=56500.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g4_i27` | 4 | tier1_EUR_JPY | EUR_JPY | 0.0866 | 0.2223 | ✅ | ❌ | ❌ | 50 | — |
| 2 | `g10_i28` | 10 | tier1_EUR_JPY | EUR_JPY | 0.0825 | 0.1270 | ✅ | ✅ | ❌ | 42 | — |
| 3 | `g11_i5` | 11 | tier1_EUR_JPY | EUR_JPY | 0.0732 | 0.1608 | ✅ | ❌ | ❌ | 40 | — |
| 4 | `g11_i25` | 11 | tier1_EUR_JPY | EUR_JPY | 0.0702 | 0.1535 | ✅ | ❌ | ❌ | 41 | — |
| 5 | `g6_i8` | 6 | tier1_EUR_JPY | EUR_JPY | 0.0689 | 0.1326 | ✅ | ❌ | ❌ | 52 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.029594761092667066 |
| 1 | 0.029594761092667066 |
| 2 | 0.029594761092667066 |
| 3 | 0.059449440243853804 |
| 4 | 0.0866065602369258 |
| 5 | 0.04512178990135417 |
| 6 | 0.06892680356850293 |
| 7 | 0.036315375091769866 |
| 8 | 0.06242685873967673 |
| 9 | 0.036315375091769866 |
| 10 | 0.08245316266426153 |
| 11 | 0.07323162392844051 |
| 12 | 0.05254440709241834 |
| 13 | 0.05254440709241834 |
| 14 | 0.05254440709241834 |
| 15 | 0.05254440709241834 |
| 16 | 0.05254440709241834 |
| 17 | 0.05254440709241834 |
| 18 | 0.0630451021589049 |
| 19 | 0.05254440709241834 |
| 20 | 0.060921259421917374 |

