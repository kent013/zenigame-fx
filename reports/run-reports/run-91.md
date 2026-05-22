# Run 91 — run_20260522_163241

**Generated**: 2026-05-22T16:32:42.097906+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: -2.573391403820326 / threshold 1.0
- ❌ **total_pnl**: -1000150.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 3467 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 0 (= Stage C 単独通過数)
- **mission_candidate_count**: 0 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 48
- generations: 20
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g11_i9`
- generation: 11
- fitness: **-0.026219602528901646**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 3467
- total_pnl: -1000150.0
- sharpe: -0.021325748338996624
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 1008
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 1008 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 1008 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=1008, mean=1.3304, median=1.0000, std=0.4703, min=1, max=2
- n_nodes: n=1008, mean=2.5585, median=2.0000, std=1.6068, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

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
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 0 |
| `median_oos_total_pnl<min` | 0 |
| `sum_oos_total_pnl<min` | 0 |
| `n_fold_effective_below_profit_safe_min` | 0 |
| `oos_total_pnl_unavailable` | 0 |
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
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 0 |
| `median_oos_total_pnl<min` | 0 |
| `sum_oos_total_pnl<min` | 0 |
| `n_fold_effective_below_profit_safe_min` | 0 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=0, None=1008

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.1% (21/1008)
- best 個体 trade_count: 3467
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 1008
- metric_stage 分布: stage_a_only=1008
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=1008, mean=-878909.6329, median=-1000150.0000, std=308750.0778, min=-1004630.0000, max=2330.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=987): n=987, mean=-897609.8379, median=-1000150.0000, std=283847.4033, min=-1004630.0000, max=2330.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体: 0 件 (比較対照なし)

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g11_i9` | 11 | tier1_EUR_JPY | EUR_JPY | -0.0262 | -0.0213 | ❌ | ❌ | ❌ | 3467 | — |
| 2 | `g12_i0` | 12 | tier1_EUR_JPY | EUR_JPY | -0.0262 | -0.0213 | ❌ | ❌ | ❌ | 3467 | — |
| 3 | `g13_i0` | 13 | tier1_EUR_JPY | EUR_JPY | -0.0262 | -0.0213 | ❌ | ❌ | ❌ | 3467 | — |
| 4 | `g14_i0` | 14 | tier1_EUR_JPY | EUR_JPY | -0.0262 | -0.0213 | ❌ | ❌ | ❌ | 3467 | — |
| 5 | `g15_i0` | 15 | tier1_EUR_JPY | EUR_JPY | -0.0262 | -0.0213 | ❌ | ❌ | ❌ | 3467 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03444273222155406 |
| 1 | -0.05320599154006127 |
| 2 | -0.03198751084433725 |
| 3 | -0.03198751084433725 |
| 4 | -0.031975102518058976 |
| 5 | -0.031975102518058976 |
| 6 | -0.031975102518058976 |
| 7 | -0.031975102518058976 |
| 8 | -0.031975102518058976 |
| 9 | -0.031975102518058976 |
| 10 | -0.031975102518058976 |
| 11 | -0.026219602528901646 |
| 12 | -0.026219602528901646 |
| 13 | -0.026219602528901646 |
| 14 | -0.026219602528901646 |
| 15 | -0.026219602528901646 |
| 16 | -0.026219602528901646 |
| 17 | -0.026219602528901646 |
| 18 | -0.026219602528901646 |
| 19 | -0.026219602528901646 |
| 20 | -0.026219602528901646 |

## 分析

### analysis-claude.md

# RUN run_20260522_160436 (Run 90) 分析（Claude 自己分析）

## 前提差分
R90 = T117 multi-pair training **min 集約** spike (Stage A fitness を EUR_JPY+USD_JPY で min 集約)、pop48 gen20 seed68 + cross-pair-enable。vs R89 (single-pair, pop96 gen60)。

## 観察事実（Facts）
- multi_pair_training.enabled (aggregate=min, anchors=['USD_JPY'], scope=stage_a) 本番動作。wall-time **13.5 分** (軽量=full 可)。
- ★ **A/B/C = 0/0/0** (R89: 2606/2142/892)。stage_a_pass=False が全 1008 個体。
- fitness_pen (min 集約後): gen0 max -0.058 → gen20 max -0.028。**全 gen で Stage A 閾値 -0.0172 未達**。
- **fitness_raw (観察 sharpe) max = 0.0** (median -0.069)。集団が target でも全く改善せず。
- threshold=-0.0172 (R89 と同一、calibration 差なし)。anchor metric_unavailable=0 (anchor データ問題なし)。

## 解釈・推論（Interpretations）

