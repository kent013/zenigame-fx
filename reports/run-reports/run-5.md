# Run 5 — run_20260425_002233

**Generated**: 2026-04-25T00:22:34.000158+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)
  - bars_stage_a: 14351
  - bars_stage_b: 14351
  - bars_holdout: 37832

## 使命判定

未達

- ✅ **sharpe**: 3.4558640577259805 / threshold 1.0
- ❌ **total_pnl**: 4450.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 28 (range 50〜5000)

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

- name: `g3_i15`
- generation: 3
- fitness: **3.4423640577259804**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 28
- total_pnl: 4450.0
- sharpe: 3.4558640577259805
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
- Stage A pass: 38
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 120 | 38 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 120 | 38 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=120, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=120, mean=2.8750, median=3.0000, std=0.8120, min=1, max=4

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
| 1 | `g3_i15` | 3 | tier1_EUR_JPY | EUR_JPY | 3.4424 | 3.4559 | ✅ | ❌ | ❌ | 28 | 3.4559 |
| 2 | `g4_i0` | 4 | tier1_EUR_JPY | EUR_JPY | 3.4424 | 3.4559 | ✅ | ❌ | ❌ | 28 | 3.4559 |
| 3 | `g4_i19` | 4 | tier1_EUR_JPY | EUR_JPY | 3.4424 | 3.4559 | ✅ | ❌ | ❌ | 28 | 3.4559 |
| 4 | `g5_i0` | 5 | tier1_EUR_JPY | EUR_JPY | 3.4424 | 3.4559 | ✅ | ❌ | ❌ | 28 | 3.4559 |
| 5 | `g5_i1` | 5 | tier1_EUR_JPY | EUR_JPY | 3.4424 | 3.4559 | ✅ | ❌ | ❌ | 28 | 3.4559 |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 2.06763933267946 |
| 2 | 2.7771100931327473 |
| 3 | 3.4423640577259804 |
| 4 | 3.4423640577259804 |
| 5 | 3.4423640577259804 |

## 分析

### analysis-claude.md

# Run 5 分析

**run_id**: `run_20260425_002233`
**generated_at**: 2026-04-25T00:22:34.000158+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 3.4558640577259805 / 閾値 1.0
- ❌ total_pnl: 4450.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 28 (許容 50〜5000)

### Best 個体

- name: `g3_i15`
- fitness (sharpe): 3.4423640577259804
- trade_count: 28
- total_pnl: 4450.0
- sharpe: 3.4558640577259805
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 3.4423640577259804
- Δfitness: 3.4423640577259804
- plateau: True

### 前回 Run との比較

- best_fitness: 2.5245932562916003 ↑ 3.4423640577259804 (Δ=0.9177708014343801)
- trade_count: 22 → 28

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

# Codex 独立分析 (skipped — observe-only stress-test mode)
stress-test 30 cycle 実行中のためスキップ。

