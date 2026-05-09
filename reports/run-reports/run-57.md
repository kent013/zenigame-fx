# Run 57 — run_20260509_084752

**Generated**: 2026-05-09T08:50:12.424086+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.21515322767744777 / threshold 1.0
- ❌ **total_pnl**: -24580.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 2.953972979161896 / threshold 20.0
- ❌ **trade_count**: 30 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 42

## Best 個体

- name: `g55_i41`
- generation: 55
- fitness: **0.19565322767744778**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 30
- total_pnl: -24580.0
- sharpe: 0.21515322767744777
- sortino: —
- calmar: —
- max_drawdown_pct: 2.953972979161896

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2121
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1084
- Stage B pass: 105
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1084 | 105 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1084 | 105 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.5546, median=2.0000, std=0.4973, min=0, max=2
- n_nodes: n=5856, mean=3.8526, median=4.0000, std=1.7120, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=104, mean=0.3727, median=0.3066, std=0.1076, min=0.2729, max=0.5415
- best mission_score: **0.5415** (`g29_i26`, gen=29, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1084, mean=0.1872, median=0.1818, std=0.0766, min=0.0000, max=0.3939
- dsr: n=0
- n_fold_effective (Stage A pass): n=1084, mean=29.4852, median=34.0000, std=8.2132, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1083, mean=0.4474, median=0.4375, std=0.1749, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1084, Stage B pass = 105, failures = 979 (primary_sum = 979)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 942 |
| `positive_fold_ratio<min` | 37 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 942 |
| `positive_fold_ratio<min` | 979 |
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
- trade_count=0 個体比率: 8.8% (515/5856)
- best 個体 trade_count: 30
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=979, stage_a_only=4772, stage_b_evaluated=105
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4772, mean=-325974.4803, median=-44330.0000, std=437152.9794, min=-1001550.0000, max=30940.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4257): n=4257, mean=-365409.9648, median=-66310.0000, std=447003.0022, min=-1001550.0000, max=30940.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1084): n=1084, mean=7652.6384, median=8420.0000, std=53605.3488, min=-1000380.0000, max=35250.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g37_i90` | 37 | tier1_EUR_JPY | EUR_JPY | 0.2430 | 0.2895 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g38_i26` | 38 | tier1_EUR_JPY | EUR_JPY | 0.2430 | 0.2895 | ✅ | ❌ | ❌ | 32 | — |
| 3 | `g20_i38` | 20 | tier1_EUR_JPY | EUR_JPY | 0.2394 | 0.2589 | ✅ | ❌ | ❌ | 54 | — |
| 4 | `g51_i9` | 51 | tier1_EUR_JPY | EUR_JPY | 0.2291 | 0.2596 | ✅ | ❌ | ❌ | 42 | — |
| 5 | `g30_i70` | 30 | tier1_EUR_JPY | EUR_JPY | 0.2250 | 0.2705 | ✅ | ❌ | ❌ | 33 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.028469469463613055 |
| 1 | -0.011834503876047576 |
| 2 | -0.011834503876047576 |
| 3 | -0.011834503876047576 |
| 4 | -0.009288071132201165 |
| 5 | 0.05115054443780871 |
| 6 | 0.05115054443780871 |
| 7 | 0.05115054443780871 |
| 8 | 0.05115054443780871 |
| 9 | 0.06410144847448648 |
| 10 | 0.08309125272530729 |
| 11 | 0.13096633785265108 |
| 12 | 0.060634207337263935 |
| 13 | 0.07966487276668005 |
| 14 | 0.08062939340026198 |
| 15 | 0.06810033433021695 |
| 16 | 0.09863300389575397 |
| 17 | 0.09341306439892233 |
| 18 | 0.09411384576037628 |
| 19 | 0.19053354024545077 |
| 20 | 0.23943023525911442 |
| 21 | 0.06692191032637898 |
| 22 | 0.20741796843571975 |
| 23 | 0.20741796843571975 |
| 24 | 0.20741796843571975 |
| 25 | 0.20741796843571975 |
| 26 | 0.1960742434043439 |
| 27 | 0.15872311829799815 |
| 28 | 0.09876420252175727 |
| 29 | 0.112609248775483 |
| 30 | 0.22495816655063244 |
| 31 | 0.22495816655063244 |
| 32 | 0.22495816655063244 |
| 33 | 0.22495816655063244 |
| 34 | 0.22495816655063244 |
| 35 | 0.22495816655063244 |
| 36 | 0.20362402674154856 |
| 37 | 0.2429594938275813 |
| 38 | 0.2429594938275813 |
| 39 | 0.19840510018491136 |
| 40 | 0.19840510018491136 |
| 41 | 0.12685258049706005 |
| 42 | 0.20404244370982016 |
| 43 | 0.15269098126986833 |
| 44 | 0.12392194313254536 |
| 45 | 0.14842148894144214 |
| 46 | 0.11524188573724195 |
| 47 | 0.17227631889020367 |
| 48 | 0.13403557981147976 |
| 49 | 0.13403557981147976 |
| 50 | 0.21357654612541385 |
| 51 | 0.22912945091481648 |
| 52 | 0.20625484913206474 |
| 53 | 0.185662700361747 |
| 54 | 0.185662700361747 |
| 55 | 0.1972823751101056 |
| 56 | 0.19565322767744778 |
| 57 | 0.19565322767744778 |
| 58 | 0.19565322767744778 |
| 59 | 0.19565322767744778 |
| 60 | 0.19565322767744778 |

