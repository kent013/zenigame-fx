# Run 22 分析

**run_id**: `run_20260426_204204`
**generated_at**: 2026-04-26T20:42:04.236776+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.14488130397605056 / 閾値 1.0
- ❌ total_pnl: 17580.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 68 (許容 50〜5000)

### Best 個体

- name: `g44_i92`
- fitness (sharpe): 0.33656668015050756
- trade_count: 68
- total_pnl: 17580.0
- sharpe: 0.14488130397605056
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0.0004721925489815041
- 最終世代 best_fitness: 0.33656668015050756
- Δfitness: 0.3360944876015260559
- plateau: True

### 前回 Run との比較

- best_fitness: 0.39563308988865625 ↓ 0.33656668015050756 (Δ=-0.05906640973814869)
- trade_count: 72 → 68

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。
