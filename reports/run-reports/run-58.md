# Run 58 — run_20260509_130902

**Generated**: 2026-05-09T13:09:03.621385+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.15989490683483948 / threshold 1.0
- ❌ **total_pnl**: 16700.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 55 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 43

## Best 個体

- name: `g46_i95`
- generation: 46
- fitness: **0.12689490683483948**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 55
- total_pnl: 16700.0
- sharpe: 0.15989490683483948
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2121
- dsr: —
- ii_lite_pass: —
- n_nodes: 7
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 312
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 312 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 312 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4474, median=1.0000, std=0.4983, min=0, max=2
- n_nodes: n=5856, mean=3.6585, median=3.0000, std=2.0225, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=312, mean=0.1470, median=0.1515, std=0.0526, min=0.0000, max=0.3333
- dsr: n=0
- n_fold_effective (Stage A pass): n=312, mean=26.1923, median=30.0000, std=6.0813, min=7, max=34
- positive_fold_ratio_effective (Stage A pass): n=312, mean=0.3990, median=0.3889, std=0.1772, min=0.0000, max=0.6000

## Stage B failure reason 集計

- Stage A pass = 312, Stage B pass = 0, failures = 312 (primary_sum = 312)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 312 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 312 |
| `positive_fold_ratio<min` | 312 |
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
- trade_count=0 個体比率: 2.0% (119/5856)
- best 個体 trade_count: 55
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=312, stage_a_only=5544
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5544, mean=-796718.4199, median=-1000120.0000, std=379318.0840, min=-1007750.0000, max=25790.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5425): n=5425, mean=-814194.8240, median=-1000130.0000, std=364429.8794, min=-1007750.0000, max=25790.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=312): n=312, mean=-7752.3077, median=10560.0000, std=139066.8674, min=-1000320.0000, max=27190.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g51_i45` | 51 | tier1_EUR_JPY | EUR_JPY | 0.3130 | 0.3670 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g52_i30` | 52 | tier1_EUR_JPY | EUR_JPY | 0.3130 | 0.3670 | ✅ | ❌ | ❌ | 32 | — |
| 3 | `g18_i54` | 18 | tier1_EUR_JPY | EUR_JPY | 0.2980 | 0.3500 | ✅ | ❌ | ❌ | 31 | — |
| 4 | `g19_i1` | 19 | tier1_EUR_JPY | EUR_JPY | 0.2980 | 0.3500 | ✅ | ❌ | ❌ | 31 | — |
| 5 | `g19_i22` | 19 | tier1_EUR_JPY | EUR_JPY | 0.2980 | 0.3500 | ✅ | ❌ | ❌ | 31 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.1374741633502286 |
| 1 | 0.1374741633502286 |
| 2 | 0.1374741633502286 |
| 3 | 0.1374741633502286 |
| 4 | 0.1374741633502286 |
| 5 | 0.1374741633502286 |
| 6 | 0.1374741633502286 |
| 7 | 0.1374741633502286 |
| 8 | 0.1374741633502286 |
| 9 | 0.1374741633502286 |
| 10 | 0.1374741633502286 |
| 11 | 0.1374741633502286 |
| 12 | 0.1374741633502286 |
| 13 | 0.1374741633502286 |
| 14 | 0.1374741633502286 |
| 15 | 0.1374741633502286 |
| 16 | 0.1374741633502286 |
| 17 | 0.1374741633502286 |
| 18 | 0.29797379262230483 |
| 19 | 0.29797379262230483 |
| 20 | 0.29797379262230483 |
| 21 | 0.29797379262230483 |
| 22 | 0.10790978089884704 |
| 23 | 0.10790978089884704 |
| 24 | 0.10790978089884704 |
| 25 | 0.2767049777576379 |
| 26 | 0.2767049777576379 |
| 27 | 0.18277123515836677 |
| 28 | 0.14484022627153512 |
| 29 | 0.14484022627153512 |
| 30 | 0.10790978089884704 |
| 31 | 0.16361787463438493 |
| 32 | 0.16361787463438493 |
| 33 | 0.10790978089884704 |
| 34 | 0.10790978089884704 |
| 35 | 0.10790978089884704 |
| 36 | 0.10790978089884704 |
| 37 | 0.10790978089884704 |
| 38 | 0.10790978089884704 |
| 39 | 0.10790978089884704 |
| 40 | 0.11713250616663795 |
| 41 | 0.13706685454560896 |
| 42 | 0.11713250616663795 |
| 43 | 0.11713250616663795 |
| 44 | 0.11713250616663795 |
| 45 | 0.11713250616663795 |
| 46 | 0.12689490683483948 |
| 47 | 0.12689490683483948 |
| 48 | 0.12689490683483948 |
| 49 | 0.12689490683483948 |
| 50 | 0.1299053353092762 |
| 51 | 0.31304132674743385 |
| 52 | 0.31304132674743385 |
| 53 | 0.12689490683483948 |
| 54 | 0.12689490683483948 |
| 55 | 0.12689490683483948 |
| 56 | 0.12689490683483948 |
| 57 | 0.12689490683483948 |
| 58 | 0.12689490683483948 |
| 59 | 0.12689490683483948 |
| 60 | 0.19020056673500824 |

