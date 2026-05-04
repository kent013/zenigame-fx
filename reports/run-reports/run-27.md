# Run 27 — run_20260504_043138

**Generated**: 2026-05-04T04:31:38.796953+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.10714648830083122 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 51 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 15
- mutation_rate: 0.3
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: None

## Best 個体

- name: `g14_i29`
- generation: 14
- fitness: **0.09814648830083122**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 51
- total_pnl: 0.0
- sharpe: 0.10714648830083122
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 640
- Stage A pass: 142
- Stage B pass: 0
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 640 | 142 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 640 | 142 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=640, mean=0.9984, median=1.0000, std=0.0395, min=0, max=1
- n_nodes: n=640, mean=2.0453, median=2.0000, std=0.7349, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=142, mean=0.1100, median=0.1250, std=0.0406, min=0.0000, max=0.1250
- dsr: n=0
- n_fold_effective (Stage A pass): n=142, mean=1.9789, median=2.0000, std=1.1596, min=0, max=9
- positive_fold_ratio_effective (Stage A pass): n=132, mean=0.4735, median=0.5000, std=0.1120, min=0.0000, max=0.5000

## Stage B failure reason 集計

- Stage A pass = 142, Stage B pass = 0, failures = 142 (primary_sum = 142)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 142 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 10 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 142 |
| `positive_fold_ratio<min` | 142 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=640

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_1_stage_b_priority`
- trade_count=0 個体比率: 3.1% (20/640)
- best 個体 trade_count: 51
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 640
- metric_stage 分布: stage_a_evaluated=142, stage_a_only=498
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=498, mean=-554263.5542, median=-644690.0000, std=452345.7464, min=-1001670.0000, max=4520.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=478): n=478, mean=-577454.4979, median=-945285.0000, std=446974.6376, min=-1001670.0000, max=4520.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=142): n=142, mean=-18356.6901, median=2250.0000, std=144286.2439, min=-1000420.0000, max=11940.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g11_i31` | 11 | tier1_EUR_JPY | EUR_JPY | 0.1509 | 0.1599 | ✅ | ❌ | ❌ | 48 | — |
| 2 | `g14_i29` | 14 | tier1_EUR_JPY | EUR_JPY | 0.0981 | 0.1071 | ✅ | ❌ | ❌ | 51 | — |
| 3 | `g15_i0` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0981 | 0.1071 | ✅ | ❌ | ❌ | 51 | — |
| 4 | `g15_i2` | 15 | tier1_EUR_JPY | EUR_JPY | 0.0981 | 0.1071 | ✅ | ❌ | ❌ | 51 | — |
| 5 | `g13_i2` | 13 | tier1_EUR_JPY | EUR_JPY | 0.0921 | 0.1071 | ✅ | ❌ | ❌ | 51 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.049367744528911545 |
| 1 | -0.030318243357735267 |
| 2 | 0.016277277324133227 |
| 3 | 0.016277277324133227 |
| 4 | 0.016277277324133227 |
| 5 | 0.016277277324133227 |
| 6 | 0.016277277324133227 |
| 7 | 0.016277277324133227 |
| 8 | 0.016277277324133227 |
| 9 | 0.016277277324133227 |
| 10 | 0.016277277324133227 |
| 11 | 0.15090754144831814 |
| 12 | 0.016277277324133227 |
| 13 | 0.09214648830083122 |
| 14 | 0.09814648830083122 |
| 15 | 0.09814648830083122 |

## 分析

### analysis-claude.md

# RUN run_20260504_032451 (run-27) 分析（Claude 自己分析）

**作成日時**: 2026-05-04 12:38 JST
**run_id**: run_20260504_032451
**run_number**: 27
**dataset**: EUR_JPY 2025-10-01 〜 2026-04-01 (183403 bars)
**ga_config**: pop_size=40 / generations=15 / max_clause=1 / max_depth=4 / max_workers=2
**実行**: 7 分 (2026-05-04 12:24-12:31)

## 前提差分
なし (= archive Parquet / summary.json / scripts/codex 全て確認済)。

