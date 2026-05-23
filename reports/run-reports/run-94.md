# Run 94 — run_20260522_200736

**Generated**: 2026-05-22T20:07:37.056719+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ✅ **sharpe**: 3.8009714382890216 / threshold 1.5
- ❌ **total_pnl**: 47020.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.4512996642015938 / threshold 20.0
- ❌ **trade_count**: 45 (range 100〜5000)

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
- seed: 68

## Best 個体

- name: `g59_i39`
- generation: 59
- fitness: **0.23719009227780538**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 45
- total_pnl: 47020.0
- sharpe: 0.29569009227780535
- sortino: —
- calmar: —
- max_drawdown_pct: 1.4512996642015938

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3939
- dsr: —
- ii_lite_pass: ❌
- n_nodes: 7
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2238
- Stage B pass: 1361
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2238 | 1361 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2238 | 1361 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4466, median=1.0000, std=0.4978, min=0, max=2
- n_nodes: n=5856, mean=4.5319, median=4.0000, std=1.9886, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1338, mean=0.7348, median=0.7701, std=0.1237, min=0.2440, max=0.9284
- best mission_score: **0.9284** (`g47_i4`, gen=47, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2238, mean=0.2153, median=0.2424, std=0.0807, min=0.0000, max=0.5455
- dsr: n=0
- n_fold_effective (Stage A pass): n=2238, mean=29.4723, median=33.0000, std=7.2563, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2236, mean=0.5585, median=0.5882, std=0.1514, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2238, Stage B pass = 1361, failures = 877 (primary_sum = 877)

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
| `positive_fold_ratio_effective<min` | 324 |
| `median_oos_total_pnl<min` | 253 |
| `sum_oos_total_pnl<min` | 148 |
| `n_fold_effective_below_profit_safe_min` | 152 |
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
| `positive_fold_ratio_effective<min` | 324 |
| `median_oos_total_pnl<min` | 577 |
| `sum_oos_total_pnl<min` | 669 |
| `n_fold_effective_below_profit_safe_min` | 250 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 22 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=1361, None=4495

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 1.8% (105/5856)
- best 個体 trade_count: 45
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=877, stage_a_only=3618, stage_b_evaluated=1361
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3618, mean=-264481.0697, median=-35455.0000, std=401459.3478, min=-1002770.0000, max=45310.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3513): n=3513, mean=-272386.1401, median=-38790.0000, std=404763.6003, min=-1002770.0000, max=45310.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2238): n=2238, mean=30884.5442, median=29790.0000, std=27511.6610, min=-1000250.0000, max=108650.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g14_i49` | 14 | tier1_EUR_JPY | EUR_JPY | 0.2882 | 0.3397 | ✅ | ❌ | ❌ | 36 | — |
| 2 | `g17_i15` | 17 | tier1_EUR_JPY | EUR_JPY | 0.2740 | 0.3310 | ✅ | ❌ | ❌ | 43 | — |
| 3 | `g18_i95` | 18 | tier1_EUR_JPY | EUR_JPY | 0.2740 | 0.3310 | ✅ | ❌ | ❌ | 43 | — |
| 4 | `g18_i14` | 18 | tier1_EUR_JPY | EUR_JPY | 0.2558 | 0.3138 | ✅ | ❌ | ❌ | 41 | — |
| 5 | `g59_i39` | 59 | tier1_EUR_JPY | EUR_JPY | 0.2372 | 0.2957 | ✅ | ✅ | ❌ | 45 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.059414916367459436 |
| 1 | 0.059414916367459436 |
| 2 | 0.1035456472460394 |
| 3 | 0.08378689335174752 |
| 4 | 0.08378689335174752 |
| 5 | 0.11903815497953113 |
| 6 | 0.11005781415502658 |
| 7 | 0.12723883204485065 |
| 8 | 0.1551836967269991 |
| 9 | 0.1551836967269991 |
| 10 | 0.11088583537874425 |
| 11 | 0.1829341398270881 |
| 12 | 0.18452214612616308 |
| 13 | 0.18452214612616308 |
| 14 | 0.2881961238894797 |
| 15 | 0.1521601579894807 |
| 16 | 0.1995005359693113 |
| 17 | 0.2740499757480311 |
| 18 | 0.2740499757480311 |
| 19 | 0.16508973731942178 |
| 20 | 0.2124319598970434 |
| 21 | 0.12340764531240578 |
| 22 | 0.15600149822535422 |
| 23 | 0.1453419716085048 |
| 24 | 0.15600149822535422 |
| 25 | 0.171518782735895 |
| 26 | 0.171518782735895 |
| 27 | 0.16784740062468514 |
| 28 | 0.16784740062468514 |
| 29 | 0.16797273086848752 |
| 30 | 0.16784740062468514 |
| 31 | 0.16784740062468514 |
| 32 | 0.16784740062468514 |
| 33 | 0.16784740062468514 |
| 34 | 0.16784740062468514 |
| 35 | 0.16784740062468514 |
| 36 | 0.16784740062468514 |
| 37 | 0.16784740062468514 |
| 38 | 0.23572841660487207 |
| 39 | 0.16784740062468514 |
| 40 | 0.18341692460260084 |
| 41 | 0.18341692460260084 |
| 42 | 0.19183270663416246 |
| 43 | 0.19183270663416246 |
| 44 | 0.19183270663416246 |
| 45 | 0.19183270663416246 |
| 46 | 0.19183270663416246 |
| 47 | 0.19183270663416246 |
| 48 | 0.19183270663416246 |
| 49 | 0.19183270663416246 |
| 50 | 0.19183270663416246 |
| 51 | 0.21571461563797095 |
| 52 | 0.19206680200405007 |
| 53 | 0.19206680200405007 |
| 54 | 0.21614135401714485 |
| 55 | 0.21614135401714485 |
| 56 | 0.21614135401714485 |
| 57 | 0.21679109486967446 |
| 58 | 0.21679109486967446 |
| 59 | 0.23719009227780538 |
| 60 | 0.23719009227780538 |

## 分析

### analysis-claude.md

# 戦略的再考分析 (cycle 12): cross-pair 汎化 7 サイクルの総括

## 前提
cycle 12 は単一 run 分析でなく **R87-R93 の 7 サイクル総括 + 戦略的再考**。

## 観察事実（Facts）

### cross-pair 汎化追求の全 approach と結果 (ii_lite_pass=True 個体数)
| Run | 施策 | ii_lite_pass | pair_failure=0 比率 | mean_sharpe max |
|-----|------|-------------|---------------------|-----------------|
| R87 | cross-pair 観測 (T114) | 0/599 | – | – |
| R88 | 選択圧 bool (T115) | 0/619 | – | – |
| R89 | 選択圧 連続値 (T116) | 0/892 | 0.3% | 0.143 |
| R90 | multi-pair min, no-ws (T117) | 0/0 (崩壊) | – | – |
| R91 | multi-pair mean, no-ws (T118) | 0/0 (崩壊) | – | – |
| R92 | multi-pair mean, +ws | 0/133 | 0.3% | 0.109 |
| R93 | multi-pair min, +ws | 0/86 | 0.0% | 0.122 |

**全 7 run・全 approach で ii_lite_pass=True は 0**。pair_failure=0 比率は 0.3% 据置〜悪化、max mean_sharpe は pass 閾値 0.15 未達。

### ★ cross-pair の位置づけ (AGENTS.md L196-200)
- cross_pair は **shadow 観測機構** (「graduation 強制は別途」「汎化の壁を ii_lite_pass 分布で定量化する観測機構」)。
- **live_criteria 本体** (target sharpe≥1.0 / total_pnl≥50000 / max_dd≤20% / trades 50-5000) は **R83/R75 で達成済** (mission_candidates=217、top annualized sharpe 5.02、cycle 23 で bug 修正後実証)。
- single-instrument では graduation は cross-pair 必須で構造的に 0 (AGENTS.md L239 KPI 分離)。

## 解釈・推論（Interpretations）

### 1. multi-pair Stage A 訓練は cross-pair 汎化に無効 (2x2 確定)
真因 (1)scope mismatch (訓練 1 anchor=USD_JPY のみ、cross-pair eval は EUR_JPY+EUR_USD+USD_JPY 全 3 ペア要求 → EUR_USD 訓練外) (2)window mismatch (訓練 Stage A 窓 vs eval holdout 窓) (3)anchor aux 非整合。pair_failure 分布が pf=2 据置 (R93 296/302) = anchor 取引枯渇が訓練後も不変。

### 2. ★ 戦略的論点: cross-pair 汎化は North Star か、self-imposed な追加バーか
- North Star = 「live_criteria 全達成個体を 1 つ → 達成後に閾値引き上げ」。**live_criteria は R83 で達成済**。
- cross-pair 汎化 (ii_lite_pass) は graduation の追加 gate だが AGENTS.md 上 **shadow 観測**。7 サイクル追求して 0 = EUR_JPY 学習戦略の他ペア転移は構造的に極めて困難 (price-scale/regime 差、現 32-primitive の表現力)。
- これは「閾値引き上げ凍結 (汎化達成まで)」の前提自体を問い直すべき局面: 汎化が構造的に困難なら、凍結が North Star (閾値引き上げ) を不当に阻んでいる可能性。

### 3. 候補アプローチの評価
- **(A) multi-pair scope/window 整合**: 訓練 anchor を cross-pair eval と同一の全ペア (EUR_USD+USD_JPY) + 同窓に。最も直接的に mismatch 解消だが、2x2 が示す「anchor 取引枯渇」の根本 (EUR_JPY 特化 entry) は scope 整合でも残る懸念。中コスト。
- **(B) NSGA2 多目的**: target/anchor を別目的 Pareto。集約 collapse 回避だが、anchor で取引しない個体が Pareto 前線に乗らない限り効果薄。大コスト (NSGA2 配線)。
- **(C) anchor aux 整合**: spike 制約解消。anchor aux 非整合が anchor 低性能の主因なら有効だが、metric_unavailable=0 (データ健全) から主因でない可能性。
- **(D) ★戦略転換**: cross-pair を long-term 研究 observable に格下げし、North Star (達成済 live_criteria の閾値引き上げ) に回帰。閾値引き上げ凍結を解除し、達成済 mission の頑健性 (sharpe 1.0→1.5 等) を高める方向。cross-pair は並行観測継続。

## 全体判定
**戦略的岐路 (CONCERN)** — 7 サイクル・4 approach で cross-pair 汎化 0 は再現性ある負の結果。cross-pair が shadow 観測 (hard 要件でない) かつ live_criteria 本体は達成済である事実から、(A)-(C) の cross-pair 追求継続 vs (D) North Star (閾値引き上げ) 回帰 を **Codex 戦略合議で決定**。これまでの負の結果から「同じ multi-pair 小改良」は避け、本質的に異なる一手か戦略転換を選ぶ。

## 次フェーズ
Codex 戦略 consensus (reasoning=high): (A)-(D) を mission 整合・効果見込み・低リスクで 1 つに収束。

## ★ cycle 12 Phase 3 追記 (実装前の決定的発見): 閾値引き上げ軸の再特定
R89 Stage C 892 個体 post-hoc 分析:
- annualized sharpe: median **4.56** / max **5.60** → **sharpe≥1.5 は全 892 クリア (hollow、GA fitness が既に sharpe 最大化)**。
- trade_count: min 50 / median **51** / p75 53 / max **97** → **96% が ≤60 (floor 50 張り付き)、≥100 はゼロ**。
- live_criteria@(sharpe≥1.5, trade≥100): **0 個体**。

→ **真に binding/meaningful な閾値は sharpe でなく trade_count_min**。現 best は trade_count=51 (floor ギリギリ) で annualized sharpe 5.60 = lucky-few-trade 過学習の典型 (AGENTS.md cycle23 C4 既知)。
**refined 施策: trade_count_min 50→100 引き上げ** (取引を増やす方向=「取引削減禁止」と整合、robustness 向上、binding)。GA を高取引数へ押すため entry_count_min (Stage A、現 50) も 100 へ整合引き上げ要。sharpe_min は 1.0→1.5 併せて引き上げ可 (hollow だが North Star 整合)。

注意: trade_count_min=100 で現状 0 個体 → GA が高取引数戦略を探索する必要。entry_count_min 整合引き上げで Stage A 圧をかける。これは「狙い撃ち floor」を上げる正当な robustness 強化。Codex で引き上げ幅 (100 vs 150) + entry_count_min 整合を確認。

