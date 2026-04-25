# Run 1 — run_20260421_090442

**Generated**: 2026-04-21T09:04:42.269019+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)

## 使命判定

未達

- ❌ **sharpe**: 0.07608531885206603 / threshold 1.0
- ❌ **total_pnl**: 50.000000 / threshold 50000
- ✅ **max_drawdown_pct**: 3.200795033011581112062264467 / threshold 20.0
- ❌ **trade_count**: 12 (range 50〜5000)

## GA 設定

- population_size: 12
- generations: 3
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 42

## Best 個体

- name: `g0_i7`
- fitness: **0.07608531885206603**
- trade_count: 12
- total_pnl: 50.000000
- win_rate: 0.4166666666666666666666666667
- profit_factor: 1.001951600312256049960967994
- sharpe: 0.07608531885206603
- sortino: 0.07498351162289076
- calmar: 0.04769364001807487694034760943
- max_drawdown_pct: 3.200795033011581112062264467
- final_equity: 1000050.000000

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07608531885206603 |
| 1 | 0.07608531885206603 |
| 2 | 0.07608531885206603 |
| 3 | 0.07608531885206603 |

## 分析

# Run 1 分析

**run_id**: `run_20260421_090442`
**generated_at**: 2026-04-21T09:04:42.269019+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.07608531885206603 / 閾値 1.0
- ❌ total_pnl: 50.000000 / 閾値 50000
- ✅ max_drawdown_pct: 3.200795033011581112062264467 / 閾値 20.0
- ❌ trade_count: 12 (許容 50〜5000)

### Best 個体

- name: `g0_i7`
- fitness (sharpe): 0.07608531885206603
- trade_count: 12
- total_pnl: 50.000000
- sharpe: 0.07608531885206603
- max_drawdown_pct: 3.200795033011581112062264467
- win_rate: 0.4166666666666666666666666667

### 収束状況

- 世代数: 4
- 初世代 best_fitness: 0.07608531885206603
- 最終世代 best_fitness: 0.07608531885206603
- Δfitness: 0E-17
- plateau: True

### 前回 Run との比較

- 前回 Run なし — 初回サイクル

## 解釈

- 未達: sharpe, total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。

