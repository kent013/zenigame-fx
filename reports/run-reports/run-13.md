# Run 13 — run_20260425_164726

**Generated**: 2026-04-25T16:47:26.210669+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.3293409794094013 / threshold 1.0
- ❌ **total_pnl**: 36110.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 68 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g38_i78`
- generation: 38
- fitness: **0.41724447954740956**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 68
- total_pnl: 36110.0
- sharpe: 0.3293409794094013
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 0

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2000
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2000 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2000 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=3.1064, median=3.0000, std=0.6977, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2000, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2000, mean=0, median=0.0000, std=0.0000, min=0, max=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 2000, Stage B pass = 0, failures = 2000 (primary_sum = 2000)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 2000 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 2000 |
| `all_folds_unavailable` | 2000 |
| `stage_b_window_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 4.6% (272/5856)
- best 個体 trade_count: 68
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g38_i78` | 38 | tier1_EUR_JPY | EUR_JPY | 0.4172 | 0.4307 | ✅ | ❌ | ❌ | 68 | — |
| 2 | `g39_i0` | 39 | tier1_EUR_JPY | EUR_JPY | 0.4172 | 0.4307 | ✅ | ❌ | ❌ | 68 | — |
| 3 | `g39_i21` | 39 | tier1_EUR_JPY | EUR_JPY | 0.4172 | 0.4307 | ✅ | ❌ | ❌ | 68 | — |
| 4 | `g39_i90` | 39 | tier1_EUR_JPY | EUR_JPY | 0.4172 | 0.4307 | ✅ | ❌ | ❌ | 68 | — |
| 5 | `g40_i0` | 40 | tier1_EUR_JPY | EUR_JPY | 0.4172 | 0.4307 | ✅ | ❌ | ❌ | 68 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0734289631996994 |
| 1 | 0.0734289631996994 |
| 2 | 0.14616799397342378 |
| 3 | 0.1643510218967289 |
| 4 | 0.1643510218967289 |
| 5 | 0.1643510218967289 |
| 6 | 0.2528461531553011 |
| 7 | 0.2789189782987802 |
| 8 | 0.2789189782987802 |
| 9 | 0.3191815085095896 |
| 10 | 0.3191815085095896 |
| 11 | 0.3191815085095896 |
| 12 | 0.3468364811410325 |
| 13 | 0.3583702997277969 |
| 14 | 0.3583702997277969 |
| 15 | 0.41320047765073786 |
| 16 | 0.41320047765073786 |
| 17 | 0.41320047765073786 |
| 18 | 0.41320047765073786 |
| 19 | 0.41320047765073786 |
| 20 | 0.41320047765073786 |
| 21 | 0.41320047765073786 |
| 22 | 0.41320047765073786 |
| 23 | 0.41320047765073786 |
| 24 | 0.41320047765073786 |
| 25 | 0.41320047765073786 |
| 26 | 0.41320047765073786 |
| 27 | 0.41320047765073786 |
| 28 | 0.41320047765073786 |
| 29 | 0.41320047765073786 |
| 30 | 0.41320047765073786 |
| 31 | 0.41320047765073786 |
| 32 | 0.41320047765073786 |
| 33 | 0.41320047765073786 |
| 34 | 0.41320047765073786 |
| 35 | 0.41320047765073786 |
| 36 | 0.41320047765073786 |
| 37 | 0.41320047765073786 |
| 38 | 0.41724447954740956 |
| 39 | 0.41724447954740956 |
| 40 | 0.41724447954740956 |
| 41 | 0.41724447954740956 |
| 42 | 0.41724447954740956 |
| 43 | 0.41724447954740956 |
| 44 | 0.41724447954740956 |
| 45 | 0.41724447954740956 |
| 46 | 0.41724447954740956 |
| 47 | 0.41724447954740956 |
| 48 | 0.41724447954740956 |
| 49 | 0.41724447954740956 |
| 50 | 0.41724447954740956 |
| 51 | 0.41724447954740956 |
| 52 | 0.41724447954740956 |
| 53 | 0.41724447954740956 |
| 54 | 0.41724447954740956 |
| 55 | 0.41724447954740956 |
| 56 | 0.41724447954740956 |
| 57 | 0.41724447954740956 |
| 58 | 0.41724447954740956 |
| 59 | 0.41724447954740956 |
| 60 | 0.41724447954740956 |

## 分析

### analysis-claude.md

# Run 12 分析

**run_id**: `run_20260425_145811`
**generated_at**: 2026-04-25T14:58:11.122929+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.05214504993538521 / 閾値 1.0
- ❌ total_pnl: 7610.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 72 (許容 50〜5000)

### Best 個体

- name: `g58_i71`
- fitness (sharpe): 0.2744026322560356
- trade_count: 72
- total_pnl: 7610.0
- sharpe: 0.05214504993538521
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.2744026322560356
- Δfitness: 0.2744026322560356
- plateau: True

### 前回 Run との比較

- best_fitness: 0.11916221861905237 ↑ 0.2744026322560356 (Δ=0.15524041363698323)
- trade_count: 31 → 72

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

**観察事実 (Facts)**  
- Run-12 では `feasible=5567/5856 (95%)` で、T031 により no-trade 個体は実質的に抑制された。  
- それでも `Stage B pass=0/5856`（60世代超で全滅継続）。  
- Best 個体は `trade_count=72` を満たす一方、`sharpe=0.052 (<1.0)` と `total_pnl=7,610 (<50,000)` で B 不通過。  
- Run-10→11→12 で trade_count は増加（3→31→72）したが、B pass は一貫して 0。  
- `max_dd=0%` は異常に強く、評価系の整合性疑義を示すシグナル。  

**解釈 (C6 分離 / C9 falsification-first)**  
- 仮説H1: **評価系の不整合**（GA最適化指標と Stage B 判定指標のズレ）で、探索が B 合格方向へ勾配を持てていない。  
  - 反証: 同一個体・同一区間で「fitness計算」と「Stage B 判定」の Sharpe/PnL/コスト内訳を完全突合し、差分ゼロなら棄却。  
- 仮説H2: **PnL/コスト計上の欠落・時点ズレ**で Sharpe/PnL が過小（または歪み）評価されている。  
  - 反証: 約定イベント単位の ledger 再計算で最終PnL/日次リターンが一致すれば棄却。  
- 仮説H3: **戦略エッジ不足そのもの**（実装バグではなく探索空間問題）。  
  - 反証: H1/H2 を潰した後も B=0 が継続するなら採択。  

**推奨 TODO 1件（Critical）**  
- **`T032 signal-eval-consistency-fix`** を cycle 2 の最優先で実装。  

- `target_metric`: 「同一個体の fitness 側と Stage B 側で `trade_count / total_pnl / sharpe / max_dd` 差分ゼロ（許容誤差1e-9）」  
- `failure_mode`: 評価不一致により、GAが“B不合格になる方向”を最適化してしまう（B全滅固定点）。  
- `causal_path`: 評価式/時点/コスト差異 -> 誤勾配 -> 世代進化がB閾値へ収束しない -> B=0継続。  
- `falsification`: run-12 の best + 上位N個体で二系統評価を突合。差分ゼロなら H1棄却し、次点で T033 へ。  
- `success_criterion`: 次Runで  
  1. 評価差分ゼロをCIで常時保証  
  2. Stage B pass が **0から正**（最低1以上）  
  3. reason_codes で主要失敗理由が単峰化し、改善ループ可能になる。  

**全体判定**  
- **CRITICAL_DRIFT**（T031で no-trade は解消したが、B全滅が構造的に固定化しているため）

