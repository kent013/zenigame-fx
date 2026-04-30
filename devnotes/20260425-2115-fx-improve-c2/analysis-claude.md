# Run 11 分析

**run_id**: `run_20260425_113652`
**generated_at**: 2026-04-25T11:36:52.520946+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.12816221861905236 / 閾値 1.0
- ❌ total_pnl: 0.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 31 (許容 50〜5000)

### Best 個体

- name: `g60_i5`
- fitness (sharpe): 0.11916221861905237
- trade_count: 31
- total_pnl: 0.0
- sharpe: 0.12816221861905236
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.11916221861905237
- Δfitness: 0.11916221861905237
- plateau: False

### 前回 Run との比較

- best_fitness: 18.480682265575506 ↓ 0.11916221861905237 (Δ=-18.36152004695645363)
- trade_count: 3 → 31

## 解釈

- 未達: sharpe, total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。
