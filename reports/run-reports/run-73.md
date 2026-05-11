# Run 73 — run_20260511_115705

**Generated**: 2026-05-11T11:57:07.021766+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.4642474363081383 / threshold 1.0
- ❌ **total_pnl**: 33600.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 36 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 58

## Best 個体

- name: `g54_i52`
- generation: 54
- fitness: **0.42324743630813827**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 36
- total_pnl: 33600.0
- sharpe: 0.4642474363081383
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0303
- dsr: —
- ii_lite_pass: —
- n_nodes: 5
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2730
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2730 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2730 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4708, median=1.0000, std=0.4998, min=0, max=2
- n_nodes: n=5856, mean=3.8649, median=4.0000, std=1.7656, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2730, mean=0.2191, median=0.1818, std=0.0990, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=2730, mean=23.8505, median=24.0000, std=8.5598, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2721, mean=0.4474, median=0.4516, std=0.1747, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2730, Stage B pass = 0, failures = 2730 (primary_sum = 2730)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2725 |
| `positive_fold_ratio<min` | 5 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 9 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2725 |
| `positive_fold_ratio<min` | 2730 |
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
- trade_count=0 個体比率: 6.6% (384/5856)
- best 個体 trade_count: 36
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2730, stage_a_only=3126
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3126, mean=-224385.8253, median=-39315.0000, std=376641.0018, min=-1001730.0000, max=37810.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=2742): n=2742, mean=-255809.6608, median=-45945.0000, std=392028.4607, min=-1001730.0000, max=37810.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2730): n=2730, mean=18725.6410, median=19335.0000, std=21081.5189, min=-1000210.0000, max=42270.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g36_i36` | 36 | tier1_EUR_JPY | EUR_JPY | 0.4943 | 0.5378 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g54_i52` | 54 | tier1_EUR_JPY | EUR_JPY | 0.4232 | 0.4642 | ✅ | ❌ | ❌ | 36 | — |
| 3 | `g55_i0` | 55 | tier1_EUR_JPY | EUR_JPY | 0.4232 | 0.4642 | ✅ | ❌ | ❌ | 36 | — |
| 4 | `g55_i65` | 55 | tier1_EUR_JPY | EUR_JPY | 0.4232 | 0.4642 | ✅ | ❌ | ❌ | 36 | — |
| 5 | `g55_i95` | 55 | tier1_EUR_JPY | EUR_JPY | 0.4232 | 0.4642 | ✅ | ❌ | ❌ | 36 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.02848251746113852 |
| 1 | 0.04388005179228273 |
| 2 | 0.04388005179228273 |
| 3 | 0.04388005179228273 |
| 4 | 0.06774507519892214 |
| 5 | 0.07347731182040507 |
| 6 | 0.08463549360556208 |
| 7 | 0.08463549360556208 |
| 8 | 0.08463549360556208 |
| 9 | 0.08977019213653208 |
| 10 | 0.18255545607218368 |
| 11 | 0.18255545607218368 |
| 12 | 0.18255545607218368 |
| 13 | 0.18768242294284768 |
| 14 | 0.21833970889669582 |
| 15 | 0.3053360183714502 |
| 16 | 0.3053360183714502 |
| 17 | 0.3053360183714502 |
| 18 | 0.3053360183714502 |
| 19 | 0.3053360183714502 |
| 20 | 0.3053360183714502 |
| 21 | 0.3053360183714502 |
| 22 | 0.3073947720889497 |
| 23 | 0.18007966497209857 |
| 24 | 0.1556478720442231 |
| 25 | 0.18909544025394512 |
| 26 | 0.16194652996427913 |
| 27 | 0.22977121430779612 |
| 28 | 0.1624833756367479 |
| 29 | 0.16218815212269605 |
| 30 | 0.17206005400085592 |
| 31 | 0.19887608939780516 |
| 32 | 0.17206005400085592 |
| 33 | 0.25212763462335663 |
| 34 | 0.19420999674575873 |
| 35 | 0.38767943360070783 |
| 36 | 0.4943030874393255 |
| 37 | 0.2996497747954385 |
| 38 | 0.320482554565064 |
| 39 | 0.32753706926911824 |
| 40 | 0.32753706926911824 |
| 41 | 0.2944279200236157 |
| 42 | 0.2958297377609241 |
| 43 | 0.3652436745292658 |
| 44 | 0.3652436745292658 |
| 45 | 0.3652436745292658 |
| 46 | 0.40607124661827243 |
| 47 | 0.40607124661827243 |
| 48 | 0.41874743630813827 |
| 49 | 0.41874743630813827 |
| 50 | 0.41874743630813827 |
| 51 | 0.41874743630813827 |
| 52 | 0.41874743630813827 |
| 53 | 0.41874743630813827 |
| 54 | 0.42324743630813827 |
| 55 | 0.42324743630813827 |
| 56 | 0.42324743630813827 |
| 57 | 0.42324743630813827 |
| 58 | 0.42324743630813827 |
| 59 | 0.42324743630813827 |
| 60 | 0.42324743630813827 |