## 分析

### analysis-claude.md

# RUN run_20260509_084752 (Run 57) 分析（Claude 自己分析）

## 前提差分

なし

## 観察事実 (Facts)

### Stage 通過数 (前 Run 比較込み)
| Stage | Run 56 | Run 57 | Δ |
|-------|------:|------:|--:|
| 全個体 | 5856 | 5856 | 0 |
| Stage A pass | 1219 | **1084** | -11% |
| Stage B pass | 458 | **105** | **-77%** |
| Stage C pass | 0 | 0 | 0 |
| graduated | 0 | 0 | 0 |
| **mission 達成** | False | False | - |

### Best 個体
- name: `g55_i41` (gen 55, ind 41)
- fitness_pen: **0.1957** (Run 56 best 0.2042 の 96%)
- stage_a_pass: ✅, stage_b_pass: ✅, stage_c_pass: ❌
- live_criteria 各項目:
  - sharpe=0.215 (<1.0 ❌)
  - total_pnl=-24580 (<50000 ❌)
  - max_dd=2.95% (<20% ✅)
  - trade_count=30 (<50 ❌)

### dataset 構成 (cycle 4 C1 適用後)
- Stage A 60日: 2025-12-21 〜 2026-02-19 (86400 bars)
- Stage B IS: 2025-04-01 〜 2025-12-21 (242483 bars、 約 8.7 ヶ月)
- Stage C holdout: **2026-02-19 〜 2026-04-19** (60232 bars、 約 60 日) ← **施策 C1 で正常化**

### archive 観測欠落 (Run 56 と同じ、 cycle 5 で対処予定)
- **DSR (Deflated Sharpe Ratio)**: 全 5856 件 NaN — 多重比較補正が無効
- **ii_lite_pass**: 全件 NaN — cross-pair shadow 未稼働 (`skipped_single_instrument`)
- **source_stage**: 全件 NaN — archive_role 記録欠落

### trade_count 分布 (Stage B pass, n=105)
| 指標 | Run 56 (n=458) | Run 57 (n=105) | Δ |
|------|--------------:|--------------:|--:|
| trade_count_stage_a (60日) | mean=49.96, median=39 | **mean=70.32, median=64** | +28 (median) |
| trade_count_stage_b | mean=55.69, median=43 | **mean=187.86, median=181** | +138 (median) |
| trade_count_full_dataset | mean=105.65, median=82 | **mean=258.18, median=245** | +163 |
| **live_criteria trade_count_stage_b>=50 充足率** | 33% (151/458) | **100% (105/105)** | +67pt |

trade_count が増えた要因:
- Stage A 60日でも閾値超過個体が増えた (max_clause=2 飽和個体だが期間範囲が前にシフトで信号機会増)
- Stage B IS 8.7ヶ月 (Run 56 4.4ヶ月) で 2 倍期間 → trade も 2 倍
- Stage C holdout 60日 (Run 56 21日) で約 3 倍 → trade も 3 倍

