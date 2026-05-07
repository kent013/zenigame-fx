# Run 53 — run_20260507_142410

**Generated**: 2026-05-07T14:25:45.124658+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.041957518015710744 / threshold 1.0
- ❌ **total_pnl**: 6270.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 61 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 100

## Best 個体

- name: `g52_i27`
- generation: 52
- fitness: **0.03745751801571075**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 61
- total_pnl: 6270.0
- sharpe: 0.041957518015710744
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1111
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1439
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1439 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1439 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6520, median=2.0000, std=0.4771, min=0, max=2
- n_nodes: n=5856, mean=2.8593, median=3.0000, std=1.3899, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1439, mean=0.1123, median=0.1111, std=0.1100, min=0.0000, max=0.4444
- dsr: n=0
- n_fold_effective (Stage A pass): n=1439, mean=8.3968, median=10, std=2.4575, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=1415, mean=0.1489, median=0.1111, std=0.1615, min=0.0000, max=0.8000

## Stage B failure reason 集計

- Stage A pass = 1439, Stage B pass = 0, failures = 1439 (primary_sum = 1439)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1439 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 24 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1439 |
| `positive_fold_ratio<min` | 1439 |
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
- trade_count=0 個体比率: 5.5% (321/5856)
- best 個体 trade_count: 61
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1439, stage_a_only=4417
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4417, mean=-281407.2606, median=-33490.0000, std=419953.0837, min=-1009680.0000, max=21670.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4096): n=4096, mean=-303460.9058, median=-36200.0000, std=428356.6288, min=-1009680.0000, max=21670.0000
  - うち PnL=0 個体: 7 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1439): n=1439, mean=10639.0202, median=11690.0000, std=46884.2237, min=-1000410.0000, max=27800.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g57_i15` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2354 | 0.2669 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g42_i54` | 42 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |
| 3 | `g43_i0` | 43 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |
| 4 | `g44_i0` | 44 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |
| 5 | `g45_i0` | 45 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.04934400993968757 |
| 1 | 0.11284516344650065 |
| 2 | 0.04934400993968757 |
| 3 | 0.04934400993968757 |
| 4 | 0.16430326896687092 |
| 5 | 0.08233710302196119 |
| 6 | 0.08233710302196119 |
| 7 | 0.08233710302196119 |
| 8 | 0.08233710302196119 |
| 9 | 0.11273559020475453 |
| 10 | 0.11273559020475453 |
| 11 | 0.11273559020475453 |
| 12 | 0.11873559020475453 |
| 13 | 0.11873559020475453 |
| 14 | 0.11873559020475453 |
| 15 | 0.11873559020475453 |
| 16 | 0.1540206798053428 |
| 17 | 0.1524495165094141 |
| 18 | 0.1524495165094141 |
| 19 | 0.1524495165094141 |
| 20 | 0.17314583341557252 |
| 21 | 0.17764583341557252 |
| 22 | 0.17764583341557252 |
| 23 | 0.17764583341557252 |
| 24 | 0.17800401537537647 |
| 25 | 0.17800401537537647 |
| 26 | 0.17800401537537647 |
| 27 | 0.17800401537537647 |
| 28 | 0.1801105561440569 |
| 29 | 0.1801105561440569 |
| 30 | 0.1801105561440569 |
| 31 | 0.1801105561440569 |
| 32 | 0.18304677149532644 |
| 33 | 0.18853988155509138 |
| 34 | 0.18936428912448988 |
| 35 | 0.18936428912448988 |
| 36 | 0.18936428912448988 |
| 37 | 0.18936428912448988 |
| 38 | 0.18936428912448988 |
| 39 | 0.18936428912448988 |
| 40 | 0.18936428912448988 |
| 41 | 0.18936428912448988 |
| 42 | 0.1915464011650908 |
| 43 | 0.1915464011650908 |
| 44 | 0.1915464011650908 |
| 45 | 0.1915464011650908 |
| 46 | 0.1915464011650908 |
| 47 | 0.1915464011650908 |
| 48 | 0.1915464011650908 |
| 49 | 0.1915464011650908 |
| 50 | 0.1915464011650908 |
| 51 | 0.1915464011650908 |
| 52 | 0.1915464011650908 |
| 53 | 0.1915464011650908 |
| 54 | 0.1915464011650908 |
| 55 | 0.08238101303303076 |
| 56 | 0.06793026642602955 |
| 57 | 0.2353886466021871 |
| 58 | 0.13724729881770123 |
| 59 | 0.06091489955926364 |
| 60 | 0.058253912145119324 |

