# Run 48 — run_20260507_014254

**Generated**: 2026-05-07T01:44:45.069467+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.2417390315293707 / threshold 1.0
- ❌ **total_pnl**: 28590.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
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
- seed: 23

## Best 個体

- name: `g56_i28`
- generation: 56
- fitness: **0.22223903152937072**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 53
- total_pnl: 28590.0
- sharpe: 0.2417390315293707
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2222
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1996
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1996 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1996 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2939, median=1.0000, std=0.4645, min=0, max=2
- n_nodes: n=5856, mean=3.8945, median=4.0000, std=1.7550, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1996, mean=0.1642, median=0.2222, std=0.1185, min=0.0000, max=0.5556
- dsr: n=0
- n_fold_effective (Stage A pass): n=1996, mean=9.7380, median=10.0000, std=1.3028, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=1987, mean=0.1046, median=0.1000, std=0.0930, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1996, Stage B pass = 0, failures = 1996 (primary_sum = 1996)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1996 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 9 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1996 |
| `positive_fold_ratio<min` | 1996 |
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
- best 個体 trade_count: 53
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1996, stage_a_only=3860
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3860, mean=-415456.9326, median=-121595.0000, std=458965.7627, min=-1006190.0000, max=20760.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3575): n=3575, mean=-448577.2755, median=-154000.0000, std=461070.0390, min=-1006190.0000, max=20760.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1996): n=1996, mean=13172.3297, median=19260.0000, std=85964.1202, min=-1000940.0000, max=42970.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g26_i95` | 26 | tier1_EUR_JPY | EUR_JPY | 0.2639 | 0.2894 | ✅ | ❌ | ❌ | 44 | — |
| 2 | `g39_i74` | 39 | tier1_EUR_JPY | EUR_JPY | 0.2318 | 0.2533 | ✅ | ❌ | ❌ | 48 | — |
| 3 | `g56_i28` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |
| 4 | `g57_i0` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |
| 5 | `g58_i0` | 58 | tier1_EUR_JPY | EUR_JPY | 0.2222 | 0.2417 | ✅ | ❌ | ❌ | 53 | — |

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
| 33 | 0.21084401307700307 |
| 34 | 0.21084401307700307 |
| 35 | 0.21084401307700307 |
| 36 | 0.21084401307700307 |
| 37 | 0.21084401307700307 |
| 38 | 0.21084401307700307 |
| 39 | 0.2318411742544719 |
| 40 | 0.21084401307700307 |
| 41 | 0.21847686997826332 |
| 42 | 0.21084401307700307 |
| 43 | 0.21084401307700307 |
| 44 | 0.21084401307700307 |
| 45 | 0.21084401307700307 |
| 46 | 0.21084401307700307 |
| 47 | 0.21084401307700307 |
| 48 | 0.21084401307700307 |
| 49 | 0.2117150834955932 |
| 50 | 0.2117150834955932 |
| 51 | 0.2131167121616712 |
| 52 | 0.2131167121616712 |
| 53 | 0.2131167121616712 |
| 54 | 0.2131167121616712 |
| 55 | 0.2131167121616712 |
| 56 | 0.22223903152937072 |
| 57 | 0.22223903152937072 |
| 58 | 0.22223903152937072 |
| 59 | 0.22223903152937072 |
| 60 | 0.22223903152937072 |