### Stage B 失敗理由 (Stage A pass=1084 のうち Stage B fail=979)
| reason | count | 比率 |
|--------|------:|----:|
| `median_oos_sharpe<min;positive_fold_ratio<min` | 941 | **96%** |
| `positive_fold_ratio<min` | 37 | 4% |
| `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` | 1 | <1% |

Run 56 では median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable が 30% を占めていたが、 Run 57 では <1% に激減 → fold 構造改善 (n_fold_effective median 8 → 34) の効果

### n_fold_effective / positive_fold_ratio (Stage B pass)
| 指標 | Run 56 | Run 57 | Δ |
|------|------:|------:|--:|
| n_fold_effective median | 8 | **34** | +26 (4.25倍) |
| positive_fold_ratio median | 0.80 | **0.62** | -0.18 |

n_fold が劇的に増加 (Stage B 8.7ヶ月で fold step=5日 → 約 34 fold)。 OOS 推定の標準誤差は √4.25 倍小さくなる (理論上)。
positive_fold_ratio は低下 (より厳しいテスト)。

### fitness_pen 分布
| 指標 | Run 56 | Run 57 | Δ |
|------|------:|------:|--:|
| Stage A pass median fp | 0.185 | **0.040** | -0.145 (-78%) |
| Stage B pass median fp | 0.186 | **0.111** | -0.075 (-40%) |
| Best fp | 0.2042 | **0.1957** | -4% |

Stage A pass の fp 分布が大幅低下 → 新 Stage B IS 期間 (2025-04-01〜2025-11-24) は個体にとって勝ちにくい regime。

### 多様性 (Stage B pass)
- unique fitness_pen: **10 / 105 (9.5%)** (Run 56: 21%)
- 上位 5 fp で 93/105 (89%) 占有 (Run 56: 48%)
- 最頻 fp=0.115 が 31 個体、 fp=0.042 が 28 個体
- → **elite collapse 悪化**: 実質 ~10 unique 戦略のクローン群

### gen 推移 (Stage A→B 進化)
| gen | Run 56 sa/sb | Run 57 sa/sb |
|----:|------------:|------------:|
| 0 | 1/0 | 0/0 |
| 5 | 9/0 | 6/0 |
| 10 | 10/6 | 8/0 |
| 20 | 12/6 | 9/0 |
| 30 | 28/10 | **19/1** |
| 40 | 33/9 | 29/6 |
| 50 | 21/7 | **31/4** |
| 60 | 32/12 | 22/3 |

Run 57 では Stage B pass の出現が遅く (gen 30 から)、 plateau 数が低い (3-6 個)。 Run 56 では 7-12 個。
これは新 regime での適応が難しい証拠。

### Stage A 表現力 (active_clause / n_nodes)
- (Run 57 で詳細未集計、 Run 56 と類似と推定: max_clause=2 飽和)

## 解釈・推論 (Interpretations、 C6 分離)

### H1 [Confirmed]: 施策 C1 (dataset 範囲修復) の主要効果は達成
- 観察: stage_partition_guard B-2 が holdout_short_override=False で pass、 trade_count_stage_b>=50 が 100% 充足
- 仮説: 「Stage C 評価環境が config 仕様通りに整い、 live_criteria の trade_count 観点は構造改善した」 → 反証: trade_count<50 個体が多く残れば False → 0/105 で confirmed
- 残課題: live_criteria の他 3 項目 (sharpe / total_pnl / max_dd) は依然未達

### H2 [Confirmed]: 新 Stage B 期間は前 RUN より厳しい regime
- 観察: Stage A pass median fp 0.185 → 0.040 (-78%)、 Stage B pass 458 → 105 (-77%)、 positive_fold_ratio 0.80 → 0.62
- 仮説: 「2025-04-01〜2025-11-24 の市場 regime は 2025-10-01〜2026-01-31 より trend が弱い / volatility パターンが違う」 → confirmed (Codex 事前合意)
- 含意: Run 比較は新 baseline で行う、 Run 56 以前との fitness 直接比較不可

