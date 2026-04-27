# Run 25 — run_20260427_055446

**Generated**: 2026-04-27T05:54:46.822278+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.015470572566791404 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 59591 (range 50〜5000)

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

- name: `g28_i35`
- generation: 28
- fitness: **0.010970572566791403**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 59591
- total_pnl: 0.0
- sharpe: 0.015470572566791404
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
- Stage A pass: 2472
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2472 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2472 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9956, median=1.0000, std=0.0665, min=0, max=1
- n_nodes: n=5856, mean=1.3306, median=1.0000, std=0.6204, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2472, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2472, mean=9, median=9.0000, std=0.0000, min=9, max=9
- positive_fold_ratio_effective (Stage A pass): n=2472, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000

## Stage B failure reason 集計

- Stage A pass = 2472, Stage B pass = 0, failures = 2472 (primary_sum = 2472)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2472 |
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
| `median_oos_sharpe<min` | 2472 |
| `positive_fold_ratio<min` | 2472 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 1.8% (105/5856)
- best 個体 trade_count: 59591
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2472, stage_a_only=3384
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3384, mean=-13265960.5792, median=-15252090.0000, std=5587288.4752, min=-19796890.0000, max=16360.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3279): n=3279, mean=-13690762.6106, median=-15437290.0000, std=5138247.1306, min=-19796890.0000, max=16360.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2472): n=2472, mean=-18077852.9854, median=-18417570.0000, std=502493.2301, min=-19277480.0000, max=-13610350.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g28_i35` | 28 | tier1_EUR_JPY | EUR_JPY | 0.0110 | 0.0155 | ✅ | ❌ | ❌ | 59591 | — |
| 2 | `g29_i0` | 29 | tier1_EUR_JPY | EUR_JPY | 0.0110 | 0.0155 | ✅ | ❌ | ❌ | 59591 | — |
| 3 | `g29_i50` | 29 | tier1_EUR_JPY | EUR_JPY | 0.0110 | 0.0155 | ✅ | ❌ | ❌ | 59591 | — |
| 4 | `g29_i63` | 29 | tier1_EUR_JPY | EUR_JPY | 0.0110 | 0.0155 | ✅ | ❌ | ❌ | 59591 | — |
| 5 | `g29_i75` | 29 | tier1_EUR_JPY | EUR_JPY | 0.0110 | 0.0155 | ✅ | ❌ | ❌ | 59591 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.027931676175382822 |
| 1 | -0.027931676175382822 |
| 2 | -0.008446505454764832 |
| 3 | 0.003957996905116242 |
| 4 | 0.003957996905116242 |
| 5 | 0.003957996905116242 |
| 6 | 0.003957996905116242 |
| 7 | 0.003957996905116242 |
| 8 | 0.003957996905116242 |
| 9 | 0.003957996905116242 |
| 10 | 0.003957996905116242 |
| 11 | 0.003957996905116242 |
| 12 | 0.003957996905116242 |
| 13 | 0.003957996905116242 |
| 14 | 0.003957996905116242 |
| 15 | 0.003957996905116242 |
| 16 | 0.003957996905116242 |
| 17 | 0.003957996905116242 |
| 18 | 0.003957996905116242 |
| 19 | 0.003957996905116242 |
| 20 | 0.003957996905116242 |
| 21 | 0.003957996905116242 |
| 22 | 0.003957996905116242 |
| 23 | 0.009032963389439954 |
| 24 | 0.009032963389439954 |
| 25 | 0.009032963389439954 |
| 26 | 0.009032963389439954 |
| 27 | 0.009032963389439954 |
| 28 | 0.010970572566791403 |
| 29 | 0.010970572566791403 |
| 30 | 0.010970572566791403 |
| 31 | 0.010970572566791403 |
| 32 | 0.010970572566791403 |
| 33 | 0.010970572566791403 |
| 34 | 0.010970572566791403 |
| 35 | 0.010970572566791403 |
| 36 | 0.010970572566791403 |
| 37 | 0.010970572566791403 |
| 38 | 0.010970572566791403 |
| 39 | 0.010970572566791403 |
| 40 | 0.010970572566791403 |
| 41 | 0.010970572566791403 |
| 42 | 0.010970572566791403 |
| 43 | 0.010970572566791403 |
| 44 | 0.010970572566791403 |
| 45 | 0.010970572566791403 |
| 46 | 0.010970572566791403 |
| 47 | 0.010970572566791403 |
| 48 | 0.010970572566791403 |
| 49 | 0.010970572566791403 |
| 50 | 0.010970572566791403 |
| 51 | 0.010970572566791403 |
| 52 | 0.010970572566791403 |
| 53 | 0.010970572566791403 |
| 54 | 0.010970572566791403 |
| 55 | 0.010970572566791403 |
| 56 | 0.010970572566791403 |
| 57 | 0.010970572566791403 |
| 58 | 0.010970572566791403 |
| 59 | 0.010970572566791403 |
| 60 | 0.010970572566791403 |

