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
