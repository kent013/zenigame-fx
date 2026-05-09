# Run 55 — run_20260509_011256

**Generated**: 2026-05-09T01:15:07.246782+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.3175891613520199 / threshold 1.0
- ❌ **total_pnl**: 19270.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ❌ **trade_count**: 31 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 100

## Best 個体

- name: `g49_i86`
- generation: 49
- fitness: **0.2850891613520199**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 31
- total_pnl: 19270.0
- sharpe: 0.3175891613520199
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 2

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 997
- Stage B pass: 0
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 997 | 0 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 997 | 0 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.6238, median=2.0000, std=0.4865, min=0, max=2
- n_nodes: n=5856, mean=2.6098, median=2.0000, std=1.3906, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した 個体が無いため未計測)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=997, mean=0.0077, median=0.0000, std=0.0395, min=0.0000, max=0.2222
- dsr: n=0
- n_fold_effective (Stage A pass): n=997, mean=2.6409, median=1, std=3.6225, min=0, max=10
- positive_fold_ratio_effective (Stage A pass): n=512, mean=0.0118, median=0.0000, std=0.0441, min=0.0000, max=0.3000

## Stage B failure reason 集計

- Stage A pass = 997, Stage B pass = 0, failures = 997 (primary_sum = 997)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 997 |
| `positive_fold_ratio<min` | 0 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 485 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 997 |
| `positive_fold_ratio<min` | 997 |
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
- trade_count=0 個体比率: 6.6% (387/5856)
- best 個体 trade_count: 31
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=997, stage_a_only=4859
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4859, mean=-394833.9494, median=-56910.0000, std=463914.1733, min=-1013480.0000, max=23320.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4472): n=4472, mean=-429002.2719, median=-88870.0000, std=468169.3763, min=-1013480.0000, max=23320.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=997): n=997, mean=1722.6379, median=14920.0000, std=106061.8533, min=-1000340.0000, max=33370.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g49_i86` | 49 | tier1_EUR_JPY | EUR_JPY | 0.2851 | 0.3176 | ✅ | ❌ | ❌ | 31 | — |
| 2 | `g50_i0` | 50 | tier1_EUR_JPY | EUR_JPY | 0.2851 | 0.3176 | ✅ | ❌ | ❌ | 31 | — |
| 3 | `g50_i25` | 50 | tier1_EUR_JPY | EUR_JPY | 0.2851 | 0.3176 | ✅ | ❌ | ❌ | 31 | — |
| 4 | `g50_i39` | 50 | tier1_EUR_JPY | EUR_JPY | 0.2851 | 0.3176 | ✅ | ❌ | ❌ | 31 | — |
| 5 | `g51_i0` | 51 | tier1_EUR_JPY | EUR_JPY | 0.2851 | 0.3176 | ✅ | ❌ | ❌ | 31 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | 0.04934400993968757 |
| 1 | 0.11284516344650065 |
| 2 | 0.11284516344650065 |
| 3 | 0.11284516344650065 |
| 4 | 0.12417890900858282 |
| 5 | 0.12417890900858282 |
| 6 | 0.12417890900858282 |
| 7 | 0.12417890900858282 |
| 8 | 0.12417890900858282 |
| 9 | 0.23021217602960048 |
| 10 | 0.23021217602960048 |
| 11 | 0.23021217602960048 |
| 12 | 0.23021217602960048 |
| 13 | 0.24757832996373202 |
| 14 | 0.2696767604924993 |
| 15 | 0.2696767604924993 |
| 16 | 0.2696767604924993 |
| 17 | 0.2696767604924993 |
| 18 | 0.2696767604924993 |
| 19 | 0.2696767604924993 |
| 20 | 0.2756767604924993 |
| 21 | 0.2756767604924993 |
| 22 | 0.2756767604924993 |
| 23 | 0.2756767604924993 |
| 24 | 0.2756767604924993 |
| 25 | 0.2756767604924993 |
| 26 | 0.2756767604924993 |
| 27 | 0.2756767604924993 |
| 28 | 0.2756767604924993 |
| 29 | 0.2756767604924993 |
| 30 | 0.2756767604924993 |
| 31 | 0.2756767604924993 |
| 32 | 0.2756767604924993 |
| 33 | 0.2756767604924993 |
| 34 | 0.2756767604924993 |
| 35 | 0.2756767604924993 |
| 36 | 0.2756767604924993 |
| 37 | 0.2756767604924993 |
| 38 | 0.2756767604924993 |
| 39 | 0.2756767604924993 |
| 40 | 0.2756767604924993 |
| 41 | 0.2756767604924993 |
| 42 | 0.2756767604924993 |
| 43 | 0.2756767604924993 |
| 44 | 0.2756767604924993 |
| 45 | 0.2756767604924993 |
| 46 | 0.2756767604924993 |
| 47 | 0.2756767604924993 |
| 48 | 0.2756767604924993 |
| 49 | 0.2850891613520199 |
| 50 | 0.2850891613520199 |
| 51 | 0.2850891613520199 |
| 52 | 0.2850891613520199 |
| 53 | 0.2850891613520199 |
| 54 | 0.2850891613520199 |
| 55 | 0.2850891613520199 |
| 56 | 0.2850891613520199 |
| 57 | 0.2850891613520199 |
| 58 | 0.2850891613520199 |
| 59 | 0.2850891613520199 |
| 60 | 0.2850891613520199 |

## 分析

### analysis-claude.md

# RUN run_20260508_224819 (run-54) 分析 — Claude 自己分析

**Generated**: 2026-05-09 09:25 JST
**run_id**: `run_20260508_224819` (run-54)
**dataset**: EUR_JPY 2025-10-01 → 2026-04-01 (183,403 bars)
**ga_config**: pop=96, gens=60, mutation=0.5, crossover=0.7, tournament=3, elite=2, max_clause=2, **seed=100**
**T091 段階 1 適用後**: stage_b_median_oos_sharpe_min: 0.05 → **0.025**

---

## 前提差分

なし (前提全件 verified)。

---

## 観察事実 (Facts)

### F1. Stage 通過数 (run-53 比較)

| Stage | run-54 | run-53 | 差分 |
|---|---:|---:|---:|
| A pass | 1,439 | 1,439 | **±0** |
| B pass | **0** | 0 | ±0 |
| C pass | **0** | 0 | ±0 |
| graduated | **0** | 0 | ±0 |

### F2. archive フィールド完全一致 (run-53 vs run-54)

```
stage_a_pass / stage_b_pass / stage_c_pass / fitness_pen / fitness_raw /
trade_count / total_pnl / positive_fold_ratio_effective / n_fold_effective:
全 0 differing rows (n=5,856 各 RUN)
```

→ T091 段階 1 (median 0.025) は GA 評価結果に影響を与えない。

### F3. Best 個体 (selection_score lex 順)

| 項目 | run-54 | run-53 | 差分 |
|---|---|---|---|
| name | g52_i27 | g52_i27 | 一致 |
| generation | 52 | 52 | 一致 |
| fitness_pen | 0.0375 | 0.0375 | 一致 |
| trade_count | 61 | 61 | 一致 |
| total_pnl | 6,270 | 6,270 | 一致 |
| pfre | 0.8 | 0.8 | 一致 |
| n_fold_eff | 5 | 5 | 一致 |
| feasible | True | True | 一致 |
| fold_robust | True | True | 一致 |
| selection_score schema | v3_3_stage_b_feasible_priority | 同 | 一致 |

→ summary.best は 100% 一致。

### F4. Stage B failure reasons の微小変化 (Stage A pass + Stage B fail = 1,439 個体)

| reason | run-54 | run-53 | 差分 |
|---|---:|---:|---:|
| `median_oos_sharpe<min` | **1,437** | 1,439 | **-2** |
| `positive_fold_ratio<min` | 1,439 | 1,439 | ±0 |
| `all_folds_unavailable` | 24 | 24 | ±0 |

→ **T091 段階 1 で 2 個体の `median_oos_sharpe<min` reason が消えた** = gate 内部で機能 verified。 ただし両 reason の同時 trigger 構造のため、 median 単独緩和では Stage B pass には繋がらず。

### F5. archive top-5 (fitness_pen 単独降順、 selection_score lex とは別)

| rank | name | gen | fp | trade | total_pnl | stage_a | stage_b | pfre | active_clause |
|---:|---|---:|---:|---:|---:|---|---|---:|---:|
| 1 | g57_i15 | 57 | 0.2354 | 32 | 15,530 | ✓ | ✗ | NaN | 2 |
| 2 | g42_i54 | 42 | 0.1915 | 56 | 26,430 | ✓ | ✗ | 0.2 | 2 |
| 3 | g43_i0 | 43 | 0.1915 | 56 | 26,430 | ✓ | ✗ | 0.2 | 2 |
| 4 | g44_i0 | 44 | 0.1915 | 56 | 26,430 | ✓ | ✗ | 0.2 | 2 |
| 5 | g45_i0 | 45 | 0.1915 | 56 | 26,430 | ✓ | ✗ | 0.2 | 2 |

→ fp 単独 top は trade=32 (feasible=False) の g57_i15、 selection_score lex は feasible 優先で trade=61 の g52_i27。

### F6. Mission-eligible @ Stage A 個体数

(Stage A pass + trade>=50 + total_pnl>=50,000) = **0 件** (run-53 と一致、 大幅退化のまま)。

### F7. Stage A pass + trade>=50 個体数

1,305 件 (run-53 と一致)、 max total_pnl = 27,800 (mission criteria 50,000 まで 22,200 不足)。

### F8. RUN 設定 / コスト

- elapsed: ~87 min (run-53 90 min から微差)
- cross_pair_runtime_mode: `skipped_single_instrument`

---

## 解釈・推論 (Interpretations)

### I1. T091 段階 1 (median 0.025) は seed=100 領域で **gate 内部機能のみ effective**

**事実**: archive 全フィールド完全一致、 summary.best 一致、 ただし `median_oos_sharpe<min` trigger 数が 1439 → 1437 (-2 件)。

**解釈**: T091 段階 1 は **gate level では設計通り機能** している (2 個体の median が 0.025-0.05 区間に位置し、 新閾値で reason が消えた)。 ただし全 1439 個体で `positive_fold_ratio<min` も同時 trigger するため、 Stage B pass には繋がらず。 cycle 1 解釈 I3 (T091 段階 1 単独では seed=100 で効果限定的) **verified**。

**反証可能性**: T091 段階 1 が gate level で機能していなければ `median_oos_sharpe<min` trigger 数も run-53 と同一 (1439) になる。 → 1437 という値は機能している証拠。

### I2. seed=100 領域の構造的限界 (cycle 1 verified を再確認)

**事実**: run-53 と run-54 で archive 完全一致 = T091 段階 1 単独では seed=100 領域の出力分布を変えない。

**解釈**: cycle 1 の I2 (seed=100 領域は profitability 構造的に低い、 max PnL 27,800、 mission criteria 50,000 まで 22,200 不足) は seed=100 における primitive collapse (F4+F13+F11) の global structure に起因。 gate 緩和では突破不可能。

**反証可能性**: T091 段階 2 (trade_count_full_dataset) を適用しても run-54 と同一の archive 出力なら、 selection 圧整合化も seed=100 では効果ゼロ → 別の介入 (mode collapse 抑制 / seed 戦略) が必要 verified。

### I3. T091 段階 2/3 の seed=100 における効果見込み

**事実**: trade_count_full_dataset は `trade_count_stage_a + trade_count_stage_b_full` の合算。 Stage A 60d で trade>=50 の個体 1305 件中、 Stage B 67d で trade rate が異なる場合 trade_count_full_dataset が変動する。

**解釈**: 段階 2 で selection feasibility が変わると、 GA 経路が異なる個体を best に押し上げる可能性。 ただし archive のフィールド (stage_a_pass / fitness_pen / pfre) は GA 評価ベースなので、 段階 2 適用後も基本分布は同一に近いと推定。 真の効果は **次 RUN (run-55) で確認**する必要がある (current archive ではなく、 段階 2 適用後の RUN 結果が必要)。

**反証可能性**: 段階 2 適用後の RUN-55 で best 個体が g52_i27 と異なる名前になる、 もしくは Stage A pass 個体の selection ranking が変わる → 段階 2 の効果あり。

### I4. Layer 1 archive replay の必要性確認

**事実**: T091 段階 1 単独効果は seed=100 archive では確認不可 (median + pfre 両方 trigger のため)。

**解釈**: 真の効果検証は **run-52 archive (seed=42) replay** で実施する必要がある。 mission-eligible 7 個体のうち pfre>=0.6 の 2 件 (g70_i9 / g83_i12) は pfre 0.7 で `positive_fold_ratio<min` trigger なし、 median<min のみ blocked と判明済 (前 session 調査)。 → T091 段階 1 適用で これら 2 件が pass する仮説は run-52 archive replay で verify 可能。

**反証可能性**: run-52 archive で g70_i9 の median_oos_sharpe 値を確認、 0.025 < value < 0.05 なら段階 1 で pass、 value < 0.025 なら段階 1 では不通過 (= H_A1' 反証)。

### I5. cycle 1 で予測した「seed=100 では graduate に繋がらない可能性が高い」 が verified

**事実**: cycle 1 Phase B-2 Codex consensus で予測、 cycle 2 で実証 (run-54 = run-53 完全一致)。

**解釈**: T091 段階 1 単独で seed=100 baseline を変えるという期待は当初からなかった。 Layer 2 検証 (seed=100 RUN) は **gate redesign の効果が現れない条件**として有用なネガティブコントロール。 真の Layer 2 検証は段階 2/3 完了 + Layer 1 で正の効果が確認された後に seed=42 で再 RUN。

---

## 次サイクル候補

### [Critical] T091 段階 2 (trade_count_full_dataset) の本 cycle 実装

事実: cycle 1 で段階 1 のみ実装、 段階 2/3 は次 cycle 継続を申し送り。 cycle 2 で段階 2 を実装することで:
- selection feasibility が Stage A 60d → データセット全期間 (~127d) に整合化
- Stage B 全期間 1 pass backtest 追加 (+37% wall-time)
- archive に新列 `trade_count_stage_a` / `trade_count_stage_b` / `trade_count_full_dataset` 追加

期待効果:
- Layer 1 archive replay で run-52 mission-eligible 個体の selection ranking 変化を verify
- Layer 2 RUN-55 で seed=100 baseline でも selection 圧整合化が effect ありか観察 (期待は中程度、 PnL 構造的限界は変えられない)

### [Warning] Layer 1 archive replay (run-52、 段階 1 単独有効性検証)

事実: run-52 mission-eligible 7 個体のうち pfre>=0.6 の 2 件 (g70_i9 / g83_i12) が median<min のみ blocked と推定済。 段階 1 適用で 1+ 件 Stage B pass する仮説 H_A1'。

提案: 本 cycle 内で archive replay を実装 (簡易 replay スクリプト)、 g70_i9 / g83_i12 の median_oos_sharpe 実値を archive から取得し 0.025 閾値で再判定。 0.025 <= median < 0.05 なら段階 1 適用で pass (gate redesign 効果 verify)、 median < 0.025 なら別根因。

### [Warning] T091 段階 3 (partition guard) の本 cycle 続行検討

事実: 段階 2 完了後、 wall-time 余裕があれば段階 3 を続行可能。 段階 3 は holdout 14日 vs 60d 不整合の起動時 fail-closed 検出 + 二重 opt-in escape hatch。

提案: 段階 2 と相互独立な変更なので、 段階 2 マージ後すぐに段階 3 ブランチを開始 (同 cycle 内で順次)。 ただし段階 3 を入れると次 RUN (run-55) 起動時に holdout 不整合で fail する → 二重 opt-in (`ZENIGAME_FX_SMOKE_TEST=1 + --allow-holdout-short`) で smoke RUN するか、 dataset 延長を別 cycle で先行する判断が必要。

### [Suggestion] 並行新規 TODO (n_fold_effective=0 ガード) の概念設計開始

事実: cycle 1 Phase B Codex consensus で「n_fold_effective=0 上位化ガード」 を新規 TODO として登録、 概念設計のみ今 cycle で開始する方針。 cycle 1 では実施しなかった (T091 段階 1 実装に集中)。

提案: cycle 2 で段階 2 完了後に余裕があれば `/zenigame-fx-alpha-design n_fold_effective_zero_guard` で正規フローを別 devnotes で実施。 TODO 登録は次 cycle 以降。

---

## 全体判定

**OK** (cycle 1 の予測通りの結果、 T091 段階 1 は gate 内部で機能 verified)

cycle 1 で「seed=100 では効果限定的」 と予測した通り、 run-54 は run-53 と完全一致。 ただし `median_oos_sharpe<min` reason の 2 件減少が gate 内部での機能を verify。 cycle 2 で段階 2 (trade_count_full_dataset) を実装し、 真の Layer 1 検証は run-52 archive replay で実施する。

### analysis-codex.md

**観察事実 (Facts)**  
- `run_54` は `run_53` と archive 主要フィールドが完全一致（`n=5,856` で差分 0）。  
- Stage 通過は `A=1,439 / B=0 / C=0 / graduated=0` で不変。  
- `median_oos_sharpe<min` reason は `-2`（1,439→1,437）だが、`positive_fold_ratio<min` は 1,439 のまま。  
- `mission-eligible@StageA (trade>=50 & pnl>=50,000)` は 0 件、`A+trade>=50` の最大 `pnl=27,800`。  
- cross-pair は `skipped_single_instrument` で、ii-lite 妥当性をこの RUN からは検証不能。  
- `seed=100, gens=60` 系列は既報比較でも Stage B=0 が継続。  
- 禁止事項に直結する明示ログ（イントラデイ逸脱、片方向化、スワップ/スプレッド無視）は提示データ内で未観測。  
- primitive 構成比・多様性の直接統計は未提示（この観点は INCONCLUSIVE）。

**解釈・推論 (Interpretations, C6分離)**  
- 仮説H1「T091段階1は gate 内部で機能した」: **条件付きで賛成**。  
  - 根拠: reason のみ `-2`。  
  - 反証条件: 同一個体で reason 集計ロジック差分/重複排除差分が原因で、閾値変更なしでも同結果になる場合。  
- 仮説H2「ボトルネックは median ではなく positive_fold_ratio」: **強く支持**。  
  - 根拠: median 側が一部改善しても B pass 0。  
  - 反証条件: `positive_fold_ratio` を満たす個体群が存在するのに別要因で全落ちしていたと確認される場合。  
- 仮説H3「seed=100 では分布がほぼ不変」: **“低い”とは断定不可（INCONCLUSIVE）**。  
  - 理由: 今回は段階1のみで影響微小だったが、段階2/3は境界個体の選抜順を非線形に変える可能性がある。  
  - 反証条件: 同 seed・同 config で段階2/3適用前後の archive hash が連続 RUN で実質不変。  
- 仮説H4「mission 到達経路が完全閉塞（CRITICAL_DRIFT）」: **全探索では未立証**。  
  - seed=100 領域の閉塞は強いが、seed 23/42 で B pass 実績あり。  
  - 反証条件: seed/gens を広げても一定期間 B/C/mission が恒常的ゼロ。  
- cross-pair shadow 妥当性: **現状は不十分**。mission 要件（ii-lite）に対する証拠が欠落。  
  - 反証条件: cross-pair 有効 RUN で shadow 統計が安定し、単一通貨ペア過適合でないと示せる。

**A. I1-I5 独立判定**  
- I1: 賛成（条件付き）。上記H1の反証試験が必要。  
- I2: 概ね賛成。`seed=100` 低収益構造はデータ整合。  
- I3: 反論寄り（断定は早い）。「変わらない見込み」はまだ弱い。  
- I4: 賛成。Layer1 replay は falsification-first に合致。  
- I5: 賛成。ただし「予測的中」は因果証明ではない。

**B. Layer1 archive replay 優先度**  
- **高優先（段階2実装より先）**。  
- 理由: 低コストで I1 を直接反証可能、次実装の期待値評価に直結。

**C. 段階2/3を本 cycle で進めるか**  
- 段階2: **条件付きで進める**（ただし replay で段階1効果の実在確認後）。  
- 段階3（partition guard）: **進めるがリスク管理必須**。  
  - 二重 opt-in smoke と holdout 14d 事前充足確認を前提にし、RUN起動失敗リスクを先に潰す。

**次サイクル候補**  
- Critical: `run-52` の `g70_i9 / g83_i12` で段階1前後の Stage B 判定を replay し、reason ベクトル差分を個体単位で検証（H1反証）。  
- Warning 1: `seed=100` 固定を一旦外した対照 RUN（例: seed 複数）で「閉塞が局所か全体か」を切り分ける。  
- Warning 2: cross-pair `skipped_single_instrument` を解除した shadow 計測 RUN を最低1本入れ、ii-lite 証拠を確保。  
- Warning 3: live_criteria 本体と stage gate 代理指標の差分監査（緩和が mission 要件を侵食していないか）を明文化。

**全体判定**  
- **CONCERN**。  
- 理由: 予測通りの結果ではあるが、`seed=100` 領域の停滞・B/Cゼロ継続・cross-pair未検証が重なっており、OK には不足。  
- ただし「全探索で完全閉塞」の立証は未了のため、現時点で `CRITICAL_DRIFT` 断定はしない。

### analysis-merged.md

# マージ分析: Run 54 (cycle 2)

**Generated**: 2026-05-09 09:30 JST
**run_id**: `run_20260508_224819`

## 合意事項 (両者一致)

| # | 観察 / 仮説 | Claude | Codex |
|---|---|---|---|
| 1 | run-53 と run-54 で archive 全フィールド完全一致 (n=5,856) | F2 | Facts |
| 2 | T091 段階 1 (median 0.025) は gate 内部で機能 verified (`median_oos_sharpe<min` reason -2 件) | I1 | H1 賛成 |
| 3 | 主ボトルネックは median ではなく positive_fold_ratio | (F4 観察) | H2 強く支持 |
| 4 | seed=100 領域は profitability 構造的に低い (cycle 1 verified を再確認) | I2 | I2 賛成 |
| 5 | Layer 1 archive replay (run-52、 g70_i9 / g83_i12) は段階 2 実装より優先 | (Suggestion) | B 高優先 |
| 6 | mission-eligible 個体は run-52 archive で 7 件存在、 うち pfre>=0.6 で positive_fold_ratio<min reason 不含は 2 件 (g70_i9 / g83_i12) | (検証データ) | (検証データ) |

## Layer 1 archive replay 結果 (本 cycle で実施)

### 検証対象 (run-52 archive)

g70_i9: trade=138, total_pnl=56,930, pfre=0.7, blocked reason="median_oos_sharpe<min" のみ
g83_i12: trade=127, total_pnl=50,820, pfre=0.7, blocked reason="median_oos_sharpe<min" のみ

### 重大な発見

**archive に `median_oos_sharpe` の実値が保存されていない**。
- `trade_sharpe_stage_b` 列は存在するが、 これは Stage B **全期間 1 pass** の trade Sharpe (T044 仕様)、 `median_oos_sharpe` (per-fold median) とは別物
- g70_i9: trade_sharpe_stage_b=-0.040269 (Stage B 全期間 backtest)、 median_oos_sharpe 値は不明
- g83_i12: trade_sharpe_stage_b=-0.035215 (Stage B 全期間 backtest)、 median_oos_sharpe 値は不明

### Layer 1 直接 verify の不可性

archive replay 経路では median_oos_sharpe の実値が取得不可のため、 T091 段階 1 (0.025) で g70_i9 / g83_i12 が pass するかは **直接 verify 不可**。

### 推定

`stage_b_reason_codes` から:
- median_oos_sharpe < 0.05 (現行閾値) — 既知
- positive_fold_ratio >= 0.6 (= pfre 0.7、 別 reason 不含)

→ median_oos_sharpe ∈ [-∞, 0.05) の範囲。 T091 段階 1 (0.025) で:
- 0.025 ≤ median < 0.05: pass (期待効果あり)
- median < 0.025: 不通過 (期待効果なし)

**結論**: 直接 verify 不可、 50/50 確率の推定。

## Claude 独自の発見

| # | 発見 |
|---|---|
| C1 | run-54 と run-53 の summary.best 完全一致 (g52_i27、 trade=61、 fp=0.0375) |
| C2 | archive top fp は g57_i15 (trade=32、 feasible=False)、 selection_score lex で g52_i27 (feasible=True) が best として選ばれる構造 verified |
| C3 | `median_oos_sharpe<min` trigger 数の 2 件減 (1439→1437) は段階 1 が gate 内部で機能している唯一の証拠 |

## Codex 独自の発見

| # | 発見 |
|---|---|
| Z1 | T091 段階 2/3 の seed=100 効果は **INCONCLUSIVE** (Claude 「変わらない見込み」 は弱い、 段階 2 で境界個体の選抜順が非線形に変わる可能性) |
| Z2 | mission 到達経路完全閉塞 (CRITICAL_DRIFT) は seed/gens を広げないと未立証、 seed 23/42 で B pass 実績ある |
| Z3 | cross-pair shadow 妥当性は **INCONCLUSIVE** (single instrument で skipped 継続、 ii-lite 証拠欠落) |

## 矛盾・要議論

| # | 論点 | Claude | Codex | 判断 |
|---|---|---|---|---|
| M1 | T091 段階 2/3 の seed=100 効果見込み | 「変わらない見込み」 | 「INCONCLUSIVE、 断定早い」 | **Codex 採用** (段階 2 で境界個体の selection 変化は実装後に verify) |

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | 期待効果 | 分類 |
|---:|---|---|---|---|---|---|
| 1 | **T091 段階 2 (trade_count_full_dataset) 実装** + **median_oos_sharpe を archive 列に追加** (Layer 1 検証用) | High | TODO + Codex 推奨 | selection 圧整合化 + Layer 1 検証可能化 | 次 RUN-55 で trade_count_full_dataset / median_oos_sharpe 列が non-null、 selection ranking 変化を観察 | Structural |
| 2 | **T091 段階 3 (partition guard) 実装** + 二重 opt-in escape hatch | Medium | TODO | mission 監査性 | holdout 14d 不整合の起動時 fail-closed 検出、 smoke override で次 RUN を smoke として継続可能 | Structural |
| 3 | (Phase 2 候補) seed 多様化 RUN (seed=23/42/100 比較) | Medium | Codex Z2 | mission 到達経路の局所/全体閉塞切り分け | 反証可能性向上 | Structural |
| 4 | (Phase 2 候補) cross-pair shadow 復帰 | Medium | Codex Z3 | ii-lite 証拠 | shadow 統計 archive 記録 | Structural |

### 採用判断

- **今 cycle 採用**:
  - 提案 1: T091 段階 2 + median_oos_sharpe archive 列追加 (Layer 1 検証用)
  - 提案 2: T091 段階 3 (smoke override で次 RUN を smoke として実行可能化)
- **Phase 2 移動**: 提案 3, 4

### 次 RUN 戦略

- T091 段階 2 + 段階 3 完了後、 二重 opt-in (smoke) で run-55 を実行
- run-55 で:
  - Layer 1 検証: archive 新列 `median_oos_sharpe` (per-fold median) で g70_i9 等の値が確認可能 (run-55 archive ではなく、 run-55 で再 RUN したものの archive)
  - 注意: run-55 は seed=100 で再実行、 run-52 (seed=42) の個体は再現されない → 段階 1 効果検証は run-55 では不可
  - 段階 1 効果の真の検証には run-52 を replay する必要があり、 これは別タスク

### 次フェーズ申し送り

- Phase C (詳細設計) で段階 2 詳細設計に **median_oos_sharpe 追加 archive 列** を併設
- 段階 3 詳細設計に二重 opt-in smoke override を含める
- 既設計 (commit 4624c7a + cycle 1 統合) を流用可能、 列追加のみ追加変更

