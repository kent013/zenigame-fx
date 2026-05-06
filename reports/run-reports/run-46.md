# Run 46 — run_20260506_212559

**Generated**: 2026-05-06T21:27:45.572641+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.24148618663304747 / threshold 1.0
- ❌ **total_pnl**: 35430.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 59 (range 50〜5000)

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

- name: `g58_i74`
- generation: 58
- fitness: **0.22048618663304748**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 59
- total_pnl: 35430.0
- sharpe: 0.24148618663304747
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1111
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1952
- Stage B pass: 88
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1952 | 88 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1952 | 88 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3881, median=1.0000, std=0.4960, min=0, max=2
- n_nodes: n=5856, mean=3.6651, median=4.0000, std=1.6833, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1952, mean=0.1491, median=0.1111, std=0.1037, min=0.0000, max=0.5556
- dsr: n=0
- n_fold_effective (Stage A pass): n=1952, mean=8.4052, median=9.0000, std=2.0075, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=1949, mean=0.3676, median=0.4000, std=0.2547, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1952, Stage B pass = 88, failures = 1864 (primary_sum = 1864)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1434 |
| `positive_fold_ratio<min` | 430 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 3 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1434 |
| `positive_fold_ratio<min` | 1857 |
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
- trade_count=0 個体比率: 5.1% (300/5856)
- best 個体 trade_count: 59
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1864, stage_a_only=3904, stage_b_evaluated=88
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3904, mean=-401890.3612, median=-101210.0000, std=456553.3412, min=-1006190.0000, max=39280.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3604): n=3604, mean=-435344.0538, median=-129725.0000, std=459595.3524, min=-1006190.0000, max=39280.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1952): n=1952, mean=9278.7500, median=14810.0000, std=86288.9175, min=-1000940.0000, max=48120.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g59_i56` | 59 | tier1_EUR_JPY | EUR_JPY | 0.5424 | 0.5804 | ✅ | ❌ | ❌ | 30 | — |
| 2 | `g52_i60` | 52 | tier1_EUR_JPY | EUR_JPY | 0.4406 | 0.4806 | ✅ | ❌ | ❌ | 31 | — |
| 3 | `g53_i30` | 53 | tier1_EUR_JPY | EUR_JPY | 0.4260 | 0.4480 | ✅ | ❌ | ❌ | 49 | — |
| 4 | `g58_i89` | 58 | tier1_EUR_JPY | EUR_JPY | 0.4072 | 0.4402 | ✅ | ❌ | ❌ | 38 | — |
| 5 | `g57_i32` | 57 | tier1_EUR_JPY | EUR_JPY | 0.4058 | 0.4268 | ✅ | ❌ | ❌ | 52 | — |

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
| 33 | 0.19886586134947973 |
| 34 | 0.1779501553759853 |
| 35 | 0.1779501553759853 |
| 36 | 0.1617805756554315 |
| 37 | 0.15885757274398857 |
| 38 | 0.24443347810607224 |
| 39 | 0.1533845751898636 |
| 40 | 0.22463371167091756 |
| 41 | 0.10697546415445239 |
| 42 | 0.15718731868590494 |
| 43 | 0.19983098145611672 |
| 44 | 0.2114164057960742 |
| 45 | 0.2114164057960742 |
| 46 | 0.2114164057960742 |
| 47 | 0.2114164057960742 |
| 48 | 0.25408456963260406 |
| 49 | 0.21149538659217532 |
| 50 | 0.2198497211239007 |
| 51 | 0.2117671922624509 |
| 52 | 0.44064292224597673 |
| 53 | 0.42604845878194425 |
| 54 | 0.2117671922624509 |
| 55 | 0.21413417419738792 |
| 56 | 0.21694013012756808 |
| 57 | 0.4057502037673329 |
| 58 | 0.4071803835711964 |
| 59 | 0.5424296342040379 |
| 60 | 0.3711950161936395 |

