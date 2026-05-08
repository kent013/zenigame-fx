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
