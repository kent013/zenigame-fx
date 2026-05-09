# Run 56 — run_20260509_023253

**Generated**: 2026-05-09T02:32:53.860763+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.2372501668886839 / threshold 1.0
- ❌ **total_pnl**: -4100.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.5486214511986729 / threshold 20.0
- ❌ **trade_count**: 17 (range 50〜5000)

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

- name: `g46_i51`
- generation: 46
- fitness: **0.20425016688868392**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 17
- total_pnl: -4100.0
- sharpe: 0.2372501668886839
- sortino: —
- calmar: —
- max_drawdown_pct: 0.5486214511986729

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1111
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1219
- Stage B pass: 458
- Stage C pass: 0

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1219 | 458 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1219 | 458 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6318, median=2.0000, std=0.4855, min=0, max=2
- n_nodes: n=5856, mean=2.9360, median=3.0000, std=1.3971, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1219, mean=0.1707, median=0.1111, std=0.1658, min=0.0000, max=0.6667
- dsr: n=0
- n_fold_effective (Stage A pass): n=1219, mean=6.2231, median=8, std=3.8415, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=994, mean=0.5544, median=0.7000, std=0.3403, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1219, Stage B pass = 458, failures = 761 (primary_sum = 761)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 729 |
| `positive_fold_ratio<min` | 32 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 225 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 729 |
| `positive_fold_ratio<min` | 756 |
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
- trade_count=0 個体比率: 4.8% (279/5856)
- best 個体 trade_count: 17
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=761, stage_a_only=4637, stage_b_evaluated=458
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4637, mean=-542485.6718, median=-1000000.0000, std=470102.0594, min=-1004820.0000, max=29330.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4358): n=4358, mean=-577215.7090, median=-1000020.0000, std=463785.9703, min=-1004820.0000, max=29330.0000
  - うち PnL=0 個体: 8 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1219): n=1219, mean=16054.0197, median=22230.0000, std=58695.8054, min=-1000370.0000, max=38110.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g53_i42` | 53 | tier1_EUR_JPY | EUR_JPY | 0.2740 | 0.2965 | ✅ | ❌ | ❌ | 38 | — |
| 2 | `g41_i12` | 41 | tier1_EUR_JPY | EUR_JPY | 0.2736 | 0.2871 | ✅ | ❌ | ❌ | 59 | — |
| 3 | `g30_i81` | 30 | tier1_EUR_JPY | EUR_JPY | 0.2583 | 0.2818 | ✅ | ❌ | ❌ | 46 | — |
| 4 | `g31_i50` | 31 | tier1_EUR_JPY | EUR_JPY | 0.2583 | 0.2818 | ✅ | ❌ | ❌ | 46 | — |
| 5 | `g33_i83` | 33 | tier1_EUR_JPY | EUR_JPY | 0.2530 | 0.2950 | ✅ | ❌ | ❌ | 32 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.01944390468558208 |
| 1 | 0.01944390468558208 |
| 2 | 0.01944390468558208 |
| 3 | 0.027992043735990752 |
| 4 | 0.13193793347922592 |
| 5 | 0.13193793347922592 |
| 6 | 0.16037535249887602 |
| 7 | 0.16037535249887602 |
| 8 | 0.16037535249887602 |
| 9 | 0.1274379334792259 |
| 10 | 0.12293793347922591 |
| 11 | 0.14480605352098408 |
| 12 | 0.14480605352098408 |
| 13 | 0.14480605352098408 |
| 14 | 0.2030929024405303 |
| 15 | 0.19610517700671407 |
| 16 | 0.16956821988290952 |
| 17 | 0.16956821988290952 |
| 18 | 0.1698699872614722 |
| 19 | 0.16935202510641886 |
| 20 | 0.20342378450075677 |
| 21 | 0.18529987229922334 |
| 22 | 0.18529987229922334 |
| 23 | 0.18529987229922334 |
| 24 | 0.18529987229922334 |
| 25 | 0.18529987229922334 |
| 26 | 0.1974237845007568 |
| 27 | 0.21062001638861302 |
| 28 | 0.1974237845007568 |
| 29 | 0.24656453255998803 |
| 30 | 0.25834787594820835 |
| 31 | 0.25834787594820835 |
| 32 | 0.24656453255998803 |
| 33 | 0.25297245636373455 |
| 34 | 0.2143220678222304 |
| 35 | 0.21791607554197256 |
| 36 | 0.21791607554197256 |
| 37 | 0.21791607554197256 |
| 38 | 0.21964949663618738 |
| 39 | 0.22564949663618733 |
| 40 | 0.21683689857131033 |
| 41 | 0.27361280548153166 |
| 42 | 0.2165114453720667 |
| 43 | 0.21791607554197256 |
| 44 | 0.21791607554197256 |
| 45 | 0.21798807260746866 |
| 46 | 0.23737308934907175 |
| 47 | 0.23737308934907175 |
| 48 | 0.23737308934907175 |
| 49 | 0.24045681434022903 |
| 50 | 0.23737308934907175 |
| 51 | 0.23737308934907175 |
| 52 | 0.22740367948151746 |
| 53 | 0.2740026786942174 |
| 54 | 0.25093812028376467 |
| 55 | 0.2325504735924447 |
| 56 | 0.2325504735924447 |
| 57 | 0.2494911120717506 |
| 58 | 0.221100101051245 |
| 59 | 0.22954692324022147 |
| 60 | 0.2208978638966972 |

## 分析

### analysis-claude.md

# RUN run_20260509_011256 (run-55) 分析 — Claude 自己分析

**Generated**: 2026-05-09 11:30 JST
**run_id**: `run_20260509_011256` (run-55)
**T091 全段階適用後 (smoke RUN)**: median 0.025 + trade_count_full_dataset + partition guard + 二重 opt-in

---

## 観察事実 (Facts)

### F1. Stage 通過数 (run-54 比較)

| Stage | run-55 | run-54 | 差分 |
|---|---:|---:|---:|
| A pass | **997** | 1,439 | **-442 (-31%)** |
| B pass | 0 | 0 | ±0 |
| C pass | 0 | 0 | ±0 |

→ T091 段階 2 selection 切替で GA dynamics 大幅変化 verified。

### F2. Best 個体

- name: g49_i86 (gen 49)、 fitness_pen=**0.2851** (archive max)
- trade_count (Stage A)=31、 trade_count_stage_b=20、 trade_count_full_dataset=**51**
- total_pnl=19,270、 **median_oos_sharpe=0.0**、 **n_fold_effective=0**、 pfre=NaN
- active_clause=2、 selection_score=[1, -0.0, 0, 0, 1, 0, 0, 1, 0, 0.2851]
- → **selection の feasibility=1 (full_dataset 51>=50)、 fold_robust=0 (fold 評価不能)**

### F3. Stage A pass の trade_count スケール変化 (T091 段階 2 effect)

| metric | Stage A | full_dataset | ratio |
|---|---:|---:|---:|
| median trade_count | 37 | 66 | 1.78x |
| feasibility (>=50) 判定 | 旧: false (37<50) | 新: true (66>=50) | 切替 |

→ 旧 selection では infeasible だった個体が新 selection で feasible に変化、 feasibility 母数が大幅増。

### F4. median_oos_sharpe 分布 (T091 段階 2 archive 新列、 Layer 1 検証データ)

- count: 997 (Stage A pass 全件で計算済)
- **max: 0.0000**
- >0: 0 件
- >=0.025 (T091): 0 件
- >=0.05 (旧): 0 件

→ **seed=100 領域では median_oos_sharpe が 0 を超える個体が一切存在しない**。 T091 段階 1 (median 0.025 緩和) の効果は seed=100 で **完全にゼロ**であることが verified。

### F5. primitive 使用率 (Stage A pass + trade>=50、 n=295)

F4=99% / F13=86% / M3=11% / F10=6% / P10=6% / F12=5% / F1=4% / F7=4%
→ run-53/54 の seed=100 collapse パターン (F4+F13+F11) と同一、 mode collapse 維持。

---

## 解釈・推論 (Interpretations)

### I1. T091 段階 2 effect verified、 段階 1 は seed=100 で構造的無効

**事実**: archive 新列が全 997 Stage A pass 個体で non-null 書き込み。 selection 切替で Stage A pass 数 -31%、 feasibility 母数大幅増。 しかし median max=0.0 で gate 通過個体ゼロ。

**解釈**:
- 段階 2 の selection 整合化は **GA dynamics に明確な効果あり** (Stage A 1439→997)
- 段階 1 (median 0.05→0.025) は **seed=100 領域で完全に無意味** (median max=0 < 0.025)
- 真の Layer 1 検証は **別 seed (seed=42)** で実施する必要がある

### I2. n_fold_effective=0 個体の上位化問題が再確認

**事実**: best 個体 g49_i86 は n_fold_eff=0 で fold 評価不能 (run-54 best と同パターン)。 selection_score lex で feasible=1 + fitness_pen が支配し、 fold_robust=0 でも上位化。

**解釈**: cycle 1/2 Codex consensus で確認済の「n_fold_effective=0 上位化ガード」 が依然として必要。 selection_score に評価可能性ペナルティ要素を追加すべき。

### I3. cycle 3 の方針: Layer 1 検証相当 RUN を seed=42 で実施

**事実**: T091 全段階 適用後の archive を seed=100 で取得済。 真の Layer 1 検証 (mission-eligible 個体に類する pfre>=0.6 個体が gate を通るか) は **別 seed が必須**。

**解釈**: cycle 3 を「seed=42 + T091 全段階適用 + 二重 opt-in smoke RUN」 で短縮実施。 これは:
- 設計・実装 skip (T091 は完了済)
- 即 RUN 開始可能
- 旧 run-52 (seed=42) との比較で T091 全段階 effect を直接検証可能

**反証可能性**: seed=42 RUN-56 で Stage B pass 数が run-52 (=136) と比較して大幅増加なら T091 effect verified。 同等以下なら別根因再調査。

---

## cycle 3 方針

**Layer 1 検証相当の seed=42 smoke RUN を実施**:
- 設計・実装 skip (T091 全段階完了済)
- run_args: `--seed 42 --generations 60 --allow-holdout-short` + env `ZENIGAME_FX_SMOKE_TEST=1`
- 期待効果:
  - run-52 (seed=42、 T091 適用前): Stage B pass=136、 mission-eligible=7
  - run-56 (seed=42、 T091 全段階適用): selection 切替で feasibility 母数変化、 Stage B pass の trade_count 中央値変化
  - **mission-eligible 個体が Stage B pass する**個体数を verify

## 全体判定

**OK** (T091 全段階適用 + GA dynamics 変化 verified、 残課題は別 seed 検証 or mode collapse 介入)

