# Run 7 分析

**run_id**: `run_20260425_002300`
**generated_at**: 2026-04-25T00:23:01.021254+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 10.165238450275181 / 閾値 1.0
- ❌ total_pnl: 4580.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 2 (許容 50〜5000)

### Best 個体

- name: `g4_i7`
- fitness (sharpe): 10.14573845027518
- trade_count: 2
- total_pnl: 4580.0
- sharpe: 10.165238450275181
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 3.430835130396937
- 最終世代 best_fitness: 10.14573845027518
- Δfitness: 6.714903319878243
- plateau: False

### 前回 Run との比較

- best_fitness: 9.412688950584354 ↑ 10.14573845027518 (Δ=0.733049499690826)
- trade_count: 2 → 2

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。
