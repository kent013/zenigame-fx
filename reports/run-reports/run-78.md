# Run 78 — run_20260514_035158

**Generated**: 2026-05-14T03:51:59.151323+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ✅ **sharpe**: 6.332737661854887 / threshold 1.0
- ❌ **total_pnl**: 41870.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 40 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 0 (= Stage C 単独通過数)
- **mission_candidate_count**: 0 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 63

## Best 個体

- name: `g45_i43`
- generation: 45
- fitness: **0.45008131782765715**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 40
- total_pnl: 41870.0
- sharpe: 0.4885813178276571
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 5
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 545
- Stage B pass: 0
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 545 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 545 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4662, median=1.0000, std=0.5073, min=0, max=2
- n_nodes: n=5856, mean=2.9051, median=3.0000, std=1.6646, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=545, mean=0.1077, median=0.1212, std=0.0892, min=0.0000, max=0.3636
- dsr: n=0
- n_fold_effective (Stage A pass): n=545, mean=24.1358, median=30, std=12.1099, min=2, max=34
- positive_fold_ratio_effective (Stage A pass): n=545, mean=0.3314, median=0.2143, std=0.3240, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 545, Stage B pass = 0, failures = 545 (primary_sum = 545)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 420 |
| `median_oos_total_pnl<min` | 17 |
| `sum_oos_total_pnl<min` | 10 |
| `n_fold_effective_below_profit_safe_min` | 98 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 420 |
| `median_oos_total_pnl<min` | 437 |
| `sum_oos_total_pnl<min` | 447 |
| `n_fold_effective_below_profit_safe_min` | 149 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 110 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 6.2% (364/5856)
- best 個体 trade_count: 40
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=545, stage_a_only=5311
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5311, mean=-631254.1103, median=-1000050.0000, std=458710.3733, min=-1007060.0000, max=35100.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4947): n=4947, mean=-677701.7546, median=-1000080.0000, std=440930.7161, min=-1007060.0000, max=35100.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=545): n=545, mean=-76162.5872, median=15880.0000, std=297281.8914, min=-1000700.0000, max=45140.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g45_i43` | 45 | tier1_EUR_JPY | EUR_JPY | 0.4501 | 0.4886 | ✅ | ❌ | ❌ | 40 | — |
| 2 | `g46_i0` | 46 | tier1_EUR_JPY | EUR_JPY | 0.4501 | 0.4886 | ✅ | ❌ | ❌ | 40 | — |
| 3 | `g47_i0` | 47 | tier1_EUR_JPY | EUR_JPY | 0.4501 | 0.4886 | ✅ | ❌ | ❌ | 40 | — |
| 4 | `g48_i0` | 48 | tier1_EUR_JPY | EUR_JPY | 0.4501 | 0.4886 | ✅ | ❌ | ❌ | 40 | — |
| 5 | `g49_i0` | 49 | tier1_EUR_JPY | EUR_JPY | 0.4501 | 0.4886 | ✅ | ❌ | ❌ | 40 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.028094256231002042 |
| 1 | -0.028094256231002042 |
| 2 | -0.01600662241352756 |
| 3 | -0.01600662241352756 |
| 4 | -0.01600662241352756 |
| 5 | -0.01600662241352756 |
| 6 | -0.01600662241352756 |
| 7 | -0.01600662241352756 |
| 8 | -0.01600662241352756 |
| 9 | -0.01600662241352756 |
| 10 | -0.01600662241352756 |
| 11 | -0.01600662241352756 |
| 12 | -0.01600662241352756 |
| 13 | -0.01600662241352756 |
| 14 | -0.01600662241352756 |
| 15 | -0.01600662241352756 |
| 16 | -0.01600662241352756 |
| 17 | -0.0063426806996858855 |
| 18 | 0.0003906433605182589 |
| 19 | 0.17134768318171362 |
| 20 | 0.17134768318171362 |
| 21 | 0.17134768318171362 |
| 22 | 0.17134768318171362 |
| 23 | 0.20389637004746664 |
| 24 | 0.27851633196673364 |
| 25 | 0.27851633196673364 |
| 26 | 0.27851633196673364 |
| 27 | 0.2793486535742801 |
| 28 | 0.3891542296849768 |
| 29 | 0.3891542296849768 |
| 30 | 0.3891542296849768 |
| 31 | 0.39365422968497676 |
| 32 | 0.39365422968497676 |
| 33 | 0.39365422968497676 |
| 34 | 0.39365422968497676 |
| 35 | 0.39365422968497676 |
| 36 | 0.39365422968497676 |
| 37 | 0.4455813178276571 |
| 38 | 0.4455813178276571 |
| 39 | 0.4455813178276571 |
| 40 | 0.4455813178276571 |
| 41 | 0.4455813178276571 |
| 42 | 0.4455813178276571 |
| 43 | 0.4455813178276571 |
| 44 | 0.4455813178276571 |
| 45 | 0.45008131782765715 |
| 46 | 0.45008131782765715 |
| 47 | 0.45008131782765715 |
| 48 | 0.45008131782765715 |
| 49 | 0.45008131782765715 |
| 50 | 0.45008131782765715 |
| 51 | 0.45008131782765715 |
| 52 | 0.45008131782765715 |
| 53 | 0.45008131782765715 |
| 54 | 0.45008131782765715 |
| 55 | 0.45008131782765715 |
| 56 | 0.45008131782765715 |
| 57 | 0.45008131782765715 |
| 58 | 0.45008131782765715 |
| 59 | 0.45008131782765715 |
| 60 | 0.45008131782765715 |

## 分析

### analysis-claude.md

# Run 76 簡易自己分析 (cycle 24 軽量モード)

cycle 24-51 は seed sweep 軽量ループ (Phase 2/3 skip、 Codex 独立分析 skip)。 各 cycle で前 Run の主要メトリクスを記録し、 累積データで profit_safe_pfr variance を測定する。

## Run 76 主要メトリクス

| 指標 | 値 |
|------|-----|
| run_id | run_20260513_235721 |
| run_number | 76 |
| seed | 61 |
| stage_b_gate_kind | profit_safe_pfr |
| 完走時間 | 116 分 |
| Stage A pass | 672 |
| Stage B pass | 220 |
| Stage C pass | **0** |
| graduated | 0 |
| best | g59_i94, fp=0.129, stage_a/b/c=T/T/F |
| best trade_count | 33 |
| best total_pnl | -38,590 |
| best sharpe (annualized) | **-5.08** |
| best max_dd | 4.75% |
| live_criteria.all_pass | False (4 中 1 pass: max_dd のみ) |
| mission_candidate_count | 0 |

## variance 観察 (Run 75 vs Run 76)

| 指標 | Run 75 (seed=60) | Run 76 (seed=61) | 差 |
|------|------------------|------------------|------|
| Stage A pass | 1291 | 672 | -48% |
| Stage B pass | 827 | 220 | -73% |
| Stage C pass | 217 | **0** | -100% |
| mission_candidates | 217 | **0** | -217 |
| best stage_c | True | False | 逆転 |
| best sharpe annualized | +2.69 | -5.08 | -7.77 |

**結論**: profit_safe_pfr の seed variance は予想以上に高い。 Run 75 の大成果は seed=60 の lucky draw が強く支持される。 cycle 24-51 で seed=62-89 を sweep し、 mission_candidates > 0 が出現する頻度を実測する。

## 軽量ループ進捗 (cycle 22-23 まで)

| cycle | seed | mode | stage_c_pass | mission_candidates |
|-------|------|------|-------------:|-------------------:|
| 22 | 60 | profit_safe_pfr | **217** | **217** |
| 23 | 61 | profit_safe_pfr | 0 | 0 |

## cycle 24 計画

- seed=62 で profit_safe_pfr 実行 (Run 77)
- Phase 2/3 skip
- 完走後 cycle 25 (seed=63) へ

