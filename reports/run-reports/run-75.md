# Run 75 — run_20260513_120619

**Generated**: 2026-05-13T12:07:54.763383+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.1904512639001093 / threshold 1.0
- ✅ **total_pnl**: 51540.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 3.7362810740452215 / threshold 20.0
- ✅ **trade_count**: 51 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 60

## Best 個体

- name: `g60_i46`
- generation: 60
- fitness: **0.1769512639001093**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 51
- total_pnl: 51540.0
- sharpe: 0.1904512639001093
- sortino: —
- calmar: —
- max_drawdown_pct: 3.7362810740452215

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2121
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1291
- Stage B pass: 827
- Stage C pass: 217

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1291 | 827 | 217 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1291 | 827 | 217 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3827, median=1.0000, std=0.4937, min=0, max=2
- n_nodes: n=5856, mean=3.3265, median=3.0000, std=1.7484, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=823, mean=0.7433, median=0.8975, std=0.2630, min=0.2705, max=0.9770
- best mission_score: **0.9770** (`g46_i69`, gen=46, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1291, mean=0.2202, median=0.2121, std=0.0792, min=0.0000, max=0.5455
- dsr: n=0
- n_fold_effective (Stage A pass): n=1291, mean=32.2827, median=34, std=5.3402, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1290, mean=0.5824, median=0.6176, std=0.1617, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1291, Stage B pass = 827, failures = 464 (primary_sum = 464)

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
| `positive_fold_ratio_effective<min` | 175 |
| `median_oos_total_pnl<min` | 105 |
| `sum_oos_total_pnl<min` | 161 |
| `n_fold_effective_below_profit_safe_min` | 23 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 175 |
| `median_oos_total_pnl<min` | 280 |
| `sum_oos_total_pnl<min` | 424 |
| `n_fold_effective_below_profit_safe_min` | 45 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 9 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.0% (119/5856)
- best 個体 trade_count: 51
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=464, stage_a_only=4565, stage_b_evaluated=610, stage_c_evaluated=217
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4565, mean=-518848.2541, median=-331440.0000, std=467907.3579, min=-1009210.0000, max=30240.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4446): n=4446, mean=-532735.5556, median=-383950.0000, std=466260.6904, min=-1009210.0000, max=30240.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1291): n=1291, mean=39693.3540, median=38170.0000, std=66638.6773, min=-1000590.0000, max=124950.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g57_i47` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2204 | 0.2474 | ✅ | ✅ | ❌ | 51 | — |
| 2 | `g58_i87` | 58 | tier1_EUR_JPY | EUR_JPY | 0.2174 | 0.2474 | ✅ | ✅ | ❌ | 51 | — |
| 3 | `g59_i39` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2058 | 0.2208 | ✅ | ✅ | ❌ | 51 | — |
| 4 | `g19_i24` | 19 | tier1_EUR_JPY | EUR_JPY | 0.2021 | 0.2336 | ✅ | ❌ | ❌ | 78 | — |
| 5 | `g60_i42` | 60 | tier1_EUR_JPY | EUR_JPY | 0.1966 | 0.2296 | ✅ | ✅ | ❌ | 51 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.04586894757299548 |
| 1 | 0.10130275101463238 |
| 2 | 0.10130275101463238 |
| 3 | 0.10130275101463238 |
| 4 | 0.10130275101463238 |
| 5 | 0.10130275101463238 |
| 6 | 0.16258147179510896 |
| 7 | 0.16258147179510896 |
| 8 | 0.16258147179510896 |
| 9 | 0.16258147179510896 |
| 10 | 0.16258147179510896 |
| 11 | 0.04046658812956685 |
| 12 | 0.06408491531617036 |
| 13 | 0.0018092094635825482 |
| 14 | 0.06797063892998025 |
| 15 | 0.08487572654163122 |
| 16 | 0.08487572654163122 |
| 17 | 0.06799354523886304 |
| 18 | 0.06799354523886304 |
| 19 | 0.20210046613214058 |
| 20 | 0.1309365757444412 |
| 21 | 0.08588418647034504 |
| 22 | 0.052459111987625984 |
| 23 | 0.0070733223564988425 |
| 24 | 0.009434348831016468 |
| 25 | 0.07191488659368939 |
| 26 | 0.09239389610939537 |
| 27 | 0.09239389610939537 |
| 28 | 0.09239389610939537 |
| 29 | 0.044306001327531014 |
| 30 | 0.052459111987625984 |
| 31 | 0.052459111987625984 |
| 32 | 0.06103433435663959 |
| 33 | 0.06103433435663959 |
| 34 | 0.08335269085509103 |
| 35 | 0.08929864230867397 |
| 36 | 0.1464951840205259 |
| 37 | 0.13518631271972567 |
| 38 | 0.12855935107241495 |
| 39 | 0.15930016928668342 |
| 40 | 0.15480016928668344 |
| 41 | 0.15480016928668344 |
| 42 | 0.15930016928668342 |
| 43 | 0.18258410424373664 |
| 44 | 0.16583282236156602 |
| 45 | 0.14280016928668343 |
| 46 | 0.14580016928668343 |
| 47 | 0.15983282236156604 |
| 48 | 0.15983282236156604 |
| 49 | 0.1589512639001093 |
| 50 | 0.1769512639001093 |
| 51 | 0.18036013077185362 |
| 52 | 0.1741447116797828 |
| 53 | 0.18264956379336955 |
| 54 | 0.1758601307718536 |
| 55 | 0.17612388493435008 |
| 56 | 0.18336013077185362 |
| 57 | 0.22041915000351472 |
| 58 | 0.21741915000351472 |
| 59 | 0.20584313894099032 |
| 60 | 0.19657037608777322 |

## 分析

### analysis-claude.md

# RUN run_20260511_201001 (Run 74) 分析（Claude 自己分析）

## 前提差分

なし。`.cache/alpha_factory/runs/genomes_run_20260511_201001.parquet` / `reports/run-reports/run-74/summary.json` / `dsr_audit.json` / `scripts/codex` / docs はすべて存在し、shallow read 成功。

ただし以下を前提として保留:
- 本 skill は archive Parquet の**深い分析**（primitive 再実行、genome_json AST 解析等）を担当しない（`zenigame-fx-analyze-genome-archive` 未移植）
- cross_pair_runtime_mode は `skipped_single_instrument`（EUR_JPY 単独実行）で cross-pair shadow 統計は本 RUN では生成されていない

---

## 観察事実（Facts）

### 1. RUN メタ
- run_id: `run_20260511_201001` / run_number: 74 / instrument: EUR_JPY (single)
- dataset: 2025-04-01 〜 2026-02-19、bars 328,883（Stage A 86,400 / Stage B 242,483 / holdout 60,232）
- ga_config: pop=96, gen=60, seed=**59** (state file history と一致), max_workers=2, mutation_rate=0.5
- ga_config.fitness_metric: sharpe
- stage_gate: stage_a_window=60日、stage_a_threshold=**-0.0172**（calibrate-gate 由来）、stage_b_window=18ヶ月、stage_c_holdout=60日、spread_stress=1.5
- selection_score_schema: `v3_3_stage_b_feasible_priority`
- 完走時間: 約 240 分

### 2. Stage 通過数（archive Parquet 5,856 行）

| Stage | 通過数 | rate vs 全体 | rate vs 前 Stage |
|-------|--------|-------------|------------------|
| Stage A | 1,723 | 29.4% | — |
| Stage B | 96 | 1.64% | 5.57% (96/1723) |
| Stage C | 0 | 0% | 0% (0/96) |
| graduated | 0 | 0% | — |

per_generation 推移:
- gen 0-9: Stage A=0（10 世代不毛）
- gen 10 で初の Stage A pass=1、gen 20 で 28、gen 30 で 39、gen 40-60 で 40-50 で安定
- gen 33 で初の Stage B pass=2、gen 34-60 で 2-6 で振動
- Stage C は per_generation で 1-7 秒 evaluate されているが全て fail（最終 graduation_count=0）

### 3. Best 個体 (selection_score v3_3 = summary.json)

- name: `g60_i45` @ gen 60 / lane: tier1_EUR_JPY / parent: g59_i52 × g59_i57
- fitness_pen: 0.1063 / fitness_raw: 0.1408
- stage_a/b/c: **True/True/False**
- trade_count: **41** / total_pnl: **-15,390** / max_dd: 5.09% / trade_sharpe_stage_b: 0.0311
- median_oos_sharpe: 0.0736 / positive_fold_ratio_effective: 0.618 (>= 0.6 を辛うじて clear) / n_fold_effective: 34
- n_nodes: 7 / active_clause: 2

### 4. archive Parquet 内 fitness_pen 最大個体

- name: `g41_i78` @ gen 41 / parent: g40_i31 × g40_i14
- fitness_pen: **0.2555**（archive 最大）/ fitness_raw: 0.2950
- stage_a/b/c: **True/False/False**
- trade_count: 33 / total_pnl: +28,160 / max_dd: 0%
- trade_sharpe_stage_b: 0.026 / median_oos_sharpe: **0.0** / positive_fold_ratio_effective: **0.0** / n_fold_effective: **11**
- stage_b_reason_codes: `median_oos_sharpe<min;positive_fold_ratio<min`
- n_nodes: 4 / active_clause: 2

→ **fitness_pen 最大個体は Stage B fail**。selection_score (v3_3 stage_b_feasible_priority) で Stage B 通過個体を優先する規約のため、最終 best は **fitness_pen が 1/2.4 倍ある g60_i45** になっている。

### 5. live_criteria 結果（best = g60_i45）

| metric | value | threshold | pass |
|--------|-------|-----------|------|
| sharpe | 0.141 | ≥ 1.0 | ❌ |
| total_pnl | -15,390 | ≥ 50,000 | ❌ |
| max_drawdown_pct | 5.09% | ≤ 20% | ✅ |
| trade_count | 41 | [50, 5000] | ❌ |

→ **1/4 pass**、`live_criteria.all_pass: false`。state file history の cycle 21 (Run 74) 記録「4 中 1 pass」と一致。

### 6. Stage B 通過群 (n=96) の構造観察

| 指標 | min | max | mean | median |
|------|-----|-----|------|--------|
| fitness_pen | -0.015 | 0.106 | 0.020 | — |
| trade_count | 41 | 58 | 51.4 | 52 |
| total_pnl | **-16,670** | **-6,940** | **-8,813** | **-7,950** |
| trade_sharpe_stage_b | — | — | **-0.033** | **-0.040** |
| median_oos_sharpe | — | — | 0.051 | 0.065 |
| positive_fold_ratio_eff | — | — | 0.623 | 0.618 |
| n_fold_effective | — | — | 34.0 | 34.0 |
| n_nodes | 2 | 7 | 2.05 | — |
| active_clause | 1 | 2 | **1.01** | — |
| max_drawdown_pct | 3.49 | 5.09 | 3.91 | — |

**極めて重要な観察**:
- **Stage B 通過群 96 個体の total_pnl が全例 negative** (max=-6,940)。
- **trade_sharpe_stage_b の mean/median が negative** (-0.033 / -0.040)。median_oos_sharpe は positive (0.05) なのに、Stage B 区間の trade sharpe は negative — sharpe 計算方法（trade-level vs fold-level）の差異。
- **active_clause が 96 個体中ほぼ全員 1**（mean 1.01、95+ が 1 clause）。max_clause=2 設定があるが clause を増やせていない。
- **n_fold_effective が全員 34 で固定**。
- **unique fitness_pen は 6 種類のみ**（6/96 = 6.2%）。クローン汚染が深刻、Stage B 通過群はほぼ同一個体の繰り返し。
  - top 5 unique fp: 0.1063 / 0.0784 / 0.0743 / 0.0421 / 0.0083
  - 0.0784 が圧倒的多数（恐らく ~80 個体）

### 7. Stage B fail 原因コード（Stage A pass 1,723 中の Stage B fail 1,627）

| reason_codes | count | rate |
|--------------|-------|------|
| `median_oos_sharpe<min;positive_fold_ratio<min` | 1,556 | **95.6%** |
| `positive_fold_ratio<min` 単独 | 68 | 4.2% |
| `median_oos_sharpe<min` 単独 | 2 | 0.12% |
| 他 | 1 | <0.1% |

→ **median_oos_sharpe と positive_fold_ratio が同時 trigger** が支配的（95.6%）。fold 全体が弱い構造的問題。

### 8. DSR proxy 監査（dsr_audit.json）

- 全 5,856 個体で **dsr_proxy_pass = 0**
- 上位 Stage B 通過個体（n_fold_effective=34）の dsr_proxy 最高は **0.0266** (best g60_i45)
- dsr_threshold = **0.7144** (sqrt(2*log(5856)/N))
- 最高個体ですら threshold まで **27 倍離れている**

### 9. cross-pair shadow

- `cross_pair_runtime_mode: skipped_single_instrument` → 本 RUN では generation されず。

### 10. 18 RUN 累積（Run 57-74 history より）

- best Stage B pass: 12/18 (67%)
- mission 達成 (live_criteria all_pass): **0/18**
- Stage C pass: 18 RUN 全て 0
- DSR proxy pass: 0/18

---

## 解釈・推論（Interpretations）

C6 Fact/Interpretation 分離: ここから先は推論。

### I1. Stage B 通過 ≡ 「赤字許容」設計の可能性 [Critical]

**観察**: Stage B 通過群 96 個体の total_pnl が **全例 negative** (-6,940 〜 -16,670)。trade_sharpe_stage_b も全例 negative (mean -0.033)。

**仮説**: Stage B 閾値 (positive_fold_ratio >= 0.6, median_oos_sharpe >= 0) は **sign-based 検査**で magnitude を見ない。「sign が positive な fold が 60% 以上」かつ「fold sharpe の中央値が 0 以上」を満たせば通過するため、**多くの fold で微利、少数 fold で大損** という赤字構造でも通過する設計になっている。

**反証可能性**:
- 反証 1: 仮にコストモデルを甘くしたら通過個体が黒字になるはず → 全例 negative なので **コストではなく利益確定不足**
- 反証 2: Stage B 閾値が magnitude を見るなら通過個体は黒字のはず → 通過個体全員赤字 → **sign-based 仮説支持**
- 反証 3: trade_sharpe_stage_b が positive な個体が 1 例でもあれば仮説は弱まる → 96 個体全例 negative → **支持**

**重要性**: これは禁止事項 #6（取引回数削減で見かけ改善）の **逆方向の問題**。GA は「利益を出す」ではなく「sign positive fold 60% を達成する」最適化に流れている。

### I2. clause collapse (active_clause 1.01) [Critical]

**観察**: max_clause=2 だが Stage B 通過群の active_clause mean 1.01。

**仮説**: GA の selection / mutation が **1 clause** に収束する dynamic を持つ。Stage A の fitness が **1 clause で十分な水準**（threshold -0.0172、相当緩い）に達するため、複雑性ペナルティ込みで 1 clause が常勝。

**反証可能性**:
- 反証: 全体集団の active_clause を見て同様に 1 集中なら GA dynamics 由来、Stage B 通過群だけ 1 集中なら閾値設計由来 → 全体 mean 3.92 (Stage A pass) → **集団は多 clause 探索しているが Stage B で 1 clause に絞られる** → I1 と整合（多 clause は赤字幅が大きく Stage B 通過しにくい）

### I3. 多様性崩壊 (Stage B unique fp 6.2%) [Critical]

**観察**: Stage B 通過群 96 個体の unique fitness_pen は 6 種類。0.0784 が dominant。

**仮説**: Stage B 通過の経路が非常に狭く、GA が同一個体（または極めて近い copy）を量産している。selection_score v3_3 が Stage B pass を強く preference するため、一度発見した Stage B pass 個体が elite として残り続け、population 全体に拡散。

**反証可能性**:
- 反証: parent_a/b の unique 数を見れば実質的な lineage 数が分かる → unique parents 110/138 → 親も多様性低下、cross-lineage 探索が機能していない

### I4. fitness_pen と Stage B pass の乖離 [Warning]

**観察**: archive 最大 fitness_pen (g41_i78, fp=0.255) は Stage B fail、selection_score best (g60_i45, fp=0.106) は Stage B pass。

**仮説**: Stage A 評価関数 (sharpe-based) と Stage B fold 評価関数 (positive_fold_ratio + median_oos_sharpe) が**異なる最適解**を生む。Stage A 最強は Stage A 期間 (60日) に過適合し、Stage B (18ヶ月) で剥がれる。

**反証可能性**:
- 反証: fitness_pen 上位 N 個体の Stage B pass 率を見る → archive 全体 Stage B pass 96/5856=1.6% に対し fitness_pen 上位の Stage B pass 率を測定する必要がある（未測定、Codex 委譲候補）

### I5. DSR proxy 27 倍離れ [Warning]

**観察**: dsr_proxy 最高 0.0266 vs threshold 0.7144。

**仮説**: M=5856 trials の多重比較補正で全個体 fail。これは「探索数が多すぎて統計的有意性を主張できない」状態。

**反証可能性**:
- 反証 1: pop_size を下げれば M も下がり threshold も下がる → 探索効率と statistical robustness のトレードオフ
- 反証 2: より「真に強い」個体が出現すれば proxy が threshold に近づく → 現状の構造改善が必要

### I6. 禁止事項違反兆候の検査 (C4)

- **イントラデイ逸脱**: trade_count_full_dataset mean 252 / Stage B mean 181 → 18ヶ月 × 月 10 trade ≒ 180 トレード ≒ 平均 1.5 日/トレード。intraday と言うには長いが、明確な逸脱ではない（要確認: 保有時間分布）
- **取引回数削減で見かけ改善**: best 個体の trade_count=41 で live_criteria 50 下限を下回っている。fitness_raw 0.14 を維持しつつ trade_count を削った形跡はあるが、Stage B 通過全員が赤字なので「見かけ改善」より「赤字許容」のほうが本質
- **live_criteria 緩和**: 設計に閾値固定の history があり、本 RUN では緩和の痕跡なし
- **ショート追加で見かけ改善**: 本 skill では trade-level direction の集計をしていない（archive に shorts / longs 別の trade_count なし）— Codex 委譲候補

### I7. live_criteria 達成見通し

18 RUN 累積で all_pass=0。最大 sharpe は Run 60 の 0.581 (single)、best total_pnl は Run 60 の +36,030 (≒ live 50k の 72%)、trade_count は Run 61 の 74 まで届いた。**しかし 4 条件同時達成 (sharpe ≥ 1.0 ∧ pnl ≥ 50k ∧ dd ≤ 20% ∧ trade ∈ [50, 5000]) は 0 例**。Stage B 通過群がそもそも赤字構造の中で live を達成するのは構造改革なしに困難。

---

## 次サイクル候補

### [Critical] C22-1: Stage B 通過の sign-based 検査の magnitude 化

**仮説**: I1 (Stage B 通過 ≡ 赤字許容) を反証/支持するため、Stage B 閾値に **magnitude 要件**を追加する。

**具体策**:
- Stage B 通過の必要条件として `median_oos_total_pnl >= 0` （または `mean_fold_pnl >= 0`）を **追加**
- 既存の `positive_fold_ratio >= 0.6` と `median_oos_sharpe >= 0` は維持
- 旧 stage_b 閾値設計の cross-run guard で `stage_gate_version` を bump（誤適用防止）

**反証実験**: 次 RUN で magnitude 要件を追加し、
- Stage B pass 数が激減 → 仮説支持（現在の Stage B pass 大半が赤字経由）
- Stage B pass 数がほぼ不変 → 仮説否定

### [Warning] C22-2: clause 2 個強制 (active_clause floor)

**仮説**: I2 (clause collapse) 対策として GA 初期化と mutation で active_clause >= 2 を強制。

**具体策**:
- `genome_init` で active_clause=2 を必須化
- mutation で active_clause が 1 に減る突然変異を抑制 (floor=2)

**反証**: clause 2 強制で Stage A pass 数が激減すれば clause collapse は GA dynamics 由来ではなく Stage A 閾値の都合 → 別仮説検証へ

### [Warning] C22-3: 多様性回復施策 (fitness sharing or niching)

**仮説**: I3 (Stage B unique 6.2%) 対策として GA selection に fitness sharing を追加。

**具体策**:
- 同一 fitness_pen (rounded to 6 digits) の個体に対し sharing penalty
- または structural diversity metric (genome AST 距離) で niching

ただし大規模変更となるため、まず **観測**段階で「Stage B unique 数の cycle ごと推移」を sieve するスクリプトを書き、データ集めから始める。

### [Warning] C22-4: cross-pair lane 復活 (single → multi-instrument)

**観察**: cross_pair_runtime_mode が `skipped_single_instrument` で shadow 統計ゼロ。EUR_JPY 単独で 18 RUN 同じ regime を擦り続けている可能性。

**具体策**:
- 次 RUN を **USD_JPY** または **EUR_USD** にスイッチして regime shift の影響を観察
- または `--instrument-list "EUR_JPY,USD_JPY"` で multi-instrument mode に切替（実装可能性は別途確認）

---

## 全体判定

**CRITICAL_DRIFT (= I1: Stage B 通過個体が全例赤字)** — 構造的に Stage B 閾値が利益を保証しない設計になっている可能性が高い。閾値チューニングではなく **設計レベルの是正**が必要。

次サイクル C22 では C22-1 (magnitude 閾値追加) を**最優先**で実装し、反証実験を行う。

---

## 未接続 hook

- `zenigame-fx-post-run-review`: 接続済 (improve-cycle Phase 1 末尾の launcher で起動。本 skill スタンドアロンでは起動しない)
  - cycle 22 では 30 RUN ループのリソース管理上 skip（marker pre-write）
- `zenigame-fx-analyze-genome-archive`: 未移植（primitive 偏在 / genome AST 距離分析が未実施 — clause collapse 仮説 I2 と多様性 I3 の verification が宙）

---

## 滞留 TODO 判断

直近 Closed TODO: T094 @ 2026-05-13 18:28。
Open TODO はすべて 2026-05-13 19:15 追加（T095-T103）→ **滞留 TODO なし**（全件 1 時間以内に新規追加）。

| ID | 判断 | 理由 |
|----|------|------|
| (なし) | — | 全 Open TODO が直近追加で滞留ゼロ |

## Conditional 昇格チェック

| ID | タイトル | トリガー条件 | 評価 | アクション |
|----|---------|-------------|------|----------|
| T104 | PR6: F6/F10/F4/F7 grammar soft downweight opt-in | PR4 smoke で F6 含有率 top decile が baseline×1.5 超 | **未成立**（PR4 smoke 結果未生成。T094 (PR4) は 2026-05-13 18:28 close 済だが Run 74 は PR4 smoke ではない） | スキップ（次サイクルで再評価） |

## TODO 選定結果

**standalone 確認**: Open テーブルに standalone 5 件（T099, T100, T101, T102, T103）あり → SKILL.md ルール「最優先 standalone 1 件、incremental 混在禁止」を適用。

**選定**: **T099 (High, standalone)** を採用。

| ID | タイトル | 優先度 | target_metric | failure_mode | causal_path | falsification | success_criterion | 判定 | 理由 |
|----|---------|--------|--------------|-------------|------------|---------------|-------------------|------|------|
| **T099** | PR5: Stage B gate pfr_only opt-in A/B | High | Stage C trade_sharpe median / Stage C pass count / Stage B 通過群 total_pnl 中央値 | Run 74 で Stage B 通過 96 個体全例赤字 (-6,940〜-16,670)、trade_sharpe_stage_b median -0.040、18 RUN 累積で Stage C pass = 0。過去 Codex 合議で archive 実測 Spearman ρ(median_oos_sharpe → trade_sharpe_stage_c) = **-0.361** (curve-fit 逆予測)、ρ(positive_fold_ratio → trade_sharpe_stage_c) = **+0.345** (唯一の正予測) | median_oos_sharpe gate が curve-fit 個体選好 → Stage C で持続性失う | Run 75 (smoke `--stage-b-gate-kind pfr_only`) で Stage B pass 数が legacy 比で激減 or Stage C median trade_sharpe が悪化なら仮説否定 (= legacy に戻す)、観測:Stage B 通過群 median total_pnl が positive 化 or Stage C pass >= 1 が出現すれば仮説支持 | Run 75 で Stage C pass >= 1 出現 OR Stage B 通過群の median total_pnl が positive 化 | **採用** | High 優先 standalone、archive 実測根拠あり、Run 74 で発見した「Stage B 全員赤字」「Stage C pass 0」を直接対処 |

**非採用** (incremental 混在禁止ルール / standalone 1 件のみルールにより):
| ID | タイトル | モード | 判定 | 理由 |
|----|---------|--------|------|------|
| T095 | T092 fold guard fixture 修正 | incremental | 見送り | standalone 採用時は混在禁止 (SKILL ルール) |
| T096 | archive.py:335 mypy narrowing fix | incremental | 見送り | 同上 |
| T097 | docs progress_criteria 明文化 | incremental | 見送り | 同上、docs 系で GA mission に直結せず |
| T098 | scripts out-of-cluster audit | incremental | 見送り | 同上 |
| T100 | Stage C stratified allocation | standalone | 見送り | T099 採用、 standalone 1 件のみルール。T099 と機能領域は重なるが T099 が pfr_only opt-in (gate 側)、T100 は Stage C 評価集団 stratifier (allocation 側) で本来両立可能。次サイクル候補に持ち越し |
| T101 | Run 71/63 系統 warmstart | standalone | 見送り | 同上、Low 優先で T099 を優先 |
| T102 | Phase 2 統合 Step 3-7 | standalone | 見送り | 同上、Medium 優先で大規模 (5 sub-PR) のため smoke 検証フローと衝突 |
| T103 | primitive 拡張 (82 primitive 相当) | standalone | 見送り | 同上、Low 優先で大規模 |

## GA 分析由来の改善候補 (Phase B で合議)

T099 と並走可能な GA 改善（competing と統合の両方を Codex 合議で判断）:

- **C22-1 (Codex Critical 提案)**: Stage B feasible 条件に純利益要件追加 (`median_oos_total_pnl >= 0` ∧ `trade_sharpe_stage_b > 0`)
  - T099 (pfr_only opt-in) と機能領域が**重なる**: 両者とも Stage B gate を改修。T099 は「median_oos_sharpe を gate から外す」、C22-1 は「pnl/sharpe magnitude 条件を追加」
  - 統合可能性: pfr_only mode + magnitude floor (`pfr >= 0.4` ∧ `median_total_pnl >= 0` ∧ `trade_sharpe_stage_b > 0`)
  - 競合可能性: T099 だけだと curve-fit 防止は効くが赤字許容構造は残る (positive_fold_ratio 0.4 を満たしても 60% が損失 fold は可能)。C22-1 を併用すれば magnitude も保証
  - **判断**: Phase B Codex consensus 合議で T099 を **strict superset** に統合提案（pfr_only + magnitude）。Codex が NG なら T099 単独で smoke 実行

cycle_focus 暫定判断: **mixed** (T099 standalone + GA 改善 C22-1 統合の 1-2 件)

### analysis-codex.md

# Run 74 独立分析 (Codex)

## 観察事実（Facts）
- Stage通過率: A `1723/5856 (29.4%)`、B `96/5856 (1.64%, A通過内5.57%)`、C `0/5856 (0%)`
- gen 0-9 は Stage A 通過 `0`、gen 33 で初 Stage B 通過、Stage C は評価されるが全 fail
- selection best `g60_i45`: `fitness_pen=0.1063`、`A/B/C=True/True/False`、`trade_count=41`、`total_pnl=-15,390`、`trade_sharpe_stage_b=0.0311`
- archive fitness_pen 最大 `g41_i78`: `fitness_pen=0.2555`、`A/B/C=True/False/False`、`total_pnl=+28,160`、`median_oos_sharpe=0.0`、`positive_fold_ratio=0.0`
- Stage B通過群 (n=96): `total_pnl max=-6,940 (全件マイナス)`、`trade_sharpe_stage_b mean=-0.033/median=-0.040`、`active_clause mean=1.01`、`unique fitness_pen=6/96 (6.2%)`
- Stage B fail理由: `median_oos_sharpe<min;positive_fold_ratio<min` が `95.6% (1556/1627)`
- live_criteria(best): `1/4 pass`（sharpe/pnl/trade_count fail）
- DSR proxy: 全個体 pass `0`、上位でも `0.0266`、threshold `0.7144`
- cross-pair shadow: `skipped_single_instrument`
- 18 run累積: mission達成 `0/18`、Stage C pass `0/18`、DSR pass `0/18`

## 解釈・推論（Interpretations）
前提（verified）:
- 入力は archive/reports 要約値のみで、個別約定ログ（保有時間、long/short内訳、コスト内訳）は未提示
- よって FX固有制約の一部は「検証不能」を明示する

1. Stage gate のボトルネック仮説  
仮説: `Stage B条件が探索を過度に絞り、収益性と乖離した通過を生む`  
falseなら観測されるはず: `Stage B通過群に正のtotal_pnlが一定数混在` し、`Stage C候補が漸増`  
観測: Stage B通過96件が全件マイナスpnl、Stage Cは0  
判定: **反証できず（仮説支持）**。Bが実質ボトルネック

2. 禁止事項違反の兆候（イントラデイ/取引回数削減/live緩和/ショート偏重）  
仮説: `禁止事項逸脱は発生していない`  
falseなら観測されるはず:  
- イントラデイ逸脱: 保有時間が日跨ぎ中心  
- 取引回数削減依存: trade_countが下限付近に貼り付き  
- live緩和: threshold改変の痕跡  
- ショート偏重: side別寄与の偏り  
観測: trade_countは `41-58` で下限50近傍に集中（bestは41でfail）。一方、保有時間・売買方向内訳・閾値変更履歴は未提示  
判定: **部分的懸念 + INCONCLUSIVE**。取引回数最適化への寄りは疑わしいが、イントラデイ逸脱/ショート偏重は未証明

3. primitive偏在と多様性崩壊  
仮説: `探索多様性は維持されている`  
falseなら観測されるはず: `active_clauseが1へ収束`、`fitness_pen重複率が高い`  
観測: `active_clause mean=1.01`、`unique fitness_pen=6.2%`  
判定: **反証できず（崩壊を支持）**。I2/I3は妥当

4. selection_score_schema v3_3 の探索歪み  
仮説: `v3_3は純利益方向と整合`  
falseなら観測されるはず: `高selection個体が赤字、黒字個体がBで落ちる`  
観測: bestはB通過だが赤字、archive最大fitness_penは黒字だがB fail  
判定: **反証できず（歪みを支持）**。I4は妥当。特に「feasible優先」が収益性より上位にある兆候

5. FX固有制約（スワップ/スプレッド純利益反映）  
仮説: `fitnessが純利益整合で、コストを適切反映`  
falseなら観測されるはず: `fitness良好でも純損失が常態化`  
観測: Stage B通過群が全件マイナスpnl  
判定: **設計上の不整合は強い**。ただし「コスト未反映」そのものはログ不足で断定不能。現時点で言えるのは「通過条件が純利益を保証していない」

## 次サイクル候補
- [Critical] Stage B feasible条件を sign判定から純利益整合へ拡張する（例: `median_oos_total_pnl >= 0` と `trade_sharpe_stage_b > 0` を必須化、selectionでも同順位以上で評価）
- [Warning] `active_clause` の collapse対策は「2個強制」より、`clause使用率ペナルティ/下限制約` を段階導入して副作用検証（強制固定は探索空間を不自然に歪める）
- [Warning] 多様性ガードを追加（`unique fitness_pen比率` や `genotype距離` の下限監視、niching/sharingを小さく導入）
- [Warning] FX制約の監査指標を必須出力化（`overnight_hold_ratio`、`long/short別PnL`、`spread_cost`、`swap_cost`、`net_pnl_after_cost`）。これがない限り逸脱検知はINCONCLUSIVEが続く

## 全体判定
CRITICAL_DRIFT

### analysis-merged.md

# マージ分析: Run 74 → Run 75

## 合意事項（Claude + Codex 両者一致）

1. **全体判定: CRITICAL_DRIFT** — Stage B 閾値が設計上の不整合を抱える
2. **Stage B 通過 96 個体が全例赤字** (-6940 〜 -16670) — sign-based 検査で magnitude を見ない設計が原因
3. **active_clause 1.01 で clause collapse** — max_clause=2 設定が機能していない
4. **unique fitness_pen 6.2%** で Stage B 通過群の多様性崩壊
5. **selection_score_schema v3_3 の歪み** — feasible 優先が収益性より上位、archive 最大 fitness_pen (黒字) は Stage B fail、selection_score best (赤字) は Stage B pass
6. **DSR proxy 27 倍離れ** — M=5856 trials の Bonferroni-like 補正で全個体 fail
7. **トレード回数依存疑い** — best trade_count=41 は live_criteria 下限 50 を下回り「取引回数最適化への寄り」が疑わしい

## Claude 独自の発見

- archive 内 fitness_pen 最大個体 (g41_i78, 0.255 黒字) と selection_score best (g60_i45, 0.106 赤字) が異なる構造（v3_3 が Stage B pass を強く preference するため）
- Stage B fail 主因の 95.6% が `median_oos_sharpe<min;positive_fold_ratio<min` 同時 trigger
- 18 RUN 累積 Stage C pass = 0 (Run 57-74 全て)

## Codex 独自の発見

- イントラデイ逸脱・ショート偏重・live_criteria 緩和は **INCONCLUSIVE** (保有時間 / side 内訳 / 閾値変更履歴が未提示) — **FX 制約の監査指標を必須出力化すべき** (overnight_hold_ratio / long_short_pnl / spread_cost / swap_cost / net_pnl_after_cost)
- clause 2 個強制は探索空間を不自然に歪めるので段階導入推奨 (clause 使用率ペナルティ / 下限制約)

## 矛盾・要議論

なし。両者の判定・提案は同方向（CRITICAL_DRIFT、Stage B gate magnitude 強化）。

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| 1 | **T099 MODIFY (profit-safe pfr)**: Stage B gate を `pfr >= 0.4 AND median_oos_total_pnl >= 0 AND trade_sharpe_stage_b > 0` に opt-in (default OFF) | **Critical** | T099 + C22-1 統合 (Codex todo-selection APPROVED) | Stage B 通過群 median_oos_total_pnl ≥ 0 達成率 / Stage C trade_sharpe median / Stage C pass count | Stage B 通過 96 個体全例赤字、median_oos_sharpe → trade_sharpe_stage_c が ρ=-0.361 で逆予測 | curve-fit 個体除外 + 赤字許容構造の解消 → Stage C pass 出現 |
| 2 | (保留) clause 使用率ペナルティ段階導入 (active_clause 1.01 対策) | Warning | Codex 独立分析 + Claude I2 | active_clause / unique fitness_pen ratio | clause 1 collapse (96/96 が 1 clause)、多様性崩壊 | clause 2 個探索を強制せず、選好で誘導 |
| 3 | (保留) FX 制約監査指標の必須出力化 (overnight_hold / long_short_pnl / spread_cost / swap_cost / net_pnl_after_cost) | Warning | Codex 独立分析独自 | INCONCLUSIVE 解消 (禁止事項違反検知) | FX 固有制約逸脱検知が監査経路なしで INCONCLUSIVE | 検知体制整備、以降の deceit-vs-real 判定基準確立 |
| 4 | (保留) cross-pair lane 復活 / multi-instrument (EUR_JPY 単独 18 RUN regime 擦り懸念) | Warning | Claude C22-4 | cross_pair_runtime_mode の skipped → shadow 統計生成 | 同 regime 擦り続け、汎化欠如懸念 | regime shift 観察、shadow 評価復活 |

## 次フェーズへの申し送り

- **#1 を cycle 22 で実装** (Phase B/C/3 で確定 → Run 75 smoke)
- **#2-#4 は保留事項** として improvement-plan.md に記録、次サイクル以降の TODO 候補
- 30 RUN ループ (cycle 22-51) を考慮し、cycle 22 で #1 のみに集中し、cycle 23 以降の seed sweep で #1 効果を検証 (大規模設計変更は避ける)

