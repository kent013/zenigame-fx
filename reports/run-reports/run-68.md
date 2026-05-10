# Run 68 — run_20260510_183709

**Generated**: 2026-05-10T18:37:10.635213+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.23734392145893643 / threshold 1.0
- ❌ **total_pnl**: -40890.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 5.316235429046004 / threshold 20.0
- ❌ **trade_count**: 43 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 53

## Best 個体

- name: `g53_i24`
- generation: 53
- fitness: **0.21784392145893644**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 43
- total_pnl: -40890.0
- sharpe: 0.23734392145893643
- sortino: —
- calmar: —
- max_drawdown_pct: 5.316235429046004

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2424
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1800
- Stage B pass: 235
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1800 | 235 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1800 | 235 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2889, median=1.0000, std=0.4600, min=0, max=2
- n_nodes: n=5856, mean=3.5268, median=3.0000, std=1.6816, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=228, mean=0.2918, median=0.2906, std=0.0118, min=0.2774, max=0.4481
- best mission_score: **0.4481** (`g42_i51`, gen=42, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1800, mean=0.1842, median=0.1818, std=0.0554, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=1800, mean=31.4828, median=34.0000, std=5.9191, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1795, mean=0.5048, median=0.5294, std=0.1199, min=0.0000, max=0.7647

## Stage B failure reason 集計

- Stage A pass = 1800, Stage B pass = 235, failures = 1565 (primary_sum = 1565)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 969 |
| `positive_fold_ratio<min` | 596 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 5 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 969 |
| `positive_fold_ratio<min` | 1565 |
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
- trade_count=0 個体比率: 5.2% (305/5856)
- best 個体 trade_count: 43
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1565, stage_a_only=4056, stage_b_evaluated=235
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4056, mean=-504105.0986, median=-277825.0000, std=474108.8969, min=-1003890.0000, max=44800.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3751): n=3751, mean=-545094.7161, median=-1000000.0000, std=469801.2279, min=-1003890.0000, max=44800.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1800): n=1800, mean=16569.6389, median=19220.0000, std=49537.9938, min=-1000210.0000, max=70370.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g36_i51` | 36 | tier1_EUR_JPY | EUR_JPY | 0.3359 | 0.3724 | ✅ | ❌ | ❌ | 33 | — |
| 2 | `g37_i53` | 37 | tier1_EUR_JPY | EUR_JPY | 0.3359 | 0.3724 | ✅ | ❌ | ❌ | 33 | — |
| 3 | `g40_i45` | 40 | tier1_EUR_JPY | EUR_JPY | 0.3270 | 0.3655 | ✅ | ❌ | ❌ | 31 | — |
| 4 | `g49_i91` | 49 | tier1_EUR_JPY | EUR_JPY | 0.3185 | 0.3560 | ✅ | ❌ | ❌ | 32 | — |
| 5 | `g60_i53` | 60 | tier1_EUR_JPY | EUR_JPY | 0.3109 | 0.3439 | ✅ | ❌ | ❌ | 32 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.0065366097006969975 |
| 1 | -0.0065366097006969975 |
| 2 | -0.0065366097006969975 |
| 3 | -0.0065366097006969975 |
| 4 | -0.0065366097006969975 |
| 5 | -0.0065366097006969975 |
| 6 | -0.0065366097006969975 |
| 7 | -0.0065366097006969975 |
| 8 | 0.11323887574533913 |
| 9 | 0.11323887574533913 |
| 10 | 0.11323887574533913 |
| 11 | 0.11798324028301126 |
| 12 | 0.12771701358636986 |
| 13 | 0.12771701358636986 |
| 14 | 0.12771701358636986 |
| 15 | 0.14892229802562434 |
| 16 | 0.14892229802562434 |
| 17 | 0.14892229802562434 |
| 18 | 0.14892229802562434 |
| 19 | 0.14892229802562434 |
| 20 | 0.14892229802562434 |
| 21 | 0.13446609349470523 |
| 22 | 0.08339697188325197 |
| 23 | 0.1068215279058931 |
| 24 | 0.15176559221164337 |
| 25 | 0.18029341140860936 |
| 26 | 0.18029341140860936 |
| 27 | 0.18029341140860936 |
| 28 | 0.1846377488446126 |
| 29 | 0.18029341140860936 |
| 30 | 0.18029341140860936 |
| 31 | 0.18681352679738172 |
| 32 | 0.18681352679738172 |
| 33 | 0.18681352679738172 |
| 34 | 0.18631272051258524 |
| 35 | 0.19007280951621064 |
| 36 | 0.33591464868188403 |
| 37 | 0.33591464868188403 |
| 38 | 0.24484858016700167 |
| 39 | 0.2467679241203088 |
| 40 | 0.32699602685255325 |
| 41 | 0.21910302231181986 |
| 42 | 0.1874101895801382 |
| 43 | 0.1874101895801382 |
| 44 | 0.1928063266944428 |
| 45 | 0.22552262676914672 |
| 46 | 0.1921450782730091 |
| 47 | 0.2373732314957934 |
| 48 | 0.19822256243587805 |
| 49 | 0.318523435846124 |
| 50 | 0.29580308758969953 |
| 51 | 0.29922319067569547 |
| 52 | 0.29580308758969953 |
| 53 | 0.29580308758969953 |
| 54 | 0.21784392145893644 |
| 55 | 0.22143817192458118 |
| 56 | 0.22143817192458118 |
| 57 | 0.21784392145893644 |
| 58 | 0.21784392145893644 |
| 59 | 0.21784392145893644 |
| 60 | 0.31085465226276654 |

