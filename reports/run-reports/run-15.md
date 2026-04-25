# Run 15 — run_20260425_185201

**Generated**: 2026-04-25T18:52:01.296687+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.06863702995285534 / threshold 1.0
- ❌ **total_pnl**: 8660.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 70 (range 50〜5000)

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

- name: `g49_i64`
- generation: 49
- fitness: **0.4655482810092501**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 70
- total_pnl: 8660.0
- sharpe: 0.06863702995285534
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
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2619
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2619 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2619 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=3.5260, median=4.0000, std=0.7693, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2619, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2619, mean=0, median=0, std=0.0000, min=0, max=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 2619, Stage B pass = 0, failures = 2619 (primary_sum = 2619)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2619 |
| `positive_fold_ratio<min` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2619 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2619 |
| `positive_fold_ratio<min` | 2619 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 2.9% (169/5856)
- best 個体 trade_count: 70
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g49_i64` | 49 | tier1_EUR_JPY | EUR_JPY | 0.4655 | 0.4835 | ✅ | ❌ | ❌ | 70 | — |
| 2 | `g50_i0` | 50 | tier1_EUR_JPY | EUR_JPY | 0.4655 | 0.4835 | ✅ | ❌ | ❌ | 70 | — |
| 3 | `g50_i90` | 50 | tier1_EUR_JPY | EUR_JPY | 0.4655 | 0.4835 | ✅ | ❌ | ❌ | 70 | — |
| 4 | `g51_i0` | 51 | tier1_EUR_JPY | EUR_JPY | 0.4655 | 0.4835 | ✅ | ❌ | ❌ | 70 | — |
| 5 | `g51_i1` | 51 | tier1_EUR_JPY | EUR_JPY | 0.4655 | 0.4835 | ✅ | ❌ | ❌ | 70 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 0.0 |
| 3 | 0.0 |
| 4 | 0.0 |
| 5 | 0.10359826590306172 |
| 6 | 0.10359826590306172 |
| 7 | 0.10359826590306172 |
| 8 | 0.10359826590306172 |
| 9 | 0.10359826590306172 |
| 10 | 0.10359826590306172 |
| 11 | 0.19188757297024225 |
| 12 | 0.19188757297024225 |
| 13 | 0.19188757297024225 |
| 14 | 0.19188757297024225 |
| 15 | 0.19188757297024225 |
| 16 | 0.19188757297024225 |
| 17 | 0.19188757297024225 |
| 18 | 0.2176921470825325 |
| 19 | 0.2927785974850615 |
| 20 | 0.31277105403204625 |
| 21 | 0.31277105403204625 |
| 22 | 0.31277105403204625 |
| 23 | 0.3236115222987543 |
| 24 | 0.32732854409238793 |
| 25 | 0.37763760145574127 |
| 26 | 0.37763760145574127 |
| 27 | 0.37763760145574127 |
| 28 | 0.37763760145574127 |
| 29 | 0.37763760145574127 |
| 30 | 0.37763760145574127 |
| 31 | 0.37763760145574127 |
| 32 | 0.37763760145574127 |
| 33 | 0.3957508209833023 |
| 34 | 0.3957508209833023 |
| 35 | 0.3957508209833023 |
| 36 | 0.3957508209833023 |
| 37 | 0.39644010264159485 |
| 38 | 0.39644010264159485 |
| 39 | 0.39644010264159485 |
| 40 | 0.39644010264159485 |
| 41 | 0.43680440155921585 |
| 42 | 0.43680440155921585 |
| 43 | 0.43680440155921585 |
| 44 | 0.43680440155921585 |
| 45 | 0.43680440155921585 |
| 46 | 0.43680440155921585 |
| 47 | 0.43680440155921585 |
| 48 | 0.43680440155921585 |
| 49 | 0.4655482810092501 |
| 50 | 0.4655482810092501 |
| 51 | 0.4655482810092501 |
| 52 | 0.4655482810092501 |
| 53 | 0.4655482810092501 |
| 54 | 0.4655482810092501 |
| 55 | 0.4655482810092501 |
| 56 | 0.4655482810092501 |
| 57 | 0.4655482810092501 |
| 58 | 0.4655482810092501 |
| 59 | 0.4655482810092501 |
| 60 | 0.4655482810092501 |

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

