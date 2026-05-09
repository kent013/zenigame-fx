# Run 59 — run_20260509_142912

**Generated**: 2026-05-09T14:29:13.718783+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.28935242008282835 / threshold 1.0
- ❌ **total_pnl**: 33230.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 45 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 44

## Best 個体

- name: `g33_i27`
- generation: 33
- fitness: **0.2588524200828283**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 45
- total_pnl: 33230.0
- sharpe: 0.28935242008282835
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0909
- dsr: —
- ii_lite_pass: —
- n_nodes: 5
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 929
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 929 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 929 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4969, median=1.0000, std=0.5031, min=0, max=2
- n_nodes: n=5856, mean=3.6959, median=4.0000, std=1.7860, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=929, mean=0.1267, median=0.0909, std=0.0775, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=929, mean=27.1776, median=32, std=8.3527, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=929, mean=0.2883, median=0.2647, std=0.2240, min=0.0000, max=0.6818

## Stage B failure reason 集計

- Stage A pass = 929, Stage B pass = 0, failures = 929 (primary_sum = 929)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 924 |
| `positive_fold_ratio<min` | 5 |
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
| `median_oos_sharpe<min` | 924 |
| `positive_fold_ratio<min` | 929 |
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
- trade_count=0 個体比率: 3.2% (187/5856)
- best 個体 trade_count: 45
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=929, stage_a_only=4927
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4927, mean=-435868.0800, median=-123580.0000, std=465030.2242, min=-1009050.0000, max=22130.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4740): n=4740, mean=-453063.7194, median=-141010.0000, std=465826.0336, min=-1009050.0000, max=22130.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=929): n=929, mean=-3870.6781, median=10970.0000, std=132334.6139, min=-1000370.0000, max=52270.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g55_i15` | 55 | tier1_EUR_JPY | EUR_JPY | 0.2840 | 0.3095 | ✅ | ❌ | ❌ | 74 | — |
| 2 | `g57_i21` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2810 | 0.3165 | ✅ | ❌ | ❌ | 40 | — |
| 3 | `g58_i88` | 58 | tier1_EUR_JPY | EUR_JPY | 0.2810 | 0.3165 | ✅ | ❌ | ❌ | 40 | — |
| 4 | `g40_i41` | 40 | tier1_EUR_JPY | EUR_JPY | 0.2624 | 0.2929 | ✅ | ❌ | ❌ | 45 | — |
| 5 | `g33_i27` | 33 | tier1_EUR_JPY | EUR_JPY | 0.2589 | 0.2894 | ✅ | ❌ | ❌ | 45 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03938231915271159 |
| 1 | -0.013939264267437716 |
| 2 | -0.013939264267437716 |
| 3 | -0.013939264267437716 |
| 4 | -0.013939264267437716 |
| 5 | -0.013939264267437716 |
| 6 | -0.013939264267437716 |
| 7 | -0.013939264267437716 |
| 8 | 0.02981455037270148 |
| 9 | 0.02981455037270148 |
| 10 | 0.10176226746761527 |
| 11 | 0.10176226746761527 |
| 12 | 0.10176226746761527 |
| 13 | 0.10176226746761527 |
| 14 | 0.10176226746761527 |
| 15 | 0.10176226746761527 |
| 16 | 0.10176226746761527 |
| 17 | 0.10176226746761527 |
| 18 | 0.10176226746761527 |
| 19 | 0.1084034343488909 |
| 20 | 0.19232863437671666 |
| 21 | 0.19232863437671666 |
| 22 | 0.1180764884199338 |
| 23 | 0.20254745055922813 |
| 24 | 0.2564733422376976 |
| 25 | 0.25757875457978485 |
| 26 | 0.25757875457978485 |
| 27 | 0.25757875457978485 |
| 28 | 0.25757875457978485 |
| 29 | 0.25757875457978485 |
| 30 | 0.25757875457978485 |
| 31 | 0.25757875457978485 |
| 32 | 0.25757875457978485 |
| 33 | 0.2588524200828283 |
| 34 | 0.2588524200828283 |
| 35 | 0.2588524200828283 |
| 36 | 0.2588524200828283 |
| 37 | 0.2588524200828283 |
| 38 | 0.2588524200828283 |
| 39 | 0.2588524200828283 |
| 40 | 0.26239734083016203 |
| 41 | 0.2588524200828283 |
| 42 | 0.2588524200828283 |
| 43 | 0.2588524200828283 |
| 44 | 0.2588524200828283 |
| 45 | 0.2588524200828283 |
| 46 | 0.2588524200828283 |
| 47 | 0.2588524200828283 |
| 48 | 0.2588524200828283 |
| 49 | 0.2588524200828283 |
| 50 | 0.2588524200828283 |
| 51 | 0.2588524200828283 |
| 52 | 0.2588524200828283 |
| 53 | 0.2588524200828283 |
| 54 | 0.2588524200828283 |
| 55 | 0.2840388331407691 |
| 56 | 0.2588524200828283 |
| 57 | 0.28096231107432706 |
| 58 | 0.28096231107432706 |
| 59 | 0.2588524200828283 |
| 60 | 0.2588524200828283 |

