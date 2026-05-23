# Run 95 — run_20260523_041132

**Generated**: 2026-05-23T04:11:33.190697+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 4.546245859186334 / threshold 1.5
- ✅ **total_pnl**: 73200.0 / threshold 70000.0
- ✅ **max_drawdown_pct**: 1.7881652829102077 / threshold 20.0
- ✅ **trade_count**: 52 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 378 (= Stage C 単独通過数)
- **mission_candidate_count**: 378 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g44_i43`
- generation: 44
- fitness: **0.10223698389045416**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 52
- total_pnl: 73200.0
- sharpe: 0.11573698389045416
- sortino: —
- calmar: —
- max_drawdown_pct: 1.7881652829102077

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
- Stage A pass: 2585
- Stage B pass: 2078
- Stage C pass: 378

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 378 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 20 | 5.3% |
| 51 | 24 | 6.3% |
| 52 | 290 | 76.7% |
| 53 | 21 | 5.6% |
| 54 | 6 | 1.6% |
| 56 | 7 | 1.9% |
| 58 | 3 | 0.8% |
| 60 | 7 | 1.9% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 20 | 358 |
| median total_pnl | 72765.0000 | 70985.0000 |
| median trade_sharpe_stage_c | 0.3221 | 0.3076 |
| median max_drawdown_pct | 1.7895 | 1.7882 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2585 | 2078 | 378 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2585 | 2078 | 378 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3009, median=1.0000, std=0.4601, min=0, max=2
- n_nodes: n=5856, mean=4.0663, median=4.0000, std=1.6697, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=2027, mean=0.8972, median=0.9276, std=0.0960, min=0.2954, max=0.9833
- best mission_score: **0.9833** (`g58_i54`, gen=58, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2585, mean=0.2578, median=0.3030, std=0.0718, min=0.0000, max=0.4545
- dsr: n=0
- n_fold_effective (Stage A pass): n=2585, mean=32.1896, median=34, std=5.2832, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2582, mean=0.5747, median=0.6176, std=0.1181, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2585, Stage B pass = 2078, failures = 507 (primary_sum = 507)

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
| `positive_fold_ratio_effective<min` | 220 |
| `median_oos_total_pnl<min` | 154 |
| `sum_oos_total_pnl<min` | 98 |
| `n_fold_effective_below_profit_safe_min` | 35 |
| `oos_total_pnl_unavailable` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 3 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 0 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `positive_fold_ratio_effective<min` | 220 |
| `median_oos_total_pnl<min` | 374 |
| `sum_oos_total_pnl<min` | 438 |
| `n_fold_effective_below_profit_safe_min` | 133 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 15 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=2078, None=3778

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.1% (123/5856)
- best 個体 trade_count: 52
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=507, stage_a_only=3271, stage_b_evaluated=1700, stage_c_evaluated=378
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3271, mean=-178696.6769, median=-21180.0000, std=343637.5720, min=-1001530.0000, max=55540.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3148): n=3148, mean=-185678.7897, median=-22520.0000, std=348431.1808, min=-1001530.0000, max=55540.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2585): n=2585, mean=24167.8956, median=24110.0000, std=24251.0061, min=-1000250.0000, max=92000.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g19_i51` | 19 | tier1_EUR_JPY | EUR_JPY | 0.3038 | 0.3228 | ✅ | ❌ | ❌ | 46 | — |
| 2 | `g32_i38` | 32 | tier1_EUR_JPY | EUR_JPY | 0.2751 | 0.2971 | ✅ | ✅ | ❌ | 32 | — |
| 3 | `g8_i46` | 8 | tier1_EUR_JPY | EUR_JPY | 0.2540 | 0.2690 | ✅ | ❌ | ❌ | 44 | — |
| 4 | `g9_i80` | 9 | tier1_EUR_JPY | EUR_JPY | 0.2410 | 0.2550 | ✅ | ❌ | ❌ | 45 | — |
| 5 | `g10_i77` | 10 | tier1_EUR_JPY | EUR_JPY | 0.2350 | 0.2550 | ✅ | ❌ | ❌ | 45 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.07391491636745944 |
| 1 | 0.06792810714621762 |
| 2 | 0.0795157801846648 |
| 3 | 0.11968274503918963 |
| 4 | 0.1291749381345223 |
| 5 | 0.14277344745495177 |
| 6 | 0.14277344745495177 |
| 7 | 0.14350533513837577 |
| 8 | 0.25400118890974477 |
| 9 | 0.24098742162727854 |
| 10 | 0.23498742162727854 |
| 11 | 0.17874980888252529 |
| 12 | 0.1367917237200553 |
| 13 | 0.14242221640403194 |
| 14 | 0.1460817001583301 |
| 15 | 0.1460817001583301 |
| 16 | 0.14087527588822094 |
| 17 | 0.1548681899535917 |
| 18 | 0.1407688596553421 |
| 19 | 0.3037862256392838 |
| 20 | 0.13842580945916438 |
| 21 | 0.1336807826123032 |
| 22 | 0.20886960906053137 |
| 23 | 0.16460924822148038 |
| 24 | 0.14221053419216814 |
| 25 | 0.14278150093604208 |
| 26 | 0.1516402058644935 |
| 27 | 0.1516402058644935 |
| 28 | 0.141542023042484 |
| 29 | 0.13554202304248403 |
| 30 | 0.12779489354395543 |
| 31 | 0.20860629937835135 |
| 32 | 0.2751160072438224 |
| 33 | 0.17489454018919048 |
| 34 | 0.15896603585146812 |
| 35 | 0.19374692071115396 |
| 36 | 0.14436137794796092 |
| 37 | 0.14436137794796092 |
| 38 | 0.14335414946384142 |
| 39 | 0.15130141903433025 |
| 40 | 0.16006853083240608 |
| 41 | 0.13096474889327647 |
| 42 | 0.14438303333216007 |
| 43 | 0.17209410062753405 |
| 44 | 0.22592940753072083 |
| 45 | 0.12702342604956873 |
| 46 | 0.15809779954300765 |
| 47 | 0.14265502659137466 |
| 48 | 0.1742597706008135 |
| 49 | 0.22725331855937875 |
| 50 | 0.2126730426340628 |
| 51 | 0.13630482012404532 |
| 52 | 0.1483299419535928 |
| 53 | 0.18911225572204948 |
| 54 | 0.17117690891031545 |
| 55 | 0.162190832652855 |
| 56 | 0.12123078092207572 |
| 57 | 0.18907927005651531 |
| 58 | 0.13533504969804733 |
| 59 | 0.17972396562914442 |
| 60 | 0.1413350496980473 |

