# Run 81 — run_20260514_144214

**Generated**: 2026-05-14T14:42:14.669530+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ✅ **sharpe**: 1.7102958747854666 / threshold 1.0
- ❌ **total_pnl**: -2970.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.9476615248139568 / threshold 20.0
- ❌ **trade_count**: 27 (range 50〜5000)

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
- seed: 66

## Best 個体

- name: `g51_i92`
- generation: 51
- fitness: **0.14260709282439635**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 27
- total_pnl: -2970.0
- sharpe: 0.16060709282439636
- sortino: —
- calmar: —
- max_drawdown_pct: 1.9476615248139568

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1818
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2293
- Stage B pass: 718
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2293 | 718 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2293 | 718 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3207, median=1.0000, std=0.4693, min=0, max=2
- n_nodes: n=5856, mean=3.2929, median=3.0000, std=1.6189, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=491, mean=0.3400, median=0.3093, std=0.0637, min=0.2759, max=0.6357
- best mission_score: **0.6357** (`g52_i94`, gen=52, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2293, mean=0.2302, median=0.2424, std=0.0882, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2293, mean=25.4117, median=28, std=7.6159, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2284, mean=0.4349, median=0.4500, std=0.1328, min=0.0000, max=0.7273

## Stage B failure reason 集計

- Stage A pass = 2293, Stage B pass = 718, failures = 1575 (primary_sum = 1575)

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
| `positive_fold_ratio_effective<min` | 849 |
| `median_oos_total_pnl<min` | 577 |
| `sum_oos_total_pnl<min` | 83 |
| `n_fold_effective_below_profit_safe_min` | 66 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 9 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 849 |
| `median_oos_total_pnl<min` | 1426 |
| `sum_oos_total_pnl<min` | 1441 |
| `n_fold_effective_below_profit_safe_min` | 441 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 25 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 9.5% (557/5856)
- best 個体 trade_count: 27
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1575, stage_a_only=3563, stage_b_evaluated=718
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3563, mean=-211698.6023, median=-36250.0000, std=365083.0222, min=-1005970.0000, max=28350.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3006): n=3006, mean=-250925.5223, median=-47505.0000, std=384889.4368, min=-1005970.0000, max=28350.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2293): n=2293, mean=17305.7436, median=19990.0000, std=22528.7024, min=-1000210.0000, max=43240.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g44_i90` | 44 | tier1_EUR_JPY | EUR_JPY | 0.5217 | 0.5562 | ✅ | ❌ | ❌ | 35 | — |
| 2 | `g28_i24` | 28 | tier1_EUR_JPY | EUR_JPY | 0.3876 | 0.4131 | ✅ | ❌ | ❌ | 38 | — |
| 3 | `g27_i52` | 27 | tier1_EUR_JPY | EUR_JPY | 0.3740 | 0.4115 | ✅ | ❌ | ❌ | 32 | — |
| 4 | `g28_i49` | 28 | tier1_EUR_JPY | EUR_JPY | 0.3724 | 0.4089 | ✅ | ❌ | ❌ | 33 | — |
| 5 | `g41_i64` | 41 | tier1_EUR_JPY | EUR_JPY | 0.3701 | 0.4246 | ✅ | ❌ | ❌ | 30 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03162410474751957 |
| 1 | -0.016914357441348577 |
| 2 | -0.016914357441348577 |
| 3 | 0.03713451301723473 |
| 4 | 0.03713451301723473 |
| 5 | 0.07583598535207484 |
| 6 | 0.07583598535207484 |
| 7 | 0.12348822350811894 |
| 8 | 0.2414109071515203 |
| 9 | 0.2414109071515203 |
| 10 | 0.27974733693017845 |
| 11 | 0.27974733693017845 |
| 12 | 0.27974733693017845 |
| 13 | 0.27974733693017845 |
| 14 | 0.3226892165780985 |
| 15 | 0.3226892165780985 |
| 16 | 0.3226892165780985 |
| 17 | 0.3226892165780985 |
| 18 | 0.30901448927708075 |
| 19 | 0.2863187018433302 |
| 20 | 0.28017546745372507 |
| 21 | 0.2988836853647613 |
| 22 | 0.2988836853647613 |
| 23 | 0.2988836853647613 |
| 24 | 0.2470094670891243 |
| 25 | 0.3337177410594205 |
| 26 | 0.35599706223903144 |
| 27 | 0.37398303429689744 |
| 28 | 0.3876412314176193 |
| 29 | 0.26853819750886077 |
| 30 | 0.12119056419747831 |
| 31 | 0.11352383966717942 |
| 32 | 0.11352383966717942 |
| 33 | 0.15172861686908332 |
| 34 | 0.16823149202735607 |
| 35 | 0.20048015186871523 |
| 36 | 0.15504437105209293 |
| 37 | 0.18035757174177994 |
| 38 | 0.31702865340781916 |
| 39 | 0.31702865340781916 |
| 40 | 0.2709709396855881 |
| 41 | 0.3700613641039151 |
| 42 | 0.3700613641039151 |
| 43 | 0.18174097298201927 |
| 44 | 0.521670482918914 |
| 45 | 0.34989869803034634 |
| 46 | 0.17959399676693824 |
| 47 | 0.20904151314820035 |
| 48 | 0.1865413237533591 |
| 49 | 0.19108413225682525 |
| 50 | 0.2285908688937903 |
| 51 | 0.2285908688937903 |
| 52 | 0.181453089389158 |
| 53 | 0.18174097298201927 |
| 54 | 0.18016769786799608 |
| 55 | 0.1819271246561562 |
| 56 | 0.17213912567117376 |
| 57 | 0.17213912567117376 |
| 58 | 0.18035757174177994 |
| 59 | 0.18035757174177994 |
| 60 | 0.1679544311370556 |

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

