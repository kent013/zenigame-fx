# Run 61 — run_20260509_183813

**Generated**: 2026-05-09T18:38:14.612602+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.05197988268000822 / threshold 1.0
- ❌ **total_pnl**: -48540.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 6.579918698386764 / threshold 20.0
- ✅ **trade_count**: 74 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 46

## Best 個体

- name: `g55_i66`
- generation: 55
- fitness: **0.03247988268000822**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 74
- total_pnl: -48540.0
- sharpe: 0.05197988268000822
- sortino: —
- calmar: —
- max_drawdown_pct: 6.579918698386764

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1325
- Stage B pass: 7
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1325 | 7 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1325 | 7 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3222, median=1.0000, std=0.4971, min=0, max=2
- n_nodes: n=5856, mean=3.0714, median=3.0000, std=1.6668, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=7, mean=0.2897, median=0.2897, std=0.0000, min=0.2897, max=0.2897
- best mission_score: **0.2897** (`g55_i66`, gen=55, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1325, mean=0.1444, median=0.1212, std=0.0558, min=0.0000, max=0.3636
- dsr: n=0
- n_fold_effective (Stage A pass): n=1325, mean=28.8974, median=34, std=8.7447, min=2, max=34
- positive_fold_ratio_effective (Stage A pass): n=1325, mean=0.3861, median=0.2941, std=0.2090, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1325, Stage B pass = 7, failures = 1318 (primary_sum = 1318)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1210 |
| `positive_fold_ratio<min` | 108 |
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
| `median_oos_sharpe<min` | 1210 |
| `positive_fold_ratio<min` | 1318 |
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
- trade_count=0 個体比率: 5.9% (346/5856)
- best 個体 trade_count: 74
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1318, stage_a_only=4531, stage_b_evaluated=7
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4531, mean=-406646.3496, median=-87770.0000, std=462980.2802, min=-1006030.0000, max=24900.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4185): n=4185, mean=-440266.3345, median=-117340.0000, std=466123.0548, min=-1006030.0000, max=24900.0000
  - うち PnL=0 個体: 2 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1325): n=1325, mean=5221.1547, median=5190.0000, std=48930.9753, min=-1000070.0000, max=46870.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g34_i60` | 34 | tier1_EUR_JPY | EUR_JPY | 0.2538 | 0.2803 | ✅ | ❌ | ❌ | 37 | — |
| 2 | `g35_i0` | 35 | tier1_EUR_JPY | EUR_JPY | 0.2538 | 0.2803 | ✅ | ❌ | ❌ | 37 | — |
| 3 | `g35_i65` | 35 | tier1_EUR_JPY | EUR_JPY | 0.2538 | 0.2803 | ✅ | ❌ | ❌ | 37 | — |
| 4 | `g36_i0` | 36 | tier1_EUR_JPY | EUR_JPY | 0.2538 | 0.2803 | ✅ | ❌ | ❌ | 37 | — |
| 5 | `g36_i1` | 36 | tier1_EUR_JPY | EUR_JPY | 0.2538 | 0.2803 | ✅ | ❌ | ❌ | 37 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.005804892214011783 |
| 1 | 0.005804892214011783 |
| 2 | 0.005804892214011783 |
| 3 | 0.005804892214011783 |
| 4 | 0.005804892214011783 |
| 5 | 0.005804892214011783 |
| 6 | 0.005804892214011783 |
| 7 | 0.005804892214011783 |
| 8 | 0.005804892214011783 |
| 9 | 0.10450551929181193 |
| 10 | 0.1784007496210153 |
| 11 | 0.1784007496210153 |
| 12 | 0.1784007496210153 |
| 13 | 0.1784007496210153 |
| 14 | 0.17990697273201686 |
| 15 | 0.17990697273201686 |
| 16 | 0.20767158699370825 |
| 17 | 0.20767158699370825 |
| 18 | 0.20767158699370825 |
| 19 | 0.20767158699370825 |
| 20 | 0.18935945878625335 |
| 21 | 0.10520229857828559 |
| 22 | 0.06458467743419634 |
| 23 | 0.06458467743419634 |
| 24 | 0.21593896059554915 |
| 25 | 0.1327371963211068 |
| 26 | 0.08911981246981154 |
| 27 | 0.10046812933808952 |
| 28 | 0.08911981246981154 |
| 29 | 0.09511981246981155 |
| 30 | 0.09511981246981155 |
| 31 | 0.09511981246981155 |
| 32 | 0.09511981246981155 |
| 33 | 0.20054231132532924 |
| 34 | 0.2538245864607133 |
| 35 | 0.2538245864607133 |
| 36 | 0.2538245864607133 |
| 37 | 0.2538245864607133 |
| 38 | 0.2538245864607133 |
| 39 | 0.2538245864607133 |
| 40 | 0.2538245864607133 |
| 41 | 0.2538245864607133 |
| 42 | 0.2538245864607133 |
| 43 | 0.2538245864607133 |
| 44 | 0.2538245864607133 |
| 45 | 0.2538245864607133 |
| 46 | 0.2538245864607133 |
| 47 | 0.2538245864607133 |
| 48 | 0.2538245864607133 |
| 49 | 0.2538245864607133 |
| 50 | 0.2538245864607133 |
| 51 | 0.2538245864607133 |
| 52 | 0.2538245864607133 |
| 53 | 0.2538245864607133 |
| 54 | 0.2538245864607133 |
| 55 | 0.2538245864607133 |
| 56 | 0.2538245864607133 |
| 57 | 0.2538245864607133 |
| 58 | 0.2538245864607133 |
| 59 | 0.2538245864607133 |
| 60 | 0.2538245864607133 |

