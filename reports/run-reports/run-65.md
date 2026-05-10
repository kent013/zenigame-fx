# Run 65 — run_20260510_083045

**Generated**: 2026-05-10T08:30:46.468857+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.42488893903325425 / threshold 1.0
- ❌ **total_pnl**: 26220.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 42 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 50

## Best 個体

- name: `g57_i57`
- generation: 57
- fitness: **0.3943889390332542**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 42
- total_pnl: 26220.0
- sharpe: 0.42488893903325425
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0606
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 408
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 408 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 408 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2862, median=1.0000, std=0.4980, min=0, max=2
- n_nodes: n=5856, mean=2.5364, median=2.0000, std=1.4894, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=408, mean=0.0504, median=0.0606, std=0.0475, min=0.0000, max=0.2121
- dsr: n=0
- n_fold_effective (Stage A pass): n=408, mean=22.0735, median=21.0000, std=10.6144, min=6, max=34
- positive_fold_ratio_effective (Stage A pass): n=408, mean=0.0974, median=0.1176, std=0.0966, min=0.0000, max=0.5000

## Stage B failure reason 集計

- Stage A pass = 408, Stage B pass = 0, failures = 408 (primary_sum = 408)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 408 |
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
| `median_oos_sharpe<min` | 408 |
| `positive_fold_ratio<min` | 408 |
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
- trade_count=0 個体比率: 6.1% (355/5856)
- best 個体 trade_count: 42
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=408, stage_a_only=5448
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5448, mean=-767730.4167, median=-1000120.0000, std=399745.8838, min=-1014140.0000, max=22750.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5093): n=5093, mean=-821243.9250, median=-1000140.0000, std=356353.0898, min=-1014140.0000, max=22750.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=408): n=408, mean=-231499.7794, median=23100.0000, std=441026.0938, min=-1000600.0000, max=32820.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g57_i57` | 57 | tier1_EUR_JPY | EUR_JPY | 0.3944 | 0.4249 | ✅ | ❌ | ❌ | 42 | — |
| 2 | `g58_i0` | 58 | tier1_EUR_JPY | EUR_JPY | 0.3944 | 0.4249 | ✅ | ❌ | ❌ | 42 | — |
| 3 | `g58_i76` | 58 | tier1_EUR_JPY | EUR_JPY | 0.3944 | 0.4249 | ✅ | ❌ | ❌ | 42 | — |
| 4 | `g59_i0` | 59 | tier1_EUR_JPY | EUR_JPY | 0.3944 | 0.4249 | ✅ | ❌ | ❌ | 42 | — |
| 5 | `g59_i1` | 59 | tier1_EUR_JPY | EUR_JPY | 0.3944 | 0.4249 | ✅ | ❌ | ❌ | 42 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.003257241606186713 |
| 1 | -0.003257241606186713 |
| 2 | -0.003257241606186713 |
| 3 | -0.003257241606186713 |
| 4 | -0.003257241606186713 |
| 5 | -0.003257241606186713 |
| 6 | -0.003257241606186713 |
| 7 | -0.003257241606186713 |
| 8 | -0.003257241606186713 |
| 9 | -0.003257241606186713 |
| 10 | -0.003257241606186713 |
| 11 | -0.003257241606186713 |
| 12 | -0.003257241606186713 |
| 13 | -0.003257241606186713 |
| 14 | -0.003257241606186713 |
| 15 | -0.003257241606186713 |
| 16 | -0.003257241606186713 |
| 17 | -0.003257241606186713 |
| 18 | -0.003257241606186713 |
| 19 | -0.003257241606186713 |
| 20 | -0.003257241606186713 |
| 21 | -0.003257241606186713 |
| 22 | -0.003257241606186713 |
| 23 | 0.0014002594015300688 |
| 24 | 0.0014002594015300688 |
| 25 | 0.0014002594015300688 |
| 26 | 0.0014002594015300688 |
| 27 | 0.0014002594015300688 |
| 28 | 0.0014002594015300688 |
| 29 | 0.0014002594015300688 |
| 30 | 0.0014002594015300688 |
| 31 | 0.0014002594015300688 |
| 32 | 0.021568859055996502 |
| 33 | 0.021568859055996502 |
| 34 | 0.021568859055996502 |
| 35 | 0.021568859055996502 |
| 36 | 0.22317212662101374 |
| 37 | 0.29466530612727965 |
| 38 | 0.29466530612727965 |
| 39 | 0.29466530612727965 |
| 40 | 0.29466530612727965 |
| 41 | 0.29466530612727965 |
| 42 | 0.3122682799350079 |
| 43 | 0.3122682799350079 |
| 44 | 0.36493457523634204 |
| 45 | 0.36493457523634204 |
| 46 | 0.36493457523634204 |
| 47 | 0.37093457523634205 |
| 48 | 0.37093457523634205 |
| 49 | 0.37093457523634205 |
| 50 | 0.37093457523634205 |
| 51 | 0.37093457523634205 |
| 52 | 0.3815565904190224 |
| 53 | 0.3815565904190224 |
| 54 | 0.3815565904190224 |
| 55 | 0.3815565904190224 |
| 56 | 0.3815565904190224 |
| 57 | 0.3943889390332542 |
| 58 | 0.3943889390332542 |
| 59 | 0.3943889390332542 |
| 60 | 0.3943889390332542 |

