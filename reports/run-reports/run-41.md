# Run 41 — run_20260506_143955

**Generated**: 2026-05-06T14:40:06.062640+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.1943720705212043 / threshold 1.0
- ❌ **total_pnl**: 30670.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 51 (range 50〜5000)

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

- name: `g44_i89`
- generation: 44
- fitness: **0.1598720705212043**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 51
- total_pnl: 30670.0
- sharpe: 0.1943720705212043
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2000
- dsr: —
- ii_lite_pass: —
- n_nodes: 7
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1666
- Stage B pass: 1
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1666 | 1 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1666 | 1 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3963, median=1.0000, std=0.4985, min=0, max=2
- n_nodes: n=5856, mean=4.1836, median=4.0000, std=1.9839, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1666, mean=0.2562, median=0.2000, std=0.1725, min=0.0000, max=0.7000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1666, mean=8.3601, median=9.0000, std=3.4084, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=1566, mean=0.3200, median=0.2727, std=0.2169, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1666, Stage B pass = 1, failures = 1665 (primary_sum = 1665)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1664 |
| `positive_fold_ratio<min` | 1 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 100 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1664 |
| `positive_fold_ratio<min` | 1662 |
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
- trade_count=0 個体比率: 3.8% (220/5856)
- best 個体 trade_count: 51
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1665, stage_a_only=4190, stage_b_evaluated=1
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4190, mean=-386528.6683, median=-100240.0000, std=449176.2060, min=-1006190.0000, max=22440.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3970): n=3970, mean=-407948.3929, median=-117150.0000, std=451886.8618, min=-1006190.0000, max=22440.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1666): n=1666, mean=4750.0360, median=12270.0000, std=92859.6294, min=-1000940.0000, max=34300.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g27_i86` | 27 | tier1_EUR_JPY | EUR_JPY | 0.2559 | 0.3044 | ✅ | ❌ | ❌ | 33 | — |
| 2 | `g34_i17` | 34 | tier1_EUR_JPY | EUR_JPY | 0.2089 | 0.2584 | ✅ | ❌ | ❌ | 32 | — |
| 3 | `g29_i30` | 29 | tier1_EUR_JPY | EUR_JPY | 0.2005 | 0.2420 | ✅ | ❌ | ❌ | 43 | — |
| 4 | `g57_i30` | 57 | tier1_EUR_JPY | EUR_JPY | 0.1820 | 0.2325 | ✅ | ❌ | ❌ | 34 | — |
| 5 | `g27_i21` | 27 | tier1_EUR_JPY | EUR_JPY | 0.1767 | 0.2072 | ✅ | ❌ | ❌ | 39 | — |

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
| 23 | 0.10833198767363127 |
| 24 | 0.11090106678941355 |
| 25 | 0.10833198767363127 |
| 26 | 0.08085449231919968 |
| 27 | 0.2558944416855591 |
| 28 | 0.15115174985878402 |
| 29 | 0.20053195979747182 |
| 30 | 0.15115174985878402 |
| 31 | 0.15115174985878402 |
| 32 | 0.15115174985878402 |
| 33 | 0.15115174985878402 |
| 34 | 0.20892267620231253 |
| 35 | 0.15115174985878402 |
| 36 | 0.15115174985878402 |
| 37 | 0.15115174985878402 |
| 38 | 0.15115174985878402 |
| 39 | 0.15115174985878402 |
| 40 | 0.15115174985878402 |
| 41 | 0.15115174985878402 |
| 42 | 0.15115174985878402 |
| 43 | 0.15134518480375386 |
| 44 | 0.1598720705212043 |
| 45 | 0.1598720705212043 |
| 46 | 0.1598720705212043 |
| 47 | 0.1598720705212043 |
| 48 | 0.1598720705212043 |
| 49 | 0.1598720705212043 |
| 50 | 0.1598720705212043 |
| 51 | 0.1598720705212043 |
| 52 | 0.1598720705212043 |
| 53 | 0.16376351508541742 |
| 54 | 0.1598720705212043 |
| 55 | 0.1598720705212043 |
| 56 | 0.1598720705212043 |
| 57 | 0.1819583733108734 |
| 58 | 0.1598720705212043 |
| 59 | 0.1598720705212043 |
| 60 | 0.1598720705212043 |

