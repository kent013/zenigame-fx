# Run 26 — run_20260427_133025

**Generated**: 2026-04-27T13:30:25.585377+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.00985197504574978 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 3494 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g42_i6`
- generation: 42
- fitness: **0.00535197504574978**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 3494
- total_pnl: 0.0
- sharpe: 0.00985197504574978
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9976, median=1.0000, std=0.0488, min=0, max=1
- n_nodes: n=5856, mean=1.3217, median=1.0000, std=0.6042, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0
- n_fold_effective (Stage A pass): n=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 0, Stage B pass = 0, failures = 0 (primary_sum = 0)

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
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 2.2% (128/5856)
- best 個体 trade_count: 3494
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_only=5856
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5856, mean=-951361.5010, median=-1000160.0000, std=206946.1605, min=-1008720.0000, max=20270.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5728): n=5728, mean=-972620.9759, median=-1000170.0000, std=152007.6434, min=-1008720.0000, max=20270.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体: 0 件 (比較対照なし)

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g42_i6` | 42 | tier1_EUR_JPY | EUR_JPY | 0.0054 | 0.0099 | ❌ | ❌ | ❌ | 3494 | — |
| 2 | `g43_i0` | 43 | tier1_EUR_JPY | EUR_JPY | 0.0054 | 0.0099 | ❌ | ❌ | ❌ | 3494 | — |
| 3 | `g43_i65` | 43 | tier1_EUR_JPY | EUR_JPY | 0.0054 | 0.0099 | ❌ | ❌ | ❌ | 3494 | — |
| 4 | `g44_i0` | 44 | tier1_EUR_JPY | EUR_JPY | 0.0054 | 0.0099 | ❌ | ❌ | ❌ | 3494 | — |
| 5 | `g44_i1` | 44 | tier1_EUR_JPY | EUR_JPY | 0.0054 | 0.0099 | ❌ | ❌ | ❌ | 3494 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.029602992763365966 |
| 1 | -0.02670434792346645 |
| 2 | -0.025289571096869783 |
| 3 | -0.018923363352771762 |
| 4 | -0.018923363352771762 |
| 5 | -0.009164171783194957 |
| 6 | -0.009164171783194957 |
| 7 | -0.009164171783194957 |
| 8 | -0.009164171783194957 |
| 9 | -0.009164171783194957 |
| 10 | -0.009164171783194957 |
| 11 | 0.0026828495623086425 |
| 12 | 0.0026828495623086425 |
| 13 | 0.0026828495623086425 |
| 14 | 0.0026828495623086425 |
| 15 | 0.0026828495623086425 |
| 16 | 0.0026828495623086425 |
| 17 | 0.0026828495623086425 |
| 18 | 0.0026828495623086425 |
| 19 | 0.0026828495623086425 |
| 20 | 0.0026828495623086425 |
| 21 | 0.0026828495623086425 |
| 22 | 0.0026828495623086425 |
| 23 | 0.0026828495623086425 |
| 24 | 0.0026828495623086425 |
| 25 | 0.0026828495623086425 |
| 26 | 0.0026828495623086425 |
| 27 | 0.0026828495623086425 |
| 28 | 0.0026828495623086425 |
| 29 | 0.0026828495623086425 |
| 30 | 0.0026828495623086425 |
| 31 | 0.0026828495623086425 |
| 32 | 0.0026828495623086425 |
| 33 | 0.0026828495623086425 |
| 34 | 0.0026828495623086425 |
| 35 | 0.0026828495623086425 |
| 36 | 0.0026828495623086425 |
| 37 | 0.0026828495623086425 |
| 38 | 0.0026828495623086425 |
| 39 | 0.0026828495623086425 |
| 40 | 0.0026828495623086425 |
| 41 | 0.0026828495623086425 |
| 42 | 0.00535197504574978 |
| 43 | 0.00535197504574978 |
| 44 | 0.00535197504574978 |
| 45 | 0.00535197504574978 |
| 46 | 0.00535197504574978 |
| 47 | 0.00535197504574978 |
| 48 | 0.00535197504574978 |
| 49 | 0.00535197504574978 |
| 50 | 0.00535197504574978 |
| 51 | 0.00535197504574978 |
| 52 | 0.00535197504574978 |
| 53 | 0.00535197504574978 |
| 54 | 0.00535197504574978 |
| 55 | 0.00535197504574978 |
| 56 | 0.00535197504574978 |
| 57 | 0.00535197504574978 |
| 58 | 0.00535197504574978 |
| 59 | 0.00535197504574978 |
| 60 | 0.00535197504574978 |

