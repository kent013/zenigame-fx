# Run 62 — run_20260509_215629

**Generated**: 2026-05-09T21:56:30.547567+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.23203907280168629 / threshold 1.0
- ❌ **total_pnl**: 3930.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 2.054485986799585 / threshold 20.0
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
- seed: 47

## Best 個体

- name: `g60_i37`
- generation: 60
- fitness: **0.20053907280168629**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 40
- total_pnl: 3930.0
- sharpe: 0.23203907280168629
- sortino: —
- calmar: —
- max_drawdown_pct: 2.054485986799585

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1515
- dsr: —
- ii_lite_pass: —
- n_nodes: 6
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2191
- Stage B pass: 52
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2191 | 52 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2191 | 52 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.5113, median=2.0000, std=0.5033, min=0, max=2
- n_nodes: n=5856, mean=3.6291, median=3.0000, std=1.5912, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=52, mean=0.3370, median=0.3193, std=0.0806, min=0.2760, max=0.6720
- best mission_score: **0.6720** (`g57_i51`, gen=57, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2191, mean=0.1529, median=0.1212, std=0.0512, min=0.0000, max=0.3636
- dsr: n=0
- n_fold_effective (Stage A pass): n=2191, mean=26.5965, median=34, std=9.4938, min=2, max=34
- positive_fold_ratio_effective (Stage A pass): n=2191, mean=0.4985, median=0.5294, std=0.1255, min=0.0000, max=0.8750

## Stage B failure reason 集計

- Stage A pass = 2191, Stage B pass = 52, failures = 2139 (primary_sum = 2139)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1430 |
| `positive_fold_ratio<min` | 709 |
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
| `median_oos_sharpe<min` | 1430 |
| `positive_fold_ratio<min` | 2139 |
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
- trade_count=0 個体比率: 7.3% (427/5856)
- best 個体 trade_count: 40
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2139, stage_a_only=3665, stage_b_evaluated=52
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3665, mean=-298539.7299, median=-38140.0000, std=421389.6717, min=-1007490.0000, max=36980.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3238): n=3238, mean=-337908.6195, median=-67275.0000, std=433223.3799, min=-1007490.0000, max=36980.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2191): n=2191, mean=18925.3492, median=21140.0000, std=39202.3676, min=-1000380.0000, max=60820.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g60_i42` | 60 | tier1_EUR_JPY | EUR_JPY | 0.3006 | 0.3371 | ✅ | ❌ | ❌ | 45 | — |
| 2 | `g15_i75` | 15 | tier1_EUR_JPY | EUR_JPY | 0.2704 | 0.3099 | ✅ | ❌ | ❌ | 42 | — |
| 3 | `g58_i62` | 58 | tier1_EUR_JPY | EUR_JPY | 0.2630 | 0.3105 | ✅ | ❌ | ❌ | 37 | — |
| 4 | `g59_i82` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2630 | 0.3105 | ✅ | ❌ | ❌ | 37 | — |
| 5 | `g60_i88` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2630 | 0.3105 | ✅ | ❌ | ❌ | 37 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036364295119237 |
| 1 | -0.030382096985709102 |
| 2 | 0.040569328369377655 |
| 3 | 0.12446170144066178 |
| 4 | 0.12446170144066178 |
| 5 | 0.12446170144066178 |
| 6 | 0.18812687797064812 |
| 7 | 0.19461235092386764 |
| 8 | 0.19461235092386764 |
| 9 | 0.19461235092386764 |
| 10 | 0.21597087354487698 |
| 11 | 0.21597087354487698 |
| 12 | 0.2169444156182832 |
| 13 | 0.22008835848905967 |
| 14 | 0.2510969465784755 |
| 15 | 0.27037225346430827 |
| 16 | 0.15734393362747123 |
| 17 | 0.16002739760586313 |
| 18 | 0.15904281547648833 |
| 19 | 0.17174735623142703 |
| 20 | 0.22174819275729069 |
| 21 | 0.1300653051572632 |
| 22 | 0.1943997612447927 |
| 23 | 0.15147233053984432 |
| 24 | 0.15597233053984433 |
| 25 | 0.15551232806035833 |
| 26 | 0.15551232806035833 |
| 27 | 0.1615271130790839 |
| 28 | 0.16452336339660814 |
| 29 | 0.16452336339660814 |
| 30 | 0.16452336339660814 |
| 31 | 0.1880233340144439 |
| 32 | 0.20064266220586902 |
| 33 | 0.17437860073759448 |
| 34 | 0.16897111222985434 |
| 35 | 0.16897111222985434 |
| 36 | 0.16897111222985434 |
| 37 | 0.16897111222985434 |
| 38 | 0.1794543822163892 |
| 39 | 0.16897111222985434 |
| 40 | 0.16897111222985434 |
| 41 | 0.16897111222985434 |
| 42 | 0.18205818014299874 |
| 43 | 0.18205818014299874 |
| 44 | 0.18205818014299874 |
| 45 | 0.19867375708643586 |
| 46 | 0.18205818014299874 |
| 47 | 0.18205818014299874 |
| 48 | 0.18205818014299874 |
| 49 | 0.20460136697531478 |
| 50 | 0.18205818014299874 |
| 51 | 0.18205818014299874 |
| 52 | 0.18205818014299874 |
| 53 | 0.18205818014299874 |
| 54 | 0.18205818014299874 |
| 55 | 0.18205818014299874 |
| 56 | 0.18139494278442422 |
| 57 | 0.18139494278442422 |
| 58 | 0.2629773560634716 |
| 59 | 0.2629773560634716 |
| 60 | 0.30062936284735786 |