## 分析

### analysis-claude.md

# RUN run_20260509_023253 (Run 56) 分析（Claude 自己分析）

## 前提差分

なし（archive Parquet / summary.json / scripts/codex 全て存在）

## 観察事実 (Facts)

### Stage 通過数
- 全個体: 5856 (96 pop × 61 gen)
- Stage A pass: **1219** (20.8%)
- Stage B pass: **458** (Stage A 比 37.6%)
- Stage C pass: **0** (Stage B 比 0%)
- graduation_count: **0**

### Best 個体
- name: `g46_i51` (gen 46, ind 51)
- fitness_pen: **0.2042**
- stage_a_pass: ✅, stage_b_pass: ✅, stage_c_pass: ❌
- live_criteria 各項目: sharpe=0.237 (<1.0 ❌), total_pnl=-4100 (<50000 ❌), max_dd=0.55% (✅), trade_count=17 (<50 ❌)
- 構造: 2 clause / 3 node、 primitive=`F7(n=25)`, `P8(mom_n=5, staleness=145)`, `P5(z_n=198)`
- entry_threshold=0.426, exit_threshold=0.067, max_pos=3, time_stop_min=66, stop_atr=2.96, take_atr=1.75

### trade_count 分布 (Stage B pass, n=458)
- trade_count_stage_a (60日): mean=49.96, median=**39**, p25=38, max=99 → **median が live_criteria threshold (50) を下回る**
- trade_count_stage_b (18ヶ月 IS+folds): mean=55.69, median=43
- trade_count_full_dataset (全期間): mean=105.65, median=82
- live_criteria 充足率 (trade_count_stage_b>=50): 151/458 = **33%**

### Stage B 失敗理由 (Stage A pass=1219 のうち Stage B fail=761)
| reason | count |
|--------|------:|
| `median_oos_sharpe<min;positive_fold_ratio<min` | 499 |
| `median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable` | 225 |
| `positive_fold_ratio<min` | 32 |
| `median_oos_sharpe<min` | 5 |

### n_fold / fold quality (Stage B pass)
- n_fold_effective: mean=8.65, median=8, min=6, max=10
- positive_fold_ratio_effective: mean=0.81, median=0.80, min=0.6, max=1.0

### Stage C 結果 (Stage B pass 458 個体すべて)
- best g46_i51 の Stage C base: sharpe=-3.45 (annual), total_pnl=-4100, trade_count=17
- canonical_max_dd=0.55%, canonical_gate_pass=False (worst_gap=14.91)
- **Stage A/B (median fold OOS Sharpe ≈ 0.05-0.20) で生き残った戦略が Stage C で崩壊**

### 多様性 (Stage B pass)
- unique fitness_pen: **96 / 458 (21%)**
- 上位 5 fp で 220/458 (48%) を占有
- fp=0.2029 が 84 個体で最頻 (g32_i9 系列)
- fp=0.1853 が 52 個体 (g21_i63 系列)
- → **Stage B pass は実質 ~96 unique 個体のクローン群、 elite collapse の兆候**

