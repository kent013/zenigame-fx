# Run 17 — run_20260426_003931

**Generated**: 2026-04-26T00:39:31.353022+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.2687807321122144 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 37 (range 50〜5000)

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

- name: `g59_i42`
- generation: 59
- fitness: **0.2507807321122144**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 37
- total_pnl: 0.0
- sharpe: 0.2687807321122144
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

- 全 archive 行数: 5856
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0, median=0.0000, std=0.0000, min=0, max=0
- n_nodes: n=5856, mean=3.6175, median=4.0000, std=0.6701, min=1, max=4

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0
- n_fold_effective (Stage A pass): n=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 0, Stage B pass = 0, failures = 0 (primary_sum = 0)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v2_feasibility`
- trade_count=0 個体比率: 3.6% (208/5856)
- best 個体 trade_count: 37
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g59_i42` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2508 | 0.2688 | ❌ | ❌ | ❌ | 37 | — |
| 2 | `g60_i0` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2508 | 0.2688 | ❌ | ❌ | ❌ | 37 | — |
| 3 | `g60_i7` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2508 | 0.2688 | ❌ | ❌ | ❌ | 37 | — |
| 4 | `g60_i73` | 60 | tier1_EUR_JPY | EUR_JPY | 0.2508 | 0.2688 | ❌ | ❌ | ❌ | 37 | — |
| 5 | `g50_i70` | 50 | tier1_EUR_JPY | EUR_JPY | 0.2499 | 0.2679 | ❌ | ❌ | ❌ | 35 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0 |
| 1 | 0.0 |
| 2 | 0.0 |
| 3 | 0.0 |
| 4 | 0.0 |
| 5 | 0.0 |
| 6 | 0.0 |
| 7 | 0.04808199378645682 |
| 8 | 0.04808199378645682 |
| 9 | 0.04808199378645682 |
| 10 | 0.04808199378645682 |
| 11 | 0.11056972973538097 |
| 12 | 0.13789017777314963 |
| 13 | 0.14081654758277154 |
| 14 | 0.14081654758277154 |
| 15 | 0.14081654758277154 |
| 16 | 0.14081654758277154 |
| 17 | 0.14081654758277154 |
| 18 | 0.16719496789067503 |
| 19 | 0.16719496789067503 |
| 20 | 0.16719496789067503 |
| 21 | 0.21467550475477162 |
| 22 | 0.21467550475477162 |
| 23 | 0.21467550475477162 |
| 24 | 0.21467550475477162 |
| 25 | 0.21467550475477162 |
| 26 | 0.21467550475477162 |
| 27 | 0.21483342211292428 |
| 28 | 0.21483342211292428 |
| 29 | 0.21483342211292428 |
| 30 | 0.21483342211292428 |
| 31 | 0.2298859236436565 |
| 32 | 0.2298859236436565 |
| 33 | 0.2298859236436565 |
| 34 | 0.2298859236436565 |
| 35 | 0.2298859236436565 |
| 36 | 0.2298859236436565 |
| 37 | 0.2298859236436565 |
| 38 | 0.2381446755058411 |
| 39 | 0.2381446755058411 |
| 40 | 0.2381446755058411 |
| 41 | 0.2381446755058411 |
| 42 | 0.2381446755058411 |
| 43 | 0.2381446755058411 |
| 44 | 0.2381446755058411 |
| 45 | 0.2381446755058411 |
| 46 | 0.2381446755058411 |
| 47 | 0.2381446755058411 |
| 48 | 0.2381446755058411 |
| 49 | 0.2381446755058411 |
| 50 | 0.24989120028516545 |
| 51 | 0.24989120028516545 |
| 52 | 0.24989120028516545 |
| 53 | 0.24989120028516545 |
| 54 | 0.24989120028516545 |
| 55 | 0.24989120028516545 |
| 56 | 0.24989120028516545 |
| 57 | 0.24989120028516545 |
| 58 | 0.24989120028516545 |
| 59 | 0.2507807321122144 |
| 60 | 0.2507807321122144 |

## 分析

### analysis-claude.md

# Run 16 分析

**run_id**: `run_20260425_235717`
**generated_at**: 2026-04-25T23:57:17.279108+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.3411706435446119 / 閾値 1.0
- ❌ total_pnl: 0.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ❌ trade_count: 30 (許容 50〜5000)

### Best 個体

- name: `g26_i34`
- fitness (sharpe): 0.3321706435446119
- trade_count: 30
- total_pnl: 0.0
- sharpe: 0.3411706435446119
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0
- 最終世代 best_fitness: 0.3321706435446119
- Δfitness: 0.3321706435446119
- plateau: True

### 前回 Run との比較

- best_fitness: 0.4655482810092501 ↓ 0.3321706435446119 (Δ=-0.1333776374646382)
- trade_count: 70 → 30

## 解釈

- 未達: sharpe, total_pnl, trade_count。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。

### analysis-codex.md

**推奨案（1件）**  
Cycle 6 は **案A: `threshold_delta_abs_max` を `0.5 -> 0.1`** を優先してください。  
理由: reset（案D）依存を避けつつ、再tightenの過補正だけを直接止められるため、最小変更で ratchet 再発リスクを下げられます。

**質問への回答**
1. ratchet即効策: **案A推奨**（B/Cは次段の微調整候補、Dは対症療法）。  
2. T031 `entry_count_min`: **50へ引き上げるべき**です。  
   これは「見栄え調整」ではなく、`live_criteria.trade_count_min=50` との整合を取る**実行可能性制約の修正**です。  
3. Cycle 6 の1施策（実行可能）  
   - 施策: `threshold_delta_abs_max=0.1`  
   - target_metric: 次Runで `A_pass_rate` を **10–30%帯**に戻す（0%脱却）  
   - falsification: `A_pass_rate=0%` または post-gate が再び急上昇（再tighten過剰）  
   - success_criterion: 連続2Runで `A_pass_rate>0` かつ gate変動が安定（急激な締め直しなし）

**全体判定**  
- Aは**制御不安定（運用バグ）**、Bは**制約不整合（設計バグ）**、Run-15で示された真因は引き続き**signal品質（median_oos_sharpe）**です。  
- まずAを止血し、その直後にBを必須整合として適用する順序が妥当です。