## 観察事実 (Facts)

### F1. Stage 通過数 (= 全壊滅)

| Stage | pass=True | pass=False | 通過率 |
|---|---:|---:|---:|
| A | 0 | 640 | 0.0% |
| B | 0 | 640 | 0.0% |
| C | 0 | 640 | 0.0% |
| graduation_count | — | — | 0 |

= **集団全 640 個体 (= pop=40 × gen=16) で Stage A の 1 段目すら通過個体ゼロ**。

### F2. Best fitness (= 局所最適停滞)

- best `fitness_pen = -0.007865665750332627` (= negative、 損失方向)
- best `fitness_raw = 0.001134` (= 限りなくゼロ近傍 positive)
- 該当 genome: `g11_i3` @ `tier1_EUR_JPY` generation 11 (n_nodes=2, active_clause=1, trade_count=3526)
- generation 11-15 で best fitness_pen=-0.0079 から動かない (= 局所最適 trap)
- 同値の top-5: g11_i3 / g11_i15 / g12_i0 / g12_i1 / g12_i8 (= 同 genome の重複 cluster)

### F3. Lane / instrument 分布 (= single instrument)

- 全 640 個体 `lane_id=tier1_EUR_JPY` のみ (= cross-pair shadow 不可能)
- 全 640 個体 `instrument=EUR_JPY` のみ
- summary.json `cross_pair_runtime_mode=skipped_single_instrument`

### F4. archive 書き込み伝搬漏れ (= 死にコード調査と整合)

- `archive_role`: 全 640 行 NaN (= mission_pass / progress_pass / score_bypass / ineligible のいずれにも分類されず)
- `source_stage`: 全 640 行 NaN
- `total_pnl`: 全 640 行 0.0
- `sharpe`: 全 640 行 NaN
- `max_drawdown_pct`: 全 640 行 0.0

= Stage A pass=False の個体は archive に raw metric が落ち、 集計可能 metric は trade_count / fitness_pen / trade_sharpe_raw のみ。

### F5. 構造的 over-trading (= 90% が >= 1500 trade)

| trade_count バケット | 件数 | 比率 | trade_sharpe_raw mean |
|---|---:|---:|---:|
| 0 (no-trade) | 9 | 1.4% | — (sentinel -1e9) |
| 1-49 (entry_count_min 未満) | 8 | 1.3% | — |
| 50-499 | 18 | 2.8% | -0.387 |
| 500-1499 | 28 | 4.4% | -0.296 |
| **>= 1500 (over-trading)** | **577** | **90.2%** | **-0.061** |

= 集団全体が「数千 trade を撃つ over-trader」 か「全く trade しない no-trader」 の 2 極化。

### F6. trade_sharpe_raw 上限が 0 を超えない (= Stage A 構造的不通過)

- max=0.001134 (= 1 個体のみ、 g11_i3 = best individual)
- mean=-0.0811、 std=0.105
- distribution: 99.8% が <= 0.0 (= negative)
- Stage A threshold=0.0 (config) → 全個体 trade_sharpe_raw <= threshold で fail

### F7. genome 多様性低下 (= active_clause / n_nodes 制約)

- `active_clause`: 全 640 個体で値 1 固定 (= config `max_clause=1` 制約)
- `n_nodes`: mean=2.4, max=4 (= config `max_depth=4` 配下)
- generation 進行で n_nodes が単調減少傾向 (gen 0: 3.05 → gen 15: 2.18) = elite 経由で短い genome に集約

### F8. fitness_pen sentinel 混入

- `fitness_pen = -1e9` (NO_EXPOSURE_FITNESS sentinel): 9 個体
- = trade_count < min_exposure_trade_count=1 で淘汰された個体 (= T034)

### F9. run-26 比較 (= performance 劣化)

| | run-26 (pop=96/gen=60, total=5856) | run-27 (pop=40/gen=15, total=640) |
|---|---|---|
| stage_a_pass=True | 0 | 0 |
| best fitness_pen | 0.005352 | -0.007866 |
| trade_sharpe_raw max | 0.0099 | 0.0011 |
| trade_count median | 3440 | 2942 |
| active_clause unique | [0, 1] | [1] |
| n_nodes mean | 1.32 | 2.40 |

