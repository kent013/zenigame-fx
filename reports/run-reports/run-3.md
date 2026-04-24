# Run 3 — run_20260423_195917

**Generated**: 2026-04-23T19:59:17.899088+00:00
**Dataset**: EUR_JPY `2026-03-15T00:00:00+00:00` → `2026-03-22T00:00:00+00:00` (bars=7166)
  - bars_stage_a: 7166
  - bars_stage_b: 7166
  - bars_holdout: 30666

## 使命判定

未達

- ❌ **sharpe**: None / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 0 (range 50〜5000)

## GA 設定

- population_size: 4
- generations: 2
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 42

## Best 個体

- name: `g0_i3`
- generation: 0
- fitness: **0**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 0
- total_pnl: 0.0
- sharpe: —
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 12
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 12 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 12 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=12, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=12, mean=3.2500, median=3.0000, std=0.5951, min=2, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=12

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g0_i3` | 0 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 2 | `g1_i0` | 1 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 3 | `g1_i2` | 1 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 4 | `g2_i0` | 2 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 5 | `g2_i1` | 2 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 0.0 |

