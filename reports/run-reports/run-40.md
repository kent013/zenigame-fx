# Run 40 — run_20260506_125955

**Generated**: 2026-05-06T13:00:07.476646+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.27151585427363467 / threshold 1.0
- ❌ **total_pnl**: 38070.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 50 (range 50〜5000)

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

- name: `g43_i71`
- generation: 43
- fitness: **0.25201585427363465**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 50
- total_pnl: 38070.0
- sharpe: 0.27151585427363467
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
- Stage A pass: 1929
- Stage B pass: 0
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1929 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1929 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2695, median=1.0000, std=0.4543, min=0, max=2
- n_nodes: n=5856, mean=3.7280, median=4.0000, std=1.6644, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1929, mean=0.1734, median=0.2000, std=0.1672, min=0.0000, max=0.7000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1929, mean=6.7994, median=9, std=4.3505, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=1812, mean=0.2879, median=0.1818, std=0.3110, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1929, Stage B pass = 0, failures = 1929 (primary_sum = 1929)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1928 |
| `positive_fold_ratio<min` | 1 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 117 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1928 |
| `positive_fold_ratio<min` | 1929 |
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
- trade_count=0 個体比率: 5.5% (320/5856)
- best 個体 trade_count: 50
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1929, stage_a_only=3927
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3927, mean=-401236.4222, median=-109900.0000, std=454629.4891, min=-1006190.0000, max=20760.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3607): n=3607, mean=-436832.6670, median=-143580.0000, std=457684.3667, min=-1006190.0000, max=20760.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1929): n=1929, mean=12483.7947, median=19360.0000, std=87221.2847, min=-1000940.0000, max=47920.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g60_i19` | 60 | tier1_EUR_JPY | EUR_JPY | 0.3226 | 0.3511 | ✅ | ❌ | ❌ | 41 | — |
| 2 | `g54_i14` | 54 | tier1_EUR_JPY | EUR_JPY | 0.3016 | 0.3261 | ✅ | ❌ | ❌ | 45 | — |
| 3 | `g56_i34` | 56 | tier1_EUR_JPY | EUR_JPY | 0.2918 | 0.3143 | ✅ | ❌ | ❌ | 47 | — |
| 4 | `g52_i93` | 52 | tier1_EUR_JPY | EUR_JPY | 0.2823 | 0.3048 | ✅ | ❌ | ❌ | 47 | — |
| 5 | `g54_i94` | 54 | tier1_EUR_JPY | EUR_JPY | 0.2664 | 0.2869 | ✅ | ❌ | ❌ | 49 | — |

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
| 16 | 0.08309148460103993 |
| 17 | 0.06981602717127808 |
| 18 | 0.08582775776566816 |
| 19 | 0.075437860456114 |
| 20 | 0.075437860456114 |
| 21 | 0.095928501821253 |
| 22 | 0.09720715568596278 |
| 23 | 0.1710709746092857 |
| 24 | 0.1746897686884248 |
| 25 | 0.1746897686884248 |
| 26 | 0.2639400194568124 |
| 27 | 0.1746897686884248 |
| 28 | 0.1746897686884248 |
| 29 | 0.17566007632298067 |
| 30 | 0.17566007632298067 |
| 31 | 0.19886586134947973 |
| 32 | 0.2186256255637327 |
| 33 | 0.20250951753917493 |
| 34 | 0.2501222661155634 |
| 35 | 0.13502639873110808 |
| 36 | 0.210205858086106 |
| 37 | 0.1811288786016748 |
| 38 | 0.21588224578654827 |
| 39 | 0.2190176196452573 |
| 40 | 0.23332657644446558 |
| 41 | 0.23332657644446558 |
| 42 | 0.23332657644446558 |
| 43 | 0.25201585427363465 |
| 44 | 0.25201585427363465 |
| 45 | 0.25614678469974833 |
| 46 | 0.2538785855201302 |
| 47 | 0.26529204888925834 |
| 48 | 0.25201585427363465 |
| 49 | 0.25201585427363465 |
| 50 | 0.25722828416851734 |
| 51 | 0.25201585427363465 |
| 52 | 0.28225099235351364 |
| 53 | 0.25201585427363465 |
| 54 | 0.301624598751725 |
| 55 | 0.25201585427363465 |
| 56 | 0.2918425320494539 |
| 57 | 0.25201585427363465 |
| 58 | 0.25201585427363465 |
| 59 | 0.25201585427363465 |
| 60 | 0.3225775414315051 |

