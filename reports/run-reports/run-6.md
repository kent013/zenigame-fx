# Run 6 — run_20260425_002246

**Generated**: 2026-04-25T00:22:47.060064+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)
  - bars_stage_a: 14351
  - bars_stage_b: 14351
  - bars_holdout: 37832

## 使命判定

未達

- ✅ **sharpe**: 9.427688950584354 / threshold 1.0
- ❌ **total_pnl**: 7700.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 2 (range 50〜5000)

## GA 設定

- population_size: 20
- generations: 5
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g5_i7`
- generation: 5
- fitness: **9.412688950584354**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 2
- total_pnl: 7700.0
- sharpe: 9.427688950584354
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 120
- Stage A pass: 49
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 120 | 49 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 120 | 49 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=120, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=120, mean=2.7500, median=3.0000, std=0.7879, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=120

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g5_i7` | 5 | tier1_EUR_JPY | EUR_JPY | 9.4127 | 9.4277 | ✅ | ❌ | ❌ | 2 | 9.4277 |
| 2 | `g1_i17` | 1 | tier1_EUR_JPY | EUR_JPY | 8.7737 | 8.7887 | ✅ | ❌ | ❌ | 2 | 8.7887 |
| 3 | `g2_i0` | 2 | tier1_EUR_JPY | EUR_JPY | 8.7737 | 8.7887 | ✅ | ❌ | ❌ | 2 | 8.7887 |
| 4 | `g3_i0` | 3 | tier1_EUR_JPY | EUR_JPY | 8.7737 | 8.7887 | ✅ | ❌ | ❌ | 2 | 8.7887 |
| 5 | `g3_i17` | 3 | tier1_EUR_JPY | EUR_JPY | 8.7737 | 8.7887 | ✅ | ❌ | ❌ | 2 | 8.7887 |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.26472000999153744 |
| 1 | 8.773748081002916 |
| 2 | 8.773748081002916 |
| 3 | 8.773748081002916 |
| 4 | 8.773748081002916 |
| 5 | 9.412688950584354 |

## 分析

### analysis-claude.md

# Run 6 分析

**run_id**: `run_20260425_002246`
**generated_at**: 2026-04-25T00:22:47.060064+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 9.427688950584354 / 閾値 1.0
- ❌ total_pnl: 7700.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 2 (許容 50〜5000)

### Best 個体

- name: `g5_i7`
- fitness (sharpe): 9.412688950584354
- trade_count: 2
- total_pnl: 7700.0
- sharpe: 9.427688950584354
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 0.26472000999153744
- 最終世代 best_fitness: 9.412688950584354
- Δfitness: 9.14796894059281656
- plateau: False

### 前回 Run との比較

- best_fitness: 3.4423640577259804 ↑ 9.412688950584354 (Δ=5.9703248928583736)
- trade_count: 28 → 2

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

# Codex 独立分析 (skipped — observe-only stress-test mode)
stress-test 30 cycle 実行中のためスキップ。