## 分析

### analysis-claude.md

# 分析 (cycle 13): trade_count 閾値の構造的限界 + 達成可能な閾値再設計

## 前提
cycle 12 で live_criteria 引き上げ (sharpe1.5/trade_count_min100/entry_count_min100) → R94 で Stage C=0、entry_count_min=100 逆効果。本分析で trade_count と品質の関係を定量化。

## 観察事実（Facts）

### R94 (引き上げ後) の負の結果
- A/B/C = 2238/1361/**0**。trade_count_min=100 で Stage C 全滅。best: sharpe3.80/pnl47020/dd1.45/**trade45**。
- entry_count_min=100 逆効果: R94 Stage B trade_count median44/max97/≥100:0 vs R89(entry50) median50/**max668/≥100:15**。短い Stage A 窓 (stage_a_window_days=1) で 100 entries 強制が hyper-active-1day 戦略を選抜し、高取引数 tail を抹殺・分布左シフト。

### ★ trade_count vs 品質の単調トレードオフ (R89 Stage C 892 個体)
| trade_count 帯 | n | annualized sharpe median | pnl median |
|---------------|---|--------------------------|-----------|
| [50,60) | 850 | **4.64** | **69970** |
| [60,80) | 36 | 3.56 | 57875 |
| [80,98) | 6 | 3.42 | 54880 |

- R89 Stage B の trade_count≥100 個体 15 → **Stage C pass 0**。holdout trade_sharpe median 0.026/max 0.133 (極低) で Stage C 品質 gate (sharpe/pnl/dd) に落ちる。

## 解釈・推論（Interpretations）

### 1. trade_count_min=100 は現戦略空間で構造的に到達不能
高取引数 (≥100) 個体は holdout 品質 (sharpe/pnl) が崩壊 (median sharpe 0.026)。trade_count↑ で sharpe/pnl が単調劣化 (4.64@50 → 3.42@80-98)。現 32-primitive・EUR_JPY では「高頻度取引 = 低 per-trade 品質」のトレードオフが steep。trade_count_min=100 は品質基準と両立せず Stage C=0。

### 2. ★「lucky-few-trade 過学習」仮説の部分棄却
cycle 12 で「50-trade floor 張り付き = lucky 過学習」と解釈したが、50-trade 帯は **850 個体・median sharpe 4.64・pnl 69970** = robust な品質最適点 (少数の lucky 外れ値でない)。floor 張り付きは「過学習」でなく「品質最適が低取引数域にある」構造。

### 3. entry_count_min=100 は誤レバー (revert 確定)
短い Stage A 窓で 100 entries 強制は不適切 (hyper-active 選抜、高取引数 tail 抹殺)。R89 (entry50) は既に max668 trade 個体を持つ。→ entry_count_min 100→50 revert。

### 4. ★ 達成可能 & 意味ある閾値引き上げ = total_pnl_min
trade_count_min=100 / sharpe1.5 (hollow、既達4.64) でなく、**total_pnl_min 50000→70000** が binding (50-trade 帯 median 69970) かつ達成可能 (約半数 pass)。pnl は品質直結で、緩和でなく引き上げ・robustness 向上。

## 次サイクル候補
- **[Critical] config 調整**: (a) entry_count_min 100→50 revert (逆効果確定)、(b) trade_count_min 100→50 revert (構造的到達不能)、(c) sharpe_min 1.5 維持 (引き上げ済、緩和しない) + **total_pnl_min 50000→70000 引き上げ** (binding & 達成可能な意味ある robustness 強化)。
- **[Warning] cross-pair shadow 観測継続**、メタ過学習回避 (pnl 引き上げで品質最適個体を選抜、取引数操作でない)。

## 全体判定
**負の結果が閾値設計を精緻化** — trade_count_min=100/entry_count_min=100 は構造的に不適切 (品質トレードオフ + Stage A 短窓歪み)。50-trade は品質最適点で lucky でない。達成可能 & 意味ある引き上げは total_pnl_min 50000→70000。Codex 合議で revert + pnl 引き上げを確定。

