# Run 69 — run_20260510_225559

**Generated**: 2026-05-10T22:56:00.649629+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.06570144754321433 / threshold 1.0
- ❌ **total_pnl**: 1000.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.9259612423890262 / threshold 20.0
- ❌ **trade_count**: 38 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 54

## Best 個体

- name: `g46_i68`
- generation: 46
- fitness: **0.029701447543214334**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 38
- total_pnl: 1000.0
- sharpe: 0.06570144754321433
- sortino: —
- calmar: —
- max_drawdown_pct: 1.9259612423890262

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3636
- dsr: —
- ii_lite_pass: —
- n_nodes: 7
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 770
- Stage B pass: 49
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 770 | 49 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 770 | 49 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4879, median=1.0000, std=0.5036, min=0, max=2
- n_nodes: n=5856, mean=3.5666, median=3.0000, std=1.8958, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=49, mean=0.3704, median=0.3750, std=0.0155, min=0.3185, max=0.3750
- best mission_score: **0.3750** (`g42_i48`, gen=42, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=770, mean=0.1531, median=0.1212, std=0.1070, min=0.0000, max=0.4545
- dsr: n=0
- n_fold_effective (Stage A pass): n=770, mean=25.5545, median=34.0000, std=11.8436, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=766, mean=0.3159, median=0.2353, std=0.2482, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 770, Stage B pass = 49, failures = 721 (primary_sum = 721)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 709 |
| `positive_fold_ratio<min` | 12 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 4 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 709 |
| `positive_fold_ratio<min` | 721 |
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
- trade_count=0 個体比率: 6.4% (372/5856)
- best 個体 trade_count: 38
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=721, stage_a_only=5086, stage_b_evaluated=49
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5086, mean=-501867.4440, median=-300420.0000, std=469563.9798, min=-1003890.0000, max=26950.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4714): n=4714, mean=-541471.7480, median=-732115.0000, std=465236.9993, min=-1003890.0000, max=26950.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=770): n=770, mean=2465.0519, median=8335.0000, std=81476.9224, min=-1000410.0000, max=38660.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g38_i72` | 38 | tier1_EUR_JPY | EUR_JPY | 0.4626 | 0.5131 | ✅ | ❌ | ❌ | 31 | — |
| 2 | `g39_i0` | 39 | tier1_EUR_JPY | EUR_JPY | 0.4626 | 0.5131 | ✅ | ❌ | ❌ | 31 | — |
| 3 | `g39_i13` | 39 | tier1_EUR_JPY | EUR_JPY | 0.4626 | 0.5131 | ✅ | ❌ | ❌ | 31 | — |
| 4 | `g40_i0` | 40 | tier1_EUR_JPY | EUR_JPY | 0.4626 | 0.5131 | ✅ | ❌ | ❌ | 31 | — |
| 5 | `g40_i1` | 40 | tier1_EUR_JPY | EUR_JPY | 0.4626 | 0.5131 | ✅ | ❌ | ❌ | 31 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.021308098791197133 |
| 1 | 0.004606053078717365 |
| 2 | 0.14229224670953372 |
| 3 | 0.14229224670953372 |
| 4 | 0.14229224670953372 |
| 5 | 0.14229224670953372 |
| 6 | 0.15975882944111724 |
| 7 | 0.15975882944111724 |
| 8 | 0.15975882944111724 |
| 9 | 0.15975882944111724 |
| 10 | 0.15975882944111724 |
| 11 | 0.15975882944111724 |
| 12 | 0.15975882944111724 |
| 13 | 0.16011352511064383 |
| 14 | 0.16790732722705598 |
| 15 | 0.16790732722705598 |
| 16 | 0.16790732722705598 |
| 17 | 0.18239687088359058 |
| 18 | 0.18239687088359058 |
| 19 | 0.18239687088359058 |
| 20 | 0.18239687088359058 |
| 21 | 0.18239687088359058 |
| 22 | 0.21026765065230676 |
| 23 | 0.21026765065230676 |
| 24 | 0.21026765065230676 |
| 25 | 0.21549702075988922 |
| 26 | 0.21549702075988922 |
| 27 | 0.21549702075988922 |
| 28 | 0.11605230711352454 |
| 29 | 0.10883210780892859 |
| 30 | 0.10883210780892859 |
| 31 | 0.10883210780892859 |
| 32 | 0.10883210780892859 |
| 33 | 0.10883210780892859 |
| 34 | 0.10883210780892859 |
| 35 | 0.10883210780892859 |
| 36 | 0.10883210780892859 |
| 37 | 0.19713519373329363 |
| 38 | 0.462592903662864 |
| 39 | 0.462592903662864 |
| 40 | 0.462592903662864 |
| 41 | 0.462592903662864 |
| 42 | 0.462592903662864 |
| 43 | 0.462592903662864 |
| 44 | 0.462592903662864 |
| 45 | 0.462592903662864 |
| 46 | 0.462592903662864 |
| 47 | 0.09634653411637013 |
| 48 | 0.27282747827743614 |
| 49 | 0.11317925436618673 |
| 50 | 0.11317925436618673 |
| 51 | 0.11763810793956603 |
| 52 | 0.31953706044673785 |
| 53 | 0.31953706044673785 |
| 54 | 0.31953706044673785 |
| 55 | 0.31953706044673785 |
| 56 | 0.31953706044673785 |
| 57 | 0.136703176292399 |
| 58 | 0.18774697013486022 |
| 59 | 0.19381051251402304 |
| 60 | 0.1523022578383996 |

