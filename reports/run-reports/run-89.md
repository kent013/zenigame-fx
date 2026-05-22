# Run 89 — run_20260522_055538

**Generated**: 2026-05-22T05:55:38.597633+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 5.601393317428497 / threshold 1.0
- ✅ **total_pnl**: 87090.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.6562657123421372 / threshold 20.0
- ✅ **trade_count**: 51 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 892 (= Stage C 単独通過数)
- **mission_candidate_count**: 892 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g58_i44`
- generation: 58
- fitness: **0.009553742538039329**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 51
- total_pnl: 87090.0
- sharpe: 0.03655374253803933
- sortino: —
- calmar: —
- max_drawdown_pct: 1.6562657123421372

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3636
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 5
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2606
- Stage B pass: 2142
- Stage C pass: 892

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 892 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 298 | 33.4% |
| 51 | 196 | 22.0% |
| 52 | 148 | 16.6% |
| 53 | 88 | 9.9% |
| 54 | 52 | 5.8% |
| 55 | 28 | 3.1% |
| 56 | 22 | 2.5% |
| 57 | 4 | 0.4% |
| 58 | 5 | 0.6% |
| 59 | 9 | 1.0% |
| 60 | 6 | 0.7% |
| 61 | 6 | 0.7% |
| 62 | 6 | 0.7% |
| 63 | 4 | 0.4% |
| 64 | 4 | 0.4% |
| 65 | 1 | 0.1% |
| 69 | 3 | 0.3% |
| 71 | 3 | 0.3% |
| 73 | 2 | 0.2% |
| 74 | 1 | 0.1% |
| 83 | 1 | 0.1% |
| 84 | 1 | 0.1% |
| 86 | 1 | 0.1% |
| 95 | 1 | 0.1% |
| 97 | 2 | 0.2% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 298 | 594 |
| median total_pnl | 72890.0000 | 65575.0000 |
| median trade_sharpe_stage_c | 0.3511 | 0.2804 |
| median max_drawdown_pct | 1.6564 | 1.7921 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2606 | 2142 | 892 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2606 | 2142 | 892 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4255, median=1.0000, std=0.4948, min=0, max=2
- n_nodes: n=5856, mean=4.4809, median=4.0000, std=1.7382, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=2110, mean=0.9351, median=0.9680, std=0.0842, min=0.2742, max=0.9830
- best mission_score: **0.9830** (`g11_i95`, gen=11, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2606, mean=0.2761, median=0.3030, std=0.0775, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2606, mean=32.6328, median=34.0000, std=4.3760, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=2606, mean=0.5896, median=0.6176, std=0.1189, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2606, Stage B pass = 2142, failures = 464 (primary_sum = 464)

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
| `positive_fold_ratio_effective<min` | 193 |
| `median_oos_total_pnl<min` | 159 |
| `sum_oos_total_pnl<min` | 77 |
| `n_fold_effective_below_profit_safe_min` | 35 |
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
| `positive_fold_ratio_effective<min` | 193 |
| `median_oos_total_pnl<min` | 352 |
| `sum_oos_total_pnl<min` | 369 |
| `n_fold_effective_below_profit_safe_min` | 87 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 7 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=2142, None=3714

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 1.7% (97/5856)
- best 個体 trade_count: 51
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=464, stage_a_only=3250, stage_b_evaluated=1250, stage_c_evaluated=892
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3250, mean=-145928.4431, median=-18360.0000, std=307529.9108, min=-1001330.0000, max=41880.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3153): n=3153, mean=-150417.8370, median=-18870.0000, std=311141.2682, min=-1001330.0000, max=41880.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2606): n=2606, mean=19004.5050, median=17500.0000, std=23049.7217, min=-1000250.0000, max=82850.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g24_i94` | 24 | tier1_EUR_JPY | EUR_JPY | 0.2459 | 0.2909 | ✅ | ❌ | ❌ | 35 | — |
| 2 | `g24_i59` | 24 | tier1_EUR_JPY | EUR_JPY | 0.2167 | 0.2687 | ✅ | ❌ | ❌ | 34 | — |
| 3 | `g31_i15` | 31 | tier1_EUR_JPY | EUR_JPY | 0.1968 | 0.2148 | ✅ | ✅ | ❌ | 37 | — |
| 4 | `g18_i11` | 18 | tier1_EUR_JPY | EUR_JPY | 0.1783 | 0.1978 | ✅ | ❌ | ❌ | 55 | — |
| 5 | `g17_i36` | 17 | tier1_EUR_JPY | EUR_JPY | 0.1752 | 0.1972 | ✅ | ❌ | ❌ | 37 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.06792810714621762 |
| 2 | 0.10581882258119091 |
| 3 | 0.13319666999817595 |
| 4 | 0.13319666999817595 |
| 5 | 0.12291277693646901 |
| 6 | 0.14633271728053227 |
| 7 | 0.15237374077364993 |
| 8 | 0.1583737407736499 |
| 9 | 0.10951787393683556 |
| 10 | 0.14746881325813105 |
| 11 | 0.16389294894787929 |
| 12 | 0.1736902456591327 |
| 13 | 0.1736902456591327 |
| 14 | 0.1481908862403093 |
| 15 | 0.1555661047123201 |
| 16 | 0.1259624772158923 |
| 17 | 0.17521017783144063 |
| 18 | 0.1782519014223291 |
| 19 | 0.14821541733044996 |
| 20 | 0.1400652910195307 |
| 21 | 0.16212785341170804 |
| 22 | 0.13742643828833492 |
| 23 | 0.15062031148830737 |
| 24 | 0.24590424419651125 |
| 25 | 0.17111392361824876 |
| 26 | 0.17279531916716429 |
| 27 | 0.15661284329766167 |
| 28 | 0.1458672398248269 |
| 29 | 0.13387659325736107 |
| 30 | 0.15032607102199103 |
| 31 | 0.19675768059821186 |
| 32 | 0.15248851531996993 |
| 33 | 0.1397614756409377 |
| 34 | 0.13468227899397328 |
| 35 | 0.1336346905176409 |
| 36 | 0.15302321097248137 |
| 37 | 0.13160284786030219 |
| 38 | 0.1236481159601265 |
| 39 | 0.13197115866983392 |
| 40 | 0.13197115866983392 |
| 41 | 0.13197115866983392 |
| 42 | 0.09401472741555522 |
| 43 | 0.13556624961369462 |
| 44 | 0.11138064772476516 |
| 45 | 0.03255244610797139 |
| 46 | 0.0970489935975987 |
| 47 | 0.03646373759701251 |
| 48 | 0.08205014380085213 |
| 49 | 0.08205014380085213 |
| 50 | 0.05189693733437155 |
| 51 | 0.07626192948931135 |
| 52 | 0.10317389967748072 |
| 53 | 0.07287131080699025 |
| 54 | 0.13728372653219909 |
| 55 | 0.07626192948931135 |
| 56 | 0.07026192948931137 |
| 57 | 0.09045853311540049 |
| 58 | 0.06730921773503398 |
| 59 | 0.09125250593549589 |
| 60 | 0.08178559499403537 |