### H3 [Critical]: DSR 配線未稼働で多重比較補正が無効
- 観察: archive dsr 全 5856 件 NaN、 ii_lite_pass 全 NaN
- 仮説: 「audit.compute_audit_dsr_for_genome 計算 logic は実装済 (audit.py:498)、 ただし run_ga.py から呼び出されず archive 書き込みパスが切られている」
- 反証: scripts/alpha_factory/run_ga.py を grep して `compute_audit_dsr_for_genome` / `build_run_audit_report` の呼び出しがあれば仮説 false
- success_criterion: cycle 5 で配線復帰、 archive dsr 列に non-NaN 値が出現

### H4 [Warning]: elite collapse 悪化 (unique fp 21% → 10%)
- 観察: Stage B pass 105 中 unique fp=10 (9.5%)、 上位 5 fp で 89% 占有
- 仮説: 「GA selection で elite が genome として複製、 多様性が更に失われている。 新 regime で勝ちにくい中、 elite が更に偏る悪循環」
- 反証: genome_json fingerprint dedup を観測、 unique 戦略数が unique fp と乖離していれば selection 圧の問題ではない別要因
- 後続: cycle 6+ で fingerprint dedup or niche preserving selection を提案 (Codex 推薦順序 3)

### H5 [Warning]: Stage B median_oos_sharpe<min が 96% で dominant
- 観察: Stage B fail 979 件のうち median_oos_sharpe<min;positive_fold_ratio<min が 941 件 (96%)
- 仮説: 「median_oos_sharpe>=0.025 の閾値が新 regime で達成困難。 ただし閾値緩和は禁止事項 4 抵触」
- 含意: 構造的対策 (regime indicator / multi-block / DSR-based gate) で対処すべき。 cycle 6+ で議論

### 禁止事項違反の兆候 (C4 検知)
- イントラデイ逸脱: best g55_i41 trade_count=30/60日 = 0.5 trade/day → イントラデイ範囲、 ✅
- 取引回数削減で見かけ改善: trade_count_stage_a median 39 → 64 で **増加**、 削減傾向なし ✅
- live_criteria 緩和: 観測されない ✅

## 次サイクル候補 (cycle 5)

### [Critical] DSR (Deflated Sharpe Ratio) 配線復帰 ← Codex 推薦順序 1
- 現状: archive dsr 全 NaN、 多重比較補正 telemetry 完全停止
- 案: scripts/alpha_factory/run_ga.py で audit.build_run_audit_report (compute_audit_dsr_for_genome 経由) を呼び出し、 archive に dsr 値を書き込む
- 既存実装: src/alpha_factory/audit.py:498 (compute_audit_dsr_for_genome) / :630 (build_run_audit_report) は完成済
- 期待効果: 5856 個体試験の PBO/DSR を観測、 後続 cycle で hard-gate 化判断材料
- 変更分類: Structural (新観測経路の配線、 既存 logic の活性化)
- 禁止事項抵触: なし

### [Warning] cross-pair shadow 再有効化 (Codex 推薦順序 2、 cycle 6+ 想定)
- 現状: ii_lite_pass 全 NaN、 cross_pair_runtime_mode=skipped_single_instrument
- 案: tier1 instrument 設定で EUR_JPY single でも anchor (EUR_USD / USD_JPY) で shadow 評価を回す
- 後続 cycle で議論

### [Warning] elite collapse 対策 (Codex 推薦順序 3、 cycle 7+ 想定)
- 現状: unique fp ratio 10%
- 案: genome_json fingerprint dedup or niche preserving selection
- 後続 cycle で議論

## 全体判定: CONCERN

cycle 4 施策 C1 は意図通り成功 (Stage C 評価環境正常化、 trade_count 構造改善)。 Stage B pass 4 倍減は事前合意された regime shift 起因。 ただし mission 達成 (Stage C pass>0、 live_criteria 全達成) には依然遠く、 観測欠落 (DSR / ii_lite / source_stage) の修復が次の最優先課題。

