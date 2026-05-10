# Run 66 — run_20260510_100012

**Generated**: 2026-05-10T10:00:14.334072+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.18539711739256318 / threshold 1.0
- ❌ **total_pnl**: -13980.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 3.6192184143625723 / threshold 20.0
- ❌ **trade_count**: 40 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 51

## Best 個体

- name: `g57_i31`
- generation: 57
- fitness: **0.15089711739256317**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 40
- total_pnl: -13980.0
- sharpe: 0.18539711739256318
- sortino: —
- calmar: —
- max_drawdown_pct: 3.6192184143625723

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1212
- dsr: —
- ii_lite_pass: —
- n_nodes: 7
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2067
- Stage B pass: 62
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2067 | 62 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2067 | 62 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.5840, median=2.0000, std=0.4967, min=0, max=2
- n_nodes: n=5856, mean=4.2862, median=4.0000, std=2.1636, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=62, mean=0.2970, median=0.2915, std=0.0306, min=0.2811, max=0.5207
- best mission_score: **0.5207** (`g60_i43`, gen=60, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2067, mean=0.1631, median=0.1818, std=0.0844, min=0.0000, max=0.6061
- dsr: n=0
- n_fold_effective (Stage A pass): n=2067, mean=30.9632, median=34, std=6.7282, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=2067, mean=0.2722, median=0.2647, std=0.1897, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2067, Stage B pass = 62, failures = 2005 (primary_sum = 2005)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1952 |
| `positive_fold_ratio<min` | 53 |
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
| `median_oos_sharpe<min` | 1952 |
| `positive_fold_ratio<min` | 2005 |
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
- trade_count=0 個体比率: 3.6% (208/5856)
- best 個体 trade_count: 40
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2005, stage_a_only=3789, stage_b_evaluated=62
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3789, mean=-329974.4603, median=-30900.0000, std=444265.8301, min=-1006430.0000, max=33090.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3581): n=3581, mean=-349140.8070, median=-40040.0000, std=449604.9406, min=-1006430.0000, max=33090.0000
  - うち PnL=0 個体: 2 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2067): n=2067, mean=14734.6638, median=15910.0000, std=56149.1885, min=-1000180.0000, max=80190.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g56_i75` | 56 | tier1_EUR_JPY | EUR_JPY | 0.3281 | 0.3806 | ✅ | ❌ | ❌ | 35 | — |
| 2 | `g59_i33` | 59 | tier1_EUR_JPY | EUR_JPY | 0.3199 | 0.3674 | ✅ | ❌ | ❌ | 40 | — |
| 3 | `g60_i81` | 60 | tier1_EUR_JPY | EUR_JPY | 0.3199 | 0.3674 | ✅ | ❌ | ❌ | 40 | — |
| 4 | `g35_i9` | 35 | tier1_EUR_JPY | EUR_JPY | 0.3137 | 0.3552 | ✅ | ❌ | ❌ | 43 | — |
| 5 | `g36_i1` | 36 | tier1_EUR_JPY | EUR_JPY | 0.3137 | 0.3552 | ✅ | ❌ | ❌ | 43 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03543202025586587 |
| 1 | 0.010115612006239713 |
| 2 | 0.010115612006239713 |
| 3 | 0.010115612006239713 |
| 4 | 0.010115612006239713 |
| 5 | 0.05233134932936201 |
| 6 | 0.05233134932936201 |
| 7 | 0.05233134932936201 |
| 8 | 0.05233134932936201 |
| 9 | 0.052370407358259 |
| 10 | 0.052370407358259 |
| 11 | 0.06346344745827032 |
| 12 | 0.08862107176720953 |
| 13 | 0.08862107176720953 |
| 14 | 0.12815642001932104 |
| 15 | 0.12815642001932104 |
| 16 | 0.12815642001932104 |
| 17 | 0.12815642001932104 |
| 18 | 0.12815642001932104 |
| 19 | 0.12815642001932104 |
| 20 | 0.12815642001932104 |
| 21 | 0.12815642001932104 |
| 22 | 0.23268223755953474 |
| 23 | 0.23268223755953474 |
| 24 | 0.23268223755953474 |
| 25 | 0.2335425746683236 |
| 26 | 0.2335425746683236 |
| 27 | 0.2335425746683236 |
| 28 | 0.2335425746683236 |
| 29 | 0.24178887542194724 |
| 30 | 0.24178887542194724 |
| 31 | 0.24178887542194724 |
| 32 | 0.2612719400715844 |
| 33 | 0.2612719400715844 |
| 34 | 0.2612719400715844 |
| 35 | 0.3137390015013326 |
| 36 | 0.3137390015013326 |
| 37 | 0.3137390015013326 |
| 38 | 0.3137390015013326 |
| 39 | 0.2612719400715844 |
| 40 | 0.30393670870255696 |
| 41 | 0.1668343238835204 |
| 42 | 0.1561653018070135 |
| 43 | 0.261402208815288 |
| 44 | 0.261402208815288 |
| 45 | 0.261402208815288 |
| 46 | 0.2392850857762159 |
| 47 | 0.23456575583485664 |
| 48 | 0.27493081929890717 |
| 49 | 0.20181192606818607 |
| 50 | 0.1879513529849397 |
| 51 | 0.21507292873461115 |
| 52 | 0.21507292873461115 |
| 53 | 0.20666896065376816 |
| 54 | 0.28357881766839077 |
| 55 | 0.2558070455568322 |
| 56 | 0.32811744236641366 |
| 57 | 0.2557135032310634 |
| 58 | 0.20370224901323397 |
| 59 | 0.31994831628437287 |
| 60 | 0.31994831628437287 |