## 分析

### analysis-claude.md

# RUN run_20260521_143444 (Run 88) 分析（Claude 自己分析）

## 前提差分
なし。R88 は T115 cross-pair in-loop selection pressure (bool tie-break) + warmstart(0.1) + seed=68 の検証 run。R87(OFF) との A/B baseline。

## 観察事実（Facts）

### T115 動作確認
- selection_key_schema=v3_4_cross_pair_pressure、pressure_effective=True、cross_pair_runtime_mode=enabled。本番動作。
- Stage A/B/C = 2541/1930/619 (R87: 2495/1970/599、同等)。

### ★ 汎化結果と飽和の定量（cycle 7 の核心）
- Stage C ii_lite_pass=True: **0/619** (R87: 0/599)。受入基準 (汎化個体>0) 未達。
- cross_pair_aggregate_fitness (Stage B 通過 1930 個体): min -0.036 / p25 0.015 / **median 0.022** / p75 0.025 / **max 0.0485**。>0: 1874/1930。**>=0.15 (pass mean_sharpe_cross_min): 0**。
- ★ **gen 別 median 推移: gen0=0.0271 → gen60=0.0216 (上昇せず、むしろ微減・平坦)**。

## 解釈・推論（Interpretations）

### 1. bool tie-break は勾配を与えていない（飽和でなく無勾配）
当初「圧で >0 へ移動し飽和」と解釈したが、gen 別推移は **gen0 から既に ~0.027 で平坦**。warmstart motif が gen0 から僅か正の aggregate_fitness を持ち、bool tie-break (>0) は **gen0 から全個体=1 で飽和し勾配ゼロ**。∴ 圧は実質的に上昇圧を与えていない。
- 反証可能性: 連続値化で median が 0.022→max(0.0485)方向へ上昇すれば「bool だから無勾配」が確認される。上昇しなければ別要因。

### 2. ★ より深い構造的天井: 単一ペア学習の cross-pair fitness 上限 ~0.05 << pass 0.15
**max aggregate_fitness=0.0485** = 全 1930 個体中の最良でも pass 閾値 0.15 の 1/3。EUR_JPY 単一ペア in-sample 最適化で得られる戦略は、anchor ペアへの転移 fitness が構造的に低い (~0.05 天井)。
- これは「選択圧の弱さ」でなく「探索空間 (EUR_JPY 学習個体) の cross-pair 転移天井」の問題。連続値化で天井 ~0.05 まで登れても pass 0.15 には届かない可能性が高い。
- 反証可能性: 連続値化 R89 で max/median が 0.05 を大きく超え 0.15 方向へ向かえば天井仮説は棄却。0.05 付近で頭打ちなら天井確定 → multi-pair training 必須。

### 3. 根本解の方向: multi-pair training（fitness を複数ペアで評価）
cross-pair mean_sharpe≥0.15 の個体を得るには、GA が **複数ペアで学習**する必要がある (EUR_JPY 単一学習 → 稀な転移個体を選抜、では天井 ~0.05)。multi-pair training は本質的だが大規模 (fitness 評価が複数ペア分、メモリ/速度大)。

