# Run 2 — run_20260421_091614

**Generated**: 2026-04-21T09:16:14.168285+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)

## 使命判定

未達

- ✅ **sharpe**: 1.3130627678387203 / threshold 1.0
- ❌ **total_pnl**: 6150.000000 / threshold 50000
- ✅ **max_drawdown_pct**: 3.174836121710204480970550827 / threshold 20.0
- ❌ **trade_count**: 12 (range 50〜5000)

## GA 設定

- population_size: 12
- generations: 3
- mutation_rate: 0.35
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g1_i3`
- fitness: **1.3130627678387203**
- trade_count: 12
- total_pnl: 6150.000000
- win_rate: 0.5
- profit_factor: 1.312658871377732587697000508
- sharpe: 1.3130627678387203
- sortino: 1.2819575657427764
- calmar: 5.914283417326507022926480027
- max_drawdown_pct: 3.174836121710204480970550827
- final_equity: 1006150.000000

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -1.687985114054767 |
| 1 | 1.3130627678387203 |
| 2 | 1.3130627678387203 |
| 3 | 1.3130627678387203 |

## 分析

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

