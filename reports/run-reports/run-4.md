# Run 4 — run_20260425_002222

**Generated**: 2026-04-25T00:22:22.553675+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)
  - bars_stage_a: 14351
  - bars_stage_b: 14351
  - bars_holdout: 37832

## 使命判定

未達

- ✅ **sharpe**: 2.5425932562916 / threshold 1.0
- ❌ **total_pnl**: 2680.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 22 (range 50〜5000)

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

- name: `g4_i11`
- generation: 4
- fitness: **2.5245932562916003**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 22
- total_pnl: 2680.0
- sharpe: 2.5425932562916
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
- Stage A pass: 14
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 120 | 14 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 120 | 14 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=120, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=120, mean=3.2333, median=4.0000, std=0.9104, min=1, max=4

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
| 1 | `g4_i11` | 4 | tier1_EUR_JPY | EUR_JPY | 2.5246 | 2.5426 | ✅ | ❌ | ❌ | 22 | 2.5426 |
| 2 | `g5_i0` | 5 | tier1_EUR_JPY | EUR_JPY | 2.5246 | 2.5426 | ✅ | ❌ | ❌ | 22 | 2.5426 |
| 3 | `g5_i5` | 5 | tier1_EUR_JPY | EUR_JPY | 2.5246 | 2.5426 | ✅ | ❌ | ❌ | 22 | 2.5426 |
| 4 | `g5_i14` | 5 | tier1_EUR_JPY | EUR_JPY | 2.5246 | 2.5426 | ✅ | ❌ | ❌ | 22 | 2.5426 |
| 5 | `g5_i16` | 5 | tier1_EUR_JPY | EUR_JPY | 2.5246 | 2.5426 | ✅ | ❌ | ❌ | 22 | 2.5426 |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 1.2933460853088687 |
| 3 | 2.4931251976184035 |
| 4 | 2.5245932562916003 |
| 5 | 2.5245932562916003 |

## 分析

### analysis-claude.md

# Run 4 分析

**run_id**: `run_20260425_002222`
**generated_at**: 2026-04-25T00:22:22.553675+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 2.5425932562916 / 閾値 1.0
- ❌ total_pnl: 2680.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 22 (許容 50〜5000)

### Best 個体

- name: `g4_i11`
- fitness (sharpe): 2.5245932562916003
- trade_count: 22
- total_pnl: 2680.0
- sharpe: 2.5425932562916
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 2.5245932562916003
- Δfitness: 2.5245932562916003
- plateau: False

### 前回 Run との比較

- best_fitness: 0 ↑ 2.5245932562916003 (Δ=2.5245932562916003)
- trade_count: 0 → 22

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

# Codex 独立分析 (skipped — observe-only stress-test mode)
stress-test 30 cycle 実行中のためスキップ。

