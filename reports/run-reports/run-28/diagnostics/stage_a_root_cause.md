# Stage A Root Cause Diagnostic: run_20260504_055856

- **run_number**: 28
- **diagnosis**: **P2**
- **confidence**: high
- **config_source**: run_effective
- **evaluated_hypotheses**: ['P1', 'P2']

## サマリー
- Stage A pass: 0 / B pass: 0 / C pass: 0
- best generation: 5
- best plateau length: 11 (start gen: 5)

## 分類判定 (= 反証結果)
- **P1**:
  - condition: `raw_max < 0.005`
  - actual: `0.005658488726607911`
  - match: **False**
- **P2**:
  - condition: `penalty_killed >= max(3, ceil(0.01*N_valid=619)) = 7`
  - actual: `62`
  - match: **True**
- **P3**:
  - condition: `n_nodes std drop > 0.5 ∧ active_clause unique == 1`
  - actual: `non_evaluable`
  - match: **False**
  - non_evaluable_reason: run-effective config max_clause=1 <= 1 のため active_clause unique==1 は config 由来の擬陽性、 P3 識別力なし

## fitness_pen 分解
| 統計量 | trade_sharpe_raw | size_norm (逆算) | penalty | fitness_pen |
|---|---|---|---|---|
| max | 0.005658 | 0.650000 | 0.019500 | -0.003342 |
| mean | -0.073858 | 0.277221 | 0.008317 | -0.082174 |
| std | 0.110720 | 0.134163 | 0.004025 | 0.111455 |

_注: 逆算 size_norm = (raw - pen) / alpha (近似) (alpha=0.03)_

## trade_sharpe_raw 世代別
| generation | n | max | mean | median | n_positive |
|---|---|---|---|---|---|
| 0 | 40 | -0.0226 | -0.2334 | -0.1017 | 0 |
| 1 | 40 | -0.0224 | -0.1008 | -0.0737 | 0 |
| 2 | 40 | -0.0176 | -0.0680 | -0.0528 | 0 |
| 3 | 40 | -0.0176 | -0.0978 | -0.0826 | 0 |
| 4 | 40 | 0.0053 | -0.0461 | -0.0424 | 1 |
| 5 | 40 | 0.0057 | -0.0850 | -0.0505 | 2 |
| 6 | 40 | 0.0057 | -0.0467 | -0.0347 | 4 |
| 7 | 40 | 0.0057 | -0.0725 | -0.0604 | 3 |
| 8 | 40 | 0.0057 | -0.0531 | -0.0499 | 6 |
| 9 | 40 | 0.0057 | -0.0635 | -0.0377 | 5 |
| 10 | 40 | 0.0057 | -0.0466 | -0.0377 | 5 |
| 11 | 40 | 0.0057 | -0.0551 | -0.0380 | 4 |
| 12 | 40 | 0.0057 | -0.0511 | -0.0362 | 6 |
| 13 | 40 | 0.0057 | -0.0550 | -0.0411 | 7 |
| 14 | 40 | 0.0057 | -0.0565 | -0.0506 | 11 |
| 15 | 40 | 0.0057 | -0.0882 | -0.0706 | 8 |

## trade_count バケット別
| バケット | n | trade_sharpe mean | fitness_pen mean |
|---|---|---|---|
| 0 | 8 | — | — |
| 1-49 | 26 | -0.5378 | -0.5443 |
| 50-499 | 11 | -0.2514 | -0.2674 |
| 500-1499 | 17 | -0.2775 | -0.2906 |
| >=1500 | 578 | -0.0541 | -0.0621 |

## diversity (n_nodes / active_clause 推移)
| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |
|---|---|---|---|---|
| 0 | 2.73 | 1.086 | 0.97 | 2 |
| 1 | 2.50 | 1.198 | 1.00 | 1 |
| 2 | 1.93 | 1.163 | 1.00 | 1 |
| 3 | 1.77 | 1.050 | 1.00 | 1 |
| 4 | 1.68 | 0.764 | 1.00 | 1 |
| 5 | 1.52 | 0.716 | 1.00 | 1 |
| 6 | 1.62 | 0.667 | 1.00 | 1 |
| 7 | 1.70 | 0.608 | 1.00 | 1 |
| 8 | 1.73 | 0.599 | 1.00 | 1 |
| 9 | 1.50 | 0.506 | 1.00 | 1 |
| 10 | 1.65 | 0.662 | 1.00 | 1 |
| 11 | 1.73 | 0.640 | 1.00 | 1 |
| 12 | 1.57 | 0.712 | 1.00 | 1 |
| 13 | 1.55 | 0.597 | 1.00 | 1 |
| 14 | 1.77 | 0.620 | 1.00 | 1 |
| 15 | 1.88 | 0.686 | 1.00 | 1 |

## penalty 効果
- raw>0 個体数: 62
- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): 62
- raw>0 ∧ fitness_pen>0 (= 通過候補): 0

## extra_metrics
- raw_positive_count: 62
- fitness_pen_positive_count: 0
- sentinel_by_generation: {0: 10, 1: 2, 4: 1, 5: 1, 6: 1, 7: 1, 9: 1, 11: 1, 12: 2, 13: 1}

## data_quality
- n_valid / n_total: 619 / 640
- sentinel 個体数: 21
  - T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能

## run_effective_config (= audit trail)
- _source: run_effective
- summary_path: /Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-28/summary.json
- summary_run_id: run_20260504_055856
- max_clause: 1
- stage_a_alpha: 0.03
- stage_a_threshold: 0.0128
