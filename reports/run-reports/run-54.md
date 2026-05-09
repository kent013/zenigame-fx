# Run 54 — run_20260508_224819

**Generated**: 2026-05-08T22:49:59.479901+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.041957518015710744 / threshold 1.0
- ❌ **total_pnl**: 6270.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 61 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 100

## Best 個体

- name: `g52_i27`
- generation: 52
- fitness: **0.03745751801571075**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 61
- total_pnl: 6270.0
- sharpe: 0.041957518015710744
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1111
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1439
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1439 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1439 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6520, median=2.0000, std=0.4771, min=0, max=2
- n_nodes: n=5856, mean=2.8593, median=3.0000, std=1.3899, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1439, mean=0.1123, median=0.1111, std=0.1100, min=0.0000, max=0.4444
- dsr: n=0
- n_fold_effective (Stage A pass): n=1439, mean=8.3968, median=10, std=2.4575, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=1415, mean=0.1489, median=0.1111, std=0.1615, min=0.0000, max=0.8000

## Stage B failure reason 集計

- Stage A pass = 1439, Stage B pass = 0, failures = 1439 (primary_sum = 1439)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1437 |
| `positive_fold_ratio<min` | 2 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 24 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1437 |
| `positive_fold_ratio<min` | 1439 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 5.5% (321/5856)
- best 個体 trade_count: 61
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1439, stage_a_only=4417
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4417, mean=-281407.2606, median=-33490.0000, std=419953.0837, min=-1009680.0000, max=21670.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4096): n=4096, mean=-303460.9058, median=-36200.0000, std=428356.6288, min=-1009680.0000, max=21670.0000
  - うち PnL=0 個体: 7 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1439): n=1439, mean=10639.0202, median=11690.0000, std=46884.2237, min=-1000410.0000, max=27800.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g57_i15` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2354 | 0.2669 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g42_i54` | 42 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |
| 3 | `g43_i0` | 43 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |
| 4 | `g44_i0` | 44 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |
| 5 | `g45_i0` | 45 | tier1_EUR_JPY | EUR_JPY | 0.1915 | 0.2095 | ✅ | ❌ | ❌ | 56 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.04934400993968757 |
| 1 | 0.11284516344650065 |
| 2 | 0.04934400993968757 |
| 3 | 0.04934400993968757 |
| 4 | 0.16430326896687092 |
| 5 | 0.08233710302196119 |
| 6 | 0.08233710302196119 |
| 7 | 0.08233710302196119 |
| 8 | 0.08233710302196119 |
| 9 | 0.11273559020475453 |
| 10 | 0.11273559020475453 |
| 11 | 0.11273559020475453 |
| 12 | 0.11873559020475453 |
| 13 | 0.11873559020475453 |
| 14 | 0.11873559020475453 |
| 15 | 0.11873559020475453 |
| 16 | 0.1540206798053428 |
| 17 | 0.1524495165094141 |
| 18 | 0.1524495165094141 |
| 19 | 0.1524495165094141 |
| 20 | 0.17314583341557252 |
| 21 | 0.17764583341557252 |
| 22 | 0.17764583341557252 |
| 23 | 0.17764583341557252 |
| 24 | 0.17800401537537647 |
| 25 | 0.17800401537537647 |
| 26 | 0.17800401537537647 |
| 27 | 0.17800401537537647 |
| 28 | 0.1801105561440569 |
| 29 | 0.1801105561440569 |
| 30 | 0.1801105561440569 |
| 31 | 0.1801105561440569 |
| 32 | 0.18304677149532644 |
| 33 | 0.18853988155509138 |
| 34 | 0.18936428912448988 |
| 35 | 0.18936428912448988 |
| 36 | 0.18936428912448988 |
| 37 | 0.18936428912448988 |
| 38 | 0.18936428912448988 |
| 39 | 0.18936428912448988 |
| 40 | 0.18936428912448988 |
| 41 | 0.18936428912448988 |
| 42 | 0.1915464011650908 |
| 43 | 0.1915464011650908 |
| 44 | 0.1915464011650908 |
| 45 | 0.1915464011650908 |
| 46 | 0.1915464011650908 |
| 47 | 0.1915464011650908 |
| 48 | 0.1915464011650908 |
| 49 | 0.1915464011650908 |
| 50 | 0.1915464011650908 |
| 51 | 0.1915464011650908 |
| 52 | 0.1915464011650908 |
| 53 | 0.1915464011650908 |
| 54 | 0.1915464011650908 |
| 55 | 0.08238101303303076 |
| 56 | 0.06793026642602955 |
| 57 | 0.2353886466021871 |
| 58 | 0.13724729881770123 |
| 59 | 0.06091489955926364 |
| 60 | 0.058253912145119324 |

