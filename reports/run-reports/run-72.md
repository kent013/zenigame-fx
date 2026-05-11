# Run 72 — run_20260511_065501

**Generated**: 2026-05-11T06:55:02.650247+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.26178943292402007 / threshold 1.0
- ❌ **total_pnl**: -19550.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 2.0177086664534696 / threshold 20.0
- ❌ **trade_count**: 37 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 57

## Best 個体

- name: `g53_i67`
- generation: 53
- fitness: **0.22278943292402006**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 37
- total_pnl: -19550.0
- sharpe: 0.26178943292402007
- sortino: —
- calmar: —
- max_drawdown_pct: 2.0177086664534696

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1515
- dsr: —
- ii_lite_pass: —
- n_nodes: 8
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1736
- Stage B pass: 68
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1736 | 68 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1736 | 68 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4635, median=1.0000, std=0.5004, min=0, max=2
- n_nodes: n=5856, mean=4.3832, median=4.0000, std=2.0262, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=65, mean=0.2957, median=0.2918, std=0.0110, min=0.2770, max=0.3086
- best mission_score: **0.3086** (`g53_i34`, gen=53, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1736, mean=0.1773, median=0.1818, std=0.0734, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=1736, mean=27.5282, median=34.0000, std=10.2771, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1735, mean=0.4197, median=0.4118, std=0.1763, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1736, Stage B pass = 68, failures = 1668 (primary_sum = 1668)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1589 |
| `positive_fold_ratio<min` | 79 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1589 |
| `positive_fold_ratio<min` | 1668 |
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
- trade_count=0 個体比率: 6.8% (396/5856)
- best 個体 trade_count: 37
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1668, stage_a_only=4120, stage_b_evaluated=68
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4120, mean=-291551.5922, median=-31710.0000, std=423300.2888, min=-1009010.0000, max=30390.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3724): n=3724, mean=-322554.3931, median=-47495.0000, std=433862.7554, min=-1009010.0000, max=30390.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1736): n=1736, mean=11452.1832, median=10535.0000, std=25613.4765, min=-1000080.0000, max=40270.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g55_i66` | 55 | tier1_EUR_JPY | EUR_JPY | 0.3892 | 0.4432 | ✅ | ❌ | ❌ | 35 | — |
| 2 | `g53_i38` | 53 | tier1_EUR_JPY | EUR_JPY | 0.3577 | 0.4137 | ✅ | ❌ | ❌ | 33 | — |
| 3 | `g54_i73` | 54 | tier1_EUR_JPY | EUR_JPY | 0.3577 | 0.4137 | ✅ | ❌ | ❌ | 33 | — |
| 4 | `g55_i77` | 55 | tier1_EUR_JPY | EUR_JPY | 0.3559 | 0.3924 | ✅ | ❌ | ❌ | 33 | — |
| 5 | `g51_i48` | 51 | tier1_EUR_JPY | EUR_JPY | 0.3487 | 0.3957 | ✅ | ❌ | ❌ | 42 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0009889464911611474 |
| 1 | 0.0009889464911611474 |
| 2 | 0.0009889464911611474 |
| 3 | 0.0009889464911611474 |
| 4 | 0.2627672573519494 |
| 5 | 0.2627672573519494 |
| 6 | 0.2627672573519494 |
| 7 | 0.2627672573519494 |
| 8 | 0.2627672573519494 |
| 9 | 0.2627672573519494 |
| 10 | 0.2627672573519494 |
| 11 | 0.2627672573519494 |
| 12 | 0.2627672573519494 |
| 13 | 0.2627672573519494 |
| 14 | 0.2627672573519494 |
| 15 | 0.2627672573519494 |
| 16 | 0.2627672573519494 |
| 17 | 0.2627672573519494 |
| 18 | 0.2627672573519494 |
| 19 | 0.2627672573519494 |
| 20 | 0.26285640842561697 |
| 21 | 0.30689941528626213 |
| 22 | 0.3323601797346473 |
| 23 | 0.3323601797346473 |
| 24 | 0.30689941528626213 |
| 25 | 0.31140003147909623 |
| 26 | 0.31140003147909623 |
| 27 | 0.31242637856275124 |
| 28 | 0.31242637856275124 |
| 29 | 0.31242637856275124 |
| 30 | 0.31242637856275124 |
| 31 | 0.31242637856275124 |
| 32 | 0.31242637856275124 |
| 33 | 0.32018997775180724 |
| 34 | 0.31242637856275124 |
| 35 | 0.31242637856275124 |
| 36 | 0.31242637856275124 |
| 37 | 0.31242637856275124 |
| 38 | 0.31242637856275124 |
| 39 | 0.31242637856275124 |
| 40 | 0.33063478449129297 |
| 41 | 0.31242637856275124 |
| 42 | 0.31387576042275306 |
| 43 | 0.31387576042275306 |
| 44 | 0.31387576042275306 |
| 45 | 0.31387576042275306 |
| 46 | 0.31387576042275306 |
| 47 | 0.31387576042275306 |
| 48 | 0.31387576042275306 |
| 49 | 0.294255240882956 |
| 50 | 0.2748857673399295 |
| 51 | 0.34873728376458024 |
| 52 | 0.3007583732607315 |
| 53 | 0.3576735293303851 |
| 54 | 0.3576735293303851 |
| 55 | 0.3892152405568574 |
| 56 | 0.3023551864735954 |
| 57 | 0.3150331941658583 |
| 58 | 0.3023551864735954 |
| 59 | 0.28166651855902025 |
| 60 | 0.3380339784148461 |

