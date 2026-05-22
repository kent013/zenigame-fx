# Run 90 — run_20260522_160436

**Generated**: 2026-05-22T16:04:37.027422+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: -2.679083328569852 / threshold 1.0
- ❌ **total_pnl**: -1000270.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 3152 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 0 (= Stage C 単独通過数)
- **mission_candidate_count**: 0 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 48
- generations: 20
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 68

## Best 個体

- name: `g2_i29`
- generation: 2
- fitness: **-0.027784583408276546**
- fitness_finite: ✅
- stage_a_pass: ❌
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 3152
- total_pnl: -1000270.0
- sharpe: -0.023284583408276546
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: —
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 1008
- Stage A pass: 0
- Stage B pass: 0
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 1008 | 0 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 1008 | 0 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=1008, mean=1.2669, median=1.0000, std=0.4468, min=0, max=2
- n_nodes: n=1008, mean=2.7331, median=2.0000, std=1.6777, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=0
- dsr: n=0
- n_fold_effective (Stage A pass): n=0
- positive_fold_ratio_effective (Stage A pass): n=0

## Stage B failure reason 集計

- Stage A pass = 0, Stage B pass = 0, failures = 0 (primary_sum = 0)

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
| `positive_fold_ratio_effective<min` | 0 |
| `median_oos_total_pnl<min` | 0 |
| `sum_oos_total_pnl<min` | 0 |
| `n_fold_effective_below_profit_safe_min` | 0 |
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
| `positive_fold_ratio_effective<min` | 0 |
| `median_oos_total_pnl<min` | 0 |
| `sum_oos_total_pnl<min` | 0 |
| `n_fold_effective_below_profit_safe_min` | 0 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: enabled
- ii_lite_pass: True=0, False=0, None=1008

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.5% (25/1008)
- best 個体 trade_count: 3152
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 1008
- metric_stage 分布: stage_a_only=1008
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=1008, mean=-883799.8611, median=-1000170.0000, std=303158.7458, min=-1002600.0000, max=5780.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=983): n=983, mean=-906276.9685, median=-1000180.0000, std=271794.2352, min=-1002600.0000, max=5780.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体: 0 件 (比較対照なし)

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g2_i29` | 2 | tier1_EUR_JPY | EUR_JPY | -0.0278 | -0.0233 | ❌ | ❌ | ❌ | 3152 | — |
| 2 | `g3_i0` | 3 | tier1_EUR_JPY | EUR_JPY | -0.0278 | -0.0233 | ❌ | ❌ | ❌ | 3152 | — |
| 3 | `g4_i0` | 4 | tier1_EUR_JPY | EUR_JPY | -0.0278 | -0.0233 | ❌ | ❌ | ❌ | 3152 | — |
| 4 | `g5_i0` | 5 | tier1_EUR_JPY | EUR_JPY | -0.0278 | -0.0233 | ❌ | ❌ | ❌ | 3152 | — |
| 5 | `g6_i0` | 6 | tier1_EUR_JPY | EUR_JPY | -0.0278 | -0.0233 | ❌ | ❌ | ❌ | 3152 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.0581932937907595 |
| 1 | -0.048582820687510866 |
| 2 | -0.027784583408276546 |
| 3 | -0.027784583408276546 |
| 4 | -0.027784583408276546 |
| 5 | -0.027784583408276546 |
| 6 | -0.027784583408276546 |
| 7 | -0.027784583408276546 |
| 8 | -0.027784583408276546 |
| 9 | -0.027784583408276546 |
| 10 | -0.027784583408276546 |
| 11 | -0.027784583408276546 |
| 12 | -0.027784583408276546 |
| 13 | -0.027784583408276546 |
| 14 | -0.027784583408276546 |
| 15 | -0.027784583408276546 |
| 16 | -0.027784583408276546 |
| 17 | -0.027784583408276546 |
| 18 | -0.027784583408276546 |
| 19 | -0.027784583408276546 |
| 20 | -0.027784583408276546 |

## 分析

### analysis-claude.md

# RUN run_20260522_055538 (Run 89) 分析（Claude 自己分析）

## 前提差分
なし。R89 は T116 連続値選択圧 + warmstart(0.1) + seed=68。R88(bool)/R87(OFF) と A/B。

## 観察事実（Facts）

### T116 連続値化動作 + A/B
- selection_key_schema=v3_5_cross_pair_pressure_continuous、effective=True。Stage A/B/C = 2606/2142/892 (R88 bool: 2541/1930/619、Stage C 増)。
- aggregate_fitness (Stage B): median 0.026 / max 0.055 (R88: 0.022/0.0485、微増)。
- ii_lite_pass=True: **0/892** (R88 0/619、R87 0/599)。

### ★ pass binding 制約の精密診断（cycle 8 の核心、T116 観測列で判明）
Stage B 2142 個体の pass 3 条件 + pair_failure:
| 指標 | 値 |
|------|-----|
| cross_pair_mean_sharpe | median 0.089 / **max 0.143** (pass≥0.15: **0**) |
| cross_pair_min_sharpe | median 0.000 / max 0.021 (pass≥-0.20: **2141/2142**、ほぼ全達成) |
| cross_pair_target_ratio | **全 NaN** (sharpe_target_single 未提供で opt-in 除外、binding でない) |
| **cross_pair_pair_failure_count** | **median 2 / max 3 / =0 はわずか 7/2142** |

mean_sharpe 上位 5 個体すべて: min_sharpe=0.000, ratio=NaN, **pair_failure=2**。

## 解釈・推論（Interpretations）

### 1. ★ 真の binding 制約 = anchor での取引枯渇 (pair_failure)、利益過学習でない
`passed = base_all and not pair_failures` (cross_pair.py:360) のため、pair_failure>0 で **強制 passed=False**。ほぼ全個体 (2135/2142) が pair_failure≥1。pair_failure の原因は `_run_pair_sharpe` の **metric_unavailable** (trade_count < min → sharpe=0.0)。
- pair_failure=2 = target EUR_JPY は取引するが **両 anchor (EUR_USD, USD_JPY) で取引不足** (sharpe=0.0 が 2 つ)。
- mean_sharpe ≈ fmean([target_sharpe, 0, 0]) = target_sharpe/3 → max 0.143 は target_sharpe≈0.43 の希釈。
- ∴ ii_lite_pass=0 の真因は「mean<0.15 (利益不足)」でなく **「EUR_JPY 特化の entry トリガーが anchor で発火せず 0/僅少取引 → metric_unavailable → pair_failure → 強制 fail」**。
- 反証可能性: anchor で取引数を確保する施策 (multi-pair training) で pair_failure→0 になれば本診断が正。

### 2. cycle 7 までの「in-sample 利益過学習の天井」診断を精緻化
T116 観測列以前は「cross-pair fitness 天井 ~0.05」「mean<0.15」と解釈したが、実態は **anchor 取引枯渇 (pair_failure)** が支配的。選択圧 (bool/連続) で aggregate を僅かに上げても、anchor で取引しない構造は変わらず pair_failure が残る → gen 平坦・汎化 0。

### 3. 根本解 = multi-pair training (fitness を複数ペアで評価)
anchor で取引する戦略を得るには、GA が **学習時に複数ペアで評価** (取引+利益を全ペアで報酬) する必要がある。EUR_JPY 単一学習 → anchor 0 取引、では構造的に pair_failure。
- 規模大 (fitness 評価が複数ペア分、メモリ/速度)。Codex 推奨の最小 spike (2 ペア短窓でコスト見積) 先行。

### 4. 禁止事項違反の兆候
なし。

## 次サイクル候補
- **[Critical] multi-pair training**: GA fitness を EUR_JPY + anchor の複数ペアで評価し、anchor でも取引する汎化戦略を進化させる。anchor 取引枯渇 (pair_failure) を根本解消。最小 spike (2 ペア短窓) でコスト/効果見積を先行 (Codex)。
- **[Warning] pair_failure の trade_count_min 緩和は不可** (取引枯渇を隠蔽 = 禁止事項 6 の逆、見かけ改善)。あくまで取引する戦略を進化させる。
- **[Warning] 閾値引き上げ**: 汎化未達のため時期尚早。

## ★ falsification 結果 (Codex Critical: pair_failure=0 個体の mean_sharpe を確認)
pair_failure=0 (全ペアで取引する) 個体は **わずか 7**。その mean_sharpe = [-0.146, 0.012, 0.024, 0.038, 0.038, 0.045, **0.087**] → **0/7 が mean≥0.15** (max 0.087)。1/7 は min<-0.20 も不達。
pair_failure 別 mean_sharpe median: pf=0→0.038, pf=2→0.090(target希釈), pf=3→0.000。

→ **両 failure mode が binding と確定**:
1. 大半 (2103/2142) は anchor で取引せず pair_failure=2 (mean は target 希釈で見かけ 0.09-0.143 だが強制 fail)。
2. anchor で取引する 7 個体も **anchor 成績が低く mean 0.087 max << pass 0.15**。
∴ 「anchor 取引枯渇」と「anchor 低性能」の両方。anchor 再選定や trade_count 緩和 (cheap 代替) だけでは不十分 (取引する個体も利益不足)。**EUR_JPY 学習戦略は anchor で取引しないか、取引しても低性能** = 真の in-sample 特化。

## 全体判定
**CRITICAL_DRIFT (Codex)、根本原因完全特定** — T116 連続値化は部分前進 (max mean_sharpe 0.143) も gen 平坦・汎化 0。falsification で確定: cross-pair 0 汎化は (1)anchor 取引枯渇 (pair_failure) + (2)取引する個体も anchor 低性能 (mean 0.087<<0.15) の両方。EUR_JPY 単一学習の構造的限界。根本解は **multi-pair training** (進化時に全ペアで取引+利益を fitness 評価) のみ。Codex 推奨: full 実装前に 2-pair 軽量 in-loop の最小 spike でコスト/効果見積 + out-of-run 固定期間で再現確認 (メタ過学習ガード)。

### analysis-codex.md

1. Facts要約  
- Run 89 は `ii_lite_pass=True 0/892`、Stage B でも `mean_sharpe_cross>=0.15` 達成は `0/2142`。  
- 一方で `min_sharpe>=-0.20` は `2141/2142` とほぼ満たしており、`ratio` は opt-in未発動（NaN）。  
- 決定的なのは `pair_failure_count=0` が `7/2142` しかなく、上位 mean 個体も `pair_failure=2`（anchor取引不足）で落ちている点。  

2. 解釈（反証可能性つき）  
- (a) 妥当性: 概ね妥当。`mean<0.15` だけでなく、実際には `pair_failure` が fail-fast で主拘束になっている可能性が高い。  
  反証条件: `pair_failure=0` の母集団でなお `mean>=0.15` がほぼゼロなら、主拘束は利益不足側。まずこの条件付き分布を確認すべき。  
- (b) 根本解: multi-pair training は有力だが、いきなり全面導入は重い。低リスク代替として先に  
  1) anchor再選定（EUR_JPYに流動性/ボラ構造が近い組合せ）  
  2) cross-pair評価の「取引成立性」診断を fitness sidecar に昇格（選択圧の観測強化、閾値変更なし）  
  を試す価値がある。  
  反証条件: anchor最適化後も `pair_failure` が高止まりなら、multi-pair in-loop が必要。  
- (c) 禁止抵触性: 「取引する戦略を進化させる」こと自体は正当で、禁止の「取引回数を減らして見かけ改善」とは別。  
  ただし guard として、選抜指標から trade_count 直接優遇を排し、PnL/DD/汎化軸の主目的を維持すること。  

3. 次サイクル候補  
- Critical: `pair_failure` 主拘束の反証実験を最優先。`pair_failure=0` 条件での `mean_sharpe_cross` 分布を世代別に監査し、拘束の主因を確定（C9/C8準拠、結論先取り禁止）。  
- Warning: 最小spikeで `anchor再選定ABテスト`（現行anchor vs 類似構造anchor）を shadow 実施し、`pair_failure率` と `ii_lite_pass率` のみ比較。  
- Warning: multi-pair training は full実装前に「2-pair限定の軽量 in-loop 評価」を短期検証し、メタ過学習ガードとして out-of-run 固定期間で再現確認。  

4. 全体判定  
- `CRITICAL_DRIFT`（汎化ゲートが実質的に機能停止。まず拘束要因の切り分けを完了させる段階）

