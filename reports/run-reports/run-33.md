# Run 33 — run_20260504_130805

**Generated**: 2026-05-04T13:08:05.211426+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 183403
  - bars_holdout: 20457

## 使命判定

未達

- ❌ **sharpe**: 0.12914332497546277 / threshold 1.0
- ❌ **total_pnl**: 0.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 53 (range 50〜5000)

## GA 設定

- population_size: 40
- generations: 15
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g15_i7`
- generation: 15
- fitness: **0.10964332497546277**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 53
- total_pnl: 0.0
- sharpe: 0.12914332497546277
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1250
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 640
- Stage A pass: 99
- Stage B pass: 2
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 640 | 99 | 2 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 640 | 99 | 2 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=640, mean=1, median=1.0000, std=0.0000, min=1, max=1
- n_nodes: n=640, mean=2.3062, median=2.0000, std=0.9937, min=1, max=4

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=99, mean=0.3131, median=0.2500, std=0.2097, min=0.0000, max=0.8750
- dsr: n=0
- n_fold_effective (Stage A pass): n=99, mean=4.4444, median=4, std=1.9552, min=0, max=9
- positive_fold_ratio_effective (Stage A pass): n=97, mean=0.5125, median=0.5000, std=0.1538, min=0.0000, max=0.8333

## Stage B failure reason 集計

- Stage A pass = 99, Stage B pass = 2, failures = 97 (primary_sum = 97)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 96 |
| `positive_fold_ratio<min` | 1 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 96 |
| `positive_fold_ratio<min` | 97 |
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
- trade_count=0 個体比率: 2.3% (15/640)
- best 個体 trade_count: 53
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 640
- metric_stage 分布: stage_a_evaluated=97, stage_a_only=541, stage_b_evaluated=2
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=541, mean=-664228.3734, median=-1000070.0000, std=444124.5534, min=-1003220.0000, max=4190.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=526): n=526, mean=-683170.2471, median=-1000080.0000, std=435810.7364, min=-1003220.0000, max=4190.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=99): n=99, mean=-8243.4343, median=14050.0000, std=142614.7885, min=-1000240.0000, max=26580.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) の辞書式 (v3.1_stage_b_priority, T046)。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g15_i7` | 15 | tier1_EUR_JPY | EUR_JPY | 0.1096 | 0.1291 | ✅ | ❌ | ❌ | 53 | — |
| 2 | `g12_i23` | 12 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |
| 3 | `g13_i0` | 13 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |
| 4 | `g13_i39` | 13 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |
| 5 | `g14_i0` | 14 | tier1_EUR_JPY | EUR_JPY | 0.0922 | 0.1012 | ✅ | ❌ | ❌ | 68 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.015449238780145872 |
| 1 | 0.015449238780145872 |
| 2 | -0.01870806106892877 |
| 3 | -0.01870806106892877 |
| 4 | -0.01870806106892877 |
| 5 | -0.01870806106892877 |
| 6 | -0.01870806106892877 |
| 7 | 0.0053274223193534725 |
| 8 | 0.06057645179905452 |
| 9 | 0.01745470245593319 |
| 10 | 0.053333119479138075 |
| 11 | 0.061198222260088 |
| 12 | 0.0921672280645699 |
| 13 | 0.0921672280645699 |
| 14 | 0.0921672280645699 |
| 15 | 0.10964332497546277 |

## 分析

### analysis-codex.md

前提を固定して結論を出します。今回は提示データのみで判定し、未検証は `INCONCLUSIVE` とします。

**前提検証（C4）**
- `g8_i33/g12_i17` はともに `stage_b_pass=True`, `n_fold_effective=9`, `positive_fold_ratio_effective=6/9=0.667`。
- `fold_trade_count_min=10`、`trade_count=16/17`、`stage_b_unavailable_reason_counts=全0` は確認済み。
- `live_criteria.trade_count_min=50` は確認済み。

**Fact（C6）**
1. Q1: `5 folds` 規範との乖離  
- もし `wf_*_days` が「営業日」実装なら、6か月（約120営業日）で9foldは出にくい。  
- ただし「実データ期間の認識違い」または「fold単位が日でない」可能性があり、現時点で bug 断定不可（C1/C2, `INCONCLUSIVE`）。

2. Q1補足: `positive_fold_min=0.60` の厳しさ  
- 9foldだと閾値は実質 `ceil(0.60*9)=6` なので `6/9=0.667` 必要。  
- 5foldだと `3/5=0.60`。  
- よって「9foldだから緩い」は成立しません。離散化の都合でむしろ厳しめです。

3. Q2: `fold_trade_count_min` 整合性  
- 全fold成立なら foldごと最低10件が必要な解釈では総計90件以上が必要。  
- 実測16/17とは論理矛盾。  
- したがって「`fold_trade_count_min` は per-fold gate として効いていない」か「`trade_count` の計測スコープが別」のどちらか（高確度）。

4. Q3: North Star整合性  
- Stage B通過個体が `trade_count<50` で Stage C落ちし続ける構造は現実に起きている。  
- これは禁止事項 #6（見栄え改善方向）と逆で、むしろ評価段の接続不整合の問題。

**結論（1 round 収束）**
- cycle 21 の最小変更は **案Aを一点集中**：  
  **Stage Bの fold有効性判定（特に `fold_trade_count_min`）を SSOT で明文化し、decision_trace に foldごとの `oos_trade_count / available判定理由` を必須出力**。  
- live_criteriaを即Stage BへAND注入（案B/C）は、まず gate実装実態を確定する前だと C1/C9違反リスクが高い。

**反証可能仮説（Q5）**
- 仮説H:  
  「low-trade個体のStage B通過は、`fold_trade_count_min` の per-fold適用欠落（または等価のスコープ不整合）が主因である。」

**1 cycleでの最小実験**
1. 判定ログを fold単位で固定出力（`oos_trade_count`, `is_available`, `unavailable_reason`）。  
2. `fold_trade_count_min` を per-fold availability に強制適用（値は変更しない）。  
3. 同一設定で cycle 21 実行。  
4. 反証条件:  
- もし g8_i33/g12_i17 がなお `stage_b_pass=True` なら仮説Hは棄却。  
- `stage_b_pass=False` へ反転し、通過群の trade_count 分布が上がれば仮説H支持。

この順なら「数値操作なし」「仕組み先行」「1サイクル検証可能」を満たします。

