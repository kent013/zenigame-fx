# Run 63 — run_20260510_033636

**Generated**: 2026-05-10T03:36:36.872966+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.13993416477134085 / threshold 1.0
- ❌ **total_pnl**: 19710.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.8512968745468432 / threshold 20.0
- ✅ **trade_count**: 53 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 48

## Best 個体

- name: `g59_i44`
- generation: 59
- fitness: **0.12043416477134085**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 53
- total_pnl: 19710.0
- sharpe: 0.13993416477134085
- sortino: —
- calmar: —
- max_drawdown_pct: 1.8512968745468432

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 774
- Stage B pass: 86
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 774 | 86 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 774 | 86 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3689, median=1.0000, std=0.4843, min=0, max=2
- n_nodes: n=5856, mean=2.5193, median=2.0000, std=1.5194, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=86, mean=0.6011, median=0.7875, std=0.2323, min=0.3044, max=0.8116
- best mission_score: **0.8116** (`g59_i66`, gen=59, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=774, mean=0.1974, median=0.2121, std=0.1128, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=774, mean=22.6977, median=28.0000, std=11.1301, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=774, mean=0.4256, median=0.4839, std=0.2191, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 774, Stage B pass = 86, failures = 688 (primary_sum = 688)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 663 |
| `positive_fold_ratio<min` | 25 |
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
| `median_oos_sharpe<min` | 663 |
| `positive_fold_ratio<min` | 688 |
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
- trade_count=0 個体比率: 5.8% (337/5856)
- best 個体 trade_count: 53
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=688, stage_a_only=5082, stage_b_evaluated=86
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5082, mean=-567232.7607, median=-1000020.0000, std=468678.1844, min=-1006050.0000, max=19800.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4745): n=4745, mean=-607518.8388, median=-1000040.0000, std=459113.6635, min=-1006050.0000, max=19800.0000
  - うち PnL=0 個体: 2 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=774): n=774, mean=-1928.0233, median=6640.0000, std=114567.2985, min=-1000320.0000, max=46260.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g48_i80` | 48 | tier1_EUR_JPY | EUR_JPY | 0.2612 | 0.2912 | ✅ | ❌ | ❌ | 65 | — |
| 2 | `g49_i25` | 49 | tier1_EUR_JPY | EUR_JPY | 0.1878 | 0.2178 | ✅ | ❌ | ❌ | 58 | — |
| 3 | `g54_i29` | 54 | tier1_EUR_JPY | EUR_JPY | 0.1605 | 0.1945 | ✅ | ❌ | ❌ | 34 | — |
| 4 | `g50_i9` | 50 | tier1_EUR_JPY | EUR_JPY | 0.1458 | 0.1503 | ✅ | ❌ | ❌ | 76 | — |
| 5 | `g51_i75` | 51 | tier1_EUR_JPY | EUR_JPY | 0.1435 | 0.1540 | ✅ | ❌ | ❌ | 73 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.02600716917263408 |
| 1 | -0.02600716917263408 |
| 2 | -0.02600716917263408 |
| 3 | -0.02600716917263408 |
| 4 | -0.02600716917263408 |
| 5 | -0.02600716917263408 |
| 6 | -0.025804590571059702 |
| 7 | -0.025804590571059702 |
| 8 | 0.02340115789605228 |
| 9 | 0.02340115789605228 |
| 10 | 0.02340115789605228 |
| 11 | 0.02340115789605228 |
| 12 | 0.02340115789605228 |
| 13 | 0.02340115789605228 |
| 14 | 0.02340115789605228 |
| 15 | 0.02340115789605228 |
| 16 | 0.02340115789605228 |
| 17 | 0.02340115789605228 |
| 18 | 0.02340115789605228 |
| 19 | 0.032072272689275635 |
| 20 | 0.032072272689275635 |
| 21 | 0.03657227268927563 |
| 22 | 0.03657227268927563 |
| 23 | 0.03657227268927563 |
| 24 | 0.03657227268927563 |
| 25 | 0.12193917445573745 |
| 26 | 0.12193917445573745 |
| 27 | 0.12793917445573744 |
| 28 | 0.12793917445573744 |
| 29 | 0.12793917445573744 |
| 30 | 0.12193917445573745 |
| 31 | 0.05002438998425114 |
| 32 | 0.03650317646983803 |
| 33 | 0.12437444756977929 |
| 34 | 0.12611938144799445 |
| 35 | 0.12611938144799445 |
| 36 | 0.12611938144799445 |
| 37 | 0.03650317646983803 |
| 38 | 0.03650317646983803 |
| 39 | 0.13176528901676668 |
| 40 | 0.1384612877010058 |
| 41 | 0.1384612877010058 |
| 42 | 0.10338887083589997 |
| 43 | 0.11742960921131072 |
| 44 | 0.1112721349520529 |
| 45 | 0.09432864679042638 |
| 46 | 0.09599664093393788 |
| 47 | 0.08832864679042639 |
| 48 | 0.26124391390647705 |
| 49 | 0.18777669360079174 |
| 50 | 0.14583446487229731 |
| 51 | 0.14346433919195214 |
| 52 | 0.14066773450778042 |
| 53 | 0.14066773450778042 |
| 54 | 0.16051397945781098 |
| 55 | 0.13091074559521038 |
| 56 | 0.13091074559521038 |
| 57 | 0.11486841777185954 |
| 58 | 0.11533538527404975 |
| 59 | 0.12043416477134085 |
| 60 | 0.12043416477134085 |

