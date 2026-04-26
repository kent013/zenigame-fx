# Run 22 — run_20260426_204204

**Generated**: 2026-04-26T20:42:04.236776+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.14488130397605056 / threshold 1.0
- ❌ **total_pnl**: 17580.0 / threshold 50000.0
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

- name: `g44_i92`
- generation: 44
- fitness: **0.33656668015050756**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 68
- total_pnl: 17580.0
- sharpe: 0.14488130397605056
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1758
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1758 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1758 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9964, median=1.0000, std=0.0598, min=0, max=1
- n_nodes: n=5856, mean=3.3263, median=4.0000, std=0.8771, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1758, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1758, mean=0, median=0.0000, std=0.0000, min=0, max=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 1758, Stage B pass = 0, failures = 1758 (primary_sum = 1758)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1758 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1758 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1758 |
| `positive_fold_ratio<min` | 1758 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 7.8% (455/5856)
- best 個体 trade_count: 68
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1758, stage_a_only=4098
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4098, mean=-1274098.7433, median=-1240.0000, std=3590000.9573, min=-18811880.0000, max=47700.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3643): n=3643, mean=-1433229.9341, median=-6910.0000, std=3777528.5547, min=-18811880.0000, max=47700.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1758): n=1758, mean=17366.7804, median=18990.0000, std=2332.4211, min=6860.0000, max=47680.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g44_i92` | 44 | tier1_EUR_JPY | EUR_JPY | 0.3366 | 0.3561 | ✅ | ❌ | ❌ | 68 | — |
| 2 | `g45_i0` | 45 | tier1_EUR_JPY | EUR_JPY | 0.3366 | 0.3561 | ✅ | ❌ | ❌ | 68 | — |
| 3 | `g46_i0` | 46 | tier1_EUR_JPY | EUR_JPY | 0.3366 | 0.3561 | ✅ | ❌ | ❌ | 68 | — |
| 4 | `g46_i79` | 46 | tier1_EUR_JPY | EUR_JPY | 0.3366 | 0.3561 | ✅ | ❌ | ❌ | 68 | — |
| 5 | `g47_i0` | 47 | tier1_EUR_JPY | EUR_JPY | 0.3366 | 0.3561 | ✅ | ❌ | ❌ | 68 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.0004721925489815041 |
| 1 | 0.0004721925489815041 |
| 2 | 0.0004721925489815041 |
| 3 | 0.060980380093572206 |
| 4 | 0.060980380093572206 |
| 5 | 0.060980380093572206 |
| 6 | 0.11188906690796287 |
| 7 | 0.11188906690796287 |
| 8 | 0.1404270043777054 |
| 9 | 0.22908764047487912 |
| 10 | 0.22908764047487912 |
| 11 | 0.22908764047487912 |
| 12 | 0.22908764047487912 |
| 13 | 0.24704441892820764 |
| 14 | 0.24704441892820764 |
| 15 | 0.24704441892820764 |
| 16 | 0.24704441892820764 |
| 17 | 0.2592138230423835 |
| 18 | 0.2592138230423835 |
| 19 | 0.2592138230423835 |
| 20 | 0.2592138230423835 |
| 21 | 0.2670105344380467 |
| 22 | 0.2670105344380467 |
| 23 | 0.2670105344380467 |
| 24 | 0.2670105344380467 |
| 25 | 0.2670105344380467 |
| 26 | 0.2670105344380467 |
| 27 | 0.2670105344380467 |
| 28 | 0.2670105344380467 |
| 29 | 0.3312115834142065 |
| 30 | 0.3312115834142065 |
| 31 | 0.3312115834142065 |
| 32 | 0.33422783239668324 |
| 33 | 0.33422783239668324 |
| 34 | 0.33422783239668324 |
| 35 | 0.33422783239668324 |
| 36 | 0.33422783239668324 |
| 37 | 0.33422783239668324 |
| 38 | 0.33422783239668324 |
| 39 | 0.33422783239668324 |
| 40 | 0.33422783239668324 |
| 41 | 0.33422783239668324 |
| 42 | 0.33422783239668324 |
| 43 | 0.33422783239668324 |
| 44 | 0.33656668015050756 |
| 45 | 0.33656668015050756 |
| 46 | 0.33656668015050756 |
| 47 | 0.33656668015050756 |
| 48 | 0.33656668015050756 |
| 49 | 0.33656668015050756 |
| 50 | 0.33656668015050756 |
| 51 | 0.33656668015050756 |
| 52 | 0.33656668015050756 |
| 53 | 0.33656668015050756 |
| 54 | 0.33656668015050756 |
| 55 | 0.33656668015050756 |
| 56 | 0.33656668015050756 |
| 57 | 0.33656668015050756 |
| 58 | 0.33656668015050756 |
| 59 | 0.33656668015050756 |
| 60 | 0.33656668015050756 |

## 分析

### analysis-claude.md

# Run 21 分析

**run_id**: `run_20260426_183119`
**generated_at**: 2026-04-26T18:31:19.935134+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: 0.10491949440299551 / 閾値 1.0
- ❌ total_pnl: 22440.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 0.0 / 閾値 20.0
- ✅ trade_count: 72 (許容 50〜5000)

### Best 個体

- name: `g58_i70`
- fitness (sharpe): 0.39563308988865625
- trade_count: 72
- total_pnl: 22440.0
- sharpe: 0.10491949440299551
- max_drawdown_pct: 0.0
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: 0.005729443411041634
- 最終世代 best_fitness: 0.39563308988865625
- Δfitness: 0.389903646477614616
- plateau: True

### 前回 Run との比較

- best_fitness: 0.06848772556319638 ↑ 0.39563308988865625 (Δ=0.32714536432545987)
- trade_count: 58 → 72

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

**観察事実**
- Run-20→Run-21で `stage_a_threshold` は **0.0→0.0778** に上昇（H2要因は実在）。
- ただし Stage A pass は 2750→2395（-12.9%）なのに、Stage B pass は 834→0（-100%）。
- Run-21 は Stage A通過2395件すべてで primary reason が `median_oos_sharpe<min`、かつ `n_fold_effective` が全件0。
- `selection_score_schema` は Run-20=`v2_feasibility`、Run-21=`v3_stage_c_feasibility`（T045）。

**解釈（C9: 反証先行）**
- H3（randomness）: **反証**。Run-20のB通過率30.3%が維持ならRun-21でB=0は統計的にほぼ起こりえない。
- H2（gate厳格化）: **単独真因は反証**。A通過減は軽微で、B全滅を説明できない。
- H1（T045選抜とWF指標の乖離）: **最有力**。v3で「単期間PnL/Sharpe正」に寄る一方、Stage BのWF `median_oos_sharpe` を直接最適化していないため、fold単位で崩れる個体群に収束した可能性が高い。

**推奨施策（1件）**
- T045を**撤回せず修正**し、`selection_score` の先頭側に Stage B整合を入れる。  
  具体: `stage_c_feasible` より前に `stage_b_pass` と `wf_shortfall`（`median_oos_sharpe`・`positive_fold_ratio`の不足量）を置く。  
  目的: 「PnL/Sharpe正」改善を維持しつつ、B=0退行を構造的に防ぐ。

**全体判定**
- **判定: H1優勢（H2は副次、H3は棄却）。T045は全撤回でなく“B整合付きv3.1”へ後退修正が妥当。**