= 規模縮小に伴い performance も劣化。 active_clause=0 の「no-clause」 個体が消滅 (= 1 固定)。

## 解釈・推論 (Interpretations)

### I1 (Critical, 反証可能性 高): 集団全体が Stage A trade_sharpe_raw 上限ゼロで固着 = primitive / 探索能力の構造的限界

- F6: trade_sharpe_raw max=0.001 で全 640 個体 negative ≒ zero
- F5: 90% が over-trading で trade_sharpe_raw mean=-0.06 (= 数千 trade で僅かに損失)
- = primitive 構成が「market neutral random-like signal」 しか生成できておらず、 GA 探索が positive sharpe 領域へ到達できない
- **反証**: もし primitive が機能的なら少なくとも N% の個体で trade_sharpe_raw > 0 が観察されるはず。 max=0.001 = 集団最高でも実質ゼロ = primitive の表現力不足が支配的

### I2 (Critical, 反証可能性 中): max_clause=1 / n_nodes mean=2.4 = genome 表現力が低すぎる

- F7: active_clause=1 固定、 n_nodes mean=2.4 (= max_depth=4 の半分)
- synthesis § 3 の cascade 設計は multi-clause を想定 (= clause 単位で signal 評価 + intersection)
- 1 clause / 2-3 node の浅い genome = 「単一 primitive の閾値判定のみ」 に近く、 複合 signal 不可
- **反証**: max_clause=2-3 + max_depth=6 で再走させて trade_sharpe_raw 分布が右シフトすれば仮説検証

### I3 (Warning, 反証可能性 高): 構造的 over-trading が signal noise を増幅 (= 禁止事項 #6 の逆問題)

- F5: 90% が >=1500 trade、 約 1 trade/3 分 (= M1 bar 期間で頻発)
- entry condition が緩すぎ → entry/exit の signal-to-noise が悪化 → trade_sharpe_raw が常に negative
- 禁止事項 #6 「取引回数削減で見かけ向上」 の逆 = 取引回数が構造的に多すぎる side
- **反証**: trade_sharpe_raw を trade_count で層別すると、 mid bucket (50-500) は -0.39 で更に悪い = signal そのものが貧弱、 trade 削減だけでは解決しない

### I4 (Warning, 反証可能性 高): archive 書き込み伝搬漏れ (= 禁止事項 #8 archive スキーマ伝搬漏れ)

- F4: archive_role / source_stage が全 NaN
- 死にコード調査 (handoff § 6.5.2) で `loop_closure.py` 全体 / `cpps_archive.determine_archive_role` が production 不到達 と判明
- archive 書き込み時 `archive_role` を None で書いている = synthesis § 8.2 の 4 状態分類が機能していない
- **反証**: stage_bc_evaluator + loop_closure 配線完了で archive_role が値を持つはず

### I5 (Warning, 反証可能性 中): cross-pair shadow 機能不可 (= single instrument のみ)

- F3: lane_id 全部 tier1_EUR_JPY、 cross_pair_runtime_mode=skipped_single_instrument
- synthesis § 1.1 mission の達成判定は「cross-pair (ii-lite) 評価も通過」 を要求
- = current config (single instrument) では構造的に mission 達成不可
- **反証**: multi-instrument config (tier1 6 ペア) で再走して cross-pair shadow が emit されるか確認

### I6 (Concern, 反証可能性 中): step 1.5-1.8 dual-path 配線で legacy 経路に副作用が出ていないか

- F9: run-26 → run-27 で best fitness_pen 劣化 (0.0054 → -0.0079)、 trade_sharpe_raw max 劣化 (0.01 → 0.001)
- step 1.5-1.8 は LOG_ONLY mode のため legacy 不変が設計、 ただし run 規模 (pop=96 → 40) も縮小しているので原因特定困難
- **反証**: pop=96/gen=60 で再走して run-26 と同 performance が再現すれば dual-path 副作用なし

