# Run 16 — run_20260425_235717

**Generated**: 2026-04-25T23:57:17.279108+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.3411706435446119 / threshold 1.0
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

- name: `g26_i34`
- generation: 26
- fitness: **0.3321706435446119**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 30
- total_pnl: 0.0
- sharpe: 0.3411706435446119
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 0

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

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=2.2876, median=2.0000, std=0.7869, min=1, max=4

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
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 16.0% (938/5856)
- best 個体 trade_count: 30
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g26_i34` | 26 | tier1_EUR_JPY | EUR_JPY | 0.3322 | 0.3412 | ❌ | ❌ | ❌ | 30 | — |
| 2 | `g27_i0` | 27 | tier1_EUR_JPY | EUR_JPY | 0.3322 | 0.3412 | ❌ | ❌ | ❌ | 30 | — |
| 3 | `g27_i11` | 27 | tier1_EUR_JPY | EUR_JPY | 0.3322 | 0.3412 | ❌ | ❌ | ❌ | 30 | — |
| 4 | `g27_i16` | 27 | tier1_EUR_JPY | EUR_JPY | 0.3322 | 0.3412 | ❌ | ❌ | ❌ | 30 | — |
| 5 | `g27_i57` | 27 | tier1_EUR_JPY | EUR_JPY | 0.3322 | 0.3412 | ❌ | ❌ | ❌ | 30 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.22185112882965508 |
| 2 | 0.22185112882965508 |
| 3 | 0.22185112882965508 |
| 4 | 0.22185112882965508 |
| 5 | 0.22785112882965505 |
| 6 | 0.22785112882965505 |
| 7 | 0.22785112882965505 |
| 8 | 0.22785112882965505 |
| 9 | 0.22785112882965505 |
| 10 | 0.22785112882965505 |
| 11 | 0.2751075193927039 |
| 12 | 0.29536503845423384 |
| 13 | 0.30136503845423385 |
| 14 | 0.30136503845423385 |
| 15 | 0.30136503845423385 |
| 16 | 0.30136503845423385 |
| 17 | 0.30136503845423385 |
| 18 | 0.30560773523130197 |
| 19 | 0.30560773523130197 |
| 20 | 0.30560773523130197 |
| 21 | 0.30560773523130197 |
| 22 | 0.30560773523130197 |
| 23 | 0.30560773523130197 |
| 24 | 0.30560773523130197 |
| 25 | 0.30560773523130197 |
| 26 | 0.3321706435446119 |
| 27 | 0.3321706435446119 |
| 28 | 0.3321706435446119 |
| 29 | 0.3321706435446119 |
| 30 | 0.3321706435446119 |
| 31 | 0.3321706435446119 |
| 32 | 0.3321706435446119 |
| 33 | 0.3321706435446119 |
| 34 | 0.3321706435446119 |
| 35 | 0.3321706435446119 |
| 36 | 0.3321706435446119 |
| 37 | 0.3321706435446119 |
| 38 | 0.3321706435446119 |
| 39 | 0.3321706435446119 |
| 40 | 0.3321706435446119 |
| 41 | 0.3321706435446119 |
| 42 | 0.3321706435446119 |
| 43 | 0.3321706435446119 |
| 44 | 0.3321706435446119 |
| 45 | 0.3321706435446119 |
| 46 | 0.3321706435446119 |
| 47 | 0.3321706435446119 |
| 48 | 0.3321706435446119 |
| 49 | 0.3321706435446119 |
| 50 | 0.3321706435446119 |
| 51 | 0.3321706435446119 |
| 52 | 0.3321706435446119 |
| 53 | 0.3321706435446119 |
| 54 | 0.3321706435446119 |
| 55 | 0.3321706435446119 |
| 56 | 0.3321706435446119 |
| 57 | 0.3321706435446119 |
| 58 | 0.3321706435446119 |
| 59 | 0.3321706435446119 |
| 60 | 0.3321706435446119 |

## 分析

### analysis-claude.md

# Run 15 分析

**run_id**: `run_20260425_185201`
**generated_at**: 2026-04-25T18:52:01.296687+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.06863702995285534 / 閾値 1.0
- ❌ total_pnl: 8660.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 70 (許容 50〜5000)

### Best 個体

- name: `g49_i64`
- fitness (sharpe): 0.4655482810092501
- trade_count: 70
- total_pnl: 8660.0
- sharpe: 0.06863702995285534
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.4655482810092501
- Δfitness: 0.4655482810092501
- plateau: True

### 前回 Run との比較

- best_fitness: 0.12058798400220912 ↑ 0.4655482810092501 (Δ=0.34496029700704098)
- trade_count: 59 → 70

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。

