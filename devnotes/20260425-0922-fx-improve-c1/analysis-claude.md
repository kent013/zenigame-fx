# Run 4 分析

**run_id**: `run_20260425_002222`
**generated_at**: 2026-04-25T00:22:22.553675+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 2.5425932562916 / 閾値 1.0
- ❌ total_pnl: 2680.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 22 (許容 50〜5000)

### Best 個体

- name: `g4_i11`
- fitness (sharpe): 2.5245932562916003
- trade_count: 22
- total_pnl: 2680.0
- sharpe: 2.5425932562916
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 2.5245932562916003
- Δfitness: 2.5245932562916003
- plateau: False

### 前回 Run との比較

- best_fitness: 0 ↑ 2.5245932562916003 (Δ=2.5245932562916003)
- trade_count: 0 → 22

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。
