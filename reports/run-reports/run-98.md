# Run 98 — run_20260524_020127

**Generated**: 2026-05-24T02:01:28.594023+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 6.121508276831233 / threshold 1.5
- ✅ **total_pnl**: 92430.0 / threshold 70000.0
- ✅ **max_drawdown_pct**: 1.4541042681491407 / threshold 20.0
- ✅ **trade_count**: 50 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 634 (= Stage C 単独通過数)
- **mission_candidate_count**: 634 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 70

## Best 個体

- name: `g48_i14`
- generation: 48
- fitness: **0.028328942069122894**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 50
- total_pnl: 92430.0
- sharpe: 0.047828942069122894
- sortino: —
- calmar: —
- max_drawdown_pct: 1.4541042681491407

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2424
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2577
- Stage B pass: 2010
- Stage C pass: 634

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 634 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 212 | 33.4% |
| 51 | 166 | 26.2% |
| 52 | 85 | 13.4% |
| 53 | 128 | 20.2% |
| 54 | 27 | 4.3% |
| 55 | 6 | 0.9% |
| 56 | 4 | 0.6% |
| 57 | 6 | 0.9% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 212 | 422 |
| median total_pnl | 85065.0000 | 79850.0000 |
| median trade_sharpe_stage_c | 0.3796 | 0.3431 |
| median max_drawdown_pct | 1.4721 | 1.4836 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2577 | 2010 | 634 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2577 | 2010 | 634 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2778, median=1.0000, std=0.4491, min=0, max=2
- n_nodes: n=5856, mean=4.1337, median=4.0000, std=1.6187, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1979, mean=0.9176, median=0.9602, std=0.0915, min=0.2801, max=0.9832
- best mission_score: **0.9832** (`g45_i87`, gen=45, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2577, mean=0.2503, median=0.2424, std=0.0724, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2577, mean=32.6717, median=34, std=4.6280, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2576, mean=0.5575, median=0.5882, std=0.1417, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2577, Stage B pass = 2010, failures = 567 (primary_sum = 567)

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
| `positive_fold_ratio_effective<min` | 271 |
| `median_oos_total_pnl<min` | 163 |
| `sum_oos_total_pnl<min` | 92 |
| `n_fold_effective_below_profit_safe_min` | 41 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 271 |
| `median_oos_total_pnl<min` | 434 |
| `sum_oos_total_pnl<min` | 491 |
| `n_fold_effective_below_profit_safe_min` | 85 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 9 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=2010, None=3846

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 1.5% (86/5856)
- best 個体 trade_count: 50
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=567, stage_a_only=3279, stage_b_evaluated=1376, stage_c_evaluated=634
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3279, mean=-223907.1699, median=-24260.0000, std=379849.8409, min=-1003610.0000, max=46980.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3193): n=3193, mean=-229937.8672, median=-25800.0000, std=383125.8286, min=-1003610.0000, max=46980.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2577): n=2577, mean=19065.6189, median=19970.0000, std=23085.7542, min=-1000090.0000, max=101030.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g43_i94` | 43 | tier1_EUR_JPY | EUR_JPY | 0.2424 | 0.2784 | ✅ | ❌ | ❌ | 54 | — |
| 2 | `g44_i39` | 44 | tier1_EUR_JPY | EUR_JPY | 0.2424 | 0.2784 | ✅ | ❌ | ❌ | 54 | — |
| 3 | `g45_i38` | 45 | tier1_EUR_JPY | EUR_JPY | 0.2424 | 0.2784 | ✅ | ❌ | ❌ | 54 | — |
| 4 | `g27_i45` | 27 | tier1_EUR_JPY | EUR_JPY | 0.2403 | 0.2688 | ✅ | ❌ | ❌ | 41 | — |
| 5 | `g43_i35` | 43 | tier1_EUR_JPY | EUR_JPY | 0.2301 | 0.2651 | ✅ | ❌ | ❌ | 30 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.1629437202835496 |
| 2 | 0.07786832965017235 |
| 3 | 0.07786832965017235 |
| 4 | 0.08506417947129344 |
| 5 | 0.05875377232748728 |
| 6 | 0.08387037855390378 |
| 7 | 0.06526198659011426 |
| 8 | 0.1290909172286291 |
| 9 | 0.14269143376379134 |
| 10 | 0.12442003885031108 |
| 11 | 0.17960219701429142 |
| 12 | 0.14294077232521765 |
| 13 | 0.1591051974651107 |
| 14 | 0.14132983679323272 |
| 15 | 0.1525643390709987 |
| 16 | 0.18084584634752535 |
| 17 | 0.18084584634752535 |
| 18 | 0.12344379128927535 |
| 19 | 0.16060286333900134 |
| 20 | 0.11159302914400022 |
| 21 | 0.1271093484502086 |
| 22 | 0.08120328930558107 |
| 23 | 0.0942366765776639 |
| 24 | 0.15303580138998632 |
| 25 | 0.13597626011703057 |
| 26 | 0.14965737228200474 |
| 27 | 0.24034240751700528 |
| 28 | 0.13221921738401488 |
| 29 | 0.15053529624492945 |
| 30 | 0.1548076235657653 |
| 31 | 0.1015311224610834 |
| 32 | 0.1524430160946093 |
| 33 | 0.11181153130380612 |
| 34 | 0.0781634089371154 |
| 35 | 0.09797855289905275 |
| 36 | 0.19682709100936685 |
| 37 | 0.07650423406892472 |
| 38 | 0.10121307430535996 |
| 39 | 0.10338014362491993 |
| 40 | 0.21675854958886281 |
| 41 | 0.22275854958886282 |
| 42 | 0.21675854958886281 |
| 43 | 0.2424139767060242 |
| 44 | 0.2424139767060242 |
| 45 | 0.2424139767060242 |
| 46 | 0.13332765331100954 |
| 47 | 0.15216854137627178 |
| 48 | 0.09844189372307255 |
| 49 | 0.1425200058353294 |
| 50 | 0.2127687941391086 |
| 51 | 0.10437300598064105 |
| 52 | 0.10437300598064105 |
| 53 | 0.15687523778354723 |
| 54 | 0.07348637427280057 |
| 55 | 0.14622841309251508 |
| 56 | 0.15275855783262227 |
| 57 | 0.11498269847989365 |
| 58 | 0.17222947077334022 |
| 59 | 0.1363070255147582 |
| 60 | 0.12985763373205564 |

