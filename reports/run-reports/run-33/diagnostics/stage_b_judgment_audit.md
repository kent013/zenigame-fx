# Stage B 判定 SSOT Audit: run_20260504_130805

- run_number: 33

## decision_trace (= C2/C4/C6 対策)
- rule_version: v1
- thresholds: {'stage_b_median_oos_sharpe_min': 0.05, 'stage_b_positive_fold_min': 0.6}
- used_metrics_source: archive
- unavailable_imputation_policy: fold metric_unavailable は 0 として母数に含める
- judgment_logic: `Stage B passed iff (median_oos_sharpe >= threshold) AND (positive_fold_ratio >= threshold) AND (not all_folds_unavailable)`

## archive 観測補助列の混同警告
- `trade_sharpe_stage_b`: Stage B IS 全期間 Sharpe (= 判定 SSOT ではない、 median_oos_sharpe と混同禁止)
- `positive_fold_ratio_effective`: unavailable 除外母数 (= 判定 SSOT ではない、 全 fold 母数の positive_fold_ratio と混同禁止)

## Stage 通過数
- A: 99 / B: 2 / C: 0

## Stage B 判定理由分布 (a_pass 個体ごと)
| reason | count |
|---|---:|
| positive_fold_ratio<min | 97 |
| median_oos_sharpe<min | 96 |
| all_folds_unavailable | 2 |
| __pass__ | 2 |

## analytical AND vs stage_b_pass 不一致観察
- analytical_AND (= sb>=0.05 ∧ pos_fr_eff>=0.60): 29
- actual stage_b_pass: 2
- discrepancy: 27
- discrepancy > 0 が観察された場合、 archive 観測補助列の AND と 判定 SSOT 不一致 (= 母数の違い + metric の違いによる identification error)

## stage_b_pass=True 個体詳細
| name | gen | trade_count | fitness_pen | sb_archive | pos_fr_eff | n_fold | C pass | live_criteria? |
|---|---|---|---|---|---|---|---|---|
| g8_i33 | 8 | 16 | 0.0606 | 0.0360 | 0.67 | 9 | False | False |
| g12_i17 | 12 | 17 | 0.0017 | -0.0064 | 0.67 | 9 | False | False |
