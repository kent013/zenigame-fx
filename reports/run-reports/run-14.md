# Run 14 — run_20260425_180142

**Generated**: 2026-04-25T18:01:42.874671+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.14008798400220912 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 59 (range 50〜5000)

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

- name: `g52_i49`
- generation: 52
- fitness: **0.12058798400220912**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 59
- total_pnl: 0.0
- sharpe: 0.14008798400220912
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
- n_nodes: n=5856, mean=3.6199, median=4.0000, std=0.7015, min=1, max=4

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
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
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
- trade_count=0 個体比率: 10.2% (595/5856)
- best 個体 trade_count: 59
- best 個体 feasibility: ✅

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g52_i49` | 52 | tier1_EUR_JPY | EUR_JPY | 0.1206 | 0.1401 | ❌ | ❌ | ❌ | 59 | — |
| 2 | `g53_i0` | 53 | tier1_EUR_JPY | EUR_JPY | 0.1206 | 0.1401 | ❌ | ❌ | ❌ | 59 | — |
| 3 | `g54_i0` | 54 | tier1_EUR_JPY | EUR_JPY | 0.1206 | 0.1401 | ❌ | ❌ | ❌ | 59 | — |
| 4 | `g54_i37` | 54 | tier1_EUR_JPY | EUR_JPY | 0.1206 | 0.1401 | ❌ | ❌ | ❌ | 59 | — |
| 5 | `g54_i53` | 54 | tier1_EUR_JPY | EUR_JPY | 0.1206 | 0.1401 | ❌ | ❌ | ❌ | 59 | — |

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
| 7 | 0.01615499556462088 |
| 8 | 0.01615499556462088 |
| 9 | 0.01615499556462088 |
| 10 | 0.01615499556462088 |
| 11 | 0.018861133707240196 |
| 12 | 0.0394075285796114 |
| 13 | 0.0394075285796114 |
| 14 | 0.0394075285796114 |
| 15 | 0.0394075285796114 |
| 16 | 0.0394075285796114 |
| 17 | 0.0394075285796114 |
| 18 | 0.0394075285796114 |
| 19 | 0.07094614064956632 |
| 20 | 0.07094614064956632 |
| 21 | 0.07094614064956632 |
| 22 | 0.07094614064956632 |
| 23 | 0.07094614064956632 |
| 24 | 0.07094614064956632 |
| 25 | 0.07094614064956632 |
| 26 | 0.07094614064956632 |
| 27 | 0.07217479261444221 |
| 28 | 0.07217479261444221 |
| 29 | 0.12010074090952262 |
| 30 | 0.12010074090952262 |
| 31 | 0.12010074090952262 |
| 32 | 0.12010074090952262 |
| 33 | 0.12010074090952262 |
| 34 | 0.12010074090952262 |
| 35 | 0.12010074090952262 |
| 36 | 0.12010074090952262 |
| 37 | 0.12010074090952262 |
| 38 | 0.12010074090952262 |
| 39 | 0.12010074090952262 |
| 40 | 0.12010074090952262 |
| 41 | 0.12010074090952262 |
| 42 | 0.12036166438988861 |
| 43 | 0.12036166438988861 |
| 44 | 0.12036166438988861 |
| 45 | 0.12036166438988861 |
| 46 | 0.12036166438988861 |
| 47 | 0.12036166438988861 |
| 48 | 0.12036166438988861 |
| 49 | 0.12036166438988861 |
| 50 | 0.12036166438988861 |
| 51 | 0.12036166438988861 |
| 52 | 0.12058798400220912 |
| 53 | 0.12058798400220912 |
| 54 | 0.12058798400220912 |
| 55 | 0.12058798400220912 |
| 56 | 0.12058798400220912 |
| 57 | 0.12058798400220912 |
| 58 | 0.12058798400220912 |
| 59 | 0.12058798400220912 |
| 60 | 0.12058798400220912 |

## 分析

### analysis-claude.md

# Run 13 分析

**run_id**: `run_20260425_164726`
**generated_at**: 2026-04-25T16:47:26.210669+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.3293409794094013 / 閾値 1.0
- ❌ total_pnl: 36110.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 68 (許容 50〜5000)

### Best 個体

- name: `g38_i78`
- fitness (sharpe): 0.41724447954740956
- trade_count: 68
- total_pnl: 36110.0
- sharpe: 0.3293409794094013
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0.0734289631996994
- 最終世代 best_fitness: 0.41724447954740956
- Δfitness: 0.34381551634771016
- plateau: True

### 前回 Run との比較

- best_fitness: 0.2744026322560356 ↑ 0.41724447954740956 (Δ=0.14284184729137396)
- trade_count: 72 → 68

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

**観察事実**
- Stage A pass 2000 / Stage B pass 0、失敗理由は `insufficient_folds=2000 (100%)` に単峰化。
- 現行WF設定 `train=120, embargo=1, test=20` は最小141観測日を要求。
- Stage B対象期間は約127観測日で、fold数が要件未達（実質1以下）になり、構造的に全Reject。
- Run-12→13で fitness/PnL は改善しており、探索品質より先に「検証器が通らない」状態。

**解釈**
- これはモデル性能問題ではなく、**Stage B feasibility不成立**が根因。
- よって最優先は「Stage Bでfoldを作れる条件を満たすこと」。ここを直さない限り他TODOは効かない。

**推奨案（C9 falsification-first）**
- 最有力: **案C（構造対応）+ 案A（即効プロファイル）**
- 具体:
  - Stage B実行前に `max_folds` を事前計算し、`min_folds`未満なら fail-fast で理由を固定出力。
  - その上で短窓WFプロファイル（例: `train=60,test=10,embargo=1`）を「feasible時のみ」適用。
- 反証条件:
  - 短窓適用後も `insufficient_folds` が主因なら仮説棄却。
  - `insufficient_folds` 解消後に Sharpe/PnL が悪化し live基準未達なら「次のボトルネックへ移行」と判定。

**各案の禁止事項チェック**
- 案A（WF縮小）:
  - 違反リスク: 値いじり化。
  - 回避: 目的を「fold成立」に限定し、Sharpe閾値等は不変更、事前反証条件を固定。
- 案B（期間延長）:
  - 違反リスク: 見栄え改善のための期間操作。
  - 回避: end日固定、start前倒し理由を「fold成立」に限定、比較は同一評価窓で実施。
- 案C（構造解決）:
  - 禁止事項適合。仕組み不全を先に修正するため最も原則準拠。

**Critical TODO（1件）**
- `title`: T038 Stage B Feasibility Contract（insufficient_folds恒久対策）
- `target_metric`: Stage B `insufficient_folds_rate` を 100% → 0%
- `failure_mode`: 観測日不足でWF fold未成立のまま全個体Reject
- `causal_path`: dataset_days と WF(required_days, step, min_folds) の不整合 → fold不足 → Stage B全滅
- `falsification`: 事前計算で `max_folds>=min_folds` を満たす設定でも `insufficient_folds` が主因なら仮説棄却
- `success_criterion`: 次Runで Stage B pass_count > 0 かつ primary reason の首位が `insufficient_folds` でない

**全体判定**
- **CRITICAL_DRIFT**（性能ドリフトではなく、検証パイプラインの構造不成立）

