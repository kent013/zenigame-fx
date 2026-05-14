# Run 80 — run_20260514_104946

**Generated**: 2026-05-14T10:49:47.493303+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: -3.4350973364090933 / threshold 1.0
- ❌ **total_pnl**: -32200.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 4.396940227703984 / threshold 20.0
- ❌ **trade_count**: 41 (range 50〜5000)

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
- seed: 65

## Best 個体

- name: `g33_i61`
- generation: 33
- fitness: **0.09647666908271153**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 41
- total_pnl: -32200.0
- sharpe: 0.11597666908271154
- sortino: —
- calmar: —
- max_drawdown_pct: 4.396940227703984

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2424
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1531
- Stage B pass: 175
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1531 | 175 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1531 | 175 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6190, median=2.0000, std=0.4891, min=0, max=2
- n_nodes: n=5856, mean=3.5248, median=3.0000, std=1.6315, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=106, mean=0.2944, median=0.2863, std=0.0469, min=0.2787, max=0.5687
- best mission_score: **0.5687** (`g44_i56`, gen=44, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1531, mean=0.1984, median=0.2121, std=0.0712, min=0.0000, max=0.3939
- dsr: n=0
- n_fold_effective (Stage A pass): n=1531, mean=31.3854, median=34, std=7.0322, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=1529, mean=0.3469, median=0.3438, std=0.1357, min=0.0000, max=0.7059

## Stage B failure reason 集計

- Stage A pass = 1531, Stage B pass = 175, failures = 1356 (primary_sum = 1356)

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
| `positive_fold_ratio_effective<min` | 1060 |
| `median_oos_total_pnl<min` | 242 |
| `sum_oos_total_pnl<min` | 54 |
| `n_fold_effective_below_profit_safe_min` | 0 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 2 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 1060 |
| `median_oos_total_pnl<min` | 1302 |
| `sum_oos_total_pnl<min` | 1342 |
| `n_fold_effective_below_profit_safe_min` | 96 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 13 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 5.2% (302/5856)
- best 個体 trade_count: 41
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1356, stage_a_only=4325, stage_b_evaluated=175
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4325, mean=-316720.0624, median=-61480.0000, std=425343.1257, min=-1007220.0000, max=33510.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4023): n=4023, mean=-340495.7171, median=-68680.0000, std=431743.4319, min=-1007220.0000, max=33510.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1531): n=1531, mean=16316.6362, median=17260.0000, std=46460.4846, min=-1000080.0000, max=70890.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g59_i35` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2717 | 0.2807 | ✅ | ❌ | ❌ | 50 | — |
| 2 | `g57_i71` | 57 | tier1_EUR_JPY | EUR_JPY | 0.2506 | 0.2836 | ✅ | ❌ | ❌ | 54 | — |
| 3 | `g10_i63` | 10 | tier1_EUR_JPY | EUR_JPY | 0.2354 | 0.2809 | ✅ | ❌ | ❌ | 30 | — |
| 4 | `g11_i0` | 11 | tier1_EUR_JPY | EUR_JPY | 0.2354 | 0.2809 | ✅ | ❌ | ❌ | 30 | — |
| 5 | `g12_i1` | 12 | tier1_EUR_JPY | EUR_JPY | 0.2354 | 0.2809 | ✅ | ❌ | ❌ | 30 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03388368884372533 |
| 1 | -0.024164486246421164 |
| 2 | -0.024164486246421164 |
| 3 | 0.2058177079302947 |
| 4 | 0.2058177079302947 |
| 5 | 0.2058177079302947 |
| 6 | 0.2058177079302947 |
| 7 | 0.2058177079302947 |
| 8 | 0.2058177079302947 |
| 9 | 0.2058177079302947 |
| 10 | 0.23540181931927104 |
| 11 | 0.23540181931927104 |
| 12 | 0.23540181931927104 |
| 13 | 0.23540181931927104 |
| 14 | 0.23540181931927104 |
| 15 | 0.23540181931927104 |
| 16 | 0.1890332987815942 |
| 17 | 0.1890332987815942 |
| 18 | 0.20254491255875062 |
| 19 | 0.19735551614313246 |
| 20 | 0.19735551614313246 |
| 21 | 0.18102500806681593 |
| 22 | 0.16806361654357624 |
| 23 | 0.11242480255935389 |
| 24 | 0.061951698087482326 |
| 25 | 0.10448939949639512 |
| 26 | 0.07076054531250843 |
| 27 | 0.1089940372754209 |
| 28 | 0.15193591637889814 |
| 29 | 0.15193591637889814 |
| 30 | 0.07816811898817315 |
| 31 | 0.07816811898817315 |
| 32 | 0.06498837781588586 |
| 33 | 0.09647666908271153 |
| 34 | 0.09647666908271153 |
| 35 | 0.15806399982093258 |
| 36 | 0.21997464086145888 |
| 37 | 0.09647666908271153 |
| 38 | 0.187424968484929 |
| 39 | 0.11161074506155395 |
| 40 | 0.10561074506155395 |
| 41 | 0.11419190095462163 |
| 42 | 0.1124182876925336 |
| 43 | 0.1124182876925336 |
| 44 | 0.1124182876925336 |
| 45 | 0.13679761197595575 |
| 46 | 0.10561074506155395 |
| 47 | 0.11700715813828762 |
| 48 | 0.11864284054457629 |
| 49 | 0.10116132081801879 |
| 50 | 0.09647666908271153 |
| 51 | 0.14183843121307435 |
| 52 | 0.13810187871562343 |
| 53 | 0.15180329597799194 |
| 54 | 0.10152837428715894 |
| 55 | 0.09647666908271153 |
| 56 | 0.1049432527671749 |
| 57 | 0.2505854127162014 |
| 58 | 0.10116132081801879 |
| 59 | 0.27173557135420345 |
| 60 | 0.12579485370387103 |

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

