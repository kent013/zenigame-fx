# Run 50 — run_20260507_060110

**Generated**: 2026-05-07T06:02:45.171119+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.33259569811469253 / threshold 1.0
- ❌ **total_pnl**: 39630.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 59 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 90
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g82_i24`
- generation: 82
- fitness: **0.3100956981146925**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 59
- total_pnl: 39630.0
- sharpe: 0.33259569811469253
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1111
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 8736
- Stage A pass: 3187
- Stage B pass: 209
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 8736 | 3187 | 209 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 8736 | 3187 | 209 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=8736, mean=1.4311, median=1.0000, std=0.5055, min=0, max=2
- n_nodes: n=8736, mean=3.6070, median=4.0000, std=1.6252, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=3187, mean=0.1428, median=0.1111, std=0.0919, min=0.0000, max=0.5556
- dsr: n=0
- n_fold_effective (Stage A pass): n=3187, mean=8.0505, median=8, std=2.0513, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=3183, mean=0.4469, median=0.5714, std=0.2367, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 3187, Stage B pass = 209, failures = 2978 (primary_sum = 2978)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2115 |
| `positive_fold_ratio<min` | 863 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 4 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2115 |
| `positive_fold_ratio<min` | 2950 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=8736

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 5.2% (454/8736)
- best 個体 trade_count: 59
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 8736
- metric_stage 分布: stage_a_evaluated=2978, stage_a_only=5549, stage_b_evaluated=209
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5549, mean=-306313.9971, median=-55380.0000, std=423002.1886, min=-1006190.0000, max=39280.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5095): n=5095, mean=-333608.7085, median=-64640.0000, std=431009.3778, min=-1006190.0000, max=39280.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=3187): n=3187, mean=11664.6219, median=13840.0000, std=67891.3391, min=-1000940.0000, max=48640.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g59_i56` | 59 | tier1_EUR_JPY | EUR_JPY | 0.5424 | 0.5804 | ✅ | ❌ | ❌ | 30 | — |
| 2 | `g71_i87` | 71 | tier1_EUR_JPY | EUR_JPY | 0.4575 | 0.4985 | ✅ | ❌ | ❌ | 30 | — |
| 3 | `g72_i78` | 72 | tier1_EUR_JPY | EUR_JPY | 0.4575 | 0.4985 | ✅ | ❌ | ❌ | 30 | — |
| 4 | `g52_i60` | 52 | tier1_EUR_JPY | EUR_JPY | 0.4406 | 0.4806 | ✅ | ❌ | ❌ | 31 | — |
| 5 | `g61_i77` | 61 | tier1_EUR_JPY | EUR_JPY | 0.4339 | 0.4549 | ✅ | ❌ | ❌ | 54 | — |

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
| 33 | 0.19886586134947973 |
| 34 | 0.1779501553759853 |
| 35 | 0.1779501553759853 |
| 36 | 0.1617805756554315 |
| 37 | 0.15885757274398857 |
| 38 | 0.24443347810607224 |
| 39 | 0.1533845751898636 |
| 40 | 0.22463371167091756 |
| 41 | 0.10697546415445239 |
| 42 | 0.15718731868590494 |
| 43 | 0.19983098145611672 |
| 44 | 0.2114164057960742 |
| 45 | 0.2114164057960742 |
| 46 | 0.2114164057960742 |
| 47 | 0.2114164057960742 |
| 48 | 0.25408456963260406 |
| 49 | 0.21149538659217532 |
| 50 | 0.2198497211239007 |
| 51 | 0.2117671922624509 |
| 52 | 0.44064292224597673 |
| 53 | 0.42604845878194425 |
| 54 | 0.2117671922624509 |
| 55 | 0.21413417419738792 |
| 56 | 0.21694013012756808 |
| 57 | 0.4057502037673329 |
| 58 | 0.4071803835711964 |
| 59 | 0.5424296342040379 |
| 60 | 0.3711950161936395 |
| 61 | 0.43388045249953455 |
| 62 | 0.25037151149898484 |
| 63 | 0.22048618663304748 |
| 64 | 0.22048618663304748 |
| 65 | 0.26263818238290093 |
| 66 | 0.4232289697501845 |
| 67 | 0.22422574328177106 |
| 68 | 0.24768026679176725 |
| 69 | 0.22169569498195055 |
| 70 | 0.40510265421057984 |
| 71 | 0.457468542496723 |
| 72 | 0.457468542496723 |
| 73 | 0.22169569498195055 |
| 74 | 0.22169569498195055 |
| 75 | 0.22169569498195055 |
| 76 | 0.22169569498195055 |
| 77 | 0.22169569498195055 |
| 78 | 0.23433797693469724 |
| 79 | 0.23433797693469724 |
| 80 | 0.36386035994703114 |
| 81 | 0.3812293080208763 |
| 82 | 0.3100956981146925 |
| 83 | 0.3100956981146925 |
| 84 | 0.34998365901965467 |
| 85 | 0.31315847842651023 |
| 86 | 0.3100956981146925 |
| 87 | 0.3100956981146925 |
| 88 | 0.38054275729486436 |
| 89 | 0.313223396919997 |
| 90 | 0.3100956981146925 |

