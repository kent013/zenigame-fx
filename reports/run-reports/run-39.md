# Run 39 — run_20260506_112348

**Generated**: 2026-05-06T11:25:45.683313+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.21651631993061826 / threshold 1.0
- ❌ **total_pnl**: 32160.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 57 (range 50〜5000)

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

- name: `g54_i2`
- generation: 54
- fitness: **0.19851631993061827**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 57
- total_pnl: 32160.0
- sharpe: 0.21651631993061826
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1640
- Stage B pass: 6
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1640 | 6 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1640 | 6 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2826, median=1.0000, std=0.4608, min=0, max=2
- n_nodes: n=5856, mean=3.7947, median=4.0000, std=1.6972, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1, mean=0.2758, median=0.2758, std=0.0000, min=0.2758, max=0.2758
- best mission_score: **0.2758** (`g42_i12`, gen=42, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1640, mean=0.2810, median=0.3000, std=0.1878, min=0.0000, max=0.7000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1640, mean=8.7000, median=11.0000, std=3.4341, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=1571, mean=0.3334, median=0.3636, std=0.2185, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1640, Stage B pass = 6, failures = 1634 (primary_sum = 1634)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1627 |
| `positive_fold_ratio<min` | 7 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 69 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1627 |
| `positive_fold_ratio<min` | 1618 |
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
- trade_count=0 個体比率: 5.7% (334/5856)
- best 個体 trade_count: 57
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1634, stage_a_only=4216, stage_b_evaluated=6
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4216, mean=-373397.8890, median=-88235.0000, std=448630.9501, min=-1006670.0000, max=23420.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3882): n=3882, mean=-405524.3431, median=-114055.0000, std=453385.6418, min=-1006670.0000, max=23420.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1640): n=1640, mean=6799.2012, median=13830.0000, std=93944.6367, min=-1000940.0000, max=42230.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g53_i6` | 53 | tier1_EUR_JPY | EUR_JPY | 0.2231 | 0.2411 | ✅ | ❌ | ❌ | 53 | — |
| 2 | `g47_i6` | 47 | tier1_EUR_JPY | EUR_JPY | 0.2078 | 0.2258 | ✅ | ❌ | ❌ | 51 | — |
| 3 | `g48_i78` | 48 | tier1_EUR_JPY | EUR_JPY | 0.2041 | 0.2576 | ✅ | ❌ | ❌ | 31 | — |
| 4 | `g54_i2` | 54 | tier1_EUR_JPY | EUR_JPY | 0.1985 | 0.2165 | ✅ | ❌ | ❌ | 57 | — |
| 5 | `g55_i0` | 55 | tier1_EUR_JPY | EUR_JPY | 0.1985 | 0.2165 | ✅ | ❌ | ❌ | 57 | — |

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
| 16 | 0.055619474207266296 |
| 17 | 0.05445714307913524 |
| 18 | 0.07713166097503243 |
| 19 | 0.04876377204319806 |
| 20 | 0.1144982061809198 |
| 21 | 0.1144982061809198 |
| 22 | 0.042385685047391805 |
| 23 | 0.07238797291455859 |
| 24 | 0.07238797291455859 |
| 25 | 0.08853091729882456 |
| 26 | 0.07175172702217286 |
| 27 | 0.07608787538204959 |
| 28 | 0.052136655024155376 |
| 29 | 0.08416512486935127 |
| 30 | 0.09079014967925596 |
| 31 | 0.07875517087398234 |
| 32 | 0.09000223718275475 |
| 33 | 0.09000223718275475 |
| 34 | 0.13895966850609742 |
| 35 | 0.09000223718275475 |
| 36 | 0.1180118315201333 |
| 37 | 0.10287690514848484 |
| 38 | 0.14288171838610492 |
| 39 | 0.14288171838610492 |
| 40 | 0.14288171838610492 |
| 41 | 0.14288171838610492 |
| 42 | 0.14288171838610492 |
| 43 | 0.15016308372665305 |
| 44 | 0.14288171838610492 |
| 45 | 0.16714671388222502 |
| 46 | 0.16714671388222502 |
| 47 | 0.20781740589329575 |
| 48 | 0.20413714415398582 |
| 49 | 0.176483254453751 |
| 50 | 0.16714671388222502 |
| 51 | 0.19222470570055325 |
| 52 | 0.19222470570055325 |
| 53 | 0.22308920347208505 |
| 54 | 0.19851631993061827 |
| 55 | 0.19851631993061827 |
| 56 | 0.19851631993061827 |
| 57 | 0.19851631993061827 |
| 58 | 0.19851631993061827 |
| 59 | 0.19851631993061827 |
| 60 | 0.19851631993061827 |

