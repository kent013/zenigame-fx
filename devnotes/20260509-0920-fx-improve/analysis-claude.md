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
