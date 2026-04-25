# Run 8 分析

**run_id**: `run_20260425_002314`
**generated_at**: 2026-04-25T00:23:14.593307+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 9.660541951434448 / 閾値 1.0
- ❌ total_pnl: 6590.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 1 (許容 50〜5000)

### Best 個体

- name: `g2_i7`
- fitness (sharpe): 9.651541951434448
- trade_count: 1
- total_pnl: 6590.0
- sharpe: 9.660541951434448
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 3.8878358054188493
- 最終世代 best_fitness: 9.651541951434448
- Δfitness: 5.7637061460155987
- plateau: True

### 前回 Run との比較

- best_fitness: 10.14573845027518 ↓ 9.651541951434448 (Δ=-0.494196498840732)
- trade_count: 2 → 1

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。
