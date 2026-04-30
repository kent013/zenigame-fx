# Run 21 分析

**run_id**: `run_20260426_183119`
**generated_at**: 2026-04-26T18:31:19.935134+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.10491949440299551 / 閾値 1.0
- ❌ total_pnl: 22440.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 72 (許容 50〜5000)

### Best 個体

- name: `g58_i70`
- fitness (sharpe): 0.39563308988865625
- trade_count: 72
- total_pnl: 22440.0
- sharpe: 0.10491949440299551
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0.005729443411041634
- 最終世代 best_fitness: 0.39563308988865625
- Δfitness: 0.389903646477614616
- plateau: True

### 前回 Run との比較

- best_fitness: 0.06848772556319638 ↑ 0.39563308988865625 (Δ=0.32714536432545987)
- trade_count: 58 → 72

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。
