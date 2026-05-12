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
