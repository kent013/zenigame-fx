# Run 51 — run_20260507_093751

**Generated**: 2026-05-07T09:39:45.147846+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.20023476933199083 / threshold 1.0
- ❌ **total_pnl**: 47540.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 87 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 42

## Best 個体

- name: `g41_i10`
- generation: 41
- fitness: **0.18523476933199085**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 87
- total_pnl: 47540.0
- sharpe: 0.20023476933199083
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2222
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1362
- Stage B pass: 55
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1362 | 55 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1362 | 55 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4438, median=1.0000, std=0.5023, min=0, max=2
- n_nodes: n=5856, mean=3.3233, median=3.0000, std=1.5941, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=5, mean=0.2849, median=0.2866, std=0.0034, min=0.2798, max=0.2884
- best mission_score: **0.2884** (`g58_i42`, gen=58, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1362, mean=0.2739, median=0.2222, std=0.1780, min=0.0000, max=0.7778
- dsr: n=0
- n_fold_effective (Stage A pass): n=1362, mean=9.9273, median=10.0000, std=0.5911, min=1, max=10
- positive_fold_ratio_effective (Stage A pass): n=1362, mean=0.3762, median=0.4000, std=0.2303, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1362, Stage B pass = 55, failures = 1307 (primary_sum = 1307)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1307 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1307 |
| `positive_fold_ratio<min` | 931 |
| `stage_b_pre_flight_underfilled` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 4.2% (244/5856)
- best 個体 trade_count: 87
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1307, stage_a_only=4494, stage_b_evaluated=55
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4494, mean=-403619.7819, median=-139915.0000, std=446651.5706, min=-1008700.0000, max=27630.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4250): n=4250, mean=-426792.3059, median=-165990.0000, std=448398.5742, min=-1008700.0000, max=27630.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1362): n=1362, mean=16352.6065, median=16670.0000, std=29873.2813, min=-1000240.0000, max=47540.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g30_i41` | 30 | tier1_EUR_JPY | EUR_JPY | 0.3456 | 0.3946 | ✅ | ❌ | ❌ | 31 | — |
| 2 | `g19_i18` | 19 | tier1_EUR_JPY | EUR_JPY | 0.2057 | 0.2297 | ✅ | ✅ | ❌ | 13 | — |
| 3 | `g15_i43` | 15 | tier1_EUR_JPY | EUR_JPY | 0.1990 | 0.2180 | ✅ | ❌ | ❌ | 49 | — |
| 4 | `g41_i10` | 41 | tier1_EUR_JPY | EUR_JPY | 0.1852 | 0.2002 | ✅ | ❌ | ❌ | 87 | — |
| 5 | `g42_i0` | 42 | tier1_EUR_JPY | EUR_JPY | 0.1852 | 0.2002 | ✅ | ❌ | ❌ | 87 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.01944390468558208 |
| 1 | 0.01944390468558208 |
| 2 | 0.01944390468558208 |
| 3 | 0.027992043735990752 |
| 4 | 0.13193793347922592 |
| 5 | 0.12983397817391845 |
| 6 | 0.10283462871428355 |
| 7 | 0.10283462871428355 |
| 8 | 0.10820859192215532 |
| 9 | 0.10764065246177758 |
| 10 | 0.1446673849515239 |
| 11 | 0.11815269038319007 |
| 12 | 0.11815269038319007 |
| 13 | 0.12288698159428808 |
| 14 | 0.12288698159428808 |
| 15 | 0.19896854089350066 |
| 16 | 0.12288698159428808 |
| 17 | 0.18163896091117746 |
| 18 | 0.12288698159428808 |
| 19 | 0.20570354544418662 |
| 20 | 0.12288698159428808 |
| 21 | 0.12669391509912198 |
| 22 | 0.15820546148217826 |
| 23 | 0.15820546148217826 |
| 24 | 0.15820546148217826 |
| 25 | 0.16813836007697702 |
| 26 | 0.15222593874559034 |
| 27 | 0.059208837250912624 |
| 28 | 0.0893110478586536 |
| 29 | 0.07658456169933277 |
| 30 | 0.34559780658002726 |
| 31 | 0.10642005067281249 |
| 32 | 0.0715236253268747 |
| 33 | 0.07930383636119431 |
| 34 | 0.13261003683194084 |
| 35 | 0.13897703470333106 |
| 36 | 0.13897703470333106 |
| 37 | 0.13897703470333106 |
| 38 | 0.13261003683194084 |
| 39 | 0.13261003683194084 |
| 40 | 0.13261003683194084 |
| 41 | 0.18523476933199085 |
| 42 | 0.18523476933199085 |
| 43 | 0.18523476933199085 |
| 44 | 0.18523476933199085 |
| 45 | 0.18523476933199085 |
| 46 | 0.18523476933199085 |
| 47 | 0.18523476933199085 |
| 48 | 0.18523476933199085 |
| 49 | 0.18523476933199085 |
| 50 | 0.18523476933199085 |
| 51 | 0.18523476933199085 |
| 52 | 0.18523476933199085 |
| 53 | 0.18523476933199085 |
| 54 | 0.18523476933199085 |
| 55 | 0.18523476933199085 |
| 56 | 0.18523476933199085 |
| 57 | 0.18523476933199085 |
| 58 | 0.18523476933199085 |
| 59 | 0.18523476933199085 |
| 60 | 0.18523476933199085 |

