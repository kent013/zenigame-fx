# Run 93 — run_20260522_181531

**Generated**: 2026-05-22T18:15:32.408942+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 3.409187727422393 / threshold 1.0
- ✅ **total_pnl**: 53280.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.5075424054969915 / threshold 20.0
- ✅ **trade_count**: 55 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 86 (= Stage C 単独通過数)
- **mission_candidate_count**: 86 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 48
- generations: 20
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g15_i33`
- generation: 15
- fitness: **0.028108590364705748**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 55
- total_pnl: 53280.0
- sharpe: 0.08325569245083418
- sortino: —
- calmar: —
- max_drawdown_pct: 1.5075424054969915

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 1008
- Stage A pass: 389
- Stage B pass: 302
- Stage C pass: 86

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 86 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 2 | 2.3% |
| 51 | 2 | 2.3% |
| 52 | 3 | 3.5% |
| 53 | 32 | 37.2% |
| 54 | 21 | 24.4% |
| 55 | 19 | 22.1% |
| 56 | 4 | 4.7% |
| 61 | 1 | 1.2% |
| 67 | 1 | 1.2% |
| 70 | 1 | 1.2% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 2 | 84 |
| median total_pnl | 59250.0000 | 53280.0000 |
| median trade_sharpe_stage_c | 0.2648 | 0.2250 |
| median max_drawdown_pct | 1.8079 | 1.5086 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 1008 | 389 | 302 | 86 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 1008 | 389 | 302 | 86 |

## active_clause / n_nodes 分布

- active_clause: n=1008, mean=1.3611, median=1.0000, std=0.4844, min=0, max=2
- n_nodes: n=1008, mean=4.1667, median=4.0000, std=1.8328, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=296, mean=0.8988, median=0.9235, std=0.1008, min=0.2862, max=0.9829
- best mission_score: **0.9829** (`g0_ws0`, gen=0, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=389, mean=0.2572, median=0.2727, std=0.0693, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=389, mean=32.1337, median=34, std=5.6843, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=388, mean=0.5646, median=0.5882, std=0.1183, min=0.0000, max=0.7647

## Stage B failure reason 集計

- Stage A pass = 389, Stage B pass = 302, failures = 87 (primary_sum = 87)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 35 |
| `median_oos_total_pnl<min` | 34 |
| `sum_oos_total_pnl<min` | 10 |
| `n_fold_effective_below_profit_safe_min` | 8 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 35 |
| `median_oos_total_pnl<min` | 69 |
| `sum_oos_total_pnl<min` | 73 |
| `n_fold_effective_below_profit_safe_min` | 19 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 2 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=302, None=706

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.5% (25/1008)
- best 個体 trade_count: 55
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 1008
- metric_stage 分布: stage_a_evaluated=87, stage_a_only=619, stage_b_evaluated=216, stage_c_evaluated=86
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=619, mean=-269277.0275, median=-35160.0000, std=405362.6090, min=-1002650.0000, max=45590.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=594): n=594, mean=-280610.2357, median=-40055.0000, std=409944.3948, min=-1002650.0000, max=45590.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=389): n=389, mean=23650.5141, median=22870.0000, std=13040.2751, min=-2220.0000, max=68620.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g14_i36` | 14 | tier1_EUR_JPY | EUR_JPY | 0.1257 | 0.1792 | ✅ | ❌ | ❌ | 64 | — |
| 2 | `g18_i14` | 18 | tier1_EUR_JPY | EUR_JPY | 0.0966 | 0.1517 | ✅ | ❌ | ❌ | 39 | — |
| 3 | `g15_i26` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0833 | 0.0968 | ✅ | ❌ | ❌ | 63 | — |
| 4 | `g17_i21` | 17 | tier1_EUR_JPY | EUR_JPY | 0.0813 | 0.2224 | ✅ | ❌ | ❌ | 39 | — |
| 5 | `g18_i47` | 18 | tier1_EUR_JPY | EUR_JPY | 0.0768 | 0.1107 | ✅ | ✅ | ❌ | 51 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.0147253941821253 |
| 1 | -0.0147253941821253 |
| 2 | 0.009691509343966889 |
| 3 | 0.01733221866192335 |
| 4 | 0.027248646055890995 |
| 5 | 0.003898812565228251 |
| 6 | 0.02863370568428426 |
| 7 | -0.0019484077486603066 |
| 8 | 0.05801432071364525 |
| 9 | -0.006752574129087064 |
| 10 | 0.057315535947103265 |
| 11 | 0.07195940778165011 |
| 12 | 0.06976163143221599 |
| 13 | 0.03308992842665668 |
| 14 | 0.1257188787263319 |
| 15 | 0.08333952793878752 |
| 16 | 0.028108590364705748 |
| 17 | 0.08129756508974816 |
| 18 | 0.0966347552503022 |
| 19 | 0.03259148923068712 |
| 20 | 0.028108590364705748 |

