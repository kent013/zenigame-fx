# Run 16 分析

**run_id**: `run_20260425_235717`
**generated_at**: 2026-04-25T23:57:17.279108+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.3411706435446119 / 閾値 1.0
- ❌ total_pnl: 0.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 30 (許容 50〜5000)

### Best 個体

- name: `g26_i34`
- fitness (sharpe): 0.3321706435446119
- trade_count: 30
- total_pnl: 0.0
- sharpe: 0.3411706435446119
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.3321706435446119
- Δfitness: 0.3321706435446119
- plateau: True

### 前回 Run との比較

- best_fitness: 0.4655482810092501 ↓ 0.3321706435446119 (Δ=-0.1333776374646382)
- trade_count: 70 → 30

## 解釈

- 未達: sharpe, total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。
