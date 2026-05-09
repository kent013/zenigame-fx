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
