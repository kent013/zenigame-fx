# Stage A Root Cause Diagnostic: run_20260504_043138

- **run_number**: 27
- **diagnosis**: **INCONCLUSIVE**
- **confidence**: low
- **config_source**: run_effective
- **evaluated_hypotheses**: ['P1', 'P2']

## サマリー
- Stage A pass: 142 / B pass: 0 / C pass: 0
- best generation: 11
- best plateau length: 2 (start gen: 14)

## 分類判定 (= 反証結果)
- **P1**:
  - condition: `raw_max < 0.005`
  - actual: `0.15990754144831815`
  - match: **False**
- **P2**:
  - condition: `penalty_killed >= max(3, ceil(0.01*N_valid=537)) = 6`
  - actual: `1`
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
| max | 0.159908 | 0.650000 | 0.019500 | 0.150908 |
| mean | -0.102578 | 0.312663 | 0.009380 | -0.111958 |
| std | 0.143054 | 0.116853 | 0.003506 | 0.142982 |

_注: 逆算 size_norm = (raw - pen) / alpha (近似) (alpha=0.03)_

## trade_sharpe_raw 世代別
| generation | n | max | mean | median | n_positive |
|---|---|---|---|---|---|
| 0 | 40 | -0.0359 | -0.2270 | -0.1443 | 0 |
| 1 | 40 | -0.0235 | -0.1683 | -0.1011 | 0 |
| 2 | 40 | 0.0253 | -0.1120 | -0.0770 | 1 |
| 3 | 40 | 0.0253 | -0.0906 | -0.0782 | 2 |
| 4 | 40 | 0.0253 | -0.0751 | -0.0659 | 3 |
| 5 | 40 | 0.0253 | -0.1124 | -0.0876 | 4 |
| 6 | 40 | 0.0253 | -0.0770 | -0.0749 | 6 |
| 7 | 40 | 0.0253 | -0.0955 | -0.0790 | 6 |
| 8 | 40 | 0.0253 | -0.1072 | -0.0704 | 8 |
| 9 | 40 | 0.0253 | -0.0576 | -0.0384 | 11 |
| 10 | 40 | 0.0253 | -0.1067 | -0.0239 | 16 |
| 11 | 40 | 0.1599 | -0.0856 | 0.0253 | 17 |
| 12 | 40 | 0.0253 | -0.1258 | -0.1635 | 12 |
| 13 | 40 | 0.1071 | -0.0976 | -0.0776 | 14 |
| 14 | 40 | 0.1071 | -0.0757 | 0.0253 | 19 |
| 15 | 40 | 0.1071 | -0.0346 | 0.0253 | 20 |

## trade_count バケット別
| バケット | n | trade_sharpe mean | fitness_pen mean |
|---|---|---|---|
| 0 | 20 | — | — |
| 1-49 | 89 | -0.4215 | -0.4312 |
| 50-499 | 215 | -0.0636 | -0.0734 |
| 500-1499 | 47 | -0.2529 | -0.2643 |
| >=1500 | 269 | -0.1003 | -0.1091 |

## diversity (n_nodes / active_clause 推移)
| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |
|---|---|---|---|---|
| 0 | 2.50 | 0.877 | 0.97 | 2 |
| 1 | 2.48 | 1.062 | 1.00 | 1 |
| 2 | 2.33 | 1.023 | 1.00 | 1 |
| 3 | 2.08 | 0.764 | 1.00 | 1 |
| 4 | 1.85 | 0.736 | 1.00 | 1 |
| 5 | 2.00 | 0.641 | 1.00 | 1 |
| 6 | 1.80 | 0.564 | 1.00 | 1 |
| 7 | 1.82 | 0.636 | 1.00 | 1 |
| 8 | 1.93 | 0.656 | 1.00 | 1 |
| 9 | 1.95 | 0.639 | 1.00 | 1 |
| 10 | 1.98 | 0.530 | 1.00 | 1 |
| 11 | 1.95 | 0.504 | 1.00 | 1 |
| 12 | 1.85 | 0.533 | 1.00 | 1 |
| 13 | 2.02 | 0.577 | 1.00 | 1 |
| 14 | 2.05 | 0.597 | 1.00 | 1 |
| 15 | 2.15 | 0.770 | 1.00 | 1 |

## penalty 効果
- raw>0 個体数: 139
- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): 1
- raw>0 ∧ fitness_pen>0 (= 通過候補): 138

## extra_metrics
- raw_positive_count: 139
- fitness_pen_positive_count: 138
- sentinel_by_generation: {0: 14, 2: 1, 3: 2, 4: 2, 5: 4, 6: 9, 7: 10, 8: 5, 9: 5, 10: 6, 11: 9, 12: 10, 13: 8, 14: 6, 15: 12}

## data_quality
- n_valid / n_total: 537 / 640
- sentinel 個体数: 103
  - T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能

## run_effective_config (= audit trail)
- _source: run_effective
- summary_path: /Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-27/summary.json
- summary_run_id: run_20260504_043138
- max_clause: 1
- stage_a_alpha: 0.03
- stage_a_threshold: -0.0172
