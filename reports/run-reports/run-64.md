# Run 64 — run_20260510_054324

**Generated**: 2026-05-10T05:43:25.647683+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.0462298935824034 / threshold 1.0
- ❌ **total_pnl**: -5470.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.654349850415073 / threshold 20.0
- ✅ **trade_count**: 54 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 49

## Best 個体

- name: `g52_i74`
- generation: 52
- fitness: **0.026729893582403397**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 54
- total_pnl: -5470.0
- sharpe: 0.0462298935824034
- sortino: —
- calmar: —
- max_drawdown_pct: 1.654349850415073

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2727
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1014
- Stage B pass: 331
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1014 | 331 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1014 | 331 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6054, median=2.0000, std=0.4919, min=0, max=2
- n_nodes: n=5856, mean=2.7987, median=3.0000, std=1.4080, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=331, mean=0.3101, median=0.3103, std=0.0005, min=0.3081, max=0.3105
- best mission_score: **0.3105** (`g30_i38`, gen=30, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1014, mean=0.2104, median=0.2121, std=0.0844, min=0.0000, max=0.5152
- dsr: n=0
- n_fold_effective (Stage A pass): n=1014, mean=27.9773, median=32.0000, std=8.8176, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=1014, mean=0.5474, median=0.6452, std=0.2140, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1014, Stage B pass = 331, failures = 683 (primary_sum = 683)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 592 |
| `positive_fold_ratio<min` | 91 |
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
| `median_oos_sharpe<min` | 592 |
| `positive_fold_ratio<min` | 663 |
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
- trade_count=0 個体比率: 6.3% (369/5856)
- best 個体 trade_count: 54
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=683, stage_a_only=4842, stage_b_evaluated=331
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4842, mean=-469668.2610, median=-158635.0000, std=461824.0010, min=-1003990.0000, max=28010.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4473): n=4473, mean=-508413.5301, median=-262530.0000, std=459540.4577, min=-1003990.0000, max=28010.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1014): n=1014, mean=5055.3452, median=6150.0000, std=63801.3978, min=-1000100.0000, max=35130.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g21_i25` | 21 | tier1_EUR_JPY | EUR_JPY | 0.2990 | 0.3320 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g22_i0` | 22 | tier1_EUR_JPY | EUR_JPY | 0.2990 | 0.3320 | ✅ | ❌ | ❌ | 32 | — |
| 3 | `g22_i22` | 22 | tier1_EUR_JPY | EUR_JPY | 0.2990 | 0.3320 | ✅ | ❌ | ❌ | 32 | — |
| 4 | `g23_i0` | 23 | tier1_EUR_JPY | EUR_JPY | 0.2990 | 0.3320 | ✅ | ❌ | ❌ | 32 | — |
| 5 | `g23_i1` | 23 | tier1_EUR_JPY | EUR_JPY | 0.2990 | 0.3320 | ✅ | ❌ | ❌ | 32 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03280681626266709 |
| 1 | 0.012236350379207863 |
| 2 | 0.012236350379207863 |
| 3 | 0.012236350379207863 |
| 4 | 0.017526265778030837 |
| 5 | 0.06565304901289751 |
| 6 | 0.06565304901289751 |
| 7 | 0.06565304901289751 |
| 8 | 0.06565304901289751 |
| 9 | 0.018710663760731487 |
| 10 | 0.02173176416056112 |
| 11 | 0.027731764160561122 |
| 12 | 0.21936864437042444 |
| 13 | 0.21936864437042444 |
| 14 | 0.21936864437042444 |
| 15 | 0.2553001275829276 |
| 16 | 0.2553001275829276 |
| 17 | 0.2553001275829276 |
| 18 | 0.27502327186493936 |
| 19 | 0.27502327186493936 |
| 20 | 0.27502327186493936 |
| 21 | 0.29898938824633164 |
| 22 | 0.29898938824633164 |
| 23 | 0.29898938824633164 |
| 24 | 0.29898938824633164 |
| 25 | 0.29898938824633164 |
| 26 | 0.29898938824633164 |
| 27 | 0.16596325648718013 |
| 28 | 0.275761110036178 |
| 29 | 0.275761110036178 |
| 30 | 0.275761110036178 |
| 31 | 0.21003519237554447 |
| 32 | 0.21276906820574276 |
| 33 | 0.10331249360422572 |
| 34 | 0.23322617345373073 |
| 35 | 0.2813715026677469 |
| 36 | 0.2813715026677469 |
| 37 | 0.242165415472455 |
| 38 | 0.242165415472455 |
| 39 | 0.08023821057612525 |
| 40 | 0.08023821057612525 |
| 41 | 0.09763528611784456 |
| 42 | 0.10682629872636921 |
| 43 | 0.10665191884068455 |
| 44 | 0.07397791721317272 |
| 45 | 0.10682629872636921 |
| 46 | 0.08340116287888863 |
| 47 | 0.045197727384456196 |
| 48 | 0.05618544651781776 |
| 49 | 0.06580941390372022 |
| 50 | 0.06923611684143421 |
| 51 | 0.05257078215691021 |
| 52 | 0.05626182360415136 |
| 53 | 0.07767979731979961 |
| 54 | 0.08282368984370135 |
| 55 | 0.06861956277734169 |
| 56 | 0.0630192357665732 |
| 57 | 0.03976801543922248 |
| 58 | 0.029521509024306638 |
| 59 | 0.04220529987743146 |
| 60 | 0.046071625045589516 |

