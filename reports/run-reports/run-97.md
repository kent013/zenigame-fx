# Run 97 — run_20260523_192605

**Generated**: 2026-05-23T19:26:06.123882+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ✅ **sharpe**: 3.5222960176344076 / threshold 1.5
- ❌ **total_pnl**: 43690.0 / threshold 74000.0
- ✅ **max_drawdown_pct**: 1.9099142182502915 / threshold 20.0
- ❌ **trade_count**: 31 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 0 (= Stage C 単独通過数)
- **mission_candidate_count**: 0 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 70

## Best 個体

- name: `g36_i91`
- generation: 36
- fitness: **0.13282266305783663**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 31
- total_pnl: 43690.0
- sharpe: 0.16132266305783663
- sortino: —
- calmar: —
- max_drawdown_pct: 1.9099142182502915

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2121
- dsr: —
- ii_lite_pass: ✅
- n_nodes: 3
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2189
- Stage B pass: 1889
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2189 | 1889 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2189 | 1889 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.5012, median=2.0000, std=0.5014, min=0, max=2
- n_nodes: n=5856, mean=3.6964, median=3.0000, std=1.8135, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1831, mean=0.7647, median=0.7851, std=0.1211, min=0.2720, max=0.9763
- best mission_score: **0.9763** (`g11_i60`, gen=11, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2189, mean=0.2872, median=0.3030, std=0.0735, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2189, mean=32.5212, median=34, std=4.4935, min=2, max=34
- positive_fold_ratio_effective (Stage A pass): n=2189, mean=0.5955, median=0.6176, std=0.1041, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2189, Stage B pass = 1889, failures = 300 (primary_sum = 300)

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
| `positive_fold_ratio_effective<min` | 106 |
| `median_oos_total_pnl<min` | 137 |
| `sum_oos_total_pnl<min` | 13 |
| `n_fold_effective_below_profit_safe_min` | 44 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 106 |
| `median_oos_total_pnl<min` | 243 |
| `sum_oos_total_pnl<min` | 188 |
| `n_fold_effective_below_profit_safe_min` | 65 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 6 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=188, False=1701, None=3967

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 3.8% (224/5856)
- best 個体 trade_count: 31
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=300, stage_a_only=3667, stage_b_evaluated=1889
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3667, mean=-218235.6586, median=-18770.0000, std=370936.4112, min=-1003610.0000, max=60780.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3443): n=3443, mean=-232433.9704, median=-21240.0000, std=378477.7960, min=-1003610.0000, max=60780.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2189): n=2189, mean=14081.0827, median=11790.0000, std=33897.5671, min=-1000170.0000, max=92380.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g53_i71` | 53 | tier1_EUR_JPY | EUR_JPY | 0.2923 | 0.3338 | ✅ | ✅ | ❌ | 32 | — |
| 2 | `g28_i30` | 28 | tier1_EUR_JPY | EUR_JPY | 0.2883 | 0.3338 | ✅ | ❌ | ❌ | 33 | — |
| 3 | `g59_i20` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2715 | 0.3040 | ✅ | ❌ | ❌ | 37 | — |
| 4 | `g59_i53` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2703 | 0.3058 | ✅ | ❌ | ❌ | 34 | — |
| 5 | `g34_i73` | 34 | tier1_EUR_JPY | EUR_JPY | 0.2682 | 0.2937 | ✅ | ✅ | ❌ | 35 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.1629437202835496 |
| 2 | 0.07786832965017235 |
| 3 | 0.07786832965017235 |
| 4 | 0.08506417947129344 |
| 5 | 0.06943684138635191 |
| 6 | 0.05742696243124654 |
| 7 | 0.11465462437718922 |
| 8 | 0.13613155112254507 |
| 9 | 0.06088324020009604 |
| 10 | 0.10190530881597502 |
| 11 | 0.0840078198667893 |
| 12 | 0.11467018879234603 |
| 13 | 0.1678584640610366 |
| 14 | 0.0938072360274452 |
| 15 | 0.0970757665497434 |
| 16 | 0.07306670083136037 |
| 17 | 0.19694390796560618 |
| 18 | 0.1461605719258724 |
| 19 | 0.1399504420939212 |
| 20 | 0.07626192948931135 |
| 21 | 0.13215405577985978 |
| 22 | 0.13215405577985978 |
| 23 | 0.13215405577985978 |
| 24 | 0.21122024984643323 |
| 25 | 0.21122024984643323 |
| 26 | 0.13215405577985978 |
| 27 | 0.23620386573190788 |
| 28 | 0.2883149885600811 |
| 29 | 0.23580368262308601 |
| 30 | 0.23580368262308601 |
| 31 | 0.2554428138199445 |
| 32 | 0.18262547689099265 |
| 33 | 0.24943896496942397 |
| 34 | 0.2682310836604676 |
| 35 | 0.16718599698435074 |
| 36 | 0.1575426177198237 |
| 37 | 0.15714225172052618 |
| 38 | 0.13493323700953228 |
| 39 | 0.13493323700953228 |
| 40 | 0.14952651538989048 |
| 41 | 0.13282266305783663 |
| 42 | 0.18451097403274036 |
| 43 | 0.13282266305783663 |
| 44 | 0.13282266305783663 |
| 45 | 0.13282266305783663 |
| 46 | 0.1786203818166483 |
| 47 | 0.1786203818166483 |
| 48 | 0.20957106140659237 |
| 49 | 0.17394226475745397 |
| 50 | 0.2682310836604676 |
| 51 | 0.13282266305783663 |
| 52 | 0.2278919745834284 |
| 53 | 0.2922814230793559 |
| 54 | 0.2448291307319736 |
| 55 | 0.2293961093784804 |
| 56 | 0.24358531346666296 |
| 57 | 0.18030532776378552 |
| 58 | 0.24241480474745597 |
| 59 | 0.27149557843605554 |
| 60 | 0.1825729818150623 |