## 分析

### analysis-claude.md

# RUN run_20260507_142410 (run-53) 分析 — Claude 自己分析

**Generated**: 2026-05-09 07:10 JST
**run_id**: `run_20260507_142410` (run-53)
**dataset**: EUR_JPY 2025-10-01 → 2026-04-01 (183,403 bars)
**ga_config**: pop=96, gens=60, mutation=0.5, crossover=0.7, tournament=3, elite=2, max_clause=2, **seed=100**
**stage_gate**: stage_a_threshold=-0.0172, wf_train=20d, wf_test=18d, fold_robust=0.55, median_oos>=0.05, pfre>=0.6

---

## 前提差分

なし (前提全件 verified)。

---

## 観察事実 (Facts)

### F1. Stage 通過数

| Stage | pass | total | rate |
|---|---:|---:|---:|
| A | 1,439 | 5,856 | 24.6% |
| B | **0** | 5,856 | 0.0% |
| C | **0** | 5,856 | 0.0% |
| graduated | **0** | 5,856 | 0.0% |

### F2. Best fitness 個体

- name: `g57_i15` @ tier1_EUR_JPY / EUR_JPY / gen 57
- fitness_pen=**0.235**、 fitness_raw=0.267
- trade_count=32、 total_pnl=15,530、 sharpe=NaN
- active_clause=2、 n_nodes=2
- **stage_a_pass=True、 stage_b_pass=False、 stage_c_pass=False**
- **n_fold_effective=0、 pfre=NaN、 fold_sign_ratio=0**
- stage_b_reason_codes=`median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable`

### F3. Stage A pass 個体の指標分布 (n=1,439)

- trade_count: median=62、 p25=56、 p75=82、 max=3,469 (extreme outlier)
- total_pnl: median=11,690、 max=**27,800**、 min=-1,000,410
- positive_fold_ratio_effective: median=0.111、 mean=0.149、 max=0.800
- n_fold_effective: median=10、 max=10
- fold_sign_ratio: median=0.111、 max=0.444

### F4. trade_count vs Stage B pass 関係 (Stage A pass)

| trade_bin | count | sb_pass | sb_rate | pfre_med | pnl_max |
|---|---:|---:|---:|---:|---:|
| (20,30] | 3 | 0 | 0% | NaN | 6,270 |
| (30,50] | 145 | 0 | 0% | 0.0 | 26,640 |
| (50,80] | **909** | 0 | 0% | 0.1 | 27,530 |
| (80,120] | 330 | 0 | 0% | 0.2 | 27,800 |
| (120,200] | 43 | 0 | 0% | 0.2 | 11,860 |
| (200,1000] | 6 | 0 | 0% | 0.2 | 19,630 |

### F5. Mission-eligible @ Stage A 個体数

- (Stage A pass + trade>=50 + total_pnl>=50,000) = **0 件** (run-52 では 7 件、 大幅退化)

### F6. Primitive 使用率 (Stage A pass + trade>=50 個体、 n=1,305)

| primitive | name | count | rate |
|---|---|---:|---:|
| F4 | ADXTrend | 1,286 | **99%** |
| F13 | ReturnAutocorrLag | 1,174 | **90%** |
| F11 | MeanReversionRange | 503 | 39% |
| P10 | (pair-specific) | 292 | 22% |
| M4 | EconomicEventGate | 122 | 9% |
| M5 | VIXRegimeGate | 98 | 8% |
| M3 | SpreadConditionGate | 93 | 7% |
| F10 | ZScoreRevert | 86 | 7% |
| F6 | SessionMomentum | 37 | **3%** |
| F8 | BollingerRevert | (低位) | <2% |
| M2 | SessionGate | 21 | 2% |

