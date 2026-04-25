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
