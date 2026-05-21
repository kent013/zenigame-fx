# Run 86 — run_20260520_232522

**Generated**: 2026-05-20T23:25:23.576088+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

🎯 **使命達成**

- ✅ **sharpe**: 4.157421890433802 / threshold 1.0
- ✅ **total_pnl**: 64160.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.808808109052779 / threshold 20.0
- ✅ **trade_count**: 50 (range 50〜5000)

## KPI 分離 (cycle 23 C2)

- **graduation_count**: 0 (仕様: Stage C pass AND cross_pair pass。 single-instrument では構造的に 0 となる)
- **stage_c_pass_count**: 622 (= Stage C 単独通過数)
- **mission_candidate_count**: 622 (= live_criteria.all_pass 個体数、 cycle 23 C1 単位修正後の真値)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 69

## Best 個体

- name: `g42_i51`
- generation: 42
- fitness: **0.107439134236755**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ✅
- trade_count: 50
- total_pnl: 64160.0
- sharpe: 0.120939134236755
- sortino: —
- calmar: —
- max_drawdown_pct: 1.808808109052779

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3030
- dsr: —
- ii_lite_pass: —
- n_nodes: 3
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 2198
- Stage B pass: 1630
- Stage C pass: 622

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群: 622 件
- live_criteria.trade_count_min = 50

### trade_count 分布

| trade_count | count | pct |
|-------------|-------|-----|
| 50 ← min | 131 | 21.1% |
| 51 | 67 | 10.8% |
| 52 | 44 | 7.1% |
| 53 | 57 | 9.2% |
| 54 | 73 | 11.7% |
| 55 | 102 | 16.4% |
| 56 | 22 | 3.5% |
| 57 | 27 | 4.3% |
| 58 | 12 | 1.9% |
| 59 | 14 | 2.3% |
| 60 | 20 | 3.2% |
| 61 | 13 | 2.1% |
| 62 | 10 | 1.6% |
| 63 | 4 | 0.6% |
| 64 | 10 | 1.6% |
| 66 | 2 | 0.3% |
| 67 | 14 | 2.3% |

### 境界張り付き (==min) vs 非張り付き (>min) 比較