### 禁止事項違反検知

| # | 禁止事項 | 観察 | 判定 |
|---|---|---|---|
| 1 | 評価期間延長 | dataset_span 不変 | OK |
| 2 | 数値操作 | sharpe NaN / total_pnl 0 = 表記不可 | N/A |
| 3 | GA ハック (fitness 関数歪曲) | fitness_pen sentinel -1e9 は T034 設計、 ハックなし | OK |
| 4 | live_criteria 緩和 | 設定不変 | OK |
| 5 | やたら複雑な案 | step 1.5-1.8 dual-path が複雑化シグナル | ⚠ Concern |
| 6 | 取引回数削減で見かけ向上 | 90% over-trading (= 逆方向) | OK |
| 7 | オーバーナイト前提 | trade_count 多 = intraday close 機能 | OK |
| 8 | archive スキーマ伝搬漏れ | archive_role / source_stage 全 NaN | ⚠ Concern |

## 次サイクル候補

### [Critical] Stage A 突破経路の確立 (= 北極星「live_criteria 充足個体出現」 への必須条件)

集団全体 trade_sharpe_raw <= 0.001 = primitive / genome 表現力 / 探索パラメータのいずれかが構造的不足。 候補施策 (= 1 つに絞って実験):

- **C1**: `max_clause` を 1 → 3、 `max_depth` を 4 → 6 に拡張 (= genome 表現力強化、 I2 反証実験)
- **C2**: primitive 拡充 (= regime filter / volatility-adjusted signal / session-aware entry threshold) — synthesis § 3 cascade 設計に合致、 ただし大規模変更
- **C3**: `mutation_rate` を 0.3 → 0.5、 `crossover_rate` を 0.7 → 0.5 で diversify (= 局所最適 trap 脱出、 cheap 試行)

**推奨**: C1 (cheap、 構造的、 反証明確) → 改善が見られなければ C2 検討

### [Warning] cross-pair 評価の有効化 (= mission 達成への前提条件)

- I5: 現 config single instrument で cross-pair shadow 不可
- swim_lane.tier1 6 ペア展開 + cross_pair.anchors の設定確認

### [Warning] archive 書き込み伝搬漏れ修正 (= 死にコード調査と統合判断)

- I4: archive_role / source_stage 全 NaN
- 死にコード解消 (handoff § 6.5.4 案 C) で loop_closure 配線 or 削除を判断
- ただし Stage A pass=0 状態では production runtime に到達しないので、 Stage A 突破後の課題

## 全体判定: **CRITICAL_DRIFT**

Stage A pass=0 が複数 Run 連続 (run-26 / run-27) = 探索の根本がブロックされている。 北極星「live_criteria 充足個体出現」 に向けて Stage A 突破機構の再設計が最優先。 cycle 13 で threshold を 0.0 に revert したが、 trade_sharpe_raw 上限ゼロという構造的問題は残存。

### analysis-codex.md

# RUN run_20260504_032451 (run-27) Codex 独立分析

## 前提
- `P1` 提供データ（archive集計・run比較）が正しいことを前提にする: **verified(入力内整合の範囲)**  
- `P2` Stage A 判定が `trade_sharpe_raw` と `threshold=0.0` に依存すること: **partially verified**（「max=0.001134」と「A通過0」が同時成立しており、判定式/別ゲートの未確認点あり）
- `P3` archive `NaN/0.0` は「保存経路の問題」であり「評価経路の問題」と同一とは限らない: **verified(C2準拠の仮置き)**
- `P4` run-26/run-27 比較は設定差（pop/gen）が大きく、単純比較は交絡を含む: **verified**
- `P5` mission は「live_criteria同時充足 + cross-pair(ii-lite)通過」: **verified**

