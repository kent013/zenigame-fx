# Run 85 — run_20260520_202321

**Generated**: 2026-05-20T20:23:22.181489+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 4.240848212862226 / threshold 1.0
- ✅ **total_pnl**: 65210.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.4908469793175152 / threshold 20.0
- ✅ **trade_count**: 51 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 43 (= Stage C 単独通過数)
- **mission_candidate_count**: 43 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

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

- name: `g51_i71`
- generation: 51
- fitness: **0.045408075289406075**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 51
- total_pnl: 65210.0
- sharpe: 0.06490807528940608
- sortino: —
- calmar: —
- max_drawdown_pct: 1.4908469793175152

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 717
- Stage B pass: 436
- Stage C pass: 43

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 43 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 51 | 21 | 48.8% |
| 54 | 1 | 2.3% |
| 55 | 5 | 11.6% |
| 56 | 7 | 16.3% |
| 58 | 5 | 11.6% |
| 70 | 4 | 9.3% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 0 | 43 |
| median total_pnl | — | 51920.0000 |
| median trade_sharpe_stage_c | — | 0.2117 |
| median max_drawdown_pct | — | 2.4625 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 717 | 436 | 43 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 717 | 436 | 43 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.4998, median=2.0000, std=0.5007, min=0, max=2
- n_nodes: n=5856, mean=3.5495, median=3.0000, std=2.0037, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=392, mean=0.8588, median=0.8890, std=0.1239, min=0.2801, max=0.9828
- best mission_score: **0.9828** (`g51_i71`, gen=51, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=717, mean=0.2202, median=0.2424, std=0.1146, min=0.0000, max=0.4242
- dsr: n=0
- n_fold_effective (Stage A pass): n=717, mean=27.7392, median=34, std=9.6746, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=713, mean=0.4670, median=0.5588, std=0.2166, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 717, Stage B pass = 436, failures = 281 (primary_sum = 281)

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
| `positive_fold_ratio_effective<min` | 202 |
| `median_oos_total_pnl<min` | 47 |
| `sum_oos_total_pnl<min` | 6 |
| `n_fold_effective_below_profit_safe_min` | 26 |
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
| `positive_fold_ratio_effective<min` | 202 |
| `median_oos_total_pnl<min` | 249 |
| `sum_oos_total_pnl<min` | 229 |
| `n_fold_effective_below_profit_safe_min` | 178 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 16 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 1.9% (111/5856)
- best 個体 trade_count: 51
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=281, stage_a_only=5139, stage_b_evaluated=393, stage_c_evaluated=43
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5139, mean=-615789.3520, median=-1000050.0000, std=463603.0421, min=-1006180.0000, max=50980.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5028): n=5028, mean=-629383.7470, median=-1000050.0000, std=459474.1724, min=-1006180.0000, max=50980.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=717): n=717, mean=860.9066, median=18790.0000, std=136850.9946, min=-1000890.0000, max=75770.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g40_i44` | 40 | tier1_EUR_JPY | EUR_JPY | 0.2635 | 0.2900 | ✅ | ❌ | ❌ | 43 | — |
| 2 | `g55_i23` | 55 | tier1_EUR_JPY | EUR_JPY | 0.2069 | 0.2454 | ✅ | ✅ | ❌ | 46 | — |
| 3 | `g47_i56` | 47 | tier1_EUR_JPY | EUR_JPY | 0.1985 | 0.2195 | ✅ | ✅ | ❌ | 26 | — |
| 4 | `g41_i27` | 41 | tier1_EUR_JPY | EUR_JPY | 0.1908 | 0.2118 | ✅ | ✅ | ❌ | 29 | — |
| 5 | `g42_i0` | 42 | tier1_EUR_JPY | EUR_JPY | 0.1908 | 0.2118 | ✅ | ✅ | ❌ | 29 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.009480436887098855 |
| 1 | -0.009480436887098855 |
| 2 | -0.009480436887098855 |
| 3 | -0.009480436887098855 |
| 4 | -0.009480436887098855 |
| 5 | -0.0016654135561131739 |
| 6 | -0.0016654135561131739 |
| 7 | -0.0016654135561131739 |
| 8 | -0.0016654135561131739 |
| 9 | -0.0016654135561131739 |
| 10 | -0.0016654135561131739 |
| 11 | -0.0016654135561131739 |
| 12 | -0.0016654135561131739 |
| 13 | -0.0016654135561131739 |
| 14 | 0.0029785279227919556 |
| 15 | 0.10331061005740243 |
| 16 | 0.10331061005740243 |
| 17 | 0.10331061005740243 |
| 18 | 0.10331061005740243 |
| 19 | 0.10331061005740243 |
| 20 | 0.10331061005740243 |
| 21 | 0.10331061005740243 |
| 22 | 0.10331061005740243 |
| 23 | 0.10331061005740243 |
| 24 | 0.10331061005740243 |
| 25 | 0.10331061005740243 |
| 26 | 0.10331061005740243 |
| 27 | 0.12057176171400047 |
| 28 | 0.12057176171400047 |
| 29 | 0.12057176171400047 |
| 30 | 0.12057176171400047 |
| 31 | 0.12057176171400047 |
| 32 | 0.12057176171400047 |
| 33 | 0.12057176171400047 |
| 34 | 0.12057176171400047 |
| 35 | 0.12554177631018876 |
| 36 | 0.10995853311540048 |
| 37 | 0.10995853311540048 |
| 38 | 0.10395853311540049 |
| 39 | 0.15963963600129588 |
| 40 | 0.26349130422327605 |
| 41 | 0.190833380801071 |
| 42 | 0.190833380801071 |
| 43 | 0.190833380801071 |
| 44 | 0.190833380801071 |
| 45 | 0.190833380801071 |
| 46 | 0.190833380801071 |
| 47 | 0.19850303720288806 |
| 48 | 0.10995853311540048 |
| 49 | 0.190833380801071 |
| 50 | 0.190833380801071 |
| 51 | 0.18011071830155956 |
| 52 | 0.08865994100444337 |
| 53 | 0.17797349156881137 |
| 54 | 0.1612243785552176 |
| 55 | 0.20686563003877387 |
| 56 | 0.10995853311540048 |
| 57 | 0.16994947893068685 |
| 58 | 0.16994947893068685 |
| 59 | 0.06901340572603823 |
| 60 | 0.10860833824615959 |

## 分析

### analysis-claude.md

# RUN run_20260520_180757 (Run 84) 分析（Claude 自己分析）

## 前提差分
なし。R84 は cycle 2 の再現性検証 run（seed=69、R83 から seed のみ変更、コード変更なし）。

## 観察事実（Facts）

### Stage 通過数の seed variance（R82/R83/R84）
| Run | seed | A | B | C | mission |
|-----|------|---|---|---|---------|
| R82 | 67 | 2687 | 941 | 0 | 0 |
| R83 | 68 | 717 | 436 | **43** | **43** |
| R84 | 69 | 391 | 62 | 0 | 0 |

- 同一設定（EUR_JPY/pop96/gen60/profit_safe_pfr）で seed のみ変えた 3 連続 run。**Stage A は 7 倍（391-2687）、Stage B は 15 倍（62-941）、Stage C は 0-43 と極端に変動**。
- R84 best（summary, selection_score）= g53_i8: a/b/c=T/T/F, live 1/4（sharpe-1.03/pnl-7170/tc45/dd1.57%pass）。
- R84 best（fitness_pen max）= g38_i77: a/b/c=T/F/F, tc45, pnl31310。
- R84 Stage B pass 62 個体: median_oos_total_pnl=1810（gate 正常動作）、total_pnl（Stage C holdout）median=-7170。
- R84 gap diagnostic（Stage C 評価 62 個体）: both_pnl_count=60, sharpe_involved=2（pass=0）。

## 解釈・推論（Interpretations）

### 1. R83 の mission 達成は seed-lucky（H84 REJECTED 確定）
seed=68 で 43 mission 個体、seed=67/69 で 0。profit_safe_pfr の seed sensitivity は前ループ（Run 75 lucky）でも観測され、本 3 連続 run で定量的に再確認。**mission は「出ることがある」が「頑健に出る」段階にない**。閾値引き上げは時期尚早（North Star: robustness 確認後）。
- 反証可能性: もし seed を変えても Stage C>0 が安定して出るなら variance は許容範囲。実測は 3 run 中 1 run のみ C>0 → 高 variance 確定。

### 2. cycle 3 の最優先は P2（Stage C stress の cost-robustness 化）— 整合性問題の修正
cycle 2 で確定: Stage C の「spread×1.5 stress」は max_spread_bps（spread フィルタ閾値、broker が spread>閾値 の trade を skip）を緩めるだけで per-trade コストを増やさず、stress_pnl_degradation が全個体 0（R83 436 件・R84 でも同様）。「stress」が名前通りの役割（高コスト耐性検証）を果たしていない。
- これは「仕組みが機能していない」状態。R83 の mission 個体も真の cost-stress を通過していない（gate が toothless）。
- P2 で per-trade コスト割増 stress を導入し、stress を名前通りの機能にする。これにより将来の mission 達成が「真に cost-robust」と保証される。
- 反証可能性: P2 導入後も stress_pnl_degradation が 0 のままなら実装/定義不整合が継続。

### 3. seed variance は cycle 3 の射程外（より深い GA dynamics 課題）
Stage A/B が seed で 7-15 倍変動するのは GA 探索の不安定性。これは multi-seed 評価や population 安定化など大きな構造課題で、P2（gate 整合性修正）とは別レーン。cycle 3 では P2 に集中し、variance は将来サイクルの課題として記録。
- 反証可能性: P2 導入で variance が変わるか（変わらないはず＝直交）を R85 で観測。

### 4. 禁止事項違反の兆候
なし。R84 は seed 変更のみで mission 未達も正味の結果。閾値緩和・取引回数操作なし。

## 次サイクル候補
- **[Critical] P2: Stage C stress の cost-robustness 化**（事前登録、cycle 2 consensus でキュー化）。spread filter 緩和でなく per-trade コスト割増 stress を導入。stress_pnl_degradation が非ゼロ化し、cost 環境下での mission 生存率を測定可能にする。Structural（整合性修正）。
- **[Warning] seed variance の構造対処**（将来）: multi-seed 評価 / population 安定化。Stage A/B の 7-15 倍変動を低減。
- **[Warning] cross-pair ii-lite の gate 化**（P3、将来）: graduation 配線。

## 全体判定
**CONCERN** — R83 mission は seed-lucky と確定（再現せず）。最優先は P2（stress 整合性修正、「仕組みが機能していない段階で値を弄るな」原則に従い gate を名前通りに直す）。seed variance は別レーンの大課題として記録。

### analysis-codex.md

1. Facts要約  
- Run 84（seed=69）は、R83（seed=68）と同一設定・コード変更なしにもかかわらず A/B/C/mission が **391/62/0/0** まで急減し、3連続runで通過数の振れが極端です。  
- R84 best は live_criteria **1/4**（sharpeのみ通過、pnl不達）で、Stage B中央値は正でも holdout では中央値が負転しています。  
- Stage C の spread×1.5 stress は実装上コスト増になっておらず、degradation=0 が構造的に発生しており、cost robustness は未検証です。

2. 解釈（反証可能性つき）  
- (a) R83 mission の seed-lucky 性: **現時点で支持**。  
反証可能性: 同一設定で seed を追加サンプル化（十分な n）し、mission率・C通過率が安定再現（例: 連続的に正のmission発生）すれば「lucky限定」は棄却可能。  
- (b) P2 を cycle3 最優先で実装する妥当性: **強く妥当**。  
反証可能性: 現行stressが実コスト増を正しく反映している証拠（per-trade cost増分がPnLに反映）を示せれば優先度は下げられるが、現状は整合性問題が確定しており反証困難。  
- (c) seed variance を P2 と別レーンにする是非: **別レーン推奨**。  
反証可能性: seed variance調査がP2実装の仕様決定に直結する依存関係を示せるなら同レーン化は合理的。ただし現状は「評価器の妥当性修復（P2）」が先で、混在は原因切り分けを悪化させる可能性が高い。

3. 次サイクル候補  
- Critical（P2具体化）  
  - Stage C stress を「閾値緩和」ではなく「約定ごとのスプレッド/コスト控除増分をPnLへ直接加算する方式」に変更し、`stress_pnl_degradation > 0` が多数個体で観測されることを受入基準にする。  
- Warning  
  - P2適用後に seed固定A/B再実行で、stress指標の分布変化と live_criteria通過率の感度を最小サンプルで確認（評価器改修の副作用検知）。  
  - seed variance は独立レーンで実施し、mission率の区間推定を出して「運」か「再現性」かを統計的に更新する。

4. 全体判定  
- **CRITICAL_DRIFT**（理由: Stage C cost robustness評価が実質無効で、mission判定の信頼性に直結するため）

