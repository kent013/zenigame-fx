# Stage A Root Cause Diagnostic: run_20260504_123921

- **run_number**: 32
- **diagnosis**: **INCONCLUSIVE**
- **confidence**: low
- **config_source**: run_effective
- **evaluated_hypotheses**: ['P1', 'P2']

## サマリー
- Stage A pass: 99 / B pass: 2 / C pass: 0
- best generation: 15
- best plateau length: 1 (start gen: 15)

## 分類判定 (= 反証結果)
- **P1**:
  - condition: `raw_max < 0.005`
  - actual: `0.12914332497546277`
  - match: **False**
- **P2**:
  - condition: `penalty_killed >= max(3, ceil(0.01*N_valid=612)) = 7`
  - actual: `5`
  - match: **False**
- **P3**:
  - condition: `n_nodes std drop > 0.5 ∧ active_clause unique == 1`
  - actual: `non_evaluable`
  - match: **False**
  - non_evaluable_reason: run-effective config max_clause=1 <= 1 のため active_clause unique==1 は config 由来の擬陽性、 P3 識別力なし

## 判定理由
- どの仮説にも明確該当せず

## fitness_pen 分解
| 統計量 | trade_sharpe_raw | size_norm (逆算) | penalty | fitness_pen |
|---|---|---|---|---|
| max | 0.129143 | 0.650000 | 0.019500 | 0.109643 |
| mean | -0.077770 | 0.359559 | 0.010787 | -0.088557 |
| std | 0.162843 | 0.163941 | 0.004918 | 0.162806 |

_注: 逆算 size_norm = (raw - pen) / alpha (近似) (alpha=0.03)_

## trade_sharpe_raw 世代別
| generation | n | max | mean | median | n_positive |
|---|---|---|---|---|---|
| 0 | 40 | 0.0349 | -0.2779 | -0.0947 | 1 |
| 1 | 40 | 0.0349 | -0.0956 | -0.0996 | 1 |
| 2 | 40 | -0.0037 | -0.0824 | -0.0710 | 0 |
| 3 | 40 | -0.0037 | -0.0878 | -0.0743 | 0 |
| 4 | 40 | -0.0037 | -0.0685 | -0.0541 | 0 |
| 5 | 40 | -0.0037 | -0.0796 | -0.0665 | 0 |
| 6 | 40 | -0.0037 | -0.0718 | -0.0663 | 0 |
| 7 | 40 | 0.0143 | -0.0626 | -0.0566 | 1 |
| 8 | 40 | 0.0801 | -0.0856 | -0.0674 | 2 |
| 9 | 40 | 0.0265 | -0.0893 | -0.0677 | 3 |
| 10 | 40 | 0.0683 | -0.0709 | -0.0682 | 5 |
| 11 | 40 | 0.0747 | -0.0651 | -0.0689 | 11 |
| 12 | 40 | 0.1012 | -0.0433 | -0.0494 | 15 |
| 13 | 40 | 0.1012 | -0.0331 | -0.0033 | 18 |
| 14 | 40 | 0.1012 | -0.0048 | 0.0293 | 20 |
| 15 | 40 | 0.1291 | -0.0511 | -0.0011 | 17 |

## trade_count バケット別
| バケット | n | trade_sharpe mean | fitness_pen mean |
|---|---|---|---|
| 0 | 15 | — | — |
| 1-49 | 24 | -0.5357 | -0.5496 |
| 50-499 | 214 | -0.0324 | -0.0445 |
| 500-1499 | 40 | -0.1878 | -0.1982 |
| >=1500 | 347 | -0.0786 | -0.0885 |

## diversity (n_nodes / active_clause 推移)
| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |
|---|---|---|---|---|
| 0 | 2.58 | 0.931 | 1.00 | 1 |
| 1 | 2.38 | 0.897 | 1.00 | 1 |
| 2 | 2.52 | 0.960 | 1.00 | 1 |
| 3 | 2.05 | 0.904 | 1.00 | 1 |
| 4 | 2.45 | 1.061 | 1.00 | 1 |
| 5 | 2.60 | 1.128 | 1.00 | 1 |
| 6 | 2.23 | 1.187 | 1.00 | 1 |
| 7 | 1.95 | 1.061 | 1.00 | 1 |
| 8 | 2.17 | 1.083 | 1.00 | 1 |
| 9 | 2.02 | 0.920 | 1.00 | 1 |
| 10 | 2.25 | 1.056 | 1.00 | 1 |
| 11 | 2.12 | 0.939 | 1.00 | 1 |
| 12 | 2.38 | 0.979 | 1.00 | 1 |
| 13 | 2.27 | 0.905 | 1.00 | 1 |
| 14 | 2.50 | 0.784 | 1.00 | 1 |
| 15 | 2.42 | 0.903 | 1.00 | 1 |

## penalty 効果
- raw>0 個体数: 94
- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): 5
- raw>0 ∧ fitness_pen>0 (= 通過候補): 89

## extra_metrics
- raw_positive_count: 94
- fitness_pen_positive_count: 89
- sentinel_by_generation: {0: 8, 2: 2, 4: 1, 5: 1, 10: 1, 11: 2, 12: 2, 13: 1, 14: 4, 15: 6}

## data_quality
- n_valid / n_total: 612 / 640
- sentinel 個体数: 28
  - T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能

## run_effective_config (= audit trail)
- _source: run_effective
- summary_path: /Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-32/summary.json
- summary_run_id: run_20260504_123921
- max_clause: 1
- stage_a_alpha: 0.03
- stage_a_threshold: -0.0172
