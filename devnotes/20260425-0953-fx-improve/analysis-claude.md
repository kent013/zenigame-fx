# Run 10 分析

**run_id**: `run_20260425_004002`
**generated_at**: 2026-04-25T00:40:13.448688+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 18.491182265575507 / 閾値 1.0
- ❌ total_pnl: 18860.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 3 (許容 50〜5000)

### Best 個体

- name: `g60_i21`
- fitness (sharpe): 18.480682265575506
- trade_count: 3
- total_pnl: 18860.0
- sharpe: 18.491182265575507
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 8.11512761939894
- 最終世代 best_fitness: 18.480682265575506
- Δfitness: 10.365554646176566
- plateau: False

### 前回 Run との比較

- best_fitness: 0 ↑ 18.480682265575506 (Δ=18.480682265575506)
- trade_count: 0 → 3

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。
