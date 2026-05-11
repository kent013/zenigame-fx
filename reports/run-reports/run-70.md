# Run 70 — run_20260511_012002

**Generated**: 2026-05-11T01:20:03.061285+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.4239063235938345 / threshold 1.0
- ❌ **total_pnl**: 26210.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 32 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 55

## Best 個体

- name: `g29_i30`
- generation: 29
- fitness: **0.3864063235938345**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 32
- total_pnl: 26210.0
- sharpe: 0.4239063235938345
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1515
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 361
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 361 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 361 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4761, median=1.0000, std=0.5008, min=0, max=2
- n_nodes: n=5856, mean=2.7365, median=3.0000, std=1.5048, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=361, mean=0.1153, median=0.1212, std=0.0577, min=0.0000, max=0.3030
- dsr: n=0
- n_fold_effective (Stage A pass): n=361, mean=22.2687, median=16, std=9.2450, min=6, max=34
- positive_fold_ratio_effective (Stage A pass): n=361, mean=0.2437, median=0.2424, std=0.1391, min=0.0000, max=0.5333

## Stage B failure reason 集計

- Stage A pass = 361, Stage B pass = 0, failures = 361 (primary_sum = 361)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 361 |
| `positive_fold_ratio<min` | 0 |
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
| `median_oos_sharpe<min` | 361 |
| `positive_fold_ratio<min` | 361 |
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
- trade_count=0 個体比率: 7.5% (441/5856)
- best 個体 trade_count: 32
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=361, stage_a_only=5495
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5495, mean=-728567.0246, median=-1000110.0000, std=420067.5959, min=-1005290.0000, max=24970.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5054): n=5054, mean=-792140.0475, median=-1000130.0000, std=376158.5389, min=-1005290.0000, max=24970.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=361): n=361, mean=-1272.2992, median=22280.0000, std=140712.5763, min=-1000450.0000, max=27940.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g29_i30` | 29 | tier1_EUR_JPY | EUR_JPY | 0.3864 | 0.4239 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g30_i0` | 30 | tier1_EUR_JPY | EUR_JPY | 0.3864 | 0.4239 | ✅ | ❌ | ❌ | 32 | — |
| 3 | `g30_i10` | 30 | tier1_EUR_JPY | EUR_JPY | 0.3864 | 0.4239 | ✅ | ❌ | ❌ | 32 | — |
| 4 | `g31_i0` | 31 | tier1_EUR_JPY | EUR_JPY | 0.3864 | 0.4239 | ✅ | ❌ | ❌ | 32 | — |
| 5 | `g31_i1` | 31 | tier1_EUR_JPY | EUR_JPY | 0.3864 | 0.4239 | ✅ | ❌ | ❌ | 32 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.04258569678620692 |
| 1 | -0.032610432539155 |
| 2 | -0.028482445855509374 |
| 3 | -0.028482445855509374 |
| 4 | -0.028482445855509374 |
| 5 | 0.052666651924700304 |
| 6 | 0.052666651924700304 |
| 7 | 0.052666651924700304 |
| 8 | 0.052666651924700304 |
| 9 | 0.052666651924700304 |
| 10 | 0.0833776042127769 |
| 11 | 0.12039865861277256 |
| 12 | 0.33370866038212005 |
| 13 | 0.33370866038212005 |
| 14 | 0.33370866038212005 |
| 15 | 0.33370866038212005 |
| 16 | 0.33370866038212005 |
| 17 | 0.33370866038212005 |
| 18 | 0.33370866038212005 |
| 19 | 0.33370866038212005 |
| 20 | 0.33370866038212005 |
| 21 | 0.33370866038212005 |
| 22 | 0.33370866038212005 |
| 23 | 0.33370866038212005 |
| 24 | 0.33370866038212005 |
| 25 | 0.33370866038212005 |
| 26 | 0.33370866038212005 |
| 27 | 0.33370866038212005 |
| 28 | 0.33370866038212005 |
| 29 | 0.3864063235938345 |
| 30 | 0.3864063235938345 |
| 31 | 0.3864063235938345 |
| 32 | 0.3864063235938345 |
| 33 | 0.3864063235938345 |
| 34 | 0.3864063235938345 |
| 35 | 0.3864063235938345 |
| 36 | 0.3864063235938345 |
| 37 | 0.3864063235938345 |
| 38 | 0.3864063235938345 |
| 39 | 0.3864063235938345 |
| 40 | 0.3864063235938345 |
| 41 | 0.3864063235938345 |
| 42 | 0.3864063235938345 |
| 43 | 0.3864063235938345 |
| 44 | 0.3864063235938345 |
| 45 | 0.3864063235938345 |
| 46 | 0.3864063235938345 |
| 47 | 0.3864063235938345 |
| 48 | 0.3864063235938345 |
| 49 | 0.3864063235938345 |
| 50 | 0.3864063235938345 |
| 51 | 0.3864063235938345 |
| 52 | 0.3864063235938345 |
| 53 | 0.3864063235938345 |
| 54 | 0.3864063235938345 |
| 55 | 0.3864063235938345 |
| 56 | 0.3864063235938345 |
| 57 | 0.3864063235938345 |
| 58 | 0.3864063235938345 |
| 59 | 0.3864063235938345 |
| 60 | 0.3864063235938345 |

