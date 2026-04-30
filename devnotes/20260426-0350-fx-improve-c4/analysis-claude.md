# Run 14 分析

**run_id**: `run_20260425_180142`
**generated_at**: 2026-04-25T18:01:42.874671+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.14008798400220912 / 閾値 1.0
- ❌ total_pnl: 0.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 59 (許容 50〜5000)

### Best 個体

- name: `g52_i49`
- fitness (sharpe): 0.12058798400220912
- trade_count: 59
- total_pnl: 0.0
- sharpe: 0.14008798400220912
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.12058798400220912
- Δfitness: 0.12058798400220912
- plateau: True

### 前回 Run との比較

- best_fitness: 0.41724447954740956 ↓ 0.12058798400220912 (Δ=-0.29665649554520044)
- trade_count: 68 → 59

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。