**比較 (run-52 / seed=42)**: F6=91%、 F8=89%、 M2=90%、 F4/F13/F11 はいずれも <5%

### F7. Population diversity (clauses-level)

- 全 60 世代を通じて diversity 0.823 - 1.0 の範囲 (健全)
- per-10-gen sample: gen 0 で 1.0、 gen 50 で 0.875、 gen 60 で 0.896

### F8. Top clone clusters (clauses-level hash)

- 72f73654: 112 個体 (最大 clone group)
- 2f1d6ba0: 37 個体
- c3012274: 35 個体
- 197e6b96: 32 個体
- bb99cb28: 29 個体

### F9. Stage B failure reason 分布 (Stage A pass + Stage B fail = 1,439)

| reason | count | rate |
|---|---:|---:|
| `median_oos_sharpe<min` | 1,439 | 100% |
| `positive_fold_ratio<min` | 1,439 | 100% |
| `all_folds_unavailable` | 24 | 1.7% |

→ 全 Stage A pass 個体が `median + positive_fold_ratio` 両方で blocked。

### F10. Lane 別落下分布

tier1_EUR_JPY のみ (single instrument RUN)。 6,856 → A=1439 → B=0 → C=0。

### F11. RUN 設定 / コスト

- elapsed: 90 min (run-53 報告と一致)
- peak RSS: 17,462 MB (worker 2 並列)
- cross_pair_runtime_mode: `skipped_single_instrument`

---

## 解釈・推論 (Interpretations)

### I1. seed=100 領域は seed=42 領域とは **完全に別 attractor**

**事実**: seed=42 (run-52) は (F6=91% + F8=89% + M2=90%) に集中。 seed=100 (run-53) は (F4=99% + F13=90% + F11=39%) に集中。 共有 primitive はほぼゼロ。

**解釈**: seed が決めるのは「primitive landscape の global structure 上のどの局所最適に到達するか」 で、 seed=42 と seed=100 は完全に異なる山頂に登っている。 これは前 session の Codex 議論で指摘された「seed sensitivity の真因は mode collapse + threshold 近接」 仮説をさらに精緻化する観察 — **複数の mode が存在し、 seed が初期 sampling で決定的影響を与える**。

**反証可能性**: seed=23 (run-50) の primitive 分布も確認。 seed=23/42/100 で 3 つの全く異なる primitive set に collapse していれば「seed が選ぶ局所最適は離散的」 仮説が支持される。 共通 primitive が見つかれば「共通 attractor が地形の中央にある」 別仮説。

### I2. seed=100 領域は **profitability が seed=42 領域より構造的に低い**

**事実**: seed=100 で max total_pnl (Stage A pass + trade>=50) = **27,800**。 seed=42 では 58,830 (= 2.1x)。 mission criteria 50,000 まで 22,200 不足。

**解釈**: seed=100 の primitive set (F4=ADXTrend + F13=ReturnAutocorrLag + F11=MeanReversionRange) は EUR_JPY M1 6 ヶ月の特性に対し、 seed=42 の (F6=SessionMomentum + F8=BollingerRevert + M2=SessionGate) より profitability が低い。 これは「seed=100 領域の attractor は地形の最低点に近い」 ことを示唆。

**反証可能性**: 同 primitive set (F4+F13+F11) で seed/mutation を変えて改めて GA を走らせ、 max PnL が常に <50,000 にとどまるか verify。 上振れすれば「primitive set の profitability 上限」 仮説が支持されない。

### I3. T091 (median 0.025 緩和) の効果は seed=100 では **限定的**

**事実**: run-53 の Stage A pass 全 1,439 個体が `median_oos_sharpe<min` AND `positive_fold_ratio<min` の両方で blocked。 一方 run-52 では 7 個体が median のみ blocked。 run-53 の pfre 中央値=0.111 は run-52 の 0.40 (Stage A pass) と大きく異なる。

**解釈**: T091 で median_oos_sharpe_min を 0.025 に下げても、 run-53 の個体は positive_fold_ratio<0.6 でも別途 reject される。 → seed=100 では T091 単独では graduate に繋がらない。

