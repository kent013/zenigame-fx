# Run 2 分析

**run_id**: `run_20260421_091614`
**generated_at**: 2026-04-21T09:16:14.168285+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 1.3130627678387203 / 閾値 1.0
- ❌ total_pnl: 6150.000000 / 閾値 50000
- ✅ max_drawdown_pct: 3.174836121710204480970550827 / 閾値 20.0
- ❌ trade_count: 12 (許容 50〜5000)

### Best 個体

- name: `g1_i3`
- fitness (sharpe): 1.3130627678387203
- trade_count: 12
- total_pnl: 6150.000000
- sharpe: 1.3130627678387203
- max_drawdown_pct: 3.174836121710204480970550827
- win_rate: 0.5

### 収束状況

- 世代数: 4
- 初世代 best_fitness: -1.687985114054767
- 最終世代 best_fitness: 1.3130627678387203
- Δfitness: 3.0010478818934873
- plateau: True

### 前回 Run との比較

- best_fitness: 0.07608531885206603 ↑ 1.3130627678387203 (Δ=1.23697744898665427)
- trade_count: 12 → 12

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。
