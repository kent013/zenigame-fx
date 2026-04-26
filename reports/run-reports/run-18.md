# Run 18 — run_20260426_013236

**Generated**: 2026-04-26T01:32:36.555678+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.2273666536398508 / threshold 1.0
- ❌ **total_pnl**: 35320.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 79 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g55_i24`
- generation: 55
- fitness: **0.2634723566578819**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 79
- total_pnl: 35320.0
- sharpe: 0.2273666536398508
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
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 3155
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 3155 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 3155 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=3.5874, median=4.0000, std=0.6562, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=3155, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=3155, mean=0, median=0, std=0.0000, min=0, max=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 3155, Stage B pass = 0, failures = 3155 (primary_sum = 3155)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 3155 |
| `positive_fold_ratio<min` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 3155 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 3155 |
| `positive_fold_ratio<min` | 3155 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 4.8% (279/5856)
- best 個体 trade_count: 79
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g55_i24` | 55 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2830 | ✅ | ❌ | ❌ | 79 | — |
| 2 | `g56_i0` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2830 | ✅ | ❌ | ❌ | 79 | — |
| 3 | `g56_i8` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2830 | ✅ | ❌ | ❌ | 79 | — |
| 4 | `g56_i56` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2830 | ✅ | ❌ | ❌ | 79 | — |
| 5 | `g57_i0` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2830 | ✅ | ❌ | ❌ | 79 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 0.0 |
| 3 | -0.021995998486421076 |
| 4 | 0.01375111561984376 |
| 5 | 0.01375111561984376 |
| 6 | 0.01375111561984376 |
| 7 | 0.054181049131885914 |
| 8 | 0.054181049131885914 |
| 9 | 0.054181049131885914 |
| 10 | 0.05715490281716262 |
| 11 | 0.05715490281716262 |
| 12 | 0.05715490281716262 |
| 13 | 0.05715490281716262 |
| 14 | 0.05715490281716262 |
| 15 | 0.10983863202119991 |
| 16 | 0.10983863202119991 |
| 17 | 0.10983863202119991 |
| 18 | 0.13633556434475222 |
| 19 | 0.15292498457030332 |
| 20 | 0.15292498457030332 |
| 21 | 0.15292498457030332 |
| 22 | 0.15292498457030332 |
| 23 | 0.15292498457030332 |
| 24 | 0.15453324689496928 |
| 25 | 0.1737301673213454 |
| 26 | 0.1737301673213454 |
| 27 | 0.17844238669172563 |
| 28 | 0.17844238669172563 |
| 29 | 0.17844238669172563 |
| 30 | 0.2184685046695975 |
| 31 | 0.2234369701931753 |
| 32 | 0.2234369701931753 |
| 33 | 0.2234369701931753 |
| 34 | 0.2234369701931753 |
| 35 | 0.246996767421758 |
| 36 | 0.246996767421758 |
| 37 | 0.246996767421758 |
| 38 | 0.246996767421758 |
| 39 | 0.246996767421758 |
| 40 | 0.2492783046505316 |
| 41 | 0.25187244792659186 |
| 42 | 0.25187244792659186 |
| 43 | 0.25187244792659186 |
| 44 | 0.25187244792659186 |
| 45 | 0.25799162521526936 |
| 46 | 0.25799162521526936 |
| 47 | 0.25799162521526936 |
| 48 | 0.25799162521526936 |
| 49 | 0.25799162521526936 |
| 50 | 0.25799162521526936 |
| 51 | 0.25799162521526936 |
| 52 | 0.25799162521526936 |
| 53 | 0.25799162521526936 |
| 54 | 0.25799162521526936 |
| 55 | 0.2634723566578819 |
| 56 | 0.2634723566578819 |
| 57 | 0.2634723566578819 |
| 58 | 0.2634723566578819 |
| 59 | 0.2634723566578819 |
| 60 | 0.2634723566578819 |