### gen 推移 (Stage A→B 進化)
| gen | total | sa_pass | sb_pass |
|----:|------:|--------:|--------:|
| 0 | 96 | 1 | 0 |
| 5 | 96 | 9 | 0 |
| 10 | 96 | 10 | 6 |
| 20 | 96 | 12 | 6 |
| 30 | 96 | 28 | 10 |
| 40 | 96 | 33 | 9 |
| 50 | 96 | 21 | 7 |
| 60 | 96 | 32 | 12 |

Stage A pass は gen 30 付近で plateau (28-33)、 Stage B pass は gen 30 付近で plateau (7-12)。

### archive メタ
- instrument: 100% EUR_JPY (cross-pair shadow 未稼働)
- lane_id: 100% tier1_EUR_JPY
- ii_lite_pass: 全件 NaN (5856/5856) → cross-pair shadow 集計未実行
- dsr: 全件 NaN → **DSR (Deflated Sharpe Ratio) 多重比較補正が動作していない**
- source_stage: 全件 NaN → archive_role が記録されていない

### active_clause / n_nodes
- Stage A pass active_clause: mean=1.96 (max=2)、 全体 mean=1.63 → **Stage A pass はほぼ全個体が max_clause=2 飽和**
- Stage A pass n_nodes: mean=3.20、 全体 2.94 → 表現力は僅かに高い

### dataset 構成 (summary.json より)
- Stage A: 2026-01-06 〜 2026-03-31 (60 日, 86400 bars)
- Stage B IS: 2025-10-01 〜 2026-01-06 (97003 bars, 18 ヶ月レンジは folds 構成と推定)
- Stage C base/stress: 2026-04-01 〜 2026-04-21 (**21 日**, 20457 bars)

## 解釈・推論 (Interpretations、 C6 分離)

### H1 [Critical]: Stage C 期間が短すぎ統計的に判定困難
- 観察: Stage C base 期間が **21 日** (60日 nominal だが実 holdout 21日)、 best 個体 trade_count=17
- 仮説: live_criteria の `sharpe>=1.0` を **17 trades / 21 日** で安定判定するのは構造的に不可能。 sharpe の標準誤差が大きく、 small sample で false negative 多発
- 反証: Stage C 期間を 60 日以上に拡張し、再 Run して Stage C pass>0 になれば仮説支持。 ならなければ Stage C 落ちは regime shift / overfitting が主因
- 整合: 禁止事項「評価期間延長は強い根拠なしに行わない」に注意。 期間延長ではなく **multi-block holdout / rolling Stage C** にする設計が代替案

### H2 [Warning]: regime shift (2026-04 が新 regime)
- 観察: Stage A (2026-01〜03) で median OOS Sharpe>=0.025 達成 → Stage C (2026-04-01〜21) で sharpe<<0
- 仮説: 2026-04 から市場 regime が変化 (volatility / trend 構造)、 Stage A/B の戦略が不通用
- 反証: 別 instrument (USD_JPY 等) の同期間 Stage C 通過率を見る、 または regime indicator (VIX-equiv / ATR 中央値) を計測

### H3 [Warning]: elite collapse による過学習
- 観察: Stage B pass 458 個体のうち unique fp=96 (21%)、 上位 5 fp で 48%
- 仮説: GA selection で elite が genome として複製され、 多様性が失われている。 同じ戦略の親子コピーで Stage A/B を「数の力」で通過、 Stage C で全滅
- 反証: archive の genome_json fingerprint dedup を実施し unique 戦略数を再計測。 もし unique 戦略数が 96 程度なら fp 一致は同一戦略 → elite collapse 確定

### H4 [Warning]: trade_count_min=50 が Stage A 60日で構造的に厳しい
- 観察: Stage A pass の trade_count_stage_a 中央値=39、 25%=37 → `trade_count_min=50` を下回る個体が大半
- 仮説: 60 日で 50 trades = 平均 0.83 trades/day。 イントラデイ短期戦略でないと到達困難。 GA は信号発生頻度を犠牲にしてフォールド OOS Sharpe を最適化している
- 反証: max_clause を 3 に上げて signal 多様性を増やす、 または exit_threshold を緩めて回転率を上げる。 trade_count_stage_a の分布が右シフトすれば仮説支持