## 観察事実 (Facts)
- run-27 は `n=640` 個体、`A/B/C pass=True = 0`、graduation=0。
- `best fitness_pen=-0.007865...`、`best fitness_raw=0.001134`。
- best 個体は `trade_count=3526`、上位は generation 11-15 で停滞。
- `instrument/lane` は全個体 `EUR_JPY/tier1_EUR_JPY` のみ。
- archive列 `archive_role/source_stage/sharpe` が全 NaN、`total_pnl/max_drawdown_pct` は全0.0。
- trade_count は `>=1500` が 90.2%、`0` は 1.4%（9個体は `fitness_pen=-1e9`）。
- `trade_sharpe_raw`: mean -0.0811, std 0.105, max 0.001134, 99.8% が 0以下。
- `active_clause` は全個体1、`n_nodes` 平均2.4（世代進行で減少）。
- run-26 比較で run-27 は best悪化（0.005352→-0.007866）、max raw Sharpe悪化（0.0099→0.0011）。

## 解釈・推論 (Interpretations)
- `I1`（Stage A固着=構造限界）: **一部支持だが確定不可**。  
  反証可能性(C9): Stage A判定ログで「失敗理由内訳（閾値未達/露出不足/他条件）」を個体単位で集計。もし閾値未達が主因でなければ I1 は棄却。
- `I2`（max_clause=1, n_nodes=2.4で表現力不足）: **現データだけでは過主張**。  
  反証可能性: 同一seed帯で `max_clause` だけを 1→2/3 に変えた A/B テスト。Stage A通過率・bestの改善がなければ棄却。  
  補足: run-26の方が良い値を出しており、単純に「複雑化不足」とは断定不能。
- `I3`（過剰取引がノイズ増幅）: **弱支持**。  
  反証可能性: trade_count分位ごとの raw Sharpe を同条件比較（同primitive/同世代）。低頻度帯も負なら「過剰取引主因」説は弱まる。  
  C7: n=640 で分布観察は妥当、ただし因果は未確定。
- `I4`（archive伝搬漏れ=loop_closure不到達）: **未確定**。  
  反証可能性: 評価時のメモリ上メトリクスと parquet 出力の差分監査。差分のみなら「観測系バグ」、評価値自体欠損なら「実行系バグ」。
- `I5`（cross-pair shadow不可）: **支持**（事実）。  
  ただし run-27段階では Stage A全滅のため、直近の一次ボトルネックではない。mission観点では中期の必須ブロッカー。
- `I6`（dual-path副作用）: **証拠不足でINCONCLUSIVE (C8)**。  
  反証可能性: legacy経路ON/OFFで同一入力リプレイし、stage判定・fitness差を比較。

### 追加で棄却/修正すべき点（Claude自己分析への指摘）
- 「全個体 `trade_sharpe_raw <= 0` でA失敗」は、提示値 `max=0.001134` と矛盾。**判定指標の取り違え/丸め/別ゲート存在**の可能性が高い。  
- `NaN列` から即「死にコード」と断定は **C2違反リスク**。保存スキーマ不一致でも同症状は起こる。  
- `max_clause拡張` を即 Critical に置くのは、**仕組み未検証のまま値を弄る**リスク。

## 次サイクル候補
- [Critical] **Stage A判定契約の監査を最優先**（判定式・入力指標・失敗理由内訳・archive出力の一致確認）。  
  目的: 「評価系が正しい」ことを先に反証不能化し、閾値/探索空間調整の前提を固める。
- [Warning] **archive伝搬漏れの切り分け修正**（実行系 vs 観測系）。  
  目的: 誤診防止。loop_closure到達可否はログ事実で確認。
- [Warning] **表現力拡張は小幅ABで検証**（`max_clause 1→2` など最小変更）。  
  目的: 大改造禁止に従い、Stage A通過率の因果を確認。
- [Warning] **cross-pair(ii-lite)を設計上有効化する準備**（複数instrumentデータ供給経路）。  
  目的: mission最終条件の未達要因を早期に解消。ただし直近は Stage A監査後。

## 全体判定
**CRITICAL_DRIFT**

---

