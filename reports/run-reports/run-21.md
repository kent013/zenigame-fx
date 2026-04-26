# Run 21 — run_20260426_183119

**Generated**: 2026-04-26T18:31:19.935134+00:00
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.10491949440299551 / threshold 1.0
- ❌ **total_pnl**: 22440.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 72 (range 50〜5000)

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

- name: `g58_i70`
- generation: 58
- fitness: **0.39563308988865625**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 72
- total_pnl: 22440.0
- sharpe: 0.10491949440299551
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
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2395
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2395 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2395 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=0.9956, median=1.0000, std=0.0665, min=0, max=1
- n_nodes: n=5856, mean=3.4153, median=4.0000, std=0.7479, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2395, mean=0.0000, median=0.0000, std=0.0000, min=0.0000, max=0.0000
- dsr: n=0
- n_fold_effective (Stage A pass): n=2395, mean=0, median=0, std=0.0000, min=0, max=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 2395, Stage B pass = 0, failures = 2395 (primary_sum = 2395)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2395 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2395 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 2395 |
| `positive_fold_ratio<min` | 2395 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_stage_c_feasibility`
- trade_count=0 個体比率: 9.4% (548/5856)
- best 個体 trade_count: 72
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=2395, stage_a_only=3461
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3461, mean=-1054820.3294, median=0.0000, std=3438004.4345, min=-19392050.0000, max=37790.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=2913): n=2913, mean=-1253255.4617, median=-3020.0000, std=3714130.5172, min=-19392050.0000, max=37790.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2395): n=2395, mean=27478.5428, median=29760.0000, std=8219.6803, min=8480.0000, max=44510.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3_stage_c_feasibility, T045)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g58_i70` | 58 | tier1_EUR_JPY | EUR_JPY | 0.3956 | 0.4091 | ✅ | ❌ | ❌ | 72 | — |
| 2 | `g59_i0` | 59 | tier1_EUR_JPY | EUR_JPY | 0.3956 | 0.4091 | ✅ | ❌ | ❌ | 72 | — |
| 3 | `g60_i0` | 60 | tier1_EUR_JPY | EUR_JPY | 0.3956 | 0.4091 | ✅ | ❌ | ❌ | 72 | — |
| 4 | `g60_i27` | 60 | tier1_EUR_JPY | EUR_JPY | 0.3905 | 0.4040 | ✅ | ❌ | ❌ | 80 | — |
| 5 | `g45_i51` | 45 | tier1_EUR_JPY | EUR_JPY | 0.3869 | 0.4004 | ✅ | ❌ | ❌ | 74 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.005729443411041634 |
| 1 | 0.005729443411041634 |
| 2 | 0.027457064556461647 |
| 3 | 0.027457064556461647 |
| 4 | 0.027457064556461647 |
| 5 | 0.0797425517638014 |
| 6 | 0.08090970752832462 |
| 7 | 0.10235993003085804 |
| 8 | 0.10235993003085804 |
| 9 | 0.10235993003085804 |
| 10 | 0.11340832510421066 |
| 11 | 0.14515871823868198 |
| 12 | 0.1516161801384155 |
| 13 | 0.1516161801384155 |
| 14 | 0.1516161801384155 |
| 15 | 0.17372411792141138 |
| 16 | 0.17372411792141138 |
| 17 | 0.17372411792141138 |
| 18 | 0.17372411792141138 |
| 19 | 0.2195490160543374 |
| 20 | 0.2195490160543374 |
| 21 | 0.2195490160543374 |
| 22 | 0.26365303162768555 |
| 23 | 0.26365303162768555 |
| 24 | 0.26365303162768555 |
| 25 | 0.26365303162768555 |
| 26 | 0.26365303162768555 |
| 27 | 0.26365303162768555 |
| 28 | 0.26365303162768555 |
| 29 | 0.26365303162768555 |
| 30 | 0.26365303162768555 |
| 31 | 0.26365303162768555 |
| 32 | 0.30334925688368153 |
| 33 | 0.30334925688368153 |
| 34 | 0.30334925688368153 |
| 35 | 0.30334925688368153 |
| 36 | 0.32681874668741223 |
| 37 | 0.32681874668741223 |
| 38 | 0.329506438768353 |
| 39 | 0.329506438768353 |
| 40 | 0.329506438768353 |
| 41 | 0.3687722454400536 |
| 42 | 0.3687722454400536 |
| 43 | 0.3687722454400536 |
| 44 | 0.3687722454400536 |
| 45 | 0.38688338471122874 |
| 46 | 0.38688338471122874 |
| 47 | 0.38688338471122874 |
| 48 | 0.38688338471122874 |
| 49 | 0.38688338471122874 |
| 50 | 0.38688338471122874 |
| 51 | 0.38688338471122874 |
| 52 | 0.38688338471122874 |
| 53 | 0.38688338471122874 |
| 54 | 0.38688338471122874 |
| 55 | 0.38688338471122874 |
| 56 | 0.38688338471122874 |
| 57 | 0.38688338471122874 |
| 58 | 0.39563308988865625 |
| 59 | 0.39563308988865625 |
| 60 | 0.39563308988865625 |