### H5 [Critical]: DSR 未計算で多重比較補正が無効
- 観察: archive dsr 列が全 5856 件 NaN
- 仮説: DSR (Deflated Sharpe Ratio) 計算経路がコード上で disabled / broken。 5856 個体を試験して best を選ぶ多重比較で、 raw Sharpe での gate 判定は false positive を増産
- 反証: dsr 計算ロジックの存在確認 (`grep -r "deflated_sharpe" src/`)、 計算結果が Stage B/C reason codes に反映されているか

### H6 [低]: cross-pair shadow 未稼働
- 観察: instrument=100% EUR_JPY、 ii_lite_pass=100% NaN
- 仮説: 単一 pair で運用、 cross-pair anchor が定義されていない or `cross_pair_runtime_mode=disabled`
- 反証: summary.json の `cross_pair_runtime_mode` 値で確認

### 禁止事項違反の兆候 (C4 検知)
- イントラデイ逸脱: time_stop_min=66 で 1 時間程度 → 範囲内 ✅
- 取引回数削減で見かけ改善: best g46_i51 trade_count=17/21日 → **削減傾向あり** ⚠️ ただし元々の `trade_count_min` 違反が支配的なので「削減で見かけ改善」というより「そもそも信号出にくい」状態
- live_criteria 緩和: 観測されない (sharpe=0.237 vs threshold 1.0、 大きく未達なので緩和される動機もない) ✅

## 次サイクル候補

### [Critical] Stage C の統計的有効性確保
- 現状: Stage C base 21 日 / best trade_count=17 → sharpe>=1.0 判定が小サンプル過小
- 案 1 (推奨): **multi-block holdout** — Stage C を 4-6 個の sub-block (各 ~30日) に分割し、 各 block で sharpe / total_pnl / dd を独立評価。 全 block 満たすなら Stage C pass
- 案 2: rolling Stage C window — Stage A の 1 ヶ月後 / 2 ヶ月後 / 3 ヶ月後の 3 holdout で多重判定
- 禁止事項抵触: 「評価期間延長は強い根拠なしに行わない」→ 本案は **延長でなく分割再利用** で対応 (期間総延長は同一)
- 期待効果: false negative (本来良い戦略が小サンプルで落ちる) を低減、 同時に regime shift robustness を強化

### [Critical] DSR (Deflated Sharpe Ratio) の archive 書き込み復活
- 現状: archive dsr 全 NaN、 多重比較補正が観測できない
- 案: dsr 計算ロジックの存在確認 → 計算経路を Stage B 評価に組み込む (gate 判定は変えず観測のみ先行) → 効果検証後に Stage B reason codes に追加
- 期待効果: 5856 個体試験で best を選ぶ overfitting を補正、 false positive を低減

### [Warning] elite collapse 抑制 (genome fingerprint dedup)
- 現状: Stage B pass 458 中 unique fp=96 (21%)
- 案: genome_json から構造 fingerprint (primitive 列 / 主要 param 量子化) を抽出し、 archive で fingerprint dedup を観測。 GA selection で同一 fingerprint の上位 K 個まで保持に制限
- 期待効果: 多様性回復、 Stage C で 1 個体集団が全滅するリスク分散

### [Warning] regime indicator の archive 書き込み (観測先行)
- 現状: regime shift 仮説の検証手段がない
- 案: Stage A/B/C 各期間の市場特性 (ATR median / autocorr / trend strength) を summary.json に記録 → analyze-run で Stage 別 metric vs Stage pass 率の相関を観測
- 期待効果: 「Stage C 期間の特殊性」を定量化、 regime-aware strategy 設計の根拠データ蓄積

### [Warning] trade_count_min と max_clause の整合性検証
- 現状: Stage A 60日で trade_count<50 個体が 67% (live_criteria 違反)、 max_clause=2 飽和
- 案: max_clause=3 に拡張した A/B 比較を 1 RUN 行い、 trade_count_stage_a 分布が右シフトするか観測
- 注意: 禁止事項「やたらに複雑な案」 → 本案は 1 パラメータ単独変更で複雑性増加は最小