### analysis-codex.md

# RUN 57 分析（Codex 独立分析）
使用スキル: zenigame-analyze-run（Alpha Factory RUN結果の深層分析）

## 観察事実 (Facts)
- Stage A pass 1084 (Run 56: 1219)、Stage B pass 105 (Run 56: 458)、Stage B最初の通過世代はgen30。
- Stage B fail内訳: median_oos_sharpe<min かつ positive_fold_ratio<min が941件、positive_fold_ratio<min単独37件、all_folds_unavailable併発1件。
- Stage B pass集合のtrade_count_stage_a中央値64、trade_count_stage_b中央値181、trade_count_stage_b≥50充足率100%。
- Stage B passのunique fp比率10%、上位5 fpで占有率89%。
- Stage A passのfp中央値0.040、Stage B passのfp中央値0.111、最高fp 0.1957。
- g55_i41はlive_criteriaでsharpe 0.215、total_pnl -24580、max_dd 2.95%、trade_count 30。
- archive内のdsr列が全てNaN、`compute_audit_dsr_for_genome`実装済ながら`run_ga.py`から未呼び出し。

## 解釈・推論 (Interpretations)
- H1 [Low / Confirmed]: 施策C1目的（holdout 60日確保とtrade_count構造改善）はStage B passのtrade_count統計とguardログで反証材料なし。
- H2 [High / Confirmed]: Stage B pass数の77%減とgen30初通過は評価窓がRun 56より厳格化した仮説と整合し、他要因（クラッシュ等）の根拠不明。
- H3 [Critical / Confirmed]: DSR配線未稼働はarchiveのNaN実測と`audit.py`実装状況で反証不可、リスク監視指標欠落が続く。
- H4 [Warning / Confirmed]: Stage B passのunique fp 10%かつ上位5 fp比率89%は多様性崩壊を示し、mutator設定や移民率変更記録が無いため別要因によるとの反証なし。
- H5 [High / Confirmed]: Stage B failの96%がSharpe閾値とpositive_fold_ratio閾値同時違反で、他カテゴリが37件と少数なため「Sharpe計測が支配的阻害要因」仮説の反証なし。
- H6 [Medium / Inconclusive]: Stage A pass fp中央値0.040への縮退が選択圧歪みを生みStage B探索を阻害している可能性は示唆されるが、基準値の改定履歴が未確認で結論保留。George E. P. Box (1976)『Science and Statistics』の指摘どおり、計測系の有用性検証が必要。

## 次サイクル候補
- [Critical] DSR配線復帰: (a) Stage B〜C評価でリスク指標を記録しmission達成判定の計器を再稼働; (b) DSR系列があればSharpe低下と損失の切り分けが可能; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: `run_ga.py`から既存`compute_audit_dsr_for_genome`呼出とarchive書き込みを追加する配線作業。
- [Warning] Stage B regimeセグメント分析: (a) Stage B失敗の時間帯・通貨ペア偏り仮説を検証; (b) 失敗集中窓を特定すれば次施策で対象プリミティブやフィルタを決められる; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: 既存genome archive集計スクリプトでカレンダーとfold指標をクロス集計。
- [Warning] コスト分解レビュー: (a) g55_i41の負P&L要因をspread・swap寄与で分解; (b) コストモデル誤差や手数料推定過小を検出すればSharpe改善余地を定量化; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: backtestログとarchive統計の照合、既存データ取り出しで完結。
- [Warning] Stage Aフィットネススケール監査: (a) fp中央値0.040への縮退が選択圧を歪めていないか検証; (b) スケール不整合を是正すればGAの探索幅が戻る可能性; (c) 禁止事項抵触リスク: なし; (d) 実装複雑性: 旧Runとのログ比較と計算式トレース。

## 全体判定: CONCERN

