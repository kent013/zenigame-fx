# Run 45 — run_20260506_194511

**Generated**: 2026-05-06T19:46:45.146270+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.14107348284287202 / threshold 1.0
- ❌ **total_pnl**: 32800.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 78 (range 50〜5000)

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

- name: `g50_i67`
- generation: 50
- fitness: **0.12157348284287202**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 78
- total_pnl: 32800.0
- sharpe: 0.14107348284287202
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3333
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1608
- Stage B pass: 33
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1608 | 33 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1608 | 33 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3251, median=1.0000, std=0.4757, min=0, max=2
- n_nodes: n=5856, mean=3.7739, median=4.0000, std=1.7772, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=5, mean=0.2796, median=0.2808, std=0.0030, min=0.2760, max=0.2840
- best mission_score: **0.2840** (`g58_i50`, gen=58, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1608, mean=0.2579, median=0.3333, std=0.1469, min=0.0000, max=0.6667
- dsr: n=0
- n_fold_effective (Stage A pass): n=1608, mean=8.9248, median=10.0000, std=2.4845, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=1574, mean=0.3188, median=0.3000, std=0.2122, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1608, Stage B pass = 33, failures = 1575 (primary_sum = 1575)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1572 |
| `positive_fold_ratio<min` | 3 |
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
| `median_oos_sharpe<min` | 1572 |
| `positive_fold_ratio<min` | 1420 |
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
- trade_count=0 個体比率: 4.7% (277/5856)
- best 個体 trade_count: 78
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1575, stage_a_only=4248, stage_b_evaluated=33
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4248, mean=-390232.1328, median=-99850.0000, std=453118.1465, min=-1006190.0000, max=30460.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3971): n=3971, mean=-417453.0597, median=-122260.0000, std=456371.0843, min=-1006190.0000, max=30460.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1608): n=1608, mean=3831.1878, median=10970.0000, std=94508.8901, min=-1000940.0000, max=47990.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g36_i18` | 36 | tier1_EUR_JPY | EUR_JPY | 0.3349 | 0.3564 | ✅ | ❌ | ❌ | 48 | — |
| 2 | `g52_i7` | 52 | tier1_EUR_JPY | EUR_JPY | 0.2882 | 0.3207 | ✅ | ❌ | ❌ | 37 | — |
| 3 | `g55_i33` | 55 | tier1_EUR_JPY | EUR_JPY | 0.2421 | 0.2691 | ✅ | ❌ | ❌ | 44 | — |
| 4 | `g31_i61` | 31 | tier1_EUR_JPY | EUR_JPY | 0.2343 | 0.2823 | ✅ | ❌ | ❌ | 38 | — |
| 5 | `g52_i22` | 52 | tier1_EUR_JPY | EUR_JPY | 0.2173 | 0.2553 | ✅ | ❌ | ❌ | 30 | — |

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
| 26 | 0.1581254899209652 |
| 27 | 0.1024697730500527 |
| 28 | 0.1423315591673341 |
| 29 | 0.11199838376509928 |
| 30 | 0.20194021881232516 |
| 31 | 0.23425019545692097 |
| 32 | 0.136959472841433 |
| 33 | 0.12253804149370635 |
| 34 | 0.12535979485154797 |
| 35 | 0.11558241883054406 |
| 36 | 0.33490240612688754 |
| 37 | 0.1391602778466725 |
| 38 | 0.09704636128501523 |
| 39 | 0.1002563796395862 |
| 40 | 0.12453396804802717 |
| 41 | 0.12081574154772276 |
| 42 | 0.1079655123002056 |
| 43 | 0.10072395407238538 |
| 44 | 0.10672395407238539 |
| 45 | 0.15743103086304872 |
| 46 | 0.207246657025147 |
| 47 | 0.10954327171406097 |
| 48 | 0.09308653892498149 |
| 49 | 0.1490630968638667 |
| 50 | 0.14892131552276372 |
| 51 | 0.21564688309891028 |
| 52 | 0.288180259938724 |
| 53 | 0.12157348284287202 |
| 54 | 0.19744721671690435 |
| 55 | 0.24211508541757562 |
| 56 | 0.1464382978358537 |
| 57 | 0.126357200796883 |
| 58 | 0.2148621858225791 |
| 59 | 0.13530417368858053 |
| 60 | 0.1776147093099918 |