**反証可能性**: T091 適用後の archive replay で、 median<0.05 だが median>=0.025 を満たす個体のうち、 positive_fold_ratio>=0.6 を併せて満たす個体が存在するか集計。 0 件なら本仮説は支持される。

### I4. positive_fold_ratio (pfre) の中央値が seed=100 で **0.11**、 seed=42 で **0.40** という差は何を意味するか

**事実**: run-53 の Stage A pass 個体は全 fold で利益符号が positive な fold が 11% しかない (= 9 fold 中 1 fold)。 run-52 では 40% (4 fold)。

**解釈**: F4+F13+F11 の戦略は fold 期間 18 日の中で 「短期で稼いで長期で吐き出す」 / 「不安定な短期トレード」 になっている可能性。 一方 F6+F8+M2 の戦略は fold ごとに均等な利益分布を持つ。 seed=100 の個体は単発の大トレードで Stage A 60 日 PnL を稼いでいるだけで、 fold-by-fold ではノイズに近い。

**反証可能性**: best 個体 g57_i15 の trade timestamps 分布を可視化し、 60 日中に集中して取引している期間があるか verify。 集中期間があれば本仮説支持。

### I5. trade_count_full_dataset 切替の効果も限定的

**事実**: run-53 では Stage A trade>=50 個体が 1,305 件 (90%)。 mission-eligible (trade>=50 + pnl>=50,000) は 0 件。

**解釈**: T091 施策 2 (trade_count_full_dataset 切替) は selection feasibility の参照スコープを広げる効果はあるが、 seed=100 領域では PnL が構造的に不足しているため graduate に繋がらない。

### I6. mode collapse (best 個体 g57_i15 の特殊性)

**事実**: best 個体 (fp=0.235) は trade=32、 n_fold_effective=0、 all_folds_unavailable。

**解釈**: best とされる個体すら fold 評価不能 (trade<10 per fold で全 fold で trade_count_min 不達)。 GA は trade=32 でかつ Stage A 60 日で総 PnL 15,530 を稼ぐ「短期集中トレーダー」 を best 候補とした。 これは feasibility (trade>=50) の selection 圧が現状 selection_score lex 順序で位置 3 (stage_b_pass_and_feasible) に依存するが、 全員 stage_b_pass=False のため位置 3 の値は 0 となり、 fitness_pen が支配 → 結果として **trade<50 個体が best に上がる**。

**反証可能性**: T091 施策 2 適用後の archive replay で best 個体が trade>=50 となるか verify。 trade<50 のままなら fitness_pen 支配が継続、 selection_score 構造の追加修正が必要。

---

## 次サイクル候補

### [Critical] T091 実装を最優先で進める

事実: run-53 で Stage B pass=0、 graduate=0、 mission-eligible=0。 T091 (Stage B gate redesign Phase 1、 commit 4624c7a) は概念設計 + 詳細設計が Codex APPROVED 済みで実装段階に進める水準。

