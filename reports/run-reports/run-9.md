# Run 9 — run_20260425_002330

**Generated**: 2026-04-25T00:23:31.205910+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)
  - bars_stage_a: 14351
  - bars_stage_b: 14351
  - bars_holdout: 37832

## 使命判定

未達

- ❌ **sharpe**: None / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 0 (range 50〜5000)

## GA 設定

- population_size: 20
- generations: 5
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g0_i1`
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
- n_nodes: 4
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 120
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 120 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 120 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=120, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=120, mean=2.8167, median=3.0000, std=1.0327, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=120

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g0_i1` | 0 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 2 | `g0_i2` | 0 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 3 | `g0_i3` | 0 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 4 | `g0_i6` | 0 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |
| 5 | `g0_i16` | 0 | tier1_EUR_JPY | EUR_JPY | 0.0000 | 0.0000 | ❌ | ❌ | ❌ | 0 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 0.0 |
| 3 | 0.0 |
| 4 | 0.0 |
| 5 | 0.0 |

## 分析

### analysis-claude.md

# Run 9 分析

**run_id**: `run_20260425_002330`
**generated_at**: 2026-04-25T00:23:31.205910+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: None / 閾値 1.0
- ❌ total_pnl: 0.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 0 (許容 50〜5000)

### Best 個体

- name: `g0_i1`
- fitness (sharpe): 0
- trade_count: 0
- total_pnl: 0.0
- sharpe: None
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0
- Δfitness: 0
- plateau: True

### 前回 Run との比較

- best_fitness: 9.651541951434448 ↓ 0 (Δ=-9.651541951434448)
- trade_count: 1 → 0

## 解釈

- 未達: sharpe, total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。

### analysis-codex.md

# Codex 独立分析 (skipped — observe-only stress-test mode)
stress-test 30 cycle 実行中のためスキップ。