### 4. 禁止事項違反の兆候
なし。

## 次サイクル候補
- **[Critical] T115 連続値化 (cheap falsification 先行)**: selection_key に bool でなく cross_pair_aggregate_fitness 連続値を反映し勾配付与。R89 で median が天井 ~0.05 方向へ上昇するか・ii_lite_pass>0 が出るかを安価に検証。**天井仮説の falsification を兼ねる** (0.05 で頭打ちなら multi-pair へ)。低リスク (既存 T115 最小拡張、default OFF)。
- **[Warning] multi-pair training**: 連続値化が天井 ~0.05 で頭打ちなら本命。大規模のため連続値化の結果を見てから。
- **[Warning] 閾値引き上げ**: 汎化未達のため時期尚早。

## 全体判定
**CONCERN→CRITICAL_DRIFT (Codex、受入 KPI 0 のまま実効改善なし)** — T115 は動作したが bool tie-break は gen0 から飽和し上昇圧ゼロ。次は連続値化で勾配を与えつつ天井仮説を安価に falsification、頭打ちなら multi-pair training へ。

### 【Codex Round1 訂正反映】
- 「天井 ~0.05」は**言い過ぎ**: aggregate_fitness = mean_sharpe − 0.5·std なので max aggregate=0.0485 では **mean_sharpe_cross の上限を直接証明できない**。正しい主張は「aggregate 軸で pass 0.15 到達ゼロ + 現選択圧 (aggregate>0) が pass 基準 (mean_sharpe_cross≥0.15 ∧ min_sharpe≥-0.20 ∧ ratio≥0.8) と未整合の可能性」。
- → cycle 7 で **mean_sharpe_cross / min_sharpe_cross / ratio (pass 3 条件の実値) を archive 観測列に追加**し、(b1) 実 max mean_sharpe_cross が 0.15 近傍か (天井検証)、(b2) aggregate proxy が pass 基準と整合するか、を世代別記録 (Codex Warning1 メタ過学習ガード=代理目的ミスアライン検知)。
- 選択圧の連続値も aggregate_fitness でなく **mean_sharpe_cross (pass 基準直結)** を使う方が整合的か Codex 合議で確定。
- Codex Warning2: multi-pair training の最小 spike (2ペア短窓) でコスト/改善幅を先に見積もる (フル導入前)。
- まず gen 別 P(aggregate>0) 比率を確認し「bool 飽和」を確証 (反証: 比率が世代変動するなら飽和主因棄却)。

### analysis-codex.md

1. Facts要約  
- Run 88 は `pressure_effective=True` で T115 は配線上は有効化されたが、`ii_lite_pass=True` は **0/619**（Run 87 と同じく 0）。  
- Stage B の `cross_pair_aggregate_fitness` は `median=0.022 / max=0.0485 / >=0.15 が0`、gen0→gen60 で中央値はむしろ微減（0.0271→0.0216）。  
- 受入条件（graduation）に対して改善シグナルは観測されない。

2. 解釈（反証可能性つき）  
- (a) 妥当。`bool(margin>0)` は gen0 でほぼ飽和していれば選択圧が消えるため、平坦系列と整合。  
反証条件: `margin>0` 比率が世代で十分変動しているなら「飽和」主因は棄却。まず世代別 `P(margin>0)` を確認。  
- (b) 現時点では**言い過ぎ**。`aggregate = mean - 0.5*std` なので、`max aggregate=0.0485` だけでは `mean_sharpe_cross` の上限を直接は証明できない。  
妥当なのは「aggregate軸では0.15到達個体が皆無で、現行選択圧が受入基準に整合していない可能性が高い」。  
反証条件: 実際に `max mean_sharpe_cross` が 0.15 近傍/超過なら「天井~0.05」仮説は棄却。  
- (c) 段階戦略は妥当。まず連続値化で cheap falsification を行い、改善ゼロなら multi-pair training へ進むのが低リスク。即 multi-pair は工数・副作用が大きい。

3. 次サイクル候補  
- Critical（1個）: T115 を連続値選択圧に拡張（default OFF）。`selection_key` に `aggregate_fitness` の連続値 tie-break を追加し、飽和回避。  
検証は seed固定A/B（OFF vs bool vs continuous）で `ii_lite_pass数 / max mean_sharpe_cross / gen傾き` 比較。  
- Warning（1）: 目的整合の監視追加（メタ過学習ガード）。`aggregate` だけでなく `mean_sharpe_cross` と pass3条件の到達率を世代別で常時記録し、代理目的のミスアラインを早期検知。  
- Warning（2）: multi-pair training の最小設計スパイク（小規模2ペア・短窓）を先に実施し、フル導入前に計算コストと改善幅を見積もる。

4. 全体判定  
- **CRITICAL_DRIFT**（受入KPIが 0 のまま、かつ T115 の実効改善が確認できないため）。

