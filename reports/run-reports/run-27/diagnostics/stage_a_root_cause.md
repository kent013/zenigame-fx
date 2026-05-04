# Stage A Root Cause Diagnostic: run_20260504_032451

- **run_number**: 27
- **diagnosis**: **INCONCLUSIVE**
- **confidence**: low
- **config_source**: run_effective
- **evaluated_hypotheses**: ['P1', 'P2']

## サマリー
- Stage A pass: 0 / B pass: 0 / C pass: 0
- best generation: 11
- best plateau length: 5 (start gen: 11)

## 分類判定 (= 反証結果)
- **P1**:
  - condition: `raw_max < 0.005`
  - actual: `0.0011343342496673721`
  - match: **True**
  - rationale: trade_sharpe_raw max が 0.005 未満 = primitive 構成が「market neutral random-like」 しか生成しておらず GA 探索が positive sharpe 領域へ到達不能
- **P2**:
  - condition: `penalty_killed >= max(3, ceil(0.01*N_valid=623)) = 7`
  - actual: `30`
  - match: **True**
- **P3**:
  - condition: `n_nodes std drop > 0.5 ∧ active_clause unique == 1`
  - actual: `non_evaluable`
  - match: **False**
  - non_evaluable_reason: summary.json から max_clause 取得不能

## 判定理由
- 複数仮説該当: ['P1', 'P2'] = 1 つに絞れず

## fitness_pen 分解
| 統計量 | trade_sharpe_raw | size_norm (逆算) | penalty | fitness_pen |
|---|---|---|---|---|
| max | 0.001134 | 0.650000 | 0.019500 | -0.007866 |
| mean | -0.081115 | 0.365490 | 0.010965 | -0.092079 |
| std | 0.105303 | 0.124027 | 0.003721 | 0.106203 |

_注: 逆算 size_norm = (raw - pen) / alpha (近似) (alpha=0.03)_

## trade_sharpe_raw 世代別
| generation | n | max | mean | median | n_positive |
|---|---|---|---|---|---|
| 0 | 40 | -0.0218 | -0.2102 | -0.1161 | 0 |
| 1 | 40 | -0.0190 | -0.1440 | -0.0926 | 0 |
| 2 | 40 | -0.0247 | -0.1135 | -0.0750 | 0 |
| 3 | 40 | -0.0132 | -0.0922 | -0.0687 | 0 |
| 4 | 40 | -0.0132 | -0.0643 | -0.0675 | 0 |
| 5 | 40 | -0.0132 | -0.0576 | -0.0512 | 0 |
| 6 | 40 | -0.0215 | -0.0537 | -0.0535 | 0 |
| 7 | 40 | -0.0215 | -0.0610 | -0.0232 | 0 |
| 8 | 40 | -0.0051 | -0.0692 | -0.0496 | 0 |
| 9 | 40 | -0.0051 | -0.0508 | -0.0215 | 0 |
| 10 | 40 | -0.0051 | -0.0694 | -0.0429 | 0 |
| 11 | 40 | 0.0011 | -0.0703 | -0.0398 | 2 |
| 12 | 40 | 0.0011 | -0.0410 | -0.0215 | 5 |
| 13 | 40 | 0.0011 | -0.0664 | -0.0707 | 6 |
| 14 | 40 | 0.0011 | -0.0949 | -0.0603 | 7 |
| 15 | 40 | 0.0011 | -0.0730 | -0.0650 | 10 |

## trade_count バケット別
| バケット | n | trade_sharpe mean | fitness_pen mean |
|---|---|---|---|
| 0 | 9 | — | — |
| 1-49 | 8 | — | — |
| 50-499 | 18 | -0.3866 | -0.4005 |
| 500-1499 | 28 | -0.2955 | -0.3069 |
| >=1500 | 577 | -0.0612 | -0.0720 |

## diversity (n_nodes / active_clause 推移)
| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |
|---|---|---|---|---|
| 0 | 3.05 | 1.011 | 1.00 | 1 |
| 1 | 3.05 | 1.011 | 1.00 | 1 |
| 2 | 2.65 | 0.864 | 1.00 | 1 |
| 3 | 2.48 | 0.905 | 1.00 | 1 |
| 4 | 2.42 | 0.958 | 1.00 | 1 |
| 5 | 2.40 | 0.810 | 1.00 | 1 |
| 6 | 2.10 | 0.441 | 1.00 | 1 |
| 7 | 2.02 | 0.423 | 1.00 | 1 |
| 8 | 2.10 | 0.545 | 1.00 | 1 |
| 9 | 2.30 | 0.464 | 1.00 | 1 |
| 10 | 2.42 | 0.636 | 1.00 | 1 |
| 11 | 2.23 | 0.530 | 1.00 | 1 |
| 12 | 2.25 | 0.543 | 1.00 | 1 |
| 13 | 2.48 | 0.679 | 1.00 | 1 |
| 14 | 2.33 | 0.656 | 1.00 | 1 |
| 15 | 2.17 | 0.781 | 1.00 | 1 |

## penalty 効果
- raw>0 個体数: 30
- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): 30
- raw>0 ∧ fitness_pen>0 (= 通過候補): 0

## extra_metrics
- raw_positive_count: 30
- fitness_pen_positive_count: 0
- sentinel_by_generation: {0: 10, 1: 2, 2: 1, 6: 2, 9: 1, 13: 1}

## data_quality
- n_valid / n_total: 623 / 640
- sentinel 個体数: 17
  - T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能
- warnings:
  - summary.run_id (run_20260504_032436) != archive run_id (run_20260504_032451) = run_id 取り違えの可能性、 P3 判定を degrade

## run_effective_config (= audit trail)
- _source: run_effective
- summary_path: /Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-27/summary.json
- summary_run_id: run_20260504_032436
- max_clause: None
- stage_a_alpha: 0.03
- stage_a_threshold: 0.0
