# Stage A Root Cause Diagnostic: run_20260504_061526

- **run_number**: 29
- **diagnosis**: **P2**
- **confidence**: high
- **config_source**: run_effective
- **evaluated_hypotheses**: ['P1', 'P2']

## サマリー
- Stage A pass: 241 / B pass: 0 / C pass: 0
- best generation: 8
- best plateau length: 1 (start gen: 15)

## 分類判定 (= 反証結果)
- **P1**:
  - condition: `raw_max < 0.005`
  - actual: `0.1479798396882517`
  - match: **False**
- **P2**:
  - condition: `penalty_killed >= max(3, ceil(0.01*N_valid=605)) = 7`
  - actual: `37`
  - match: **True**
- **P3**:
  - condition: `n_nodes std drop > 0.5 ∧ active_clause unique == 1`
  - actual: `non_evaluable`
  - match: **False**
  - non_evaluable_reason: run-effective config max_clause=1 <= 1 のため active_clause unique==1 は config 由来の擬陽性、 P3 識別力なし

## fitness_pen 分解
| 統計量 | trade_sharpe_raw | size_norm (逆算) | penalty | fitness_pen |
|---|---|---|---|---|
| max | 0.147980 | 0.650000 | 0.019500 | 0.129980 |
| mean | -0.041722 | 0.439174 | 0.013175 | -0.054897 |
| std | 0.124304 | 0.145669 | 0.004370 | 0.123669 |

_注: 逆算 size_norm = (raw - pen) / alpha (近似) (alpha=0.03)_

## trade_sharpe_raw 世代別
| generation | n | max | mean | median | n_positive |
|---|---|---|---|---|---|
| 0 | 40 | -0.0215 | -0.2090 | -0.2022 | 0 |
| 1 | 40 | -0.0214 | -0.1106 | -0.0940 | 0 |
| 2 | 40 | -0.0108 | -0.0906 | -0.0586 | 0 |
| 3 | 40 | -0.0108 | -0.1090 | -0.0593 | 0 |
| 4 | 40 | -0.0003 | -0.1029 | -0.0620 | 0 |
| 5 | 40 | 0.0059 | -0.0768 | -0.0727 | 2 |
| 6 | 40 | 0.0387 | -0.0539 | -0.0214 | 6 |
| 7 | 40 | 0.0743 | -0.0474 | -0.0108 | 15 |
| 8 | 40 | 0.1480 | -0.0013 | 0.0065 | 24 |
| 9 | 40 | 0.1030 | -0.0007 | 0.0260 | 23 |
| 10 | 40 | 0.1030 | -0.0532 | -0.0084 | 18 |
| 11 | 40 | 0.1105 | 0.0101 | 0.0384 | 24 |
| 12 | 40 | 0.1030 | 0.0263 | 0.0572 | 30 |
| 13 | 40 | 0.1036 | 0.0243 | 0.0732 | 32 |
| 14 | 40 | 0.1205 | 0.0591 | 0.0837 | 35 |
| 15 | 40 | 0.1134 | 0.0473 | 0.0838 | 33 |

## trade_count バケット別
| バケット | n | trade_sharpe mean | fitness_pen mean |
|---|---|---|---|
| 0 | 15 | — | — |
| 1-49 | 39 | -0.0437 | -0.0609 |
| 50-499 | 394 | -0.0070 | -0.0209 |
| 500-1499 | 35 | -0.2676 | -0.2813 |
| >=1500 | 157 | -0.0783 | -0.0889 |

## diversity (n_nodes / active_clause 推移)
| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |
|---|---|---|---|---|
| 0 | 2.90 | 1.081 | 0.97 | 2 |
| 1 | 2.80 | 1.091 | 1.00 | 1 |
| 2 | 2.77 | 1.143 | 1.00 | 1 |
| 3 | 2.38 | 1.055 | 1.00 | 1 |
| 4 | 2.42 | 1.083 | 1.00 | 1 |
| 5 | 2.80 | 1.181 | 1.00 | 1 |
| 6 | 3.30 | 1.091 | 1.00 | 1 |
| 7 | 3.17 | 0.931 | 1.00 | 1 |
| 8 | 3.33 | 0.859 | 1.00 | 1 |
| 9 | 2.95 | 0.904 | 1.00 | 1 |
| 10 | 2.52 | 0.905 | 1.00 | 1 |
| 11 | 2.77 | 0.733 | 1.00 | 1 |
| 12 | 2.95 | 0.714 | 1.00 | 1 |
| 13 | 2.92 | 0.616 | 1.00 | 1 |
| 14 | 3.00 | 0.506 | 1.00 | 1 |
| 15 | 2.92 | 0.526 | 1.00 | 1 |

## penalty 効果
- raw>0 個体数: 242
- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): 37
- raw>0 ∧ fitness_pen>0 (= 通過候補): 205

## extra_metrics
- raw_positive_count: 242
- fitness_pen_positive_count: 205
- sentinel_by_generation: {0: 6, 1: 3, 2: 2, 3: 2, 4: 2, 6: 1, 7: 2, 8: 6, 9: 5, 10: 1, 11: 2, 12: 2, 15: 1}

## data_quality
- n_valid / n_total: 605 / 640
- sentinel 個体数: 35
  - T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能

## run_effective_config (= audit trail)
- _source: run_effective
- summary_path: /Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-29/summary.json
- summary_run_id: run_20260504_061526
- max_clause: 1
- stage_a_alpha: 0.03
- stage_a_threshold: -0.0172
