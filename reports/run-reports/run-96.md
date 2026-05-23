# Run 96 — run_20260523_122605

**Generated**: 2026-05-23T12:26:06.263501+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 4.398507064705867 / threshold 1.5
- ✅ **total_pnl**: 70680.0 / threshold 70000.0
- ✅ **max_drawdown_pct**: 1.8008003557136505 / threshold 20.0
- ✅ **trade_count**: 55 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 209 (= Stage C 単独通過数)
- **mission_candidate_count**: 209 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 69

## Best 個体

- name: `g12_i85`
- generation: 12
- fitness: **0.08838721023257146**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 55
- total_pnl: 70680.0
- sharpe: 0.10188721023257145
- sortino: —
- calmar: —
- max_drawdown_pct: 1.8008003557136505

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2163
- Stage B pass: 1612
- Stage C pass: 209

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 209 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 2 | 1.0% |
| 51 | 14 | 6.7% |
| 52 | 44 | 21.1% |
| 53 | 2 | 1.0% |
| 55 | 146 | 69.9% |
| 65 | 1 | 0.5% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 2 | 207 |
| median total_pnl | 72335.0000 | 70680.0000 |
| median trade_sharpe_stage_c | 0.3270 | 0.2894 |
| median max_drawdown_pct | 1.7033 | 1.8008 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2163 | 1612 | 209 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2163 | 1612 | 209 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2995, median=1.0000, std=0.4603, min=0, max=2
- n_nodes: n=5856, mean=3.8323, median=4.0000, std=1.6783, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1539, mean=0.8602, median=0.8763, std=0.1195, min=0.2766, max=0.9829
- best mission_score: **0.9829** (`g18_i5`, gen=18, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2163, mean=0.2528, median=0.2727, std=0.0818, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=2163, mean=30.7587, median=34, std=6.6529, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=2163, mean=0.5668, median=0.5882, std=0.1300, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2163, Stage B pass = 1612, failures = 551 (primary_sum = 551)

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
| `positive_fold_ratio_effective<min` | 235 |
| `median_oos_total_pnl<min` | 154 |
| `sum_oos_total_pnl<min` | 87 |
| `n_fold_effective_below_profit_safe_min` | 75 |
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
| `positive_fold_ratio_effective<min` | 235 |
| `median_oos_total_pnl<min` | 389 |
| `sum_oos_total_pnl<min` | 439 |
| `n_fold_effective_below_profit_safe_min` | 206 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 11 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=1612, None=4244

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.7% (157/5856)
- best 個体 trade_count: 55
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=551, stage_a_only=3693, stage_b_evaluated=1403, stage_c_evaluated=209
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3693, mean=-229883.9263, median=-28530.0000, std=377234.5703, min=-1002090.0000, max=47860.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3536): n=3536, mean=-240090.8767, median=-31325.0000, std=382326.7878, min=-1002090.0000, max=47860.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2163): n=2163, mean=24091.0171, median=24420.0000, std=14832.8679, min=-8160.0000, max=105670.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g47_i7` | 47 | tier1_EUR_JPY | EUR_JPY | 0.3268 | 0.3643 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g39_i18` | 39 | tier1_EUR_JPY | EUR_JPY | 0.3048 | 0.3563 | ✅ | ❌ | ❌ | 36 | — |
| 3 | `g20_i31` | 20 | tier1_EUR_JPY | EUR_JPY | 0.2958 | 0.3283 | ✅ | ❌ | ❌ | 37 | — |
| 4 | `g51_i22` | 51 | tier1_EUR_JPY | EUR_JPY | 0.2882 | 0.3257 | ✅ | ❌ | ❌ | 32 | — |
| 5 | `g57_i13` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2836 | 0.3211 | ✅ | ❌ | ❌ | 32 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.07391491636745944 |
| 2 | 0.07391491636745944 |
| 3 | 0.07391491636745944 |
| 4 | 0.14181545331430204 |
| 5 | 0.24450845000181376 |
| 6 | 0.24450845000181376 |
| 7 | 0.2490084500018137 |
| 8 | 0.13261696766579414 |
| 9 | 0.12844347122462962 |
| 10 | 0.17772189704634414 |
| 11 | 0.19928339392303682 |
| 12 | 0.2747715471179649 |
| 13 | 0.17772189704634414 |
| 14 | 0.19928339392303682 |
| 15 | 0.22325156136473148 |
| 16 | 0.22325156136473148 |
| 17 | 0.22325156136473148 |
| 18 | 0.19800777958696478 |
| 19 | 0.2657607927131022 |
| 20 | 0.29581488950678636 |
| 21 | 0.17039856368965248 |
| 22 | 0.1857819448924043 |
| 23 | 0.21657674224928267 |
| 24 | 0.1696602545044278 |
| 25 | 0.17747454094160528 |
| 26 | 0.18879680032185964 |
| 27 | 0.2088718642438242 |
| 28 | 0.2088718642438242 |
| 29 | 0.17552956718355264 |
| 30 | 0.11661658180129698 |
| 31 | 0.11661658180129698 |
| 32 | 0.1211748470975713 |
| 33 | 0.16479840112270686 |
| 34 | 0.1422135086721223 |
| 35 | 0.12013545448372133 |
| 36 | 0.22829940027639414 |
| 37 | 0.2311326576244204 |
| 38 | 0.25854522582014416 |
| 39 | 0.30476761983389905 |
| 40 | 0.14742717369834898 |
| 41 | 0.11058966001928226 |
| 42 | 0.1152681241553118 |
| 43 | 0.1257233017790568 |
| 44 | 0.13643665871506483 |
| 45 | 0.2311326576244204 |
| 46 | 0.2311326576244204 |
| 47 | 0.326756332244714 |
| 48 | 0.23667706628218302 |
| 49 | 0.23667706628218302 |
| 50 | 0.23667706628218302 |
| 51 | 0.2881739903182678 |
| 52 | 0.21985898535201076 |
| 53 | 0.25133582326592785 |
| 54 | 0.25133582326592785 |
| 55 | 0.2385397993481214 |
| 56 | 0.20642537637450845 |
| 57 | 0.2835663243187992 |
| 58 | 0.21037001703521307 |
| 59 | 0.21883944365656446 |
| 60 | 0.2293293967339466 |

