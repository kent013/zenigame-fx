# Run 74 — run_20260511_201001

**Generated**: 2026-05-11T20:10:01.804712+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.14077442900558587 / threshold 1.0
- ❌ **total_pnl**: -15390.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 5.093055637269322 / threshold 20.0
- ❌ **trade_count**: 41 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 59

## Best 個体

- name: `g60_i45`
- generation: 60
- fitness: **0.10627442900558587**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 41
- total_pnl: -15390.0
- sharpe: 0.14077442900558587
- sortino: —
- calmar: —
- max_drawdown_pct: 5.093055637269322

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2424
- dsr: —
- ii_lite_pass: —
- n_nodes: 7
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1723
- Stage B pass: 96
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1723 | 96 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1723 | 96 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3868, median=1.0000, std=0.4881, min=0, max=2
- n_nodes: n=5856, mean=3.5312, median=3.0000, std=1.7791, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=96, mean=0.2986, median=0.3008, std=0.0046, min=0.2835, max=0.3013
- best mission_score: **0.3013** (`g39_i76`, gen=39, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1723, mean=0.2331, median=0.2424, std=0.0598, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=1723, mean=33.4272, median=34, std=3.0672, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1722, mean=0.3521, median=0.3235, std=0.1225, min=0.0000, max=0.6667

## Stage B failure reason 集計

- Stage A pass = 1723, Stage B pass = 96, failures = 1627 (primary_sum = 1627)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1559 |
| `positive_fold_ratio<min` | 68 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 1 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1559 |
| `positive_fold_ratio<min` | 1625 |
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
- trade_count=0 個体比率: 4.1% (241/5856)
- best 個体 trade_count: 41
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1627, stage_a_only=4133, stage_b_evaluated=96
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4133, mean=-460459.5548, median=-144750.0000, std=470714.1627, min=-1001900.0000, max=26380.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3892): n=3892, mean=-488972.0812, median=-217310.0000, std=470478.6285, min=-1001900.0000, max=26380.0000
  - うち PnL=0 個体: 2 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1723): n=1723, mean=19203.8712, median=21460.0000, std=62302.9557, min=-1000240.0000, max=82310.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g41_i78` | 41 | tier1_EUR_JPY | EUR_JPY | 0.2555 | 0.2950 | ✅ | ❌ | ❌ | 33 | — |
| 2 | `g47_i79` | 47 | tier1_EUR_JPY | EUR_JPY | 0.2311 | 0.2681 | ✅ | ❌ | ❌ | 31 | — |
| 3 | `g48_i93` | 48 | tier1_EUR_JPY | EUR_JPY | 0.2311 | 0.2681 | ✅ | ❌ | ❌ | 31 | — |
| 4 | `g34_i53` | 34 | tier1_EUR_JPY | EUR_JPY | 0.2029 | 0.2329 | ✅ | ❌ | ❌ | 69 | — |
| 5 | `g43_i48` | 43 | tier1_EUR_JPY | EUR_JPY | 0.1899 | 0.2434 | ✅ | ❌ | ❌ | 31 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.033969307993533954 |
| 1 | -0.03260010972474051 |
| 2 | -0.03260010972474051 |
| 3 | -0.03187195426287701 |
| 4 | -0.030943930126514287 |
| 5 | -0.027266150406777226 |
| 6 | -0.023321573900180106 |
| 7 | -0.023321573900180106 |
| 8 | -0.023321573900180106 |
| 9 | -0.023321573900180106 |
| 10 | 0.000973001603852372 |
| 11 | 0.013225511000567678 |
| 12 | 0.013225511000567678 |
| 13 | 0.015819843725171246 |
| 14 | 0.015819843725171246 |
| 15 | 0.015819843725171246 |
| 16 | 0.015819843725171246 |
| 17 | 0.017277088254517094 |
| 18 | 0.03251942493545155 |
| 19 | 0.04246025373752821 |
| 20 | 0.1104259452256543 |
| 21 | 0.1104259452256543 |
| 22 | 0.1104259452256543 |
| 23 | 0.1104259452256543 |
| 24 | 0.1104259452256543 |
| 25 | 0.05022243563404653 |
| 26 | 0.05871360473902283 |
| 27 | 0.08619492742596183 |
| 28 | 0.10739577147030555 |
| 29 | 0.10694391922881696 |
| 30 | 0.10694391922881696 |
| 31 | 0.10887496924386758 |
| 32 | 0.18329594533586624 |
| 33 | 0.18329594533586624 |
| 34 | 0.2029375277932069 |
| 35 | 0.1686718236056454 |
| 36 | 0.09185231962991984 |
| 37 | 0.10453015347670358 |
| 38 | 0.08841603471925198 |
| 39 | 0.15306491500766634 |
| 40 | 0.14407901142105556 |
| 41 | 0.25548856945710713 |
| 42 | 0.12480606770502076 |
| 43 | 0.1898881795939028 |
| 44 | 0.12485794893738357 |
| 45 | 0.1747542570031412 |
| 46 | 0.14974696861518008 |
| 47 | 0.2311061675296317 |
| 48 | 0.2311061675296317 |
| 49 | 0.1394506004784067 |
| 50 | 0.13548460126631953 |
| 51 | 0.11458860570085101 |
| 52 | 0.11458860570085101 |
| 53 | 0.1247257776865501 |
| 54 | 0.1247257776865501 |
| 55 | 0.14880710546902207 |
| 56 | 0.1425627976717998 |
| 57 | 0.1425627976717998 |
| 58 | 0.13490036563331517 |
| 59 | 0.1267056111441801 |
| 60 | 0.13397451081728773 |