## Claude 自己分析との差分
- Stage Aフィットネス縮退を探索圧の潜在ボトルネックとして追加し、H6として扱った。
- best個体がSharpe基準を満たしつつtotal_pnlで敗退している点を強調し、コスト分解レビューを次サイクル候補に含めた。
- DSR配線復帰をCritical施策として承認しつつ、Sharpe低下の時間窓特定タスクを補完提案として列挙。

### analysis-merged.md

# マージ分析: Run 57 (run_20260509_084752)

## 合意事項（両者一致）

### F1. 施策 C1 (cycle 4) の主要効果は達成
- stage_partition_guard B-2 が holdout_short_override=False で pass
- holdout 60日構造的に確保 (60232 bars)
- trade_count_stage_b>=50 充足率 100% (Run 56: 33% から劇的改善)

### F2. mission 達成は依然遠い
- Stage C pass=0、 graduation=0
- best g55_i41 live_criteria 4 中 1 (max_dd) のみ pass

### F3. archive 観測欠落 (継続課題)
- DSR / ii_lite_pass / source_stage 全 NaN
- 多重比較補正 telemetry 完全停止

### F4. GA 多様性悪化
- unique fp ratio 21% → 10% (Stage B pass のうち実質 10 unique 戦略)

### F5. 新 Stage B 期間が前 RUN より厳しい regime
- Stage A pass median fp 0.185 → 0.040 (-78%)
- positive_fold_ratio median 0.80 → 0.62
- gen 30 で初の Stage B pass (Run 56 は gen 10)

## Codex 独自の発見

### X1. H6: Stage A fp 縮退が選択圧を歪めている可能性 (Inconclusive)
- Stage A pass fp median 0.040 という低水準が Stage B 探索を阻害している可能性
- George E. P. Box (1976) "Science and Statistics" — 計測系の有用性検証が必要

### X2. best 個体は Sharpe 基準を満たしつつ total_pnl で敗退
- g55_i41: sharpe=0.215, trade_count=30、 total_pnl=-24580
- コスト (spread / swap) 寄与の分解が必要

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 | 分類 |
|---|------|--------|------|--------------|-------------|---------|------|
| 1 | DSR 配線復帰 | **Critical** | Codex 順序 1 / Claude H3 | 多重比較補正 telemetry | dsr 全 NaN | 5856 個体試験での overfitting risk 観測可能化 | Structural |
| 2 | 再現性 check (seed=43 で Run 58) | Warning | Claude 追加 | fp 分布の安定性 | Run 57 が cycle 4 後の最初 RUN で variance 不明 | 新 baseline の安定性確認、 fp variance 推定 | Principled (探索独立性) |
| 3 | regime セグメント分析 | Warning | Codex 順序 2 | Stage B fail の時間 / pair 偏り | Stage B fail 96% が同一 reason | 失敗集中窓特定で primitive / filter 設計の根拠データ蓄積 | Structural (観測先行) |
| 4 | コスト分解レビュー | Warning | Codex 順序 3 | total_pnl 分解 (spread / swap) | best total_pnl=-24580 の構造不明 | コスト過小 / 過大の検出、 純 PnL 改善余地定量化 | Structural (観測先行) |
| 5 | Stage A fitness スケール監査 | Warning | Codex H6 | 選択圧歪み | Stage A pass fp median 0.040 縮退 | スケール不整合是正で GA 探索幅復活可能性 | Inconclusive (要調査) |

## 棄却 / 保留

| # | 提案 | 理由 |
|---|------|------|
| - | median_oos_sharpe_min 閾値緩和 | 禁止事項 4 抵触 |
| - | max_clause=3 拡張 A/B 検証 | 思考原則「仕組みが機能していない段階で値を弄るな」 (cycle 4 と同じ判断) |

## 全体判定: CONCERN (Codex 判定継承)

cycle 4 施策 C1 は意図通り成功、 ただし mission 達成に向けた「観測の質」と「戦略の進化」の両面で課題。 cycle 5 では観測強化 (DSR 配線復帰) を Critical 施策として進めるか、 実装複雑性ゆえに分割が必要かを Codex 合議で決定する。

