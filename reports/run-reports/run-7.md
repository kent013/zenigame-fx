# Run 7 — run_20260425_002300

**Generated**: 2026-04-25T00:23:01.021254+00:00
**Dataset**: EUR_JPY `2026-03-01T00:00:00+00:00` → `2026-03-15T00:00:00+00:00` (bars=14351)
  - bars_stage_a: 14351
  - bars_stage_b: 14351
  - bars_holdout: 37832

## 使命判定

未達

- ✅ **sharpe**: 10.165238450275181 / threshold 1.0
- ❌ **total_pnl**: 4580.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 2 (range 50〜5000)

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

- name: `g4_i7`
- generation: 4
- fitness: **10.14573845027518**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 2
- total_pnl: 4580.0
- sharpe: 10.165238450275181
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
- Stage A pass: 48
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 120 | 48 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 120 | 48 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=120, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=120, mean=2.9333, median=3.0000, std=0.8340, min=1, max=4

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
| 1 | `g4_i7` | 4 | tier1_EUR_JPY | EUR_JPY | 10.1457 | 10.1652 | ✅ | ❌ | ❌ | 2 | 10.1652 |
| 2 | `g5_i0` | 5 | tier1_EUR_JPY | EUR_JPY | 10.1457 | 10.1652 | ✅ | ❌ | ❌ | 2 | 10.1652 |
| 3 | `g3_i13` | 3 | tier1_EUR_JPY | EUR_JPY | 9.0858 | 9.0993 | ✅ | ❌ | ❌ | 2 | 9.0993 |
| 4 | `g4_i0` | 4 | tier1_EUR_JPY | EUR_JPY | 9.0858 | 9.0993 | ✅ | ❌ | ❌ | 2 | 9.0993 |
| 5 | `g5_i1` | 5 | tier1_EUR_JPY | EUR_JPY | 9.0858 | 9.0993 | ✅ | ❌ | ❌ | 2 | 9.0993 |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 3.430835130396937 |
| 1 | 3.430835130396937 |
| 2 | 4.273669500757904 |
| 3 | 9.08582000521702 |
| 4 | 10.14573845027518 |
| 5 | 10.14573845027518 |

## 分析

### analysis-claude.md

# Run 7 分析

**run_id**: `run_20260425_002300`
**generated_at**: 2026-04-25T00:23:01.021254+00:00

## 観察事実

### 使命判定 (live_criteria)

- ✅ sharpe: 10.165238450275181 / 閾値 1.0
- ❌ total_pnl: 4580.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 2 (許容 50〜5000)

### Best 個体

- name: `g4_i7`
- fitness (sharpe): 10.14573845027518
- trade_count: 2
- total_pnl: 4580.0
- sharpe: 10.165238450275181
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 6
- 初世代 best_fitness: 3.430835130396937
- 最終世代 best_fitness: 10.14573845027518
- Δfitness: 6.714903319878243
- plateau: False

### 前回 Run との比較

- best_fitness: 9.412688950584354 ↑ 10.14573845027518 (Δ=0.733049499690826)
- trade_count: 2 → 2

## 解釈

- 未達: total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

# Codex 独立分析 (skipped — observe-only stress-test mode)
stress-test 30 cycle 実行中のためスキップ。

