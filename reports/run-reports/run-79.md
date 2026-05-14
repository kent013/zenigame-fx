# Run 79 — run_20260514_053352

**Generated**: 2026-05-14T05:33:53.386517+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: -1.0025462140790249 / threshold 1.0
- ❌ **total_pnl**: -12360.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 3.528389110593069 / threshold 20.0
- ❌ **trade_count**: 32 (range 50〜5000)

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
- seed: 64

## Best 個体

- name: `g52_i93`
- generation: 52
- fitness: **0.2838421490337154**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 32
- total_pnl: -12360.0
- sharpe: 0.31984214903371544
- sortino: —
- calmar: —
- max_drawdown_pct: 3.528389110593069

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.2121
- dsr: —
- ii_lite_pass: —
- n_nodes: 6
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2087
- Stage B pass: 458
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2087 | 458 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2087 | 458 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4908, median=1.0000, std=0.5020, min=0, max=2
- n_nodes: n=5856, mean=4.1137, median=4.0000, std=1.7607, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=419, mean=0.3458, median=0.2883, std=0.1484, min=0.2669, max=0.8596
- best mission_score: **0.8596** (`g56_i73`, gen=56, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2087, mean=0.1996, median=0.2121, std=0.0681, min=0.0000, max=0.3939
- dsr: n=0
- n_fold_effective (Stage A pass): n=2087, mean=30.3057, median=34, std=7.4860, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2083, mean=0.4131, median=0.4118, std=0.1519, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2087, Stage B pass = 458, failures = 1629 (primary_sum = 1629)

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
| `positive_fold_ratio_effective<min` | 987 |
| `median_oos_total_pnl<min` | 469 |
| `sum_oos_total_pnl<min` | 83 |
| `n_fold_effective_below_profit_safe_min` | 90 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 4 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 987 |
| `median_oos_total_pnl<min` | 1456 |
| `sum_oos_total_pnl<min` | 1452 |
| `n_fold_effective_below_profit_safe_min` | 221 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 35 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 4.4% (256/5856)
- best 個体 trade_count: 32
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1629, stage_a_only=3769, stage_b_evaluated=458
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3769, mean=-267302.9610, median=-33770.0000, std=406691.9078, min=-1010480.0000, max=87270.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3513): n=3513, mean=-286781.9129, median=-42740.0000, std=414566.0786, min=-1010480.0000, max=87270.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2087): n=2087, mean=25295.2036, median=22480.0000, std=36699.5625, min=-1000350.0000, max=79700.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g40_i87` | 40 | tier1_EUR_JPY | EUR_JPY | 0.3769 | 0.4249 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g40_i72` | 40 | tier1_EUR_JPY | EUR_JPY | 0.3541 | 0.3906 | ✅ | ❌ | ❌ | 39 | — |
| 3 | `g39_i15` | 39 | tier1_EUR_JPY | EUR_JPY | 0.3528 | 0.3893 | ✅ | ❌ | ❌ | 39 | — |
| 4 | `g43_i87` | 43 | tier1_EUR_JPY | EUR_JPY | 0.3303 | 0.3753 | ✅ | ❌ | ❌ | 35 | — |
| 5 | `g44_i4` | 44 | tier1_EUR_JPY | EUR_JPY | 0.3268 | 0.3718 | ✅ | ❌ | ❌ | 35 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.028130094352268067 |
| 1 | 0.04629804219307401 |
| 2 | 0.05659158133594664 |
| 3 | 0.05659158133594664 |
| 4 | 0.06986461445431574 |
| 5 | 0.07691415175520919 |
| 6 | 0.15891675251409246 |
| 7 | 0.17546059287135507 |
| 8 | 0.17546059287135507 |
| 9 | 0.17546059287135507 |
| 10 | 0.21829461894009408 |
| 11 | 0.21829461894009408 |
| 12 | 0.21829461894009408 |
| 13 | 0.21829461894009408 |
| 14 | 0.21829461894009408 |
| 15 | 0.21829461894009408 |
| 16 | 0.25720828640013604 |
| 17 | 0.25720828640013604 |
| 18 | 0.25720828640013604 |
| 19 | 0.25720828640013604 |
| 20 | 0.25720828640013604 |
| 21 | 0.15397637226981656 |
| 22 | 0.10420550469016712 |
| 23 | 0.10903282487359159 |
| 24 | 0.13422192846804978 |
| 25 | 0.10791033080461392 |
| 26 | 0.1841094329040866 |
| 27 | 0.17169098314495668 |
| 28 | 0.21689541842017812 |
| 29 | 0.23976887371924732 |
| 30 | 0.15696912198880578 |
| 31 | 0.1700598945362058 |
| 32 | 0.15696912198880578 |
| 33 | 0.2758890176940743 |
| 34 | 0.25990989605999204 |
| 35 | 0.24801281148910237 |
| 36 | 0.21637873306370242 |
| 37 | 0.21637873306370242 |
| 38 | 0.26069854846508195 |
| 39 | 0.3528456846331588 |
| 40 | 0.3769184639750026 |
| 41 | 0.26069854846508195 |
| 42 | 0.29773189068075057 |
| 43 | 0.33031829253080025 |
| 44 | 0.32675032388701897 |
| 45 | 0.2870384952577961 |
| 46 | 0.29776521184550164 |
| 47 | 0.30113059107838497 |
| 48 | 0.2685194361422665 |
| 49 | 0.26069854846508195 |
| 50 | 0.27868128078507526 |
| 51 | 0.27868128078507526 |
| 52 | 0.2838421490337154 |
| 53 | 0.2838421490337154 |
| 54 | 0.2838421490337154 |
| 55 | 0.2838421490337154 |
| 56 | 0.2838421490337154 |
| 57 | 0.3015825331506451 |
| 58 | 0.2838421490337154 |
| 59 | 0.2838421490337154 |
| 60 | 0.2838421490337154 |

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

