# Run 67 — run_20260510_143709

**Generated**: 2026-05-10T14:37:10.027602+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.05726611115251221 / threshold 1.0
- ❌ **total_pnl**: -5780.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 2.5682577096837558 / threshold 20.0
- ✅ **trade_count**: 75 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 52

## Best 個体

- name: `g58_i71`
- generation: 58
- fitness: **0.04826611115251221**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 75
- total_pnl: -5780.0
- sharpe: 0.05726611115251221
- sortino: —
- calmar: —
- max_drawdown_pct: 2.5682577096837558

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2424
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1497
- Stage B pass: 101
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1497 | 101 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1497 | 101 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4903, median=1.0000, std=0.5033, min=0, max=2
- n_nodes: n=5856, mean=4.3651, median=4.0000, std=2.0747, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=101, mean=0.5757, median=0.5109, std=0.1532, min=0.2938, max=0.7438
- best mission_score: **0.7438** (`g46_i80`, gen=46, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1497, mean=0.2111, median=0.2121, std=0.0934, min=0.0000, max=0.4545
- dsr: n=0
- n_fold_effective (Stage A pass): n=1497, mean=26.8150, median=31, std=8.2339, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=1497, mean=0.4001, median=0.4286, std=0.1581, min=0.0000, max=0.7619

## Stage B failure reason 集計

- Stage A pass = 1497, Stage B pass = 101, failures = 1396 (primary_sum = 1396)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1296 |
| `positive_fold_ratio<min` | 100 |
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
| `median_oos_sharpe<min` | 1296 |
| `positive_fold_ratio<min` | 1396 |
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
- trade_count=0 個体比率: 4.9% (289/5856)
- best 個体 trade_count: 75
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1396, stage_a_only=4359, stage_b_evaluated=101
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4359, mean=-420364.3427, median=-112580.0000, std=460758.6208, min=-1006850.0000, max=31850.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4070): n=4070, mean=-450213.3096, median=-141315.0000, std=462530.9323, min=-1006850.0000, max=31850.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1497): n=1497, mean=14275.0434, median=12760.0000, std=9497.8964, min=-4760.0000, max=56140.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g45_i5` | 45 | tier1_EUR_JPY | EUR_JPY | 0.4101 | 0.4666 | ✅ | ❌ | ❌ | 31 | — |
| 2 | `g36_i56` | 36 | tier1_EUR_JPY | EUR_JPY | 0.4008 | 0.4583 | ✅ | ❌ | ❌ | 30 | — |
| 3 | `g37_i57` | 37 | tier1_EUR_JPY | EUR_JPY | 0.3888 | 0.4463 | ✅ | ❌ | ❌ | 30 | — |
| 4 | `g32_i27` | 32 | tier1_EUR_JPY | EUR_JPY | 0.3658 | 0.4233 | ✅ | ❌ | ❌ | 30 | — |
| 5 | `g33_i0` | 33 | tier1_EUR_JPY | EUR_JPY | 0.3658 | 0.4233 | ✅ | ❌ | ❌ | 30 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.05739123789916521 |
| 1 | 0.05739123789916521 |
| 2 | 0.05739123789916521 |
| 3 | 0.05739123789916521 |
| 4 | 0.05739123789916521 |
| 5 | 0.05739123789916521 |
| 6 | 0.05739123789916521 |
| 7 | 0.05739123789916521 |
| 8 | 0.05739123789916521 |
| 9 | 0.05739123789916521 |
| 10 | 0.05739123789916521 |
| 11 | 0.05739123789916521 |
| 12 | 0.05739123789916521 |
| 13 | 0.05739123789916521 |
| 14 | 0.05739123789916521 |
| 15 | 0.05739123789916521 |
| 16 | 0.1342724090099567 |
| 17 | 0.1342724090099567 |
| 18 | 0.1342724090099567 |
| 19 | 0.1342724090099567 |
| 20 | 0.13601007166936968 |
| 21 | 0.13601007166936968 |
| 22 | 0.13601007166936968 |
| 23 | 0.13601007166936968 |
| 24 | 0.3494309244315439 |
| 25 | 0.3494309244315439 |
| 26 | 0.3494309244315439 |
| 27 | 0.3494309244315439 |
| 28 | 0.3494309244315439 |
| 29 | 0.3494309244315439 |
| 30 | 0.3494309244315439 |
| 31 | 0.3494309244315439 |
| 32 | 0.3657787237325321 |
| 33 | 0.3657787237325321 |
| 34 | 0.3657787237325321 |
| 35 | 0.3657787237325321 |
| 36 | 0.40080393600682446 |
| 37 | 0.3888200042261026 |
| 38 | 0.2059527995597238 |
| 39 | 0.2059527995597238 |
| 40 | 0.32809679988279333 |
| 41 | 0.32809679988279333 |
| 42 | 0.32809679988279333 |
| 43 | 0.32809679988279333 |
| 44 | 0.32809679988279333 |
| 45 | 0.4101102164677815 |
| 46 | 0.32809679988279333 |
| 47 | 0.158585593015105 |
| 48 | 0.22829328424302736 |
| 49 | 0.1638065551785674 |
| 50 | 0.1638065551785674 |
| 51 | 0.18761319361099946 |
| 52 | 0.1638065551785674 |
| 53 | 0.1638065551785674 |
| 54 | 0.24214838341038167 |
| 55 | 0.24214838341038167 |
| 56 | 0.24214838341038167 |
| 57 | 0.23862629861185344 |
| 58 | 0.24214838341038167 |
| 59 | 0.1961676934642375 |
| 60 | 0.1976696328979116 |

