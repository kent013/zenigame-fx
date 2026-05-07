# Run 47 — run_20260506_233855

**Generated**: 2026-05-06T23:40:45.164245+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.12673669720275707 / threshold 1.0
- ❌ **total_pnl**: 33790.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 89 (range 50〜5000)

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

- name: `g52_i42`
- generation: 52
- fitness: **0.08773669720275706**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 89
- total_pnl: 33790.0
- sharpe: 0.12673669720275707
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2857
- dsr: —
- ii_lite_pass: —
- n_nodes: 8
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1868
- Stage B pass: 3
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1868 | 3 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1868 | 3 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3386, median=1.0000, std=0.4793, min=0, max=2
- n_nodes: n=5856, mean=4.0227, median=4.0000, std=1.8794, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1868, mean=0.0972, median=0.0000, std=0.1471, min=0.0000, max=0.8571
- dsr: n=0
- n_fold_effective (Stage A pass): n=1868, mean=7.9342, median=8.0000, std=0.5178, min=0, max=8
- positive_fold_ratio_effective (Stage A pass): n=1867, mean=0.1210, median=0.0000, std=0.2024, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1868, Stage B pass = 3, failures = 1865 (primary_sum = 1865)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1865 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1865 |
| `positive_fold_ratio<min` | 1730 |
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
- trade_count=0 個体比率: 4.9% (285/5856)
- best 個体 trade_count: 89
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1865, stage_a_only=3988, stage_b_evaluated=3
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3988, mean=-398300.7623, median=-101560.0000, std=456061.0310, min=-1006190.0000, max=24790.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3703): n=3703, mean=-428955.8304, median=-128280.0000, std=459184.0522, min=-1006190.0000, max=24790.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1868): n=1868, mean=10009.0578, median=16135.0000, std=88346.2533, min=-1000940.0000, max=42970.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g26_i95` | 26 | tier1_EUR_JPY | EUR_JPY | 0.2639 | 0.2894 | ✅ | ❌ | ❌ | 44 | — |
| 2 | `g56_i35` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2616 | 0.3146 | ✅ | ❌ | ❌ | 33 | — |
| 3 | `g60_i62` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2475 | 0.2690 | ✅ | ❌ | ❌ | 48 | — |
| 4 | `g39_i66` | 39 | tier1_EUR_JPY | EUR_JPY | 0.2348 | 0.2483 | ✅ | ❌ | ❌ | 52 | — |
| 5 | `g33_i8` | 33 | tier1_EUR_JPY | EUR_JPY | 0.2253 | 0.2473 | ✅ | ❌ | ❌ | 46 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036511484633228654 |
| 1 | -0.0319411810750956 |
| 2 | -0.0319411810750956 |
| 3 | 0.008183593274836639 |
| 4 | 0.008183593274836639 |
| 5 | 0.0267055293483965 |
| 6 | 0.139714460202822 |
| 7 | 0.03140854028223269 |
| 8 | 0.03140854028223269 |
| 9 | 0.03140854028223269 |
| 10 | 0.03140854028223269 |
| 11 | 0.0432778368111328 |
| 12 | 0.05010482931060396 |
| 13 | 0.05445714307913524 |
| 14 | 0.05445714307913524 |
| 15 | 0.12073834278431067 |
| 16 | 0.08309148460103993 |
| 17 | 0.06981602717127808 |
| 18 | 0.08582775776566816 |
| 19 | 0.075437860456114 |
| 20 | 0.075437860456114 |
| 21 | 0.095928501821253 |
| 22 | 0.09720715568596278 |
| 23 | 0.1710709746092857 |
| 24 | 0.1746897686884248 |
| 25 | 0.1746897686884248 |
| 26 | 0.2639400194568124 |
| 27 | 0.1746897686884248 |
| 28 | 0.1746897686884248 |
| 29 | 0.17566007632298067 |
| 30 | 0.17566007632298067 |
| 31 | 0.19886586134947973 |
| 32 | 0.2186256255637327 |
| 33 | 0.2253109404484472 |
| 34 | 0.21084401307700307 |
| 35 | 0.21084401307700307 |
| 36 | 0.192860364788898 |
| 37 | 0.192860364788898 |
| 38 | 0.17166663844964855 |
| 39 | 0.2348220688689197 |
| 40 | 0.20939117536233784 |
| 41 | 0.17166663844964855 |
| 42 | 0.18525708739954855 |
| 43 | 0.17890500808521614 |
| 44 | 0.18525708739954855 |
| 45 | 0.17983235782542886 |
| 46 | 0.18639128533677873 |
| 47 | 0.18392488028976958 |
| 48 | 0.17860013367664682 |
| 49 | 0.19256140941115146 |
| 50 | 0.19256140941115146 |
| 51 | 0.19256140941115146 |
| 52 | 0.19256140941115146 |
| 53 | 0.19256140941115146 |
| 54 | 0.20245752704469058 |
| 55 | 0.20450562570593528 |
| 56 | 0.2616297942188539 |
| 57 | 0.19704310813178114 |
| 58 | 0.14103472061072242 |
| 59 | 0.1363145404454982 |
| 60 | 0.24745478552976466 |

