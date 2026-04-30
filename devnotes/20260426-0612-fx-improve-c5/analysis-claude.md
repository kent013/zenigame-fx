# Run 15 分析

**run_id**: `run_20260425_185201`
**generated_at**: 2026-04-25T18:52:01.296687+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.06863702995285534 / 閾値 1.0
- ❌ total_pnl: 8660.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 70 (許容 50〜5000)

### Best 個体

- name: `g49_i64`
- fitness (sharpe): 0.4655482810092501
- trade_count: 70
- total_pnl: 8660.0
- sharpe: 0.06863702995285534
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.4655482810092501
- Δfitness: 0.4655482810092501
- plateau: True

### 前回 Run との比較

- best_fitness: 0.12058798400220912 ↑ 0.4655482810092501 (Δ=0.34496029700704098)
- trade_count: 59 → 70

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。