### 質問への直答（要約）
1. **反証可能**: I1-I6すべて反証可能。現時点で明確に棄却寄りは `I2`（断定過剰）, `I4`（死にコード断定過剰）, `I6`（証拠不足）。  
2. 優先順位（mission寄与）: `Stage A判定契約監査` > `archive切り分け` > `小幅な表現力AB` > `cross-pair有効化`。  
3. 先人の知恵:  
   - Bailey et al. (2014) *The Probability of Backtest Overfitting*（見かけ改善の罠）  
   - López de Prado (2018) *Advances in Financial Machine Learning*（検証設計・リーク管理）  
   - Poli, Langdon, McPhee (2008) *A Field Guide to Genetic Programming*（早熟収束/表現力）  
   - zenigame内の同種実例は本回答では**要確認**（実ファイル未照合）。  
4. 見落とし候補: 「Stage A失敗理由の内訳不足」「評価値と保存値の分離」「判定式の符号/比較演算子/丸め誤差」。  
5. C1-C9観点のover-claim: 上記 `I2/I4/I6` が主。特に C1, C2, C8 の逸脱リスクがある。

### analysis-merged.md

# マージ分析: Run 27

**作成日時**: 2026-05-04 12:43 JST
**入力**: analysis-claude.md / analysis-codex.md
**全体判定**: 両者 CRITICAL_DRIFT 一致

## 合意事項 (両者一致)

| # | 合意点 | Claude | Codex |
|---|---|---|---|
| C1 | Stage A pass=0 全 640 個体 = 集団全壊滅 | F1 | Facts |
| C2 | best fitness_pen=-0.0079 で gen 11-15 停滞 | F2 | Facts |
| C3 | trade_count >= 1500 が 90% (構造的 over-trading) | F5 | Facts |
| C4 | trade_sharpe_raw 99.8% が <= 0.0 | F6 | Facts |
| C5 | active_clause=1 / n_nodes mean=2.4 (genome 表現力低) | F7 | Facts |
| C6 | archive_role / source_stage 全 NaN (= 観測異常あり) | F4 | Facts |
| C7 | single instrument (tier1_EUR_JPY のみ) | F3 | Facts |
| C8 | run-26 → run-27 で performance 劣化 | F9 | Facts |
| C9 | 全体判定 CRITICAL_DRIFT | 判定 | 判定 |

## Claude 独自の発見