## 全体判定: CONCERN

- Stage A→B の進化は機能している (gen 30 で plateau だが上昇トレンドあり)
- Stage B→C の崩壊が構造的問題 (regime shift + 短 holdout + elite collapse の複合)
- DSR / cross-pair shadow / source_stage 等の観測データが欠落 → **観測の充実が次サイクルの最優先**
- 大規模設計変更 (Stage C multi-block) と観測強化 (DSR 書き込み / fingerprint dedup) を並行で進めるべき

### analysis-codex.md

# RUN 56 分析（Codex 独立分析）

## 観察事実 (Facts) ※C6 分離遵守、 数値のみ
- Stage C ホールドアウトは 20457 本（約 21.3 日）で終了し、設定値 60 日との乖離 38.7 日を確認。
- 最良個体 g46_i51 の Stage C 指標は Sharpe -3.45、total_pnl -4100、trade_count 17。
- Stage B 通過 458 件に対し Stage C 通過 0 件、graduation 0 件、ii_lite/DSR/source_stage は全 5856 件で NaN。
- Stage B 失敗 761 件の主因は median_oos_sharpe<min & positive_fold_ratio<min が 499 件、all_folds_unavailable を伴うケース 225 件。
- Stage B 通過群の trade_count_stage_a 平均 49.96（中央値 39）、trade_count_stage_b 平均 55.69、trade_count_full_dataset 平均 105.65。
- Stage B 通過群の unique fitness_pen は 96/458（21%）で、fp=0.2029 系列が 84 個体を占有し、上位 5 fp で 220 個体（48%）を占有。

## 解釈・推論 (Interpretations、 仮説と反証可能性)
- H1 [Rejected]: 「Stage C が 21 日と短いせいで統計判定できない」/ 反証条件: Stage C が閾値から大幅に乖離していれば期間延長の有無に関わらず mission 未達 → Sharpe -3.45、total_pnl -4100 の実測で反証成立（Lo, 2002, “The Statistics of Sharpe Ratios” も小標本で Sharpe が不安定でも、ここまでの負値はノイズ域を超過）。
- H2 [Critical]: 「Stage C のデータ欠損（60 日設定に対し実データ 21 日）が評価ループを破壊している」/ 反証条件: データ取得ログが 60 日を満たし trade_count>=50 を確保できていること → summary でホールドアウト最終時刻 2026-04-21T07:25:00+00:00 を確認、残 39 日が欠落しており反証不可。
- H3 [Warning]: 「DSR パイプライン停止が多重比較補正を無効化し、Stage C 失敗率を底上げしている」/ 反証条件: dsr フィールドが算出済みで統計的有意性検査が適用されていること → 全件 NaN のため未反証。Bailey, Borwein, López de Prado, Zhu (2014) “The Probability of Backtest Overfitting” が警告する多重検定リスクに抵触。
- H4 [Warning]: 「GA の選択圧が特定 fp 系列（g32_i9 由来）へ収束し探索多様性を喪失している」/ 反証条件: 世代別に fp が広く分散し上位占有率が低いこと → 上位 5 fp が 48% を占有し反証できず。
- H5 [Inconclusive]: 「trade_count_min=50 が Stage A 60 日条件下で構造的に不適合」/ 反証条件: Stage A で 50 以上の個体が十分に存在すること → 平均 49.96 で閾値近辺、分布をさらに確かめないと結論不能（追加データ要）。

## 次サイクル候補
- [Critical] Stage C ホールドアウト欠損の起因解析: (a) 60 日分バーを確保し mission 必須要件の trade_count>=50 を満たす (b) 評価ループの整合性回復、負値指標の原因切り分け (c) 禁止事項該当なし (d) データ取得ジョブとステージ分割ロジックの追跡が主体で中程度。
- [Warning] DSR 算出パイプラインの再稼働: (a) 多重比較補正を復元し Stage B→C 移行の信頼度を担保 (b) 偽陽性戦略の排除率向上 (c) 禁止事項該当なし (d) 既存コンポーネントの診断・修正で中程度。
- [Warning] GA 多様性監視と調整（mutation/crossover 設定の軽微検証 + 世代別 fp モニタリング強化）: (a) 単一系列への収束を緩和し Stage B→C 成果率を回復 (b) exploration 向上と過剰適合リスク低下 (c) 禁止事項 5（過度な複雑化）を避け、最小限のパラメータ微調整とモニタに留める (d) 低〜中、既存ログ解析と設定差分評価で対応可能。
- [Warning] Stage C 取引頻度の根拠調査（エントリ条件の intraday 適合性をログで検証）: (a) イントラデイ方針に沿った実際のエントリタイミングを把握 (b) trade_count>=50 を自然に満たす設計可否の判断材料獲得 (c) 禁止事項 6 を避け、閾値を弄らず発生要因の分析に限定 (d) 低、既存 fill ログ/トレードログ解析中心。

