# Run 82 — run_20260514_211202

**Generated**: 2026-05-14T21:12:03.122461+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ✅ **sharpe**: 2.2760392549070056 / threshold 1.0
- ❌ **total_pnl**: 4670.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.234506446313903 / threshold 20.0
- ❌ **trade_count**: 23 (range 50〜5000)

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
- seed: 67

## Best 個体

- name: `g56_i79`
- generation: 56
- fitness: **0.20457473986525568**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 23
- total_pnl: 4670.0
- sharpe: 0.23157473986525567
- sortino: —
- calmar: —
- max_drawdown_pct: 1.234506446313903

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1212
- dsr: —
- ii_lite_pass: —
- n_nodes: 5
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2687
- Stage B pass: 941
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2687 | 941 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2687 | 941 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4366, median=1.0000, std=0.4984, min=0, max=2
- n_nodes: n=5856, mean=3.4334, median=3.0000, std=1.7052, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=651, mean=0.3518, median=0.3096, std=0.0991, min=0.2725, max=0.6896
- best mission_score: **0.6896** (`g56_i11`, gen=56, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2687, mean=0.2326, median=0.2424, std=0.0818, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=2687, mean=25.3037, median=26, std=6.3256, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2678, mean=0.4779, median=0.5000, std=0.1301, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2687, Stage B pass = 941, failures = 1746 (primary_sum = 1746)

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
| `positive_fold_ratio_effective<min` | 661 |
| `median_oos_total_pnl<min` | 701 |
| `sum_oos_total_pnl<min` | 278 |
| `n_fold_effective_below_profit_safe_min` | 106 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 9 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 661 |
| `median_oos_total_pnl<min` | 1362 |
| `sum_oos_total_pnl<min` | 1604 |
| `n_fold_effective_below_profit_safe_min` | 337 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 15 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 6.4% (374/5856)
- best 個体 trade_count: 23
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1746, stage_a_only=3169, stage_b_evaluated=941
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3169, mean=-217091.9659, median=-44040.0000, std=367323.3422, min=-1001630.0000, max=43970.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=2795): n=2795, mean=-246141.1234, median=-48470.0000, std=381877.9946, min=-1001630.0000, max=43970.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2687): n=2687, mean=19630.0744, median=21840.0000, std=21275.2126, min=-1000050.0000, max=43240.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g53_i19` | 53 | tier1_EUR_JPY | EUR_JPY | 0.4890 | 0.5280 | ✅ | ❌ | ❌ | 41 | — |
| 2 | `g48_i20` | 48 | tier1_EUR_JPY | EUR_JPY | 0.4852 | 0.5267 | ✅ | ❌ | ❌ | 40 | — |
| 3 | `g40_i64` | 40 | tier1_EUR_JPY | EUR_JPY | 0.4245 | 0.4645 | ✅ | ❌ | ❌ | 37 | — |
| 4 | `g31_i23` | 31 | tier1_EUR_JPY | EUR_JPY | 0.4064 | 0.4569 | ✅ | ❌ | ❌ | 31 | — |
| 5 | `g30_i62` | 30 | tier1_EUR_JPY | EUR_JPY | 0.4039 | 0.4544 | ✅ | ❌ | ❌ | 31 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.05183302611567577 |
| 1 | 0.05183302611567577 |
| 2 | 0.05183302611567577 |
| 3 | 0.06864631848378444 |
| 4 | 0.06864631848378444 |
| 5 | 0.06864631848378444 |
| 6 | 0.07687773967064425 |
| 7 | 0.07687773967064425 |
| 8 | 0.2334851127338863 |
| 9 | 0.24805596641485206 |
| 10 | 0.10313974660159535 |
| 11 | 0.1506512801048228 |
| 12 | 0.135796568015868 |
| 13 | 0.1313971263285702 |
| 14 | 0.14376525887151417 |
| 15 | 0.15755568464609046 |
| 16 | 0.15774739925038656 |
| 17 | 0.20700806496241372 |
| 18 | 0.20700806496241372 |
| 19 | 0.2440784799429767 |
| 20 | 0.1707838995718746 |
| 21 | 0.17153667814092455 |
| 22 | 0.1632903191675086 |
| 23 | 0.16703964348894876 |
| 24 | 0.16955568464609044 |
| 25 | 0.16955568464609044 |
| 26 | 0.2509538800215536 |
| 27 | 0.16416983456402065 |
| 28 | 0.16786400578238705 |
| 29 | 0.3357070077571671 |
| 30 | 0.4038712945232301 |
| 31 | 0.4064186051908477 |
| 32 | 0.34286824053165393 |
| 33 | 0.17044310655688938 |
| 34 | 0.1905813408452876 |
| 35 | 0.19759393505633788 |
| 36 | 0.16955568464609044 |
| 37 | 0.2071324249527789 |
| 38 | 0.16746159299475805 |
| 39 | 0.18265787049663645 |
| 40 | 0.42451924190003065 |
| 41 | 0.17148568791616073 |
| 42 | 0.2879494077689262 |
| 43 | 0.19696292498095394 |
| 44 | 0.35391391027880326 |
| 45 | 0.19815736252742738 |
| 46 | 0.18976197980866905 |
| 47 | 0.2999177501122546 |
| 48 | 0.48515537407796183 |
| 49 | 0.2087078477797418 |
| 50 | 0.25785239883791033 |
| 51 | 0.3284438687219539 |
| 52 | 0.36278495071405387 |
| 53 | 0.48902607058283676 |
| 54 | 0.2233961175834609 |
| 55 | 0.331467878372722 |
| 56 | 0.3023111511559524 |
| 57 | 0.3744360896113227 |
| 58 | 0.2919509375759485 |
| 59 | 0.24016621940164332 |
| 60 | 0.35607498434157286 |