| 指標 | 境界張り付き (==min) | 非張り付き (>min) |
|------|---------------------|------------------|
| count | 131 | 491 |
| median total_pnl | 64160.0000 | 57860.0000 |
| median trade_sharpe_stage_c | 0.2869 | 0.2338 |
| median max_drawdown_pct | 1.8088 | 1.8076 |

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 2198 | 1630 | 622 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 2198 | 1630 | 622 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3328, median=1.0000, std=0.4756, min=0, max=2
- n_nodes: n=5856, mean=4.1569, median=4.0000, std=1.8179, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1594, mean=0.9116, median=0.9563, std=0.1083, min=0.2840, max=0.9829
- best mission_score: **0.9829** (`g56_i87`, gen=56, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=2198, mean=0.2597, median=0.2727, std=0.0770, min=0.0000, max=0.4848
- dsr: n=0
- n_fold_effective (Stage A pass): n=2198, mean=31.9586, median=34.0000, std=5.4968, min=0, max=34
- positive_fold_ratio_effective (Stage A pass): n=2194, mean=0.5648, median=0.6176, std=0.1447, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 2198, Stage B pass = 1630, failures = 568 (primary_sum = 568)

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
| `positive_fold_ratio_effective<min` | 310 |
| `median_oos_total_pnl<min` | 162 |
| `sum_oos_total_pnl<min` | 56 |
| `n_fold_effective_below_profit_safe_min` | 40 |
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
| `positive_fold_ratio_effective<min` | 310 |
| `median_oos_total_pnl<min` | 472 |
| `sum_oos_total_pnl<min` | 505 |
| `n_fold_effective_below_profit_safe_min` | 122 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 12 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 2.0% (120/5856)
- best 個体 trade_count: 50
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=568, stage_a_only=3658, stage_b_evaluated=1008, stage_c_evaluated=622
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=3658, mean=-225242.3537, median=-27090.0000, std=374911.5296, min=-1005840.0000, max=82670.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3538): n=3538, mean=-232882.0040, median=-29875.0000, std=378875.8524, min=-1005840.0000, max=82670.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=2198): n=2198, mean=23729.7589, median=22960.0000, std=27076.3555, min=-1000090.0000, max=135920.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g27_i53` | 27 | tier1_EUR_JPY | EUR_JPY | 0.3196 | 0.3426 | ✅ | ❌ | ❌ | 42 | — |
| 2 | `g24_i42` | 24 | tier1_EUR_JPY | EUR_JPY | 0.3033 | 0.3308 | ✅ | ❌ | ❌ | 42 | — |
| 3 | `g17_i56` | 17 | tier1_EUR_JPY | EUR_JPY | 0.2925 | 0.3150 | ✅ | ❌ | ❌ | 61 | — |
| 4 | `g34_i38` | 34 | tier1_EUR_JPY | EUR_JPY | 0.2532 | 0.2772 | ✅ | ❌ | ❌ | 41 | — |
| 5 | `g9_i77` | 9 | tier1_EUR_JPY | EUR_JPY | 0.2307 | 0.2772 | ✅ | ❌ | ❌ | 41 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.045408075289406075 |
| 1 | 0.045408075289406075 |
| 2 | 0.045408075289406075 |
| 3 | 0.045408075289406075 |
| 4 | 0.045408075289406075 |
| 5 | 0.059140686185826075 |
| 6 | 0.06386673930849494 |
| 7 | 0.13173472000059466 |
| 8 | 0.13173472000059466 |
| 9 | 0.23071664443114984 |
| 10 | 0.21910775912787747 |
| 11 | 0.20121892502665392 |
| 12 | 0.21076335575004015 |
| 13 | 0.20064173588089995 |
| 14 | 0.19686578797915374 |
| 15 | 0.1779050340809969 |
| 16 | 0.1779050340809969 |
| 17 | 0.292459342948914 |
| 18 | 0.1632562752231715 |
| 19 | 0.13851632191733848 |
| 20 | 0.13477014060619122 |
| 21 | 0.186300258617901 |
| 22 | 0.09498936649641758 |
| 23 | 0.15883516470918768 |
| 24 | 0.3032859558478269 |
| 25 | 0.1390954817739452 |
| 26 | 0.18572817756618068 |
| 27 | 0.3195593828099782 |
| 28 | 0.1884782101147671 |
| 29 | 0.20354272058601347 |
| 30 | 0.22087792163146486 |
| 31 | 0.22087792163146486 |
| 32 | 0.16701838050942663 |
| 33 | 0.16775925951379192 |
| 34 | 0.25324503195374376 |
| 35 | 0.15864745639392502 |
| 36 | 0.15864745639392502 |
| 37 | 0.1674379838977022 |
| 38 | 0.11135496094967152 |
| 39 | 0.19615869679908585 |
| 40 | 0.19615869679908585 |
| 41 | 0.13380226244619164 |
| 42 | 0.12938748637541797 |
| 43 | 0.15296117708233375 |
| 44 | 0.107439134236755 |
| 45 | 0.18115323289315857 |
| 46 | 0.13094082752815833 |
| 47 | 0.14914335742788493 |
| 48 | 0.1636356995240639 |
| 49 | 0.1424489926500926 |
| 50 | 0.20277899822896062 |
| 51 | 0.20277899822896062 |
| 52 | 0.20076733969504534 |
| 53 | 0.20619643773970603 |
| 54 | 0.12472542379110467 |
| 55 | 0.12068528254047968 |
| 56 | 0.12027879980183052 |
| 57 | 0.16733993465104677 |
| 58 | 0.1959372686724834 |
| 59 | 0.12960117480513555 |
| 60 | 0.16902609279326736 |

## 分析

### analysis-claude.md

# RUN run_20260520_202321 (Run 85) 分析（Claude 自己分析）

## 前提差分
なし。R85 は P2 (T110: Stage C stress cost-robustness 化) 適用後の検証 run（seed=68 = R83 と同 seed）。

## 観察事実（Facts）

### P2 検証結果（cycle 3 の主眼）
- **stress_pnl_degradation が全 436 Stage-C 評価個体で非ゼロ化**（min 3475 / median 11454 / max 22235）。R83 では全件 0（toothless）→ **P2 で cost stress が実際に PnL を悪化させるようになった**。
- Stage A/B/C = 717/436/**43**（R83 と完全同一）。gap_class 分布も同一（both_pnl_count176/pnl_only162/pass43/count_only35/sharpe_involved20）。
- best g51_i71 は live all_pass=True（sharpe4.24/pnl65210/dd1.49%/tc51）= R83 と同一。**真の spread×1.5 cost stress（~11k PnL 悪化）下でも Stage C 通過 = cost-robust 実証**。
- Stage C 通過数が不変な理由: stress gate 閾値（spread_stress_min_total_pnl=0 / spread_stress_min_sharpe=0）が緩く、43 個体は ~11k cost を吸収しても stressed pnl/sharpe>=0 を維持。

### ★ seed variance（同一 config、EUR_JPY/pop96/gen60/profit_safe_pfr）
| Run | seed | A | B | C |
|-----|------|---|---|---|
| R82 | 67 | 2687 | 941 | 0 |
| R83 | 68 | 717 | 436 | **43** |
| R84 | 69 | 391 | 62 | 0 |
| R85 | 68 | 717 | 436 | **43** |

- **R83 と R85（同 seed=68）は完全同一** → GA は seed 固定で deterministic。
- seed 67/68/69 で Stage C = 0/43/0、Stage B = 941/436/62（15倍変動）→ **探索結果が seed に極端依存（seed-locked trajectory）**。
- R85 で Stage C 個体が初出現するのは **gen 43**（遅い）。mission 個体は後期世代でのみ出現。

### graduation
- graduation_count=0（cross-pair ii-lite が shadow-only、ii_lite_pass 全件 None の構造は不変）。

## 解釈・推論（Interpretations）

### 1. mission 達成は seed=68 で deterministic だが seed 非依存に再現しない（確定）
R83=R85 の完全一致は「同 seed なら確実に 43 mission 個体」を示す。一方 seed 67/69 では 0。**run-to-run noise ではなく seed-locked**。GA の初期集団 + 確率的演算が seed で決まり、profitable region への到達可否が seed で分岐する。
- 反証可能性: もし別の複数 seed でも Stage C>0 が安定して出るなら variance は許容内。実測 4 run 中 seed=68 のみ → seed sensitivity 確定。

### 2. 最大の残課題は seed variance（再現性）であり、これが真の robustness gap
P2 で cost 整合性は解消し、seed=68 mission 個体は cost-robust と実証済。残るのは「mission 個体を **seed 非依存に確実に得る**」こと。これは GA 探索の安定性の問題。
- mission（live_criteria 達成個体を 1 つ得る）の観点では **既に g51_i71 を保持**しているが、システムが再現的に produce できないと「1 個体の偶然」の域を出ない。

### 3. seed variance への構造アプローチ候補
- **(a) warmstart（T101、登録済 standalone）**: 既知 mission 個体（g51_i71）を初期集団に注入 → gen 0 から評価され seed に依らず保持される。mission 個体の喪失を防ぎ再現性を担保。最も直接的で低リスク（初期集団への注入のみ、評価ロジック不変）。
- **(b) multi-seed 評価**: 複数 seed で GA を回し winner を intersect → 頑健性を統計的に確認。コスト N 倍（runtime 増）、loop 停止リスク中。
- **(c) population 安定化 / diversity 維持**: 大集団・selection 変更で seed 依存を低減。GA dynamics 大改変、リスク高。
- **(d) cross-pair ii-lite gate 昇格（P3）**: graduation を真の多ペア汎化ゲートに。seed variance とは別軸（graduation 配線）。

### 4. 禁止事項違反の兆候
なし。P2 は cost 厳格化（緩和でない）。seed variance 対処は探索安定化であり閾値操作でない。

## 次サイクル候補
- **[Critical] seed variance/再現性への構造対処**: 最有力は **warmstart（T101）**— 既知 mission 個体を初期集団に注入し seed 非依存に mission 個体を保持。低リスク（初期集団注入のみ、評価不変）。Codex 合議で warmstart vs multi-seed を 1 つに収束。
- **[Warning] cross-pair ii-lite gate 昇格（P3）**: graduation=0 の構造解消。多ペア汎化を要求する次の壁。中-大リスク。
- **[Warning] stress gate 閾値の妥当性**: P2 で cost が効くようになったが stress gate 閾値（pnl/sharpe>=0）が緩く強フィルタでない。cost-robust を要件として強める余地（ただし mission が seed 脆弱な現状では時期尚早、warmstart で再現性確保が先）。

## 全体判定
**OK（P2 完遂・検証成功、ただし seed variance が残る最大課題）** — cost 整合性問題は解消し seed=68 mission 個体は cost-robust と実証。残るのは mission 個体を seed 非依存に得る再現性。次は warmstart 等で探索安定化（閾値引き上げは再現性確保後）。

### analysis-codex.md

1. Facts要約  
- P2で`stress_pnl_degradation`は全436個体で非ゼロ化し、Stage C stressがtoothlessではなくなった（R83の全0を解消）。  
- Run 85（seed=68）はR83とA/B/C=`717/436/43`で完全一致し、`g51_i71`が`live_criteria all_pass=True`（cost stress下でも通過）。  
- ただしseed間は`C=0/43/0`（s67/s68/s69）で極端に不安定、graduationは0のまま。  

2. 解釈（反証可能性つき）  
- (a) 「mission達成は再現的か」  
  - 現状評価: **seed=68内の決定論的再現は確認**、しかし**seed非依存再現は未達**。  
  - 反証条件: 同一コード/同一データでseedを変えてもall_pass個体が安定出現すれば、この懸念は棄却。現データでは棄却できない。  
- (b) 「seed varianceは真のrobustness gapか」  
  - 現状評価: **ほぼYes**。R83=R85完全一致により「非決定性ノイズ説」は反証済み。差分の主因は探索軌道（seed依存）。  
  - 反証条件: seedを跨いでもStage C到達率が収束する設計変更で改善すれば、gapは縮小可能。  
- (c) 「warmstartは有効か／答え注入で過学習か」  
  - 現状評価: **低リスクで有効**。初期集団注入は評価関数・閾値を変えないため、ルール改ざんではない。  
  - リスク: 1個体固定注入のみだと“探索の多様性低下”は起こり得る。  
  - 反証条件: warmstart後に複数seedでall_pass保持でき、かつstress指標悪化が再現するなら「単なる注入過学習」懸念は弱まる。  

3. 次サイクル候補  
- Critical（1個）: **T101 warmstartを即適用**  
  - 方針: `g51_i71`を初期集団に固定1スロット注入（評価不変・閾値据え置き）。  
  - 受入基準: 少なくとも`s67/s68/s69`で各runに`live_criteria all_pass >=1`を達成。未達なら次にmulti-seed常設へ。  
- Warning 1: warmstartは単一個体固定で止めず、近傍変異 or top-N archive注入で多様性維持（緩和はしない）。  
- Warning 2: graduation=0（ii-lite未配線）はP3で継続。mission達成とは分離して管理。  

4. 全体判定  
**CRITICAL_DRIFT**（理由: mission個体はあるが、現状はseed-lockで運用再現性が不足）。