### 1. ★ min-collapse: min 集約が target 改善への選抜圧を消した
fitness = min(target_fp, anchor_fp)。anchor (USD_JPY) は EUR_JPY 学習の random/未成熟 genome では普遍的に低性能 (fp ~-0.1〜-0.9)。→ min は常に anchor を拾う → **selection fitness ≈ anchor で、target を改善しても min は上がらない** → GA は target 改善を報酬されず、集団が target でも改善しない (fitness_raw max 0.0)。
- R89 (single-pair) は fitness=target_fp で target 改善を直接報酬 → 集団進化 → 2606 passes。R90 は target 信号が min で消失 → 0 passes。
- stage_a_pass=0 の理由: passed=target の判定だが、集団が target-good 個体を進化させられず target_fp も閾値未達 (fitness_raw max 0.0 が傍証)。
- 反証可能性: mean 集約で target 改善が報酬される (mean は target/2 の重みで上昇) なら A/B/C>0 回復 → min-collapse 仮説が正。

### 2. mean 集約が min-collapse を回避する理論
fitness = (target_fp + anchor_fp)/2。target を改善すると mean が target/2 の重みで上昇 → **target 改善が報酬される** → 集団が target-good 個体を進化 (R89 同様)。かつ anchor も従重みで報酬 → anchor も nudge。target-good 個体は high target が mean を閾値上に持ち上げ生存 (min なら anchor で殺される)。
- 懸念: mean でも anchor が極端に低い (-0.9) と mean を閾値下に引きずる個体あり。だが target が十分高ければ (R89 best target fp は閾値を大きく超過) mean 救済。Codex で確認。

### 3. Codex 予測リスクの顕在化
cycle8 Codex consensus は min を「全ペアで機能強制」として推奨も、「tie 多発回避に mean 併記監視」と留保。R90 で min が過酷すぎ集団崩壊 = 予測リスク顕在化。mean (実装済) が次の自然な検証。

### 4. 禁止事項違反の兆候
なし。multi-pair は評価拡張 (緩和でない)。

## 次サイクル候補
- **[Critical] mean 集約 R91**: aggregate=mean で min-collapse 回避を検証。T117 実装済だが CLI に aggregate 渡す経路なし (現状 yaml default min) → `--multi-pair-aggregate` CLI 最小追加。R91 (mean, pop48 gen20 同条件) で A/B/C>0 回復 + pair_failure=0 比率 + cross_pair_mean_sharpe を R90 min/R89 single と A/B。
- **[Warning] weighted blend / NSGA2 多目的**: mean も不十分なら target+λ·anchor (target 主) or 既存 nsga2_selection で target/anchor を別目的 Pareto (集約せず両立)。
- **[Warning] 閾値引き上げ**: 汎化未達のため時期尚早。

## 全体判定
**CONCERN→負の結果が次施策を明確化** — R90 min 集約 spike は A/B/C 0/0/0 で min-collapse (min が target 改善への選抜圧を消し集団崩壊)。但しコスト軽量 (13.5 分)・anchor データ健全を確認。**mean 集約 (target 信号を半重みで保持) が min-collapse を回避する**理論的見込みで、T117 の aggregate=mean を CLI 経由で R91 検証 (最小実装) が次の Critical。

### analysis-codex.md

1. Facts要約  
- Run 90（T117, `aggregate=min`）は Stage A/B/C が **0/0/0**、`stage_a_pass` 全個体 False で、Run 89（single-pair 2606/2142/892）から構造的に崩壊しています。  
- 世代進行で `fitness_pen` は改善（-0.058→-0.028）した一方、Stage A閾値 -0.0172 を一度も超えず、`fitness_raw(max)=0.0` で target 側改善も報酬化されていません。  
- anchor 側 `metric_unavailable=0` なので、主因はデータ欠損ではなく選抜設計側です。  

2. 解釈（反証可能性）  
- (a) `min-collapse` 診断は妥当です。`min(target,anchor)` は常に弱い側（初期は anchor）で決まり、target 改善の選抜圧を消します。  
反証条件: 「minの決定因子が大半の個体でanchorではない」または「target上位個体が実際に親選抜で優遇されている」が観測されればこの診断は棄却。  
- (b) mean集約の見込みは妥当です。`(target+anchor)/2` なら target 改善が即時に fitness へ寄与し、探索が停止しにくい。  
リスク: anchor が極端に悪いと mean も閾値未達になり得る（過剰淘汰）。ただし min よりは「target高性能で救済」される余地が明確に増えます。  
- (c) 優先順位は **mean先行 > weighted blend > NSGA2多目的** が低リスクです。NSGA2（集約せず両立）は理論的に本質解に近いですが、pair別目的の配線追加が大きく、いまの0/0/0ドリフトを止める即効性では mean が最善です。  

3. 次サイクル候補  
- Critical（1個）: **R91で `aggregate=mean` を同条件再実行**（最小実装: `--multi-pair-aggregate {min,mean}` 追加）。  
判定基準（反証可能）: Stage A pass が 0→正へ回復し、target 指標が世代で単調改善するか。回復しなければ「min-collapse単独原因」は棄却。  
- Warning（1）: weighted blend（target主, anchor従）は R91失敗時の次善策としてのみ実施（自由度増で過学習リスク）。  
- Warning（2）: NSGA2 pair別多目的は設計タスク化して後段へ（即時run投入は変更半径が大きい）。  

4. 全体判定  
**CRITICAL_DRIFT**

