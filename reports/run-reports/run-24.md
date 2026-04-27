# Run 24 — run_20260427_015804

**Generated**: 2026-04-27T01:58:04.062166+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.3016982223218697 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 30 (range 50〜5000)

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

- name: `g58_i19`
- generation: 58
- fitness: **0.2821982223218697**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 30
- total_pnl: 0.0
- sharpe: 0.3016982223218697
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
- Stage A pass: 3745
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 3745 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 3745 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9973, median=1.0000, std=0.0522, min=0, max=1
- n_nodes: n=5856, mean=3.6008, median=4.0000, std=0.7544, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=3745, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=3745, mean=0, median=0, std=0.0000, min=0, max=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 3745, Stage B pass = 0, failures = 3745 (primary_sum = 3745)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 3745 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 3745 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 3745 |
| `positive_fold_ratio<min` | 3745 |
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
- trade_count=0 個体比率: 3.9% (227/5856)
- best 個体 trade_count: 30
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=3745, stage_a_only=2111
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=2111, mean=-1990934.4387, median=-23340.0000, std=4420512.3829, min=-18262070.0000, max=29220.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=1884): n=1884, mean=-2230818.7898, median=-26870.0000, std=4621714.5148, min=-18262070.0000, max=29220.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=3745): n=3745, mean=24199.0788, median=26300.0000, std=7706.5565, min=1640.0000, max=32450.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g58_i19` | 58 | tier1_EUR_JPY | EUR_JPY | 0.2822 | 0.3017 | ✅ | ❌ | ❌ | 30 | — |
| 2 | `g59_i0` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2822 | 0.3017 | ✅ | ❌ | ❌ | 30 | — |
| 3 | `g60_i0` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2822 | 0.3017 | ✅ | ❌ | ❌ | 30 | — |
| 4 | `g60_i64` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2822 | 0.3017 | ✅ | ❌ | ❌ | 30 | — |
| 5 | `g52_i38` | 52 | tier1_EUR_JPY | EUR_JPY | 0.2820 | 0.3015 | ✅ | ❌ | ❌ | 30 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.017765415985992114 |
| 1 | 0.017765415985992114 |
| 2 | 0.017765415985992114 |
| 3 | 0.017765415985992114 |
| 4 | 0.03260386945790364 |
| 5 | 0.07958925848983463 |
| 6 | 0.07958925848983463 |
| 7 | 0.20100289517794948 |
| 8 | 0.20100289517794948 |
| 9 | 0.20100289517794948 |
| 10 | 0.20100289517794948 |
| 11 | 0.20100289517794948 |
| 12 | 0.22910947108336704 |
| 13 | 0.22910947108336704 |
| 14 | 0.22910947108336704 |
| 15 | 0.22999849551387663 |
| 16 | 0.22999849551387663 |
| 17 | 0.22999849551387663 |
| 18 | 0.22999849551387663 |
| 19 | 0.23051633633886073 |
| 20 | 0.2322864636965626 |
| 21 | 0.2322864636965626 |
| 22 | 0.23451647697111164 |
| 23 | 0.23451647697111164 |
| 24 | 0.2506611517486728 |
| 25 | 0.2506611517486728 |
| 26 | 0.2506611517486728 |
| 27 | 0.2652205657654838 |
| 28 | 0.2652205657654838 |
| 29 | 0.2652205657654838 |
| 30 | 0.2652205657654838 |
| 31 | 0.2652205657654838 |
| 32 | 0.2652205657654838 |
| 33 | 0.2652205657654838 |
| 34 | 0.2652205657654838 |
| 35 | 0.2652205657654838 |
| 36 | 0.2652205657654838 |
| 37 | 0.2652205657654838 |
| 38 | 0.2652205657654838 |
| 39 | 0.2652205657654838 |
| 40 | 0.2652205657654838 |
| 41 | 0.2652205657654838 |
| 42 | 0.2652205657654838 |
| 43 | 0.2678037329984189 |
| 44 | 0.2678037329984189 |
| 45 | 0.2678037329984189 |
| 46 | 0.2678037329984189 |
| 47 | 0.26885310745508834 |
| 48 | 0.26885310745508834 |
| 49 | 0.26885310745508834 |
| 50 | 0.26885310745508834 |
| 51 | 0.26885310745508834 |
| 52 | 0.28198319294381174 |
| 53 | 0.28198319294381174 |
| 54 | 0.28198319294381174 |
| 55 | 0.28198319294381174 |
| 56 | 0.28198319294381174 |
| 57 | 0.28198319294381174 |
| 58 | 0.2821982223218697 |
| 59 | 0.2821982223218697 |
| 60 | 0.2821982223218697 |

