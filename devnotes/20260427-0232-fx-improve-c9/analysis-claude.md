# Run 20 分析

**run_id**: `run_20260426_145502`
**generated_at**: 2026-04-26T14:55:02.637176+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: -0.18918533668417017 / 閾値 1.0
- ❌ total_pnl: -16850.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 2.0554226475279105 / 閾値 20.0
- ✅ trade_count: 58 (許容 50〜5000)

### Best 個体

- name: `g53_i76`
- fitness (sharpe): 0.06848772556319638
- trade_count: 58
- total_pnl: -16850.0
- sharpe: -0.18918533668417017
- max_drawdown_pct: 2.0554226475279105
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: -0.03565276596897986
- 最終世代 best_fitness: 0.1394470808326284
- Δfitness: 0.17509984680160826
- plateau: False

### 前回 Run との比較

- best_fitness: -0.011671197424478152 ↑ 0.06848772556319638 (Δ=0.080158922987674532)
- trade_count: 9578 → 58

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。