| # | 発見 | 検証要否 |
|---|---|---|
| Cl1 | step 1.5-1.8 dual-path 配線が複雑化シグナル (禁止事項 #5) | 検証要 |
| Cl2 | sentinel value -1e9 (NO_EXPOSURE_FITNESS) 9 個体 | 観察済 |
| Cl3 | n_nodes が generation 進行で単調減少 (3.05 → 2.18) | 観察済 |

## Codex 独自の発見・指摘 (= Claude 修正点)

| # | 指摘 | 重要度 | C ルール |
|---|---|---|---|
| Cx1 | **Stage A 判定契約を最優先で監査せよ**: trade_sharpe_raw max=0.001134 が threshold=0 を上回るのに pass=0 = 判定指標の取り違え or 別ゲート存在の可能性 | Critical | C1 (design-first), C2 |
| Cx2 | 「archive NaN = 死にコード = loop_closure 不到達」 と即決は **C2 違反**。 評価系 vs 観測系の切り分けが先 | Warning | C2 |
| Cx3 | 「max_clause 拡張」 を即 Critical に置くのは **「仕組み未検証で値弄り」 思考原則違反** | Warning | 思考原則 |
| Cx4 | 「全個体 trade_sharpe_raw <= 0 で A 失敗」 は提示値 max=0.001134 と矛盾 (= 判定指標の取り違え/丸め/別ゲート) | Critical | C2 |
| Cx5 | run-26 → run-27 比較は pop/gen の差が大きく交絡を含む = 単純比較は危険 | Warning | C3 (collider/confounder) |
| Cx6 | 先人の知恵: Bailey et al. (2014) Probability of Backtest Overfitting / López de Prado (2018) Advances in FinML / Poli et al. (2008) GP Field Guide (= 早熟収束/表現力) | Reference | — |

## 矛盾・要議論

| # | 論点 | Claude | Codex | 判定 |
|---|---|---|---|---|
| M1 | I1 「集団 trade_sharpe_raw 上限ゼロは primitive 限界」 | 強支持 | 「一部支持だが確定不可、 まず判定契約監査」 | **Codex 採用** (= 判定契約を先に監査) |
| M2 | I2 「max_clause=1 は genome 表現力不足」 | 強支持 | 「現データだけでは過主張、 同一 seed 帯で AB テスト必要」 | **Codex 採用** (= 小幅 AB で検証) |
| M3 | I4 「archive NaN = loop_closure 死にコード」 | 強支持 | 「未確定、 切り分け監査が先」 | **Codex 採用** |
| M4 | I6 「dual-path 副作用」 | Concern | 「証拠不足 INCONCLUSIVE (C8)」 | **Codex 採用** (= INCONCLUSIVE 第一級) |

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | causal_path | falsification | success_criterion | 期待効果 |
|---|---|---|---|---|---|---|---|---|---|
| **P1** | **Stage A 判定契約の監査** (= 判定式・入力指標・失敗理由内訳・archive 出力の一致確認) | **Critical** | Codex Cx1, Cx4 | (前段) Stage A pass>0 の前提条件 | trade_sharpe_raw max=0.001 > threshold=0 なのに pass=0 | 判定式が trade_sharpe_raw 以外を見ている / 別ゲート存在 / 丸め誤差 | 監査で「判定式は正しい」 と確認できれば棄却 = primitive 仮説 (P3) へ進む | (a) 判定式の SSOT 文書化 (b) 個体毎 fail reason 集計が出る (c) archive 観測値と評価時値の一致 | 「評価系正しい」 を反証不能化 → 後続施策の前提固める |
| **P2** | **archive 伝搬漏れの切り分け監査** (= 評価時 in-memory metric vs parquet 出力の差分監査) | Warning | Codex Cx2 | (観測) archive_role / source_stage / sharpe / total_pnl が値を持つ | archive 列全 NaN | 観測経路 (archive write) のバグ or 評価経路 (loop_closure 不到達) | 評価時に値があれば「観測系バグ」、 評価時にもなければ「評価系バグ」 | 切り分け結果が log で確認可能 | 誤診防止 → 次サイクルで適切な fix を選択 |
| **P3** | **小幅 AB で表現力拡張** (max_clause 1→2 のみ、 max_depth 不変) | Warning | Codex 推薦 | (探索能力) trade_sharpe_raw max が右シフト | trade_sharpe_raw max=0.001 が天井 | 1 clause では複合 signal 不可 → 2 clause で intersection 可能 | AB で trade_sharpe_raw max 改善なければ棄却 | trade_sharpe_raw max > 0.005 が観測される | Stage A 通過率の因果を最小変更で確認 |
| **P4** | **cross-pair (ii-lite) 有効化準備** (= multi-instrument config) | Warning | Codex Cx, Claude I5 | (mission 最終条件) cross_pair_runtime_mode != skipped | single instrument のため cross-pair 評価不可 | tier1_EUR_JPY 単独 lane → cross-pair anchor 不在 | ただし Stage A 全滅では一次 ボトルネックではない | tier1 6 ペア展開後 cross_pair shadow が emit | mission の最終ブロッカー除去準備 (= 中期) |

**提案数**: 4 件、 Codex の優先順位推奨 (P1 > P2 > P3 > P4) を採用。

## 次フェーズへの申し送り

- B-2 改善策合議では **P1 を最優先で議論**、 P3 (max_clause 拡張) は P1 監査結果次第で gate 判断
- P4 cross-pair は中期、 今サイクルでは「準備のみ」 (= 実装ではなく config / lane 設計の review)
- P2 archive 伝搬漏れは P1 監査と同時実行可能 (= 並列、 同一監査セッション内で扱う)
- メタ過学習ガード: 全提案が「数値弄り」 ではなく「監査・切り分け・最小 AB」 = Reactive Parametric ではない