## 全体判定: CRITICAL_DRIFT
Stage C データ欠損という構造的バグと DSR 停止による検定抜けが同時発生しており、現状の GA サイクルは mission 達成に向けた正当な評価環境を確保できていない。Stage C 指標も大幅な負値で drift が顕在化。

## Claude 自己分析との差分
- Stage C 失敗を「期間が短い」ではなく、先に実測が大幅赤字である点を強調し、延長提案を反証済みと判断。
- Phase 直近で最優先とすべきはホールドアウト欠損の修復であり、regime shift 仮説や multi-block 化はその後に再検証するべきと結論。
- GA 多様性崩壊をランダム性不足ではなく特定 fitness_pen 系列への偏りとして定量化し、探索パラメータ監視を提案。

### analysis-merged.md

# マージ分析: Run 56 (run_20260509_023253)

## 合意事項（両者一致）

### F1. Stage C 通過 0 / graduation 0
- Stage A pass=1219 → B pass=458 → C pass=**0**
- best g46_i51: stage_c_pass=False, Sharpe=-3.45, total_pnl=-4100, trade_count=17
- live_criteria 4 項目中 1 項目のみ pass (max_dd<20%)、 残り 3 項目 (sharpe / total_pnl / trade_count) 未達

### F2. archive 観測の重大欠落
- **DSR (Deflated Sharpe Ratio)**: 全 5856 件 NaN — 多重比較補正が無効化されている
- **ii_lite_pass**: 全件 NaN — cross-pair shadow が `skipped_single_instrument` で稼働せず
- **source_stage**: 全件 NaN — archive_role 記録欠落
- これらは「観測の質そのもの」の問題であり、 戦略改善の前提が揺らぐ

### F3. GA 多様性の崩壊（elite collapse）
- Stage B pass 458 個体のうち unique fitness_pen=96 (21%)
- 上位 5 fp で 220 個体 (48%) を占有
- 最頻 fp=0.2029 が 84 個体 (g32_i9 系列)
- → 実質 ~96 unique 戦略、 多様性が失われている

### F4. trade_count_min=50 が現状の戦略集団で構造的に未達
- Stage B pass の trade_count_stage_a 中央値=39 (live_criteria の 50 を下回る)
- 60 日で 50 trades = 0.83 trades/day がイントラデイ短期戦略の必要回転率

## Claude 独自の発見

### C1. Stage C 期間が 21 日と短い（Codex により reframe された）
- 当初 Claude H1: 「21 日 holdout で sharpe>=1.0 判定が小サンプル過小、 multi-block holdout 提案」
- → Codex の反証: Sharpe -3.45 はノイズ域を超過している。 期間問題ではなく**実測が大幅赤字**である事実を直視すべき
- → 残る価値: 21 日が config の 60 日と乖離している点は別問題（C2 で詳述）

### C2. Stage A 表現力の飽和
- Stage A pass の active_clause: mean=1.96 (max=2 で飽和)、 全体 mean=1.63
- max_clause=2 を使い切る個体ばかりが Stage A 通過 → 表現力の上限に達している

### C3. Stage B fail 理由 dominance
- median_oos_sharpe<min;positive_fold_ratio<min: 499/761 (66%)
- median_oos_sharpe<min;positive_fold_ratio<min;all_folds_unavailable: 225/761 (30%)
- → Stage B 落ちの 96% が「sharpe + fold_ratio」の同時 trigger

## Codex 独自の発見

