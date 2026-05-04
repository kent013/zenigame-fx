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
