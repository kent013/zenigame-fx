# Run 30 — run_20260504_064135

**Generated**: 2026-05-04T06:41:35.468535+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.0111867293340056 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 2983 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 30
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g13_i15`
- generation: 13
- fitness: **0.002186729334005601**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 2983
- total_pnl: 0.0
- sharpe: 0.0111867293340056
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 1240
- Stage A pass: 208
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 1240 | 208 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 1240 | 208 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=1240, mean=0.9581, median=1.0000, std=0.2004, min=0, max=1
- n_nodes: n=1240, mean=2.3298, median=2.0000, std=0.8539, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=208, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=208, mean=9, median=9.0000, std=0.0000, min=9, max=9
- positive_fold_ratio_effective (Stage A pass): n=208, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000

## Stage B failure reason 集計

- Stage A pass = 208, Stage B pass = 0, failures = 208 (primary_sum = 208)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 208 |
| `positive_fold_ratio<min` | 0 |
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
| `median_oos_sharpe<min` | 208 |
| `positive_fold_ratio<min` | 208 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=1240

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 5.2% (65/1240)
- best 個体 trade_count: 2983
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 1240
- metric_stage 分布: stage_a_evaluated=208, stage_a_only=1032
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=1032, mean=-874154.8256, median=-1000190.0000, std=320566.8828, min=-1002520.0000, max=2780.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=967): n=967, mean=-932913.9400, median=-1000190.0000, std=234208.2019, min=-1002520.0000, max=2780.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=208): n=208, mean=-1000558.8942, median=-1000560.0000, std=15.9092, min=-1000560.0000, max=-1000330.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g13_i15` | 13 | tier1_EUR_JPY | EUR_JPY | 0.0022 | 0.0112 | ✅ | ❌ | ❌ | 2983 | — |
| 2 | `g14_i0` | 14 | tier1_EUR_JPY | EUR_JPY | 0.0022 | 0.0112 | ✅ | ❌ | ❌ | 2983 | — |
| 3 | `g14_i38` | 14 | tier1_EUR_JPY | EUR_JPY | 0.0022 | 0.0112 | ✅ | ❌ | ❌ | 2983 | — |
| 4 | `g15_i0` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0022 | 0.0112 | ✅ | ❌ | ❌ | 2983 | — |
| 5 | `g15_i1` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0022 | 0.0112 | ✅ | ❌ | ❌ | 2983 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03412788290635155 |
| 1 | -0.03412788290635155 |
| 2 | -0.033921855727081784 |
| 3 | -0.033921855727081784 |
| 4 | -0.033921855727081784 |
| 5 | -0.030097785172664444 |
| 6 | -0.030097785172664444 |
| 7 | -0.026991823478650173 |
| 8 | -0.026991823478650173 |
| 9 | -0.026991823478650173 |
| 10 | -0.026991823478650173 |
| 11 | -0.026991823478650173 |
| 12 | -0.026991823478650173 |
| 13 | 0.002186729334005601 |
| 14 | 0.002186729334005601 |
| 15 | 0.002186729334005601 |
| 16 | 0.002186729334005601 |
| 17 | 0.002186729334005601 |
| 18 | 0.002186729334005601 |
| 19 | 0.002186729334005601 |
| 20 | 0.002186729334005601 |
| 21 | 0.002186729334005601 |
| 22 | 0.002186729334005601 |
| 23 | 0.002186729334005601 |
| 24 | 0.002186729334005601 |
| 25 | 0.002186729334005601 |
| 26 | 0.002186729334005601 |
| 27 | 0.002186729334005601 |
| 28 | 0.002186729334005601 |
| 29 | 0.002186729334005601 |
| 30 | 0.002186729334005601 |

