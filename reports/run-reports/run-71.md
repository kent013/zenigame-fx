# Run 71 — run_20260511_024600

**Generated**: 2026-05-11T02:46:00.876199+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.10691550038000608 / threshold 1.0
- ❌ **total_pnl**: -2600.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 2.2605078293630547 / threshold 20.0
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
- seed: 56

## Best 個体

- name: `g52_i30`
- generation: 52
- fitness: **0.07041550038000607**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 33
- total_pnl: -2600.0
- sharpe: 0.10691550038000608
- sortino: —
- calmar: —
- max_drawdown_pct: 2.2605078293630547

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2727
- dsr: —
- ii_lite_pass: —
- n_nodes: 6
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1358
- Stage B pass: 82
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1358 | 82 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1358 | 82 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6247, median=2.0000, std=0.4849, min=0, max=2
- n_nodes: n=5856, mean=4.8926, median=5.0000, std=2.0932, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=82, mean=0.6897, median=0.8163, std=0.2250, min=0.2810, max=0.8522
- best mission_score: **0.8522** (`g34_i76`, gen=34, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1358, mean=0.1264, median=0.1212, std=0.1008, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=1358, mean=25.7828, median=33.0000, std=11.2143, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1348, mean=0.2872, median=0.2000, std=0.2655, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1358, Stage B pass = 82, failures = 1276 (primary_sum = 1276)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1258 |
| `positive_fold_ratio<min` | 18 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 10 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1258 |
| `positive_fold_ratio<min` | 1276 |
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
- trade_count=0 個体比率: 5.2% (306/5856)
- best 個体 trade_count: 33
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1276, stage_a_only=4498, stage_b_evaluated=82
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4498, mean=-452935.3957, median=-156565.0000, std=467109.8672, min=-1007110.0000, max=24050.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4192): n=4192, mean=-485997.9509, median=-237330.0000, std=466958.7241, min=-1007110.0000, max=24050.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1358): n=1358, mean=16945.7879, median=17270.0000, std=29051.6089, min=-1000250.0000, max=60740.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g40_i37` | 40 | tier1_EUR_JPY | EUR_JPY | 0.5330 | 0.5890 | ✅ | ❌ | ❌ | 30 | — |
| 2 | `g41_i72` | 41 | tier1_EUR_JPY | EUR_JPY | 0.4344 | 0.4874 | ✅ | ❌ | ❌ | 33 | — |
| 3 | `g42_i19` | 42 | tier1_EUR_JPY | EUR_JPY | 0.4344 | 0.4874 | ✅ | ❌ | ❌ | 33 | — |
| 4 | `g25_i68` | 25 | tier1_EUR_JPY | EUR_JPY | 0.4275 | 0.4845 | ✅ | ❌ | ❌ | 32 | — |
| 5 | `g21_i35` | 21 | tier1_EUR_JPY | EUR_JPY | 0.4162 | 0.4712 | ✅ | ❌ | ❌ | 34 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.038861152168284965 |
| 1 | -0.025164469212811975 |
| 2 | -0.025164469212811975 |
| 3 | -0.025164469212811975 |
| 4 | 0.011251780325108256 |
| 5 | 0.011251780325108256 |
| 6 | 0.011251780325108256 |
| 7 | 0.011251780325108256 |
| 8 | 0.018359032617500666 |
| 9 | 0.1477365519473849 |
| 10 | 0.1477365519473849 |
| 11 | 0.1477365519473849 |
| 12 | 0.18367789286801783 |
| 13 | 0.24042251460764574 |
| 14 | 0.24042251460764574 |
| 15 | 0.24042251460764574 |
| 16 | 0.33310066834460395 |
| 17 | 0.33310066834460395 |
| 18 | 0.33310066834460395 |
| 19 | 0.33310066834460395 |
| 20 | 0.33310066834460395 |
| 21 | 0.4161926125281129 |
| 22 | 0.4161926125281129 |
| 23 | 0.4161926125281129 |
| 24 | 0.4161926125281129 |
| 25 | 0.42746665213342666 |
| 26 | 0.4161926125281129 |
| 27 | 0.40586683901967013 |
| 28 | 0.3462757970126502 |
| 29 | 0.3480216884912892 |
| 30 | 0.3503581124509585 |
| 31 | 0.3367973141442124 |
| 32 | 0.3657807627763232 |
| 33 | 0.33383816057830124 |
| 34 | 0.3137911317898091 |
| 35 | 0.27743722422831046 |
| 36 | 0.3091388732050647 |
| 37 | 0.3059321348328276 |
| 38 | 0.27951588569283115 |
| 39 | 0.2850639300788696 |
| 40 | 0.5330438777670864 |
| 41 | 0.4344340389950981 |
| 42 | 0.4344340389950981 |
| 43 | 0.24450368642933362 |
| 44 | 0.18462042304596352 |
| 45 | 0.1960167247045597 |
| 46 | 0.3737054399201383 |
| 47 | 0.17587263848090492 |
| 48 | 0.3288915187879118 |
| 49 | 0.312858976318769 |
| 50 | 0.18321540321884408 |
| 51 | 0.18321540321884408 |
| 52 | 0.18321540321884408 |
| 53 | 0.18321540321884408 |
| 54 | 0.23633327129556989 |
| 55 | 0.10591148434876026 |
| 56 | 0.10117108760227067 |
| 57 | 0.24425127292953383 |
| 58 | 0.24425127292953383 |
| 59 | 0.2618079577977995 |
| 60 | 0.29824992485570345 |

