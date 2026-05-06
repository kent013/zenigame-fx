# Run 43 — run_20260506_170904

**Generated**: 2026-05-06T17:10:45.464744+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.015171643669561764 / threshold 1.0
- ❌ **total_pnl**: -1000130.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 3387 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 5
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g27_i3`
- generation: 27
- fitness: **0.010671643669561765**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 3387
- total_pnl: -1000130.0
- sharpe: 0.015171643669561764
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1199
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1199 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1199 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2442, median=1.0000, std=0.4324, min=0, max=2
- n_nodes: n=5856, mean=2.0702, median=1.0000, std=1.4373, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1199, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1199, mean=11, median=11, std=0.0000, min=11, max=11
- positive_fold_ratio_effective (Stage A pass): n=1199, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000

## Stage B failure reason 集計

- Stage A pass = 1199, Stage B pass = 0, failures = 1199 (primary_sum = 1199)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1199 |
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
| `median_oos_sharpe<min` | 1199 |
| `positive_fold_ratio<min` | 1199 |
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
- trade_count=0 個体比率: 2.1% (125/5856)
- best 個体 trade_count: 3387
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1199, stage_a_only=4657
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4657, mean=-921525.9674, median=-1000200.0000, std=257058.6835, min=-1008690.0000, max=26980.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4532): n=4532, mean=-946943.1664, median=-1000210.0000, std=209363.5492, min=-1008690.0000, max=26980.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1199): n=1199, mean=-1000336.7807, median=-1000130.0000, std=258.3110, min=-1001670.0000, max=-1000010.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g27_i3` | 27 | tier1_EUR_JPY | EUR_JPY | 0.0107 | 0.0152 | ✅ | ❌ | ❌ | 3387 | — |
| 2 | `g28_i0` | 28 | tier1_EUR_JPY | EUR_JPY | 0.0107 | 0.0152 | ✅ | ❌ | ❌ | 3387 | — |
| 3 | `g28_i3` | 28 | tier1_EUR_JPY | EUR_JPY | 0.0107 | 0.0152 | ✅ | ❌ | ❌ | 3387 | — |
| 4 | `g28_i25` | 28 | tier1_EUR_JPY | EUR_JPY | 0.0107 | 0.0152 | ✅ | ❌ | ❌ | 3387 | — |
| 5 | `g29_i0` | 29 | tier1_EUR_JPY | EUR_JPY | 0.0107 | 0.0152 | ✅ | ❌ | ❌ | 3387 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036511484633228654 |
| 1 | -0.029208169806112176 |
| 2 | -0.02581615842249805 |
| 3 | -0.02581615842249805 |
| 4 | -0.02581615842249805 |
| 5 | -0.02581615842249805 |
| 6 | -0.02581615842249805 |
| 7 | -0.02581615842249805 |
| 8 | 0.0055671683186517525 |
| 9 | 0.0055671683186517525 |
| 10 | 0.0055671683186517525 |
| 11 | 0.0055671683186517525 |
| 12 | 0.0055671683186517525 |
| 13 | 0.0055671683186517525 |
| 14 | 0.0055671683186517525 |
| 15 | 0.0055671683186517525 |
| 16 | 0.0055671683186517525 |
| 17 | 0.0055671683186517525 |
| 18 | 0.0055671683186517525 |
| 19 | 0.0055671683186517525 |
| 20 | 0.0055671683186517525 |
| 21 | 0.0055671683186517525 |
| 22 | 0.0055671683186517525 |
| 23 | 0.0055671683186517525 |
| 24 | 0.0055671683186517525 |
| 25 | 0.0055671683186517525 |
| 26 | 0.0055671683186517525 |
| 27 | 0.010671643669561765 |
| 28 | 0.010671643669561765 |
| 29 | 0.010671643669561765 |
| 30 | 0.010671643669561765 |
| 31 | 0.010671643669561765 |
| 32 | 0.010671643669561765 |
| 33 | 0.010671643669561765 |
| 34 | 0.010671643669561765 |
| 35 | 0.010671643669561765 |
| 36 | 0.010671643669561765 |
| 37 | 0.010671643669561765 |
| 38 | 0.010671643669561765 |
| 39 | 0.010671643669561765 |
| 40 | 0.010671643669561765 |
| 41 | 0.010671643669561765 |
| 42 | 0.010671643669561765 |
| 43 | 0.010671643669561765 |
| 44 | 0.010671643669561765 |
| 45 | 0.010671643669561765 |
| 46 | 0.010671643669561765 |
| 47 | 0.010671643669561765 |
| 48 | 0.010671643669561765 |
| 49 | 0.010671643669561765 |
| 50 | 0.010671643669561765 |
| 51 | 0.010671643669561765 |
| 52 | 0.010671643669561765 |
| 53 | 0.010671643669561765 |
| 54 | 0.010671643669561765 |
| 55 | 0.010671643669561765 |
| 56 | 0.010671643669561765 |
| 57 | 0.010671643669561765 |
| 58 | 0.010671643669561765 |
| 59 | 0.010671643669561765 |
| 60 | 0.010671643669561765 |

