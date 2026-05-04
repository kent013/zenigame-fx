# Stage A Root Cause Diagnostic: run_20260504_065916

- **run_number**: 31
- **diagnosis**: **P1**
- **confidence**: high
- **config_source**: run_effective
- **evaluated_hypotheses**: ['P1', 'P2']

## サマリー
- Stage A pass: 2 / B pass: 0 / C pass: 0
- best generation: 14
- best plateau length: 2 (start gen: 14)

## 分類判定 (= 反証結果)
- **P1**:
  - condition: `raw_max < 0.005`
  - actual: `0.004640911397074999`
  - match: **True**
  - rationale: trade_sharpe_raw max が 0.005 未満 = primitive 構成が「market neutral random-like」 しか生成しておらず GA 探索が positive sharpe 領域へ到達不能
- **P2**:
  - condition: `penalty_killed >= max(3, ceil(0.01*N_valid=606)) = 7`
  - actual: `2`
  - match: **False**
- **P3**:
  - condition: `n_nodes std drop > 0.5 ∧ active_clause unique == 1`
  - actual: `non_evaluable`
  - match: **False**
  - non_evaluable_reason: run-effective config max_clause=1 <= 1 のため active_clause unique==1 は config 由来の擬陽性、 P3 識別力なし

## fitness_pen 分解
| 統計量 | trade_sharpe_raw | size_norm (逆算) | penalty | fitness_pen |
|---|---|---|---|---|
| max | 0.004641 | 0.650000 | 0.019500 | -0.008859 |
| mean | -0.077638 | 0.383581 | 0.011507 | -0.089145 |
| std | 0.097470 | 0.150669 | 0.004520 | 0.097619 |

_注: 逆算 size_norm = (raw - pen) / alpha (近似) (alpha=0.03)_

## trade_sharpe_raw 世代別
| generation | n | max | mean | median | n_positive |
|---|---|---|---|---|---|
| 0 | 40 | -0.0300 | -0.1837 | -0.1070 | 0 |
| 1 | 40 | -0.0177 | -0.1097 | -0.0654 | 0 |
| 2 | 40 | -0.0177 | -0.1143 | -0.0573 | 0 |
| 3 | 40 | -0.0118 | -0.0891 | -0.0537 | 0 |
| 4 | 40 | -0.0118 | -0.1056 | -0.0659 | 0 |
| 5 | 40 | -0.0118 | -0.0691 | -0.0659 | 0 |
| 6 | 40 | -0.0118 | -0.0673 | -0.0651 | 0 |
| 7 | 40 | -0.0118 | -0.0624 | -0.0672 | 0 |
| 8 | 40 | -0.0118 | -0.0664 | -0.0698 | 0 |
| 9 | 40 | -0.0118 | -0.0876 | -0.0566 | 0 |
| 10 | 40 | -0.0118 | -0.0487 | -0.0394 | 0 |
| 11 | 40 | -0.0118 | -0.0405 | -0.0310 | 0 |
| 12 | 40 | -0.0118 | -0.0666 | -0.0490 | 0 |
| 13 | 40 | -0.0118 | -0.0746 | -0.0118 | 0 |
| 14 | 40 | 0.0046 | -0.0483 | -0.0522 | 1 |
| 15 | 40 | 0.0046 | -0.0468 | -0.0426 | 1 |

## trade_count バケット別
| バケット | n | trade_sharpe mean | fitness_pen mean |
|---|---|---|---|
| 0 | 19 | — | — |
| 1-49 | 20 | -0.5602 | -0.5668 |
| 50-499 | 21 | -0.2346 | -0.2487 |
| 500-1499 | 21 | -0.3100 | -0.3246 |
| >=1500 | 559 | -0.0587 | -0.0700 |

## diversity (n_nodes / active_clause 推移)
| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |
|---|---|---|---|---|
| 0 | 2.62 | 1.005 | 0.95 | 2 |
| 1 | 3.20 | 0.853 | 1.00 | 1 |
| 2 | 3.05 | 0.986 | 1.00 | 1 |
| 3 | 2.90 | 0.900 | 1.00 | 1 |
| 4 | 2.52 | 0.987 | 1.00 | 1 |
| 5 | 1.75 | 0.809 | 1.00 | 1 |
| 6 | 1.65 | 0.802 | 1.00 | 1 |
| 7 | 1.90 | 0.871 | 1.00 | 1 |
| 8 | 1.85 | 0.864 | 1.00 | 1 |
| 9 | 2.23 | 0.920 | 1.00 | 1 |
| 10 | 2.23 | 1.074 | 1.00 | 1 |
| 11 | 2.62 | 0.740 | 1.00 | 1 |
| 12 | 2.98 | 0.577 | 1.00 | 1 |
| 13 | 2.95 | 0.639 | 1.00 | 1 |
| 14 | 3.00 | 0.506 | 1.00 | 1 |
| 15 | 2.90 | 0.672 | 1.00 | 1 |

## penalty 効果
- raw>0 個体数: 2
- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): 2
- raw>0 ∧ fitness_pen>0 (= 通過候補): 0

## extra_metrics
- raw_positive_count: 2
- fitness_pen_positive_count: 0
- sentinel_by_generation: {0: 12, 1: 2, 2: 4, 4: 5, 5: 1, 6: 1, 7: 1, 8: 1, 9: 2, 10: 1, 12: 2, 13: 2}

## data_quality
- n_valid / n_total: 606 / 640
- sentinel 個体数: 34
  - T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能

## run_effective_config (= audit trail)
- _source: run_effective
- summary_path: /Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-31/summary.json
- summary_run_id: run_20260504_065916
- max_clause: 1
- stage_a_alpha: 0.03
- stage_a_threshold: -0.0172
