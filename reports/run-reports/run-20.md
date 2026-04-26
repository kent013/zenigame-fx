# Run 20 — run_20260426_145502

**Generated**: 2026-04-26T14:55:02.637176+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: -0.18918533668417017 / threshold 1.0
- ❌ **total_pnl**: -16850.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 2.0554226475279105 / threshold 20.0
- ✅ **trade_count**: 58 (range 50〜5000)

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

- name: `g53_i76`
- generation: 53
- fitness: **0.06848772556319638**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 58
- total_pnl: -16850.0
- sharpe: -0.18918533668417017
- sortino: —
- calmar: —
- max_drawdown_pct: 2.0554226475279105

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3750
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2750
- Stage B pass: 834
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2750 | 834 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2750 | 834 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9978, median=1.0000, std=0.0471, min=0, max=1
- n_nodes: n=5856, mean=2.8887, median=3.0000, std=0.9770, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=834, mean=0.3088, median=0.3091, std=0.0009, min=0.2969, max=0.3111
- best mission_score: **0.3111** (`g60_i56`, gen=60, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2750, mean=0.1105, median=0.0000, std=0.1472, min=0.0000, max=0.6250
- dsr: n=0
- n_fold_effective (Stage A pass): n=2750, mean=3.1251, median=1.0000, std=3.6541, min=0, max=9
- positive_fold_ratio_effective (Stage A pass): n=1461, mean=0.7003, median=0.7778, std=0.2297, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2750, Stage B pass = 834, failures = 1916 (primary_sum = 1916)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1869 |
| `positive_fold_ratio<min` | 47 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1289 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1869 |
| `positive_fold_ratio<min` | 1902 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 3.0% (173/5856)
- best 個体 trade_count: 58
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- Stage A provenance: not available (sidecar 不在)

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g32_i48` | 32 | tier1_EUR_JPY | EUR_JPY | 0.3269 | 0.3464 | ✅ | ❌ | ❌ | 86 | — |
| 2 | `g33_i32` | 33 | tier1_EUR_JPY | EUR_JPY | 0.3166 | 0.3361 | ✅ | ❌ | ❌ | 64 | — |
| 3 | `g34_i69` | 34 | tier1_EUR_JPY | EUR_JPY | 0.3088 | 0.3283 | ✅ | ❌ | ❌ | 69 | — |
| 4 | `g35_i51` | 35 | tier1_EUR_JPY | EUR_JPY | 0.3088 | 0.3283 | ✅ | ❌ | ❌ | 69 | — |
| 5 | `g36_i65` | 36 | tier1_EUR_JPY | EUR_JPY | 0.3088 | 0.3283 | ✅ | ❌ | ❌ | 69 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03565276596897986 |
| 1 | -0.025767087750850626 |
| 2 | -0.02278017361223504 |
| 3 | -0.02278017361223504 |
| 4 | -0.010946774701307154 |
| 5 | -0.010946774701307154 |
| 6 | -0.010946774701307154 |
| 7 | -0.010946774701307154 |
| 8 | -0.010946774701307154 |
| 9 | -0.010946774701307154 |
| 10 | -0.010946774701307154 |
| 11 | -0.007426282374568747 |
| 12 | 0.001191574878890109 |
| 13 | 0.004814598025298145 |
| 14 | 0.004814598025298145 |
| 15 | 0.05157940282817973 |
| 16 | 0.05157940282817973 |
| 17 | 0.05157940282817973 |
| 18 | 0.10604102199043948 |
| 19 | 0.10604102199043948 |
| 20 | 0.10604102199043948 |
| 21 | 0.17954890756165115 |
| 22 | 0.17954890756165115 |
| 23 | 0.17954890756165115 |
| 24 | 0.20904109805531643 |
| 25 | 0.20904109805531643 |
| 26 | 0.21958003469474682 |
| 27 | 0.25718984871011935 |
| 28 | 0.2751739251742484 |
| 29 | 0.27626446485518574 |
| 30 | 0.27626446485518574 |
| 31 | 0.29117505893462275 |
| 32 | 0.3269043027120239 |
| 33 | 0.3165521256234477 |
| 34 | 0.30875937297469086 |
| 35 | 0.30875937297469086 |
| 36 | 0.30875937297469086 |
| 37 | 0.2939414689188005 |
| 38 | 0.24017498220288444 |
| 39 | 0.1411986348648418 |
| 40 | 0.20047695643396904 |
| 41 | 0.19541632626570307 |
| 42 | 0.11414384215683938 |
| 43 | 0.12725100637568962 |
| 44 | 0.11328032500429762 |
| 45 | 0.13975179033388155 |
| 46 | 0.144366401431209 |
| 47 | 0.13671988074391464 |
| 48 | 0.18312721063938112 |
| 49 | 0.16188679760589111 |
| 50 | 0.16188679760589111 |
| 51 | 0.1522718310606993 |
| 52 | 0.11176207305762302 |
| 53 | 0.1265421440372535 |
| 54 | 0.1265421440372535 |
| 55 | 0.1265421440372535 |
| 56 | 0.13551802211758468 |
| 57 | 0.11904586832132098 |
| 58 | 0.1160406739402315 |
| 59 | 0.11479206224578649 |
| 60 | 0.1394470808326284 |