## 分析

### analysis-claude.md

# Run 20 分析

**run_id**: `run_20260426_145502`
**generated_at**: 2026-04-26T14:55:02.637176+00:00

## 観察事実

### 使命判定 (live_criteria)

- ❌ sharpe: -0.18918533668417017 / 閾値 1.0
- ❌ total_pnl: -16850.0 / 閾値 50000.0
- ✅ max_drawdown_pct: 2.0554226475279105 / 閾値 20.0
- ✅ trade_count: 58 (許容 50〜5000)

### Best 個体

- name: `g53_i76`
- fitness (sharpe): 0.06848772556319638
- trade_count: 58
- total_pnl: -16850.0
- sharpe: -0.18918533668417017
- max_drawdown_pct: 2.0554226475279105
- win_rate: None

### 収束状況

- 世代数: 61
- 初世代 best_fitness: -0.03565276596897986
- 最終世代 best_fitness: 0.1394470808326284
- Δfitness: 0.17509984680160826
- plateau: False

### 前回 Run との比較

- best_fitness: -0.011671197424478152 ↑ 0.06848772556319638 (Δ=0.080158922987674532)
- trade_count: 9578 → 58

## 解釈

- 未達: sharpe, total_pnl。これらが次サイクルの改善ターゲット。
- 前回より改善。方向性は正しい可能性。

### analysis-codex.md

**観察事実**
- Stage B は 834 個体通過し、`trade_count` と `max_dd` は満たせている（取引実行フェーズには到達）。
- しかし Stage C は 0 通過、best 個体でも `sharpe=-0.19`・`total_pnl=-16850`。
- `positive_fold_ratio_effective` の中央値は 0.78 と高く、fold 単位の勝率は悪くない一方で、収益量/分散調整後成績が負けている。

**解釈（C9 falsification-first）**
- まず反証すべき仮説: 「Stage C不通過の主因は閾値が厳しすぎるだけ」  
  - 反証根拠: best 個体自体が Sharpe/PnL 負で、閾値緩和だけでは本質解決しない可能性が高い。
- より有力な仮説: 「GAの最適化目標が Stage C 要件（Sharpe/PnL正）と構造的にずれている」  
  - `mission_score` が soft 合算のため、負PnL個体が生き残れる。

**推奨施策（1件）**
- **fitness設計改善**: GA を「可行性優先の2段階最適化」に変更する。  
  - 第1段: `total_pnl>0` かつ `median_oos_sharpe>0` を満たす個体を優先（満たさない個体は強いペナルティ）。  
  - 第2段: 可行性を満たした母集団内で mission_score 4軸を最適化。  
- これが最も影響力が高い方向です。理由は、現状ボトルネックが signal の有無ではなく「選抜圧の向き」に見えるためです。

**新規TODO設計（提案）**
- `target_metric`: Stage C pass count（0→>0）、B-pass内の `PnL>0 & Sharpe>0` 個体比率、best `total_pnl`、best `median_oos_sharpe`  
- `failure_mode`: soft合算fitnessにより、負PnL/負Sharpe個体が上位選抜され、Stage C可行領域へ収束しない  
- `causal_path`: fitnessを可行性優先へ変更 → 世代ごとの親選抜が正PnL/正Sharpe側へ偏る → Stage C通過候補密度が上がる  
- `falsification`: 変更後2-3 runで「B-pass内の正PnL正Sharpe比率」が有意に増えない、または Stage C pass が依然0なら仮説棄却（signal品質側へピボット）  
- `success_criterion`: 連続2 runで Stage C pass > 0、かつ best 個体が `total_pnl>0`・`median_oos_sharpe>0` を同時達成

**全体判定**
- Stage B突破は完了、現ボトルネックは **探索空間不足より選抜目的のミスマッチ** である可能性が高い。次の1手は fitness の構造修正が妥当です。

