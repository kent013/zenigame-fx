# Run 84 — run_20260520_180757

**Generated**: 2026-05-20T18:07:58.686122+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: -1.0250663992683666 / threshold 1.0
- ❌ **total_pnl**: -7170.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 1.5690178704763802 / threshold 20.0
- ❌ **trade_count**: 45 (range 50〜5000)

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
- seed: 69

## Best 個体

- name: `g53_i8`
- generation: 53
- fitness: **0.08401655593237661**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 45
- total_pnl: -7170.0
- sharpe: 0.08851655593237662
- sortino: —
- calmar: —
- max_drawdown_pct: 1.5690178704763802

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.3939
- dsr: —
- ii_lite_pass: —
- n_nodes: 1
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 391
- Stage B pass: 62
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 391 | 62 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 391 | 62 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3321, median=1.0000, std=0.4891, min=0, max=2
- n_nodes: n=5856, mean=2.9501, median=3.0000, std=1.6952, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=62, mean=0.3024, median=0.3033, std=0.0046, min=0.2746, max=0.3101
- best mission_score: **0.3101** (`g58_i23`, gen=58, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=391, mean=0.1583, median=0.1212, std=0.1269, min=0.0000, max=0.5152
- dsr: n=0
- n_fold_effective (Stage A pass): n=391, mean=24.8107, median=29, std=9.3808, min=5, max=34
- positive_fold_ratio_effective (Stage A pass): n=391, mean=0.2879, median=0.2647, std=0.2041, min=0.0000, max=0.8421

## Stage B failure reason 集計

- Stage A pass = 391, Stage B pass = 62, failures = 329 (primary_sum = 329)

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
| `positive_fold_ratio_effective<min` | 290 |
| `median_oos_total_pnl<min` | 18 |
| `sum_oos_total_pnl<min` | 9 |
| `n_fold_effective_below_profit_safe_min` | 12 |
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
| `positive_fold_ratio_effective<min` | 290 |
| `median_oos_total_pnl<min` | 308 |
| `sum_oos_total_pnl<min` | 317 |
| `n_fold_effective_below_profit_safe_min` | 144 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 0 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 5.1% (297/5856)
- best 個体 trade_count: 45
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=329, stage_a_only=5465, stage_b_evaluated=62
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5465, mean=-736813.9122, median=-1000110.0000, std=414004.2760, min=-1005930.0000, max=21850.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=5168): n=5168, mean=-779157.9005, median=-1000120.0000, std=385041.6271, min=-1005930.0000, max=21850.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=391): n=391, mean=9261.4578, median=13980.0000, std=89383.2033, min=-1000340.0000, max=34760.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g38_i77` | 38 | tier1_EUR_JPY | EUR_JPY | 0.3037 | 0.3237 | ✅ | ❌ | ❌ | 45 | — |
| 2 | `g39_i0` | 39 | tier1_EUR_JPY | EUR_JPY | 0.3037 | 0.3237 | ✅ | ❌ | ❌ | 45 | — |
| 3 | `g39_i59` | 39 | tier1_EUR_JPY | EUR_JPY | 0.3037 | 0.3237 | ✅ | ❌ | ❌ | 45 | — |
| 4 | `g40_i0` | 40 | tier1_EUR_JPY | EUR_JPY | 0.3037 | 0.3237 | ✅ | ❌ | ❌ | 45 | — |
| 5 | `g40_i1` | 40 | tier1_EUR_JPY | EUR_JPY | 0.3037 | 0.3237 | ✅ | ❌ | ❌ | 45 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.0361667957986967 |
| 1 | -0.0361667957986967 |
| 2 | -0.02744785190839908 |
| 3 | -0.013636361639246215 |
| 4 | -0.010472801233364394 |
| 5 | 0.036344884906442165 |
| 6 | 0.036344884906442165 |
| 7 | 0.036344884906442165 |
| 8 | 0.036344884906442165 |
| 9 | 0.036344884906442165 |
| 10 | 0.036344884906442165 |
| 11 | 0.14257537827571715 |
| 12 | 0.14257537827571715 |
| 13 | 0.1683191602492789 |
| 14 | 0.28101115379404035 |
| 15 | 0.28101115379404035 |
| 16 | 0.28101115379404035 |
| 17 | 0.28101115379404035 |
| 18 | 0.28101115379404035 |
| 19 | 0.28101115379404035 |
| 20 | 0.28101115379404035 |
| 21 | 0.28101115379404035 |
| 22 | 0.28349114321046226 |
| 23 | 0.28349114321046226 |
| 24 | 0.29385942003345755 |
| 25 | 0.29385942003345755 |
| 26 | 0.29385942003345755 |
| 27 | 0.29385942003345755 |
| 28 | 0.29385942003345755 |
| 29 | 0.29385942003345755 |
| 30 | 0.29385942003345755 |
| 31 | 0.29385942003345755 |
| 32 | 0.29385942003345755 |
| 33 | 0.29385942003345755 |
| 34 | 0.29385942003345755 |
| 35 | 0.29385942003345755 |
| 36 | 0.29385942003345755 |
| 37 | 0.29385942003345755 |
| 38 | 0.303665783558681 |
| 39 | 0.303665783558681 |
| 40 | 0.303665783558681 |
| 41 | 0.303665783558681 |
| 42 | 0.303665783558681 |
| 43 | 0.303665783558681 |
| 44 | 0.303665783558681 |
| 45 | 0.303665783558681 |
| 46 | 0.303665783558681 |
| 47 | 0.303665783558681 |
| 48 | 0.303665783558681 |
| 49 | 0.303665783558681 |
| 50 | 0.303665783558681 |
| 51 | 0.303665783558681 |
| 52 | 0.303665783558681 |
| 53 | 0.303665783558681 |
| 54 | 0.12979269027270673 |
| 55 | 0.08401655593237661 |
| 56 | 0.08753385616074238 |
| 57 | 0.08753385616074238 |
| 58 | 0.15259798689031226 |
| 59 | 0.1526092697841579 |
| 60 | 0.26345523441237845 |

## 分析

### analysis-claude.md

# RUN run_20260520_152204 (Run 83) 分析（Claude 自己分析）

## 前提差分
なし（archive Parquet / summary.json / analyze_run.py / codex 全て疎通確認済み）。本 Run は T109 (Stage B→C gap diagnostic v1) 適用後の最初の full run。

## 観察事実（Facts）

### Stage 通過数（vs Run 82）
| Stage | Run 83 | Run 82 | 差分 |
|-------|--------|--------|------|
| A pass | 717 | 2687 | -1970 |
| B pass | 436 | 941 | -505 |
| C pass | **43** | 0 | +43 ← Run 75 以来 2 度目の C>0 |
| graduated | 0 | 0 | ±0 |

- seed=68（Run82=67）。stage_b_gate_kind=profit_safe_pfr。Stage A/B が Run82 比で大幅減（seed variance、前ループでも確認済の現象）。

### ★ 使命達成（live_criteria all_pass=True）
best `g51_i71`（gen51, tier1_EUR_JPY, fitness_pen=0.0454）:
| 指標 | value | threshold | pass |
|------|-------|-----------|------|
| sharpe (annualized) | 4.24 | 1.0 | ✅ |
| total_pnl | 65210 | 50000 | ✅ |
| max_drawdown_pct | 1.49% | 20% | ✅ |
| trade_count | 51 | 50–5000 | ✅ |

→ **4/4 達成**。run-report も `🎯 使命達成` と判定。North Star（live_criteria 全達成個体の出現）に到達。

### Stage C 通過 43 個体の分布（mission-eligible 集団）
| 指標 | min | median | max |
|------|-----|--------|-----|
| total_pnl | 50260 | 51920 | 65210 |
| trade_count | 51 | 54 | 70 |
| trade_sharpe_stage_c (raw) | 0.167 | 0.212 | 0.290 |
| max_drawdown_pct | 1.49 | 2.46 | 2.86 |
| n_fold_effective | 34 | 34 | 34 |
| positive_fold_ratio_effective | 0.529 | 0.588 | 0.647 |
| mission_score | 0.966 | 0.971 | 0.983 |

→ **43 個体すべてが total_pnl≥50k かつ trade_count≥50**（best 1 体の lucky draw でなく、mission-eligible 集団）。

### Stage C 通過 43 個体の多様性（収束度）
- 世代分布: gen 43-60（18 世代に持続、単一世代の fluke ではない）
- **unique fitness_pen: 7 / 43**、**distinct primitive-set: 6 / 43** → 実質 ~6 種の genotype の複製。
- primitive 頻度: P7(43 全), P9(39), F4(39), P11(37) が支配的モチーフ。active_clause 1-2、n_nodes med 4（浅い）。
- → **1 戦略ファミリー（P7+P9+F4+P11 モチーフ）に収束**。内部的に持続するが genotype 多様性は低い。

### graduation=0 の構造的理由
- **ii_lite_pass が全 5856 個体で None**（cross-pair ii-lite は Phase 2 で shadow-only、gate 化されていない）。
- C-pass 43 個体の `canonical_gate_pass_c_shadow` は全件 False、persistence_score_shadow med 0.50。
- graduation = Stage C pass AND cross-pair pass の AND。cross-pair が None のため graduation は構造的に発火不能。

### ★ T109 diagnostic（Stage C 評価 436 個体の gap_class）
| gap_class | n | base_trade_count med | base_total_pnl med | stress_pnl_degradation |
|-----------|---|---------------------|--------------------|-----------------------|
| pnl_only | 162 | 58 (≥50 OK) | 36420 (全件 0<pnl<50k) | **0** |
| both_pnl_count | 176 | 38 (<50) | 27750 (-20640〜49470) | **0** |
| count_only | 35 | 44 (<50) | 59490 (≥50k profitable) | **0** |
| pass | 43 | 54 | 51920 | **0** |
| sharpe_involved | 20 | — | — | 0 |

## 解釈・推論（Interpretations）

### 1. mission 達成は「near-miss 群の山の頂上」であり、profit magnitude が binding
T109 診断が明快に示す: B→C gap の主因は **total_pnl の magnitude 不足**。
- pnl_only 162 個体は trade_count 十分（med 58）だが pnl が 18k-50k で **50k 閾値に僅差で未達**（near-miss、中央値 36k = 目標の 72%）。
- pass 43 と pnl_only 162 は連続体: 同じモチーフで pnl が 50k を超えたか僅かに届かなかったかの差。
- 反証可能性: もし pnl_only 群の primitive-set が pass 群と全く別系統なら「別の壁」。同系統なら「magnitude の連続的不足」。→ 次サイクルで pset 重なりを確認。

### 2. cost stress は B→C gap の要因では「ない」（stress_pnl_degradation=0）
全 436 個体で stress_pnl_degradation=0（spread×1.5 が PnL を 1 円も変えていない）。
- 解釈 A: これらの戦略の entry/exit は spread が binding しない時間帯/頻度 → cost robust。
- 解釈 B: stress 機構が実質 toothless（spread cost モデルが multiplier に非感応、または max_spread_bps が効いていない）。
- いずれにせよ **cycle 1 の H83 が想定した「cost 二次要因」は棄却**。cost は要因ですらない。
- 反証可能性: 解釈 B が真なら、spread_stress_multiplier を上げても degradation は 0 のまま。解釈 A が真なら、極端な multiplier では degradation>0 に転じる。→ 要検証（cycle 2 で stress 機構の健全性監査）。

### 3. graduation=0 は品質問題でなく「cross-pair が shadow-only」の構造
ii_lite_pass が常に None のため graduation は発火不能。**mission（live_criteria）は達成済だが、graduation という別ゲートが未配線**。
- これは「次の水準」の自然な候補: cross-pair ii-lite を shadow → hard gate に昇格すれば、graduation が真の汎化（複数ペアで通用）を要求する高い壁になる。
- 反証可能性: cross-pair を hard 化して graduation>0 が出れば真の多ペア汎化個体。0 のままなら EUR_JPY 特化の過学習。

### 4. 達成の頑健性は「未確定」（seed variance + 低 genotype 多様性 + 単一ペア）
- 43 個体は 18 世代持続するが ~6 genotype の複製（P7+P9+F4+P11 モチーフ 1 ファミリー）。
- 前ループ知見: profit_safe_pfr は seed variance 極端（Run 75 lucky の前例）。本 Run は seed=68 単発。
- cross-pair shadow は全 False、cross-seed 検証なし。
- → **単一 seed・単一ペア・単一モチーフの達成**。durable victory と断定するには cross-seed / cross-pair / OOS 検証が必要。**閾値の即時引き上げは時期尚早**。

### 5. 禁止事項違反の兆候
- 取引回数削減で見かけ改善（禁止 6）: C-pass の trade_count は 51-70 で live 下限 50 を実質満たす。near-miss 群も count med 58。回数削減の兆候なし。
- live_criteria 緩和: なし（閾値不変、達成は正味）。
- イントラデイ逸脱: max_dd 1.5-2.9% と健全、暴走なし。

## 次サイクル候補

- **[Critical] mission 達成の頑健性検証（cross-seed / cross-pair）を最優先**。単一 seed=68・単一ペア・~6 genotype の達成。次 Run を別 seed で回す or cross-pair ii-lite を shadow→hard 昇格して「複数ペア通用」を要求する。これが North Star の「達成後に水準を引き上げる」の正攻法（閾値緩和でなく gate 追加 = Structural）。
- **[Warning] cross-pair ii-lite の gate 化検討**: graduation=0 は ii_lite_pass=None の構造。shadow→hard 昇格で graduation を真の汎化ゲートにする（ただし全滅リスクは smoke で確認）。
- **[Warning] stress 機構の健全性監査**: stress_pnl_degradation が全個体 0。spread×1.5 stress が toothless でないか（cost robust なのか機構不全なのか）を切り分ける。toothless なら cost gate は形骸化。
- **[Warning] profit magnitude の押し上げ（pnl_only 162 near-miss 群）**: 多くが 36k 前後で 50k に僅差未達。同モチーフの pnl scaling（position sizing 等）を検討。ただし mission は既に達成済のため優先度は robustness より下。

## 全体判定
**OK（mission 達成、ただし要追検証）** — live_criteria 全達成個体が 43 出現（North Star 到達）。cost は B→C gap の要因でないと判明（stress=0）。残課題は (1) 達成の頑健性（seed/pair/motif 集中）、(2) graduation gap（cross-pair shadow-only）。閾値引き上げは robustness 確認後。T109 diagnostic は設計通り機能し、profit magnitude が binding constraint と特定した（cycle 1 の最大の成果）。

### analysis-codex.md

## 1. 観察事実（Facts）
- Run 83 は `seed=68, EUR_JPY, pop96, gen60, profit_safe_pfr`、T109 diagnostic 適用後初の full run。
- Stage 通過数は `A=717, B=436, C=43, graduated=0`。Run 82 比で A/B は減少、C は 0→43。
- `g51_i71` が live_criteria 4項目を同時達成した。  
  `sharpe(annualized)=4.24>=1.0`、`total_pnl=65210>=50000`、`max_dd=1.49%<=20%`、`trade_count=51>=50`。
- Stage C pass 43個体は全件 `total_pnl>=50k` かつ `trade_count>=50`。レンジは `pnl=50260〜65210`、`trade_count=51〜70`、`raw sharpe=0.167〜0.290`、`max_dd=1.49〜2.86%`。
- Stage C pass 43個体の多様性は低く、`unique fitness_pen=7/43`、`distinct primitive-set=6/43`。P7+P9+F4+P11 モチーフへ収束。
- `ii_lite_pass` は全 5856個体で `None`。C-pass 43件の `canonical_gate_pass_c_shadow` は全件 `False`。`persistence_score_shadow` 中央値 0.50。
- T109 diagnostic（Stage C評価 436個体）で gap_class は `pnl_only=162`、`both_pnl_count=176`、`count_only=35`、`pass=43`、`sharpe_involved=20`。
- 全 gap_class で `stress_pnl_degradation=0`（spread×1.5 stress の影響ゼロ）。

## 2. 解釈・推論（仮説と反証可能性）
- 仮説A: mission達成は「達成事実として有効」だが、頑健性は未確認。  
  根拠は単一seed・単一pair・実質約6 genotype収束。  
  反証可能性: 同一設定で seed を複数化（例: 5 seeds）し、`mission達成率` と `上位個体のprimitive-set多様性` が維持されれば「偶然性高い」仮説は棄却可能。
- 仮説B: `graduated=0` の主因は性能不足ではなく、cross-pair が shadow-only で `None/False` 固定の構造。  
  反証可能性: ii-lite を gate入力として実際に計算可能化した上で再実行し、C-pass個体が graduation に到達し始めるか確認。
- 仮説C: `stress_pnl_degradation=0` は「cost耐性が高い」より「stress機構が効いていない」可能性が高い。  
  理由は 436個体全件ゼロが不自然。  
  反証可能性: spread適用経路の監査（約定価格/手数料再計算）と、stress倍率を段階化した感度試験で `ΔPnL!=0` が出るか検証。
- 仮説D: B→C gap の主拘束は profit magnitude（pnl_only=162）で、取引回数不足は副拘束。  
  反証可能性: count十分群（pnl_only）に限定し、`PnL押上げ` 介入後に C pass が増えるかを A/B テスト。
- 禁止事項違反の兆候:  
  取引回数を削って見かけ改善する兆候は弱い（pass群 median 54、最低51）。  
  一方、`50k/50件` 近傍に候補が密集しており、境界最適化圧は存在。

## 3. 次サイクル候補
- **Critical（1件）**: `graduation` を実行可能にする構造修正。  
  cross-pair ii-lite を `None` で終わらせず計算・判定可能化し、shadowから段階昇格（いきなり全面hard化ではなく、まず「計測可能化→部分hard化」）。
- **Warning（1）**: stress評価の有効性監査。  
  `stress_pnl_degradation=0` 全件の原因を特定し、stressがPnLへ実際に伝播することをテストで担保。
- **Warning（2）**: profit magnitude 直撃の目的関数介入。  
  `pnl_only` 群を主対象に、閾値緩和なしで `50k未満ペナルティ` を導入し near-miss を pass 側へ押し上げる。
- **Warning（3）**: mission達成後の「次水準」引き上げ。  
  単発達成の次は、再現性条件を先に追加（複数seed×複数pairで達成）し、その後に `pnl_min` と `sharpe_min` を段階的に引き上げる（緩和はしない）。

## 4. 全体判定
**CONCERN**  
（mission達成は前進だが、再現性・graduation経路・stress有効性の3点が未充足）

### analysis-merged.md

# マージ分析: Run 83 (run_20260520_152204)

## 合意事項（Claude + Codex 一致）
- **mission 達成**: best g51_i71 が live_criteria 4/4 達成。Stage C 通過 43 個体すべて total_pnl≥50k・trade_count≥50（mission_score 0.97+）。North Star 到達。
- ただし **3 点が未充足**で「達成は前進だが頑健性は未確認」（Claude=OK要追検証 / Codex=CONCERN）:
  1. **再現性**: 単一 seed=68・単一ペア EUR_JPY・実質 ~6 genotype（P7+P9+F4+P11 モチーフ 1 ファミリー）への収束。前ループで profit_safe_pfr の seed variance 極端（Run75 lucky 前例）。
  2. **graduation=0 の構造**: ii_lite_pass が全 5856 個体 None（cross-pair ii-lite は shadow-only、gate 未配線）。graduation 構造的に発火不能。
  3. **stress 機構の無効性**: stress_pnl_degradation が全 436 個体 0。
- B→C gap 主因は **profit magnitude**（pnl_only 162 は count 十分だが pnl 18k-50k で 50k に near-miss）、cost は非要因。

## 確定した整合性問題（Claude 検証 + Codex 仮説C 一致）
**Stage C の「spread×1.5 stress」は cost robustness を検証していない。**
- `max_spread_bps` は `set_spread_filter`（broker が spread>閾値 の trade を skip する**フィルタ閾値**）であり、per-trade コストではない（src/broker/mock.py:165-195, src/backtest/engine.py:169）。
- spread×1.5 stress は**フィルタを緩める**だけ（より高 spread の trade を通す）でコストを増やさない → 境界付近に trade がなければ degradation=0。
- 結果、436 個体全件 degradation=0。「stress」という名前が果たすべき役割（高コスト環境でのロバスト性検証）を果たしていない（思考原則: 機能の名前に立ち返れ）。
- 含意: mission 達成個体の「cost robustness」は実質未検証。

## Claude 独自の発見
- 43 C-pass は gen43-60 持続だが unique fitness_pen 7 / distinct primitive-set 6 → 低 genotype 多様性。
- pnl_only 162 は near-miss（median 36k = 目標 72%）、同モチーフの pnl scaling 余地。

## Codex 独自の発見
- 仮説B 検証法: ii-lite を gate 入力として計算可能化 → 段階昇格（いきなり全面 hard でなく「計測可能化→部分 hard」）。
- 仮説C: 436 全件 0 は不自然 → stress 機構不全の可能性高い（Claude が filter/cost 取り違えと確認）。
- 「次水準」は再現性条件（複数 seed×複数 pair）を先に追加 → その後 pnl_min/sharpe_min を段階引き上げ（緩和禁止）。

## 矛盾・要議論
- 優先順位: (a) 再現性検証（seed 変更、ゼロコード risk）と (b) stress 機構修正（整合性問題、中 risk）のどちらを cycle 2 に。
  - (a) は「達成が seed-lucky か」を最速で判定。(b) は「達成個体が真に cost-robust か」を検証可能にする。
  - mission 達成済のため、North Star「達成後は robustness 確認後に閾値引き上げ」に従い再現性が先。だが stress 無効は達成の妥当性そのものに関わる。

## 統合改善提案（優先度順、Codex 合議で確定）
| # | 提案 | 優先度 | 出所 | 変更分類 | target_metric | 期待効果 |
|---|------|--------|------|---------|--------------|---------|
| P1 | 再現性検証: 別 seed で R84 を回し mission 再現率と genotype 多様性を観測（コード変更なし or 最小） | Critical | 両者 | 観測 | 全 live_criteria | 達成が seed-lucky か頑健かを判定。閾値引き上げ前の必須ゲート |
| P2 | stress 機構の cost-robustness 化（spread filter 緩和でなく per-trade コスト割増 stress を導入、または stress を診断計測可能化） | High | 両者(整合性) | Structural | 全 live_criteria の妥当性 | mission 個体の真の cost robustness 検証 |
| P3 | cross-pair ii-lite の計測可能化→段階 gate 昇格 | Warning | Codex | Structural | cross-pair / graduation | graduation を真の多ペア汎化ゲートに |

## 次フェーズへの申し送り
- cycle_focus = `ga_improvements`（T100 design-stale 既知、他 standalone は本 Run ボトルネックと非整合）。
- Codex 合議で P1/P2/P3 を「1 反証可能仮説 + 1 最小変更」に収束。低リスク（loop 停止回避）最優先。

