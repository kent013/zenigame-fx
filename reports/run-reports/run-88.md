# Run 88 — run_20260521_143444

**Generated**: 2026-05-21T14:34:45.216084+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 3.628340552176085 / threshold 1.0
- ✅ **total_pnl**: 55340.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.8992214069245086 / threshold 20.0
- ✅ **trade_count**: 50 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 619 (= Stage C 単独通過数)
- **mission_candidate_count**: 619 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

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

- name: `g60_i95`
- generation: 60
- fitness: **0.17996347441527544**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 50
- total_pnl: 55340.0
- sharpe: 0.19796347441527543
- sortino: —
- calmar: —
- max_drawdown_pct: 1.8992214069245086

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3333
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2541
- Stage B pass: 1930
- Stage C pass: 619

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 619 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 230 | 37.2% |
| 51 | 39 | 6.3% |
| 52 | 70 | 11.3% |
| 53 | 42 | 6.8% |
| 54 | 67 | 10.8% |
| 55 | 65 | 10.5% |
| 56 | 32 | 5.2% |
| 57 | 9 | 1.5% |
| 58 | 19 | 3.1% |
| 59 | 7 | 1.1% |
| 60 | 8 | 1.3% |
| 61 | 6 | 1.0% |
| 62 | 6 | 1.0% |
| 63 | 5 | 0.8% |
| 64 | 7 | 1.1% |
| 65 | 1 | 0.2% |
| 67 | 1 | 0.2% |
| 68 | 4 | 0.6% |
| 70 | 1 | 0.2% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 230 | 389 |
| median total_pnl | 56040.0000 | 58770.0000 |
| median trade_sharpe_stage_c | 0.2507 | 0.2395 |
| median max_drawdown_pct | 1.8992 | 1.8105 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2541 | 1930 | 619 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2541 | 1930 | 619 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2749, median=1.0000, std=0.4472, min=0, max=2
- n_nodes: n=5856, mean=4.0967, median=4.0000, std=1.6433, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1886, mean=0.9185, median=0.9511, std=0.0939, min=0.2903, max=0.9833
- best mission_score: **0.9833** (`g51_i10`, gen=51, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2541, mean=0.2458, median=0.2424, std=0.0776, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2541, mean=31.5222, median=34, std=6.1823, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2539, mean=0.5638, median=0.5882, std=0.1356, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2541, Stage B pass = 1930, failures = 611 (primary_sum = 611)

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
| `positive_fold_ratio_effective<min` | 270 |
| `median_oos_total_pnl<min` | 181 |
| `sum_oos_total_pnl<min` | 101 |
| `n_fold_effective_below_profit_safe_min` | 59 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 270 |
| `median_oos_total_pnl<min` | 451 |
| `sum_oos_total_pnl<min` | 505 |
| `n_fold_effective_below_profit_safe_min` | 183 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 14 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=1930, None=3926

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 1.9% (109/5856)
- best 個体 trade_count: 50
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=611, stage_a_only=3315, stage_b_evaluated=1311, stage_c_evaluated=619
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3315, mean=-202689.3454, median=-23590.0000, std=358444.7481, min=-1001680.0000, max=53180.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3206): n=3206, mean=-209580.5303, median=-24790.0000, std=362500.5222, min=-1001680.0000, max=53180.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2541): n=2541, mean=25789.7757, median=23780.0000, std=26458.7344, min=-1000250.0000, max=96390.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g47_i76` | 47 | tier1_EUR_JPY | EUR_JPY | 0.3116 | 0.3341 | ✅ | ❌ | ❌ | 41 | — |
| 2 | `g30_i7` | 30 | tier1_EUR_JPY | EUR_JPY | 0.3062 | 0.3332 | ✅ | ❌ | ❌ | 41 | — |
| 3 | `g41_i45` | 41 | tier1_EUR_JPY | EUR_JPY | 0.2871 | 0.3171 | ✅ | ❌ | ❌ | 38 | — |
| 4 | `g26_i91` | 26 | tier1_EUR_JPY | EUR_JPY | 0.2816 | 0.3096 | ✅ | ❌ | ❌ | 40 | — |
| 5 | `g50_i82` | 50 | tier1_EUR_JPY | EUR_JPY | 0.2686 | 0.2821 | ✅ | ❌ | ❌ | 57 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.07391491636745944 |
| 2 | 0.07391491636745944 |
| 3 | 0.1302730946292371 |
| 4 | 0.07391491636745944 |
| 5 | 0.14126771045037836 |
| 6 | 0.17080370960081656 |
| 7 | 0.2531909783675465 |
| 8 | 0.18034404395774 |
| 9 | 0.14832221429922715 |
| 10 | 0.15667228692796994 |
| 11 | 0.17046315813123114 |
| 12 | 0.1942400800955573 |
| 13 | 0.15637031160364226 |
| 14 | 0.20111033327544744 |
| 15 | 0.19081813262618041 |
| 16 | 0.19081813262618041 |
| 17 | 0.15753616880044222 |
| 18 | 0.1893975017014446 |
| 19 | 0.1682062720926354 |
| 20 | 0.16978559154098896 |
| 21 | 0.1729356685523249 |
| 22 | 0.19134641642050565 |
| 23 | 0.19886658881200953 |
| 24 | 0.21539282575187627 |
| 25 | 0.19454556712107496 |
| 26 | 0.281557418547064 |
| 27 | 0.23597652999527371 |
| 28 | 0.252611674605025 |
| 29 | 0.18693668294823274 |
| 30 | 0.30617672970245446 |
| 31 | 0.22433977987307524 |
| 32 | 0.1824526656159671 |
| 33 | 0.20896689321231623 |
| 34 | 0.2066996400299893 |
| 35 | 0.21670344220760326 |
| 36 | 0.21670344220760326 |
| 37 | 0.21670344220760326 |
| 38 | 0.21670344220760326 |
| 39 | 0.21389394252854405 |
| 40 | 0.2061786894681384 |
| 41 | 0.2870999598263846 |
| 42 | 0.2061786894681384 |
| 43 | 0.1777309659190881 |
| 44 | 0.1820785348206846 |
| 45 | 0.19534970479442454 |
| 46 | 0.18566803833940831 |
| 47 | 0.3115592532370642 |
| 48 | 0.1798876009489311 |
| 49 | 0.1798876009489311 |
| 50 | 0.2685705571792769 |
| 51 | 0.21499338770711734 |
| 52 | 0.20258915694270346 |
| 53 | 0.16987942360724914 |
| 54 | 0.21117868649158522 |
| 55 | 0.23497479896010132 |
| 56 | 0.23497479896010132 |
| 57 | 0.1946789792303151 |
| 58 | 0.18571404060003371 |
| 59 | 0.2516049934388381 |
| 60 | 0.18832990411069175 |

## 分析

### analysis-claude.md

# RUN run_20260521_061439 (Run 87) 分析（Claude 自己分析）

## 前提差分
なし。R87 は T114 cross-pair enable + warmstart(0.1, motif=R86) + seed=68 の検証 run。

## 観察事実（Facts）

### T114 cross-pair enable の動作確認（cycle 5 の主眼、成功）
- cross_pair_runtime_mode = **enabled**（anchors = EUR_USD + USD_JPY、n_pairs=3）。
- ii_lite_pass が None→bool 化: 全体 {None:3886, False:1970}、Stage B 通過群は全件 False に評価された（cross-pair が実走）。

### ★ 汎化定量化（cycle 6 の核心）
R87 Stage A/B/C = 2495/1970/**599**。Stage C 通過 599 個体の cross-pair:
| 指標 | 値 |
|------|-----|
| ii_lite_pass=True（cross-pair 汎化） | **0 / 599** |
| graduation | **0** |
| mission_signed_margin_c_shadow | **中央値 -1.367**、min -15.622、max 0.919、**正は 4/599 のみ** |
| mission_signed_margin_b_shadow | 中央値 -3.147（Stage B 期間ではさらに悪い） |

→ EUR_JPY の mission/Stage-C 個体は **0% が cross-pair 汎化**。しかも margin は限界的失敗（≈0）でなく **深い負（中央値 -1.37）** = 強い in-sample 過学習。

## 解釈・推論（Interpretations）

### 1. mission 個体は EUR_JPY 特化の過学習で、汎化フロンティアは未踏（決定的確証）
4-5 サイクルで mission を 達成可能(R83)+cost-robust(R85)+再現可能(R86) にしたが、R87 で **多ペア汎化は 0/599** と確定。warmstart は in-sample winner を増幅するだけで汎化に寄与しない（設計時に明記済の通り）。margin median -1.37 は「あと少しで通る」でなく「全く通らない」水準。
- 反証可能性: 汎化施策後に ii_lite_pass=True が 1 個体でも出れば前進。0 のままなら施策が効いていない。

### 2. 根本原因: GA fitness/selection に汎化への選択圧がゼロ
- 現 fitness_pen = EUR_JPY in-sample sharpe − α·size。GA は EUR_JPY 単一ペアの in-sample 成績のみで選択 → 純粋な in-sample winner に収束。
- cross-pair は **最終 Stage C でしか評価されない**（GA ループ内に汎化シグナルが入らない）。∴ GA は汎化方向に一切探索圧を受けない。
- これは「機能の名前に立ち返れ」: graduation = 多ペア汎化ゲートだが、GA はそのゲートを意識せず探索している。

### 3. 汎化を促す構造介入が次の施策（cycle 6 の方向）
GA に汎化シグナルを与える必要がある。候補:
- **(a) multi-pair training**: fitness を複数ペアの成績で評価（構造的・本質的だが大規模・メモリ/速度大。R87 は cross-pair 最終評価だけで ~7h）。
- **(b) cross-pair を in-loop selection pressure 化**: GA 選択キー or fitness に cross-pair 結果を反映（最終 gate でなく探索中に汎化を促す。中規模だが cross-pair eval ×3 を毎世代は高コスト → 間引き/近似が要点）。
- **(c) overfit penalty**: in-sample 特化を fitness で抑制（安価な汎化 proxy が必要。cross-pair eval が高コストなので proxy 設計が鍵）。

### 4. 禁止事項違反の兆候
なし。汎化施策は評価の厳格化（緩和でない）。閾値引き上げは汎化達成後。

## 次サイクル候補
- **[Critical] 汎化を促す GA 構造介入**: (b) cross-pair in-loop selection pressure を軸に、コスト対策（間引き世代・top-N のみ cross-pair eval・近似 proxy）込みで設計。低リスク段階導入（default OFF、まず弱い圧から）。
- **[Warning] (a) multi-pair training**: より本質的だが大規模。コスト次第で将来。
- **[Warning] (c) overfit penalty proxy**: 安価な汎化 proxy（例: regime/sub-period 分割の成績分散）を fitness に。cross-pair eval なしで近似できれば低コスト。

## 全体判定
**OK（T114 成功、汎化フロンティアを定量化）** — mission は in-sample で 達成可能+cost-robust+再現可能 だが cross-pair 汎化 0/599（margin median -1.37 = 深い過学習）。次は GA に汎化への選択圧を与える構造介入（cross-pair in-loop pressure / multi-pair training / overfit penalty proxy）を低リスク段階導入で。コスト（cross-pair eval ×3 は高い）が設計の主制約。

### analysis-codex.md

1. Facts要約  
- Run 87 は `cross_pair_runtime_mode=enabled` で実行され、`ii_lite_pass` は `None→bool` に正常化。  
- Stage C 599 個体の `ii_lite_pass` が **0/599**、`graduation=0`。  
- `mission_signed_margin_c_shadow` 中央値 `-1.367`（正は 4/599）で、「閾値近傍の失敗」ではなく大幅な負側集中。

2. 解釈（反証可能性つき）  
- (a) 診断妥当性: 「深い過学習 + GAの汎化選択圧ゼロ」は現時点で妥当。  
  反証条件は「実装/データ不整合で cross-pair が構造的に落ちている」ことだが、`enabled` で値が連続分布し一部正値もあるため“常時バグ落ち”仮説は弱い。  
- (b) 高コスト下の実行可能策: 最有力は **(b) in-loop selection pressure の疎評価導入**。  
  全個体3ペア評価は重すぎるため、`top-Nのみ` + `世代間キャッシュ` + `M世代ごと再評価` で圧を入れるのが現実的。  
- (c) 安価proxyの成立性: **限定的に成立**（過学習抑制の前段フィルタとして有効）。  
  ただし proxy 単独は「cross-pair汎化」の代理として不完全。反証は「proxy改善しても `ii_lite_pass` が増えない」場合で、その時点で棄却すべき。

3. 次サイクル候補  
- Critical（1個）: **opt-in の段階導入で (b) を実装**。`default不変(OFF)` のまま、Stage B上位候補にのみ cross-pair shadow を疎注入し、選抜キーに“弱く”反映（閾値緩和なし）。目的は loop 停止回避と汎化圧の最小注入。  
- Warning（1）: (c) の proxy（sub-period安定性/分散ペナルティ）は **prefilter専用** に限定し、最終判定へ直結させない（Reactive Parametric禁止）。  
- Warning（2）: 変更評価は固定 seed 複数本で A/B 比較し、`ii_lite_pass率` と `mission_signed_margin_c_shadow` の改善が無ければ即ロールバック（閾値は上げるのみ、緩和なし）。

4. 全体判定  
- **CRITICAL_DRIFT**（達成指標に対し探索圧がミスマッチのため）。

