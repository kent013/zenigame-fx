# Run 13 分析

**run_id**: `run_20260425_164726`
**generated_at**: 2026-04-25T16:47:26.210669+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.3293409794094013 / 閾値 1.0
- ❌ total_pnl: 36110.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 68 (許容 50〜5000)

### Best 個体

- name: `g38_i78`
- fitness (sharpe): 0.41724447954740956
- trade_count: 68
- total_pnl: 36110.0
- sharpe: 0.3293409794094013
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0.0734289631996994
- 最終世代 best_fitness: 0.41724447954740956
- Δfitness: 0.34381551634771016
- plateau: True

### 前回 Run との比較

- best_fitness: 0.2744026322560356 ↑ 0.41724447954740956 (Δ=0.14284184729137396)
- trade_count: 72 → 68

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。
