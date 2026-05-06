# Run 42 — run_20260506_161320

**Generated**: 2026-05-06T16:13:31.047553+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.040145970017523396 / threshold 1.0
- ❌ **total_pnl**: 8120.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 104 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g60_i35`
- generation: 60
- fitness: **0.029645970017523397**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 104
- total_pnl: 8120.0
- sharpe: 0.040145970017523396
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 745
- Stage B pass: 0
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 745 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 745 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3823, median=1.0000, std=0.5866, min=0, max=3
- n_nodes: n=5856, mean=2.6723, median=2.0000, std=1.7881, min=1, max=12

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=745, mean=0.0072, median=0.0000, std=0.0352, min=0.0000, max=0.3000
- dsr: n=0
- n_fold_effective (Stage A pass): n=745, mean=8.2631, median=11, std=4.0653, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=711, mean=0.0186, median=0.0000, std=0.0926, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 745, Stage B pass = 0, failures = 745 (primary_sum = 745)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 745 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 34 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 745 |
| `positive_fold_ratio<min` | 745 |
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
- trade_count=0 個体比率: 4.4% (259/5856)
- best 個体 trade_count: 104
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=745, stage_a_only=5111
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5111, mean=-829716.8754, median=-1000160.0000, std=358543.1422, min=-1008530.0000, max=29390.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4852): n=4852, mean=-874007.2032, median=-1000170.0000, std=310974.7492, min=-1008530.0000, max=29390.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=745): n=745, mean=-654250.2013, median=-1000480.0000, std=485773.8456, min=-1001000.0000, max=42120.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g44_i30` | 44 | tier1_EUR_JPY | EUR_JPY | 0.2922 | 0.3057 | ✅ | ❌ | ❌ | 47 | — |
| 2 | `g52_i29` | 52 | tier1_EUR_JPY | EUR_JPY | 0.2683 | 0.2843 | ✅ | ❌ | ❌ | 49 | — |
| 3 | `g59_i87` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2603 | 0.2753 | ✅ | ❌ | ❌ | 64 | — |
| 4 | `g60_i1` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2603 | 0.2753 | ✅ | ❌ | ❌ | 64 | — |
| 5 | `g60_i57` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2603 | 0.2753 | ✅ | ❌ | ❌ | 64 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.031639558606700126 |
| 1 | -0.015094251607596754 |
| 2 | -0.015094251607596754 |
| 3 | -0.015094251607596754 |
| 4 | 0.03381005997320434 |
| 5 | -0.008238163610070551 |
| 6 | -0.008238163610070551 |
| 7 | -0.002238163610070552 |
| 8 | -0.002238163610070552 |
| 9 | -0.002238163610070552 |
| 10 | -0.002238163610070552 |
| 11 | -0.002238163610070552 |
| 12 | -0.002238163610070552 |
| 13 | -0.002238163610070552 |
| 14 | -0.002238163610070552 |
| 15 | -0.002238163610070552 |
| 16 | -0.002238163610070552 |
| 17 | -0.002238163610070552 |
| 18 | -0.002238163610070552 |
| 19 | -0.002238163610070552 |
| 20 | -0.002238163610070552 |
| 21 | 0.005791344150884138 |
| 22 | 0.005791344150884138 |
| 23 | 0.005791344150884138 |
| 24 | 0.005791344150884138 |
| 25 | 0.005791344150884138 |
| 26 | 0.005791344150884138 |
| 27 | 0.005791344150884138 |
| 28 | 0.005791344150884138 |
| 29 | 0.005791344150884138 |
| 30 | 0.005791344150884138 |
| 31 | 0.005791344150884138 |
| 32 | 0.005791344150884138 |
| 33 | 0.005791344150884138 |
| 34 | 0.0909535943539708 |
| 35 | 0.0909535943539708 |
| 36 | 0.0909535943539708 |
| 37 | 0.1809531091973276 |
| 38 | 0.0909535943539708 |
| 39 | 0.0909535943539708 |
| 40 | 0.0909535943539708 |
| 41 | 0.14023059299145263 |
| 42 | 0.14023059299145263 |
| 43 | 0.14023059299145263 |
| 44 | 0.29215212734041957 |
| 45 | 0.14377166088108162 |
| 46 | 0.2465973935942365 |
| 47 | 0.2465973935942365 |
| 48 | 0.2465973935942365 |
| 49 | 0.2465973935942365 |
| 50 | 0.2465973935942365 |
| 51 | 0.2465973935942365 |
| 52 | 0.26831891622567083 |
| 53 | 0.2465973935942365 |
| 54 | 0.2465973935942365 |
| 55 | 0.2465973935942365 |
| 56 | 0.2467253966914159 |
| 57 | 0.2467253966914159 |
| 58 | 0.2467253966914159 |
| 59 | 0.2603492668734158 |
| 60 | 0.2603492668734158 |

