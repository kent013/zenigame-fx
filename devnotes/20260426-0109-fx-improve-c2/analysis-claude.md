# Run 12 分析

**run_id**: `run_20260425_145811`
**generated_at**: 2026-04-25T14:58:11.122929+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.05214504993538521 / 閾値 1.0
- ❌ total_pnl: 7610.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 72 (許容 50〜5000)

### Best 個体

- name: `g58_i71`
- fitness (sharpe): 0.2744026322560356
- trade_count: 72
- total_pnl: 7610.0
- sharpe: 0.05214504993538521
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.2744026322560356
- Δfitness: 0.2744026322560356
- plateau: True

### 前回 Run との比較

- best_fitness: 0.11916221861905237 ↑ 0.2744026322560356 (Δ=0.15524041363698323)
- trade_count: 31 → 72

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。