予測効果:
- run-52 archive replay で 1+ 件 Stage B pass 出現 (期待 H_A1' confirmed)
- run-53 (seed=100) では graduate に繋がらない可能性が高いが、 archive replay で gate 機能の verify は可能
- 次 RUN (seed=42 推奨) で graduate 出現の可能性がある

### [Warning] seed=42 を次 RUN に固定

事実: seed=23 / 42 / 100 で primitive collapse 領域が大きく異なり、 max PnL も 48,640 / 58,830 / 27,800 と 2 倍以上の差。 seed=42 が現状最も mission criteria に近い。

提案: 次 RUN は `--seed 42 --generations 60` で T091 適用後の効果検証。 multi-seed batch は Phase 1 完了後に検討。

### [Warning] mode collapse 介入を Phase 1 並行タスクとして登録

事実: run-53 で F4+F13+F11、 run-52 で F6+F8+M2、 run-50 で別の attractor。 17 primitive のうち 3 個に collapse する現象は seed 不変。

提案: T091 完了後すぐに **niching (clauses ハッシュ duplicate penalty)** を Phase 1 並行タスクとして詳細設計開始。 Codex 議論結果 (codex-discussion-summary.md Q3 推奨 B≻D≻C≻E≻A) に従う。

### [Suggestion] best 個体 g57_i15 の調査 (Stage A trade timestamps 集中度)

I4/I6 反証検証のため、 g57_i15 の trade timestamps を archive から抽出し、 60 日中の取引分布を可視化。 集中期間があれば「短期集中トレーダー」 仮説が支持され、 selection_score 修正の根拠強化。

### [Suggestion] T091 の RUN 後検証用に baseline を確定

run-53 を baseline として保持し、 T091 適用後に同 seed=100 で再 RUN して Stage B pass 数の差分を測定。 (Layer 1 archive replay と Layer 2 RUN 検証を分離)

---

## 全体判定

**CONCERN** (graduate=0 が続く中で mode collapse の構造が seed 別に複数存在することが判明)

T091 の実装と niching 介入の両輪で進める必要がある。 現状 T091 のみでは graduate 達成は未保証、 mode collapse 介入を並行で進めることで効果を相乗化する。

---

## 滞留 TODO 判断

T091 は 2026-05-08 13:17 追加 (前 session 末尾)、 直近 close (T090 は 2026-05-05 22:15) より新しい。
→ **滞留なし**。

## Conditional 昇格チェック

Conditional テーブル 0 件。 → スキップ。

## TODO 由来の改善候補

| ID | タイトル | 優先度 | target_metric | failure_mode | causal_path | falsification | success_criterion | 判定 | 理由 |
|---|---|---|---|---|---|---|---|---|---|
| T091 | Stage B gate redesign Phase 1 | High | Sharpe + Total PnL (live_criteria 4 軸の必要条件) | run-53 で Stage A pass=1439 全員が `median_oos_sharpe<min` AND `positive_fold_ratio<min` で blocked、 Stage B pass=0 / graduate=0 | Lo (2002) SE 公式から median_oos SE ≈ 0.10、 現行 0.05 閾値が真値 SR=0.05 個体の検出力 50% に固定。 0.025 で 60% に拡張。 trade_count_full_dataset で selection 圧を Stage A 60d 高頻度バイアスから整合化。 stage_partition_guard で holdout 不整合を顕在化 | run-52 archive replay (pfre>=0.6 の 2 件 g70_i9 / g83_i12) が新 gate でも 0 件 pass なら H_A1' 反証、 別根因再調査 | Layer 1: archive replay で 1+ 件 Stage B pass + 新 archive 列 (trade_count_*_dataset) 非 null。 Layer 2: 次 RUN で trade_count_full_dataset>=50 + total_pnl>=50,000 個体 1+ 件出現 | 採用候補 | 設計 v3 が Codex APPROVED (Round 5)、 incremental 実装で 3 段階分割 (median 0.025 → trade_count_full_dataset → partition guard)。 |

(Codex 推奨の 4 候補 — seed-robustness 検証 / n_fold_eff=0 ガード / primitive entropy / cross-pair 復帰 — は新規 TODO 登録対象として Phase B-2 で議論)

### analysis-codex.md

**観察事実 (Facts)**  
- Stage通過は `A=1,439/5,856 (24.6%)`, `B=0`, `C=0`, `graduated=0`。  
- Stage B失敗理由は `median_oos_sharpe<min` と `positive_fold_ratio<min` がともに `1,439/1,439`。  
- Stage A通過群の `positive_fold_ratio_effective` は中央値 `0.111`、`n_fold_effective` 中央値 `10`。  
- Mission条件 (`trade>=50 && total_pnl>=50,000`) をStage Aで満たす個体は `0`（run-52は`7`）。  
- best個体 `g57_i15` は `trade=32`, `total_pnl=15,530`, `n_fold_effective=0`, `pfre=NaN`。  
- primitive使用は run-53で `F4(99%)`, `F13(90%)` 偏重、run-52(seed=42)では `F6/F8/M2` 高率で分布が大きく逆転。  
- clauses-level diversityは `0.823-1.0` で極端な単一クローン化は未確認。  
- cross-pairは `skipped_single_instrument` で実行されていない。  

**解釈・推論 (Interpretations)**  
- 仮説H1: 主ボトルネックは「Stage B閾値」単体ではなく、「Stage Aで生成される候補のOOS符号安定性不足（pfre低位）」が主因。  
- H1の反証可能性: もしH1が偽なら、同じseed=100でも `positive_fold_ratio` 分布が高く、Stage B通過が閾値調整なしで一部発生するはず。  
- 仮説H2: run-53の劣化は「seed依存のattractor移動」により、利益上限の低いprimitive領域に収束した可能性が高い。  
- H2の反証可能性: もしH2が偽なら、seedを変えても primitive構成と `max_pnl` がほぼ不変になるはず。  
- 仮説H3: best個体が `n_fold_effective=0` でも上位化される設計経路があり、短期集中・評価不能個体が探索を汚染している可能性。  
- H3の反証可能性: もしH3が偽なら、上位個体で `n_fold_effective=0` は稀で、best近傍ほどfold有効本数が増えるはず。  
- 禁止事項兆候: 「イントラデイ逸脱」「live_criteria緩和」はデータ上は未確認。ただし `trade_count` 低位個体の上位化は「取引回数削減方向」へのドリフト兆候。  
- primitive偏在と多様性: 個体多様性は見かけ上維持される一方、機能多様性（primitive空間）が崩れているため、探索の実質多様性は低下。  
- cross-pair妥当性: 実行自体が無いため妥当性評価は **INCONCLUSIVE**（C8）。  

**I1-I6 独立判定（C9: falsification-first）**  
- I1 賛成。反証条件: 複数seedで primitive分布が再収束すること。  
- I2 賛成。反証条件: seed=100近傍で `max_pnl>=50,000` が再現的に出ること。  
- I3 概ね賛成。反証条件: `median_oos` 緩和のみで `positive_fold_ratio` も同時改善しStage B通過が増えること。  
- I4 賛成（ただし因果は保留）。反証条件: pfre低位でも mission候補が安定的に出ること。  
- I5 賛成。反証条件: `trade_count_full_dataset` 切替だけで `max_pnl` 分布が有意改善すること。  
- I6 賛成。反証条件: best選抜ロジックで `n_fold_effective=0` 個体が自然に排除される挙動が確認されること。  

**C7サンプルサイズ評価**  
- `n=1,439`（Stage A pass）と `n=1,305`（trade>=50）は分布比較に十分。  
- `n=7`（run-52 mission-eligible）は因果主張には弱く、再現確認が必要。  

**次サイクル候補**  
1. Critical: `seed-robustness前提のStage B再設計検証`（固定少数seed比較で pfre/positive_fold_ratio 分布を先に反証。閾値調整前に「候補品質問題かゲート問題か」を分離）。  
2. Warning: `best選抜の有効fold下限ガード`（`n_fold_effective=0` 上位化を抑止し、評価不能個体の選好を切る）。  
3. Warning: `primitive空間の崩壊監視`（clauses多様性ではなく primitive entropy を世代ごとに監査）。  
4. Warning: `cross-pair shadow最小実行の復帰`（ii-lite未実行は使命適合性監査不能のため、判定系を INCONCLUSIVE のままにしない）。  

**全体判定**  
- **CRITICAL_DRIFT**（mission到達経路が実質断たれ、Stage B全滅が候補品質側でも発生している可能性が高い）。

### analysis-merged.md

# マージ分析: Run 53

**Generated**: 2026-05-09 07:20 JST
**run_id**: `run_20260507_142410`

## 合意事項 (両者一致)

| # | 観察 / 仮説 | Claude | Codex |
|---|---|---|---|
| 1 | Stage A=1439, Stage B=0, Stage C=0, graduated=0 | ✓ | ✓ |
| 2 | best 個体 (g57_i15) は n_fold_effective=0 で fold 評価不能、 GA が短期集中トレーダーを上位化 | I6 | H3 賛成 |
| 3 | seed=100 と seed=42 で primitive collapse 領域が完全に異なる (F4+F13+F11 vs F6+F8+M2) | I1 | H2 賛成 |
| 4 | seed=100 領域は profitability 構造的に低い (max PnL 27,800 vs 58,830) | I2 | 賛成 |
| 5 | Stage B 全員 fail with `median_oos_sharpe<min` AND `positive_fold_ratio<min` | F9 | Facts |
| 6 | T091 (median 0.025) 単独では seed=100 の graduate に繋がらない (positive_fold_ratio<min も同時 trigger) | I3 | I3 賛成 |
| 7 | clauses-level diversity は 0.823-1.0 で健全だが、 機能多様性 (primitive entropy) は seed 別に大幅低下 | F7 / F6 | Interpretations |

## Claude 独自の発見

| # | 発見 |
|---|---|
| C1 | run-53 の Stage A pass の pfre 中央値=0.111 は run-52 の 0.40 と大きく異なる → 短期集中トレーダー支配 |
| C2 | best 個体 g57_i15 の trade=32 で n_fold_effective=0 = 全 fold で trade<10 で fold_unavailable → selection_score の lex 順序で fitness_pen が支配 → trade<50 個体が best 候補化 |
| C3 | trade_count vs Stage B pass の関係を bin 別に集計、 trade>=50 で全 0 件、 全分布で 0% (run-52 と異なり trade=10-30 でも 0%) |

## Codex 独自の発見

| # | 発見 |
|---|---|
| Z1 | clauses 多様性は維持されているが **機能多様性 (primitive entropy)** が崩れている → 探索の実質多様性は低下 |
| Z2 | cross-pair shadow が `skipped_single_instrument` で実行されていない → ii-lite 通過判定が INCONCLUSIVE のまま |
| Z3 | T091 単独では「Stage B が gate 問題か候補品質問題か」 が分離できない → 閾値調整前に固定少数 seed 比較で先に分離検証すべき (Critical 推奨) |

## 矛盾・要議論

| # | 論点 | Claude | Codex | 判断 |
|---|---|---|---|---|
| M1 | seed=42 を次 RUN に固定するか | [Warning] 固定推奨 | REJECT (Reactive / cherry-pick) | **Codex 採用** (Reactive 兆候を回避) |
| M2 | T091 を単独で進めるか、 Z3 (seed-robustness 検証) を先行するか | T091 + niching 並行 | T091 単独 + Layer 1 replay で先に検証、 seed 戦略は別議論 | **Codex 採用** (T091 を先に Layer 1 で因果検証) |

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 | 分類 |
|---:|---|---|---|---|---|---|---|
| 1 | **T091 実装 (Stage B gate redesign Phase 1)** | High | TODO | Sharpe + Total PnL の必要条件 | Stage B 全滅 (median + pfre 両方 trigger) | Layer 1 archive replay で 1+ 件 Stage B pass、 Layer 2 RUN で trade_count_full_dataset>=50 + pnl>=50,000 個体 1+ 件 | Structural + Principled Parametric |
| 2 | **n_fold_effective=0 上位化ガード (新規 TODO)** | High | Codex (Z3 / I6) | best 個体の品質 | best 個体が trade<50 / n_fold_eff=0 で評価不能 | best 個体が trade>=50 + n_fold_eff>=5 を満たす個体になる | Structural |
| 3 | (Phase 2 候補) primitive entropy 監視 | Medium | Codex (Z1) | 探索多様性 | 機能多様性低下が seed 別に発生 | 世代単位 primitive entropy が 1.5 以上を維持 | Structural |
| 4 | (Phase 2 候補) cross-pair shadow 復帰 | Medium | Codex (Z2) | mission 監査性 | ii-lite 判定が INCONCLUSIVE のまま | shadow 評価結果が archive に記録 | Structural |

### 採用判断

- **今 cycle 採用**: 提案 1 (T091)
- **次 cycle 採用候補 (新規 TODO 登録のみ今 cycle で実施)**: 提案 2 (n_fold_eff=0 ガード)
- **Phase 2 移動**: 提案 3, 4 (Z1, Z2)

### 次フェーズ申し送り

- T091 の実装を Phase C (詳細設計) で確認 (既存 detailed-design.md は Codex APPROVED 済み、 統合テスト計画と各段階のテストを明示する程度の確認)
- 提案 2 (n_fold_eff=0 ガード) は plan-and-design 範囲外で別途 `/zenigame-fx-alpha-design` で設計開始 (Phase B-4 に申し送り、 Phase D で TODO 登録)
- 次 RUN の seed 戦略は Layer 1 検証完了後に別議論で決定 (今 cycle では決めない)