### X1. Stage C ホールドアウト データ範囲欠損 (CRITICAL)
- `stage_gate_config.stage_c_holdout_days = 60` 設定
- しかし dataset.bars_holdout = 20457 (約 21.3 日) のみ
- holdout_bar_first=2026-04-01 / holdout_bar_last=2026-04-21 → **39 日分が欠落**
- → 評価ループそのものが構造的に壊れている（mission 必須要件の trade_count>=50 を確保不能）

### X2. Stage C 実測が深い赤字 (Sharpe -3.45) はノイズ域超過
- Lo, A. W. (2002), "The Statistics of Sharpe Ratios", Financial Analysts Journal — 小標本でも Sharpe -3.45 は単なる noise では説明困難
- → 期間延長より先に「データセット完全性 + 評価環境の修復」を優先

### X3. Bailey, Borwein, López de Prado, Zhu (2014) の DSR / PBO 引用
- "The Probability of Backtest Overfitting" (J. Computational Finance)
- 5856 個体を試験して best を選ぶ多重検定リスクは正に PBO の典型例
- → DSR 計算が NaN は致命的観測欠陥

## 矛盾・要議論

### M1. Stage C 期間の扱い
- Claude: 「21 日が短すぎ、 multi-block にすべき」
- Codex: 「21 日でも -3.45 は明らかに失敗。 期間延長より先にデータ範囲修復・統計補正復活」
- → **Codex 採用**: データ範囲そのものの欠損（X1）が先決問題。 multi-block 化は X1 修復後に再検討

### M2. trade_count_min の扱い
- Claude H4: 「50 trades / 60 日が構造的に厳しい、 max_clause=3 拡張で検証」
- Codex: trade_count<50 は live_criteria 違反だが、 まずは Stage A→C の評価環境修復が先。 max_clause 拡張は次々サイクル
- → **Codex 採用**: 評価環境を直してから max_clause を弄る (思考原則「仕組みが機能していない段階で値を弄るな」)

## 統合改善提案（優先度順）

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 | 分類 |
|---|------|--------|------|--------------|-------------|---------|------|
| 1 | Stage C ホールドアウトデータ範囲修復 (60日確保) | **Critical** | Codex X1 | trade_count, total_pnl, sharpe | bars_holdout=20457 (21日) で config 60日と乖離 | 評価ループの整合性回復 → Stage C 通過個体が観測可能になる | Structural |
| 2 | DSR (Deflated Sharpe Ratio) 算出パイプライン復活 | **Critical** | Codex X3 / Claude H5 | 多重比較補正による Stage B/C false positive 抑制 | dsr 全件 NaN | 5856 個体試験での overfitting リスク低減、 後続サイクルの判断材料蓄積 | Structural |
| 3 | GA 多様性監視 (unique fp / fingerprint dedup 観測先行) | Warning | Claude H3 / Codex H4 | Stage B/C 通過個体の集団多様性 | unique fp=21%, 上位 5 が 48%占有 | elite collapse の定量化、 後続サイクルでの selection 改善判断材料 | Structural (観測先行) |

## 棄却された提案 / 保留

| # | 提案 | 出所 | 棄却/保留 理由 |
|---|------|------|---------------|
| - | Stage C を multi-block holdout に再設計 | Claude H1 | Codex X1 (データ範囲欠損) が先決問題。 X1 修復後に再検討 |
| - | regime indicator の archive 書き込み | Claude H4 | 観測先行型の正当な提案だが、 X1/X3 修復が優先。 次々サイクルで採用 |
| - | max_clause=3 拡張 A/B 検証 | Claude H5 | 「仕組みが機能していない段階で値を弄るな」原則。 評価環境修復後に検討 |
| - | regime_penalty_weight 等のパラメータ調整 | (Reactive Parametric 例) | メタ過学習ガード抵触、 Reactive 分類のため |

## 全体判定: CRITICAL_DRIFT (Codex 判定継承)

Stage C ホールドアウトデータ欠損 (config 60日 vs 実 21日) と DSR 観測停止が同時発生。 現状 GA サイクルは mission 達成に向けた正当な評価環境を確保できていない。
**最優先**: 評価環境（データ完全性 + 多重比較補正）の構造的修復。 戦略レベルの改善 (multi-block / max_clause / regime indicator 等) はこの修復後に再評価する。

