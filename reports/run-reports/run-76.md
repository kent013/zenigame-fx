# Run 76 — run_20260513_235721

**Generated**: 2026-05-13T23:57:22.450025+00:00
**dataset_epoch_id**: `epoch_20250401_20260219`
**Dataset**: EUR_JPY `2025-04-01T00:00:00+00:00` → `2026-02-19T00:00:00+00:00` (bars=328883)
  - bars_stage_a: 86400
  - bars_stage_b: 242483
  - bars_holdout: 60232
  - Stage B excludes Stage A window (stage_b: 2025-04-01T00:00:00+00:00 → 2025-11-24T15:52:00+00:00, stage_a: 2025-11-24T15:53:00+00:00 → 2026-02-18T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: -5.079368902148316 / threshold 1.0
- ❌ **total_pnl**: -38590.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 4.7463987530899745 / threshold 20.0
- ❌ **trade_count**: 33 (range 50〜5000)

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
- seed: 61

## Best 個体

- name: `g59_i94`
- generation: 59
- fitness: **0.12909092890559468**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ✅
- stage_c_pass: ❌
- trade_count: 33
- total_pnl: -38590.0
- sharpe: 0.1415909289055947
- sortino: —
- calmar: —
- max_drawdown_pct: 4.7463987530899745

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.1212
- dsr: —
- ii_lite_pass: —
- n_nodes: 2
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 672
- Stage B pass: 220
- Stage C pass: 0

## trade_count 境界張り付き分析 (cycle 23 C4)

- Stage C 通過群が 0 件、分析対象なし

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 672 | 220 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 672 | 220 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.3866, median=1.0000, std=0.5035, min=0, max=2
- n_nodes: n=5856, mean=2.6465, median=2.0000, std=1.5142, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=220, mean=0.4165, median=0.2974, std=0.1609, min=0.2696, max=0.6636
- best mission_score: **0.6636** (`g55_i10`, gen=55, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=672, mean=0.1090, median=0.1515, std=0.0797, min=0.0000, max=0.3030
- dsr: n=0
- n_fold_effective (Stage A pass): n=672, mean=20.3333, median=21.0000, std=10.7050, min=1, max=34
- positive_fold_ratio_effective (Stage A pass): n=672, mean=0.5778, median=0.5294, std=0.2758, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 672, Stage B pass = 220, failures = 452 (primary_sum = 452)

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
| `positive_fold_ratio_effective<min` | 95 |
| `median_oos_total_pnl<min` | 86 |
| `sum_oos_total_pnl<min` | 47 |
| `n_fold_effective_below_profit_safe_min` | 224 |
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
| `positive_fold_ratio_effective<min` | 95 |
| `median_oos_total_pnl<min` | 181 |
| `sum_oos_total_pnl<min` | 215 |
| `n_fold_effective_below_profit_safe_min` | 297 |
| `oos_total_pnl_unavailable` | 0 |
| `other` | 11 |

## Cross-pair shadow 集計

- runtime mode: skipped_single_instrument
- ii_lite_pass: True=0, False=0, None=5856

## Graduation

- archive graduated: 0
- summary.graduation_count: 0

## Feasibility 集計

- selection_score schema: `v3_3_stage_b_feasible_priority`
- trade_count=0 個体比率: 3.2% (187/5856)
- best 個体 trade_count: 33
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=452, stage_a_only=5184, stage_b_evaluated=220
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=5184, mean=-724071.6628, median=-1000110.0000, std=424417.0953, min=-1003090.0000, max=14190.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=4997): n=4997, mean=-751168.2009, median=-1000120.0000, std=408064.5962, min=-1003090.0000, max=14190.0000
  - うち PnL=0 個体: 0 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=672): n=672, mean=-78424.8512, median=4130.0000, std=280646.6595, min=-1000440.0000, max=31560.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g36_i36` | 36 | tier1_EUR_JPY | EUR_JPY | 0.3337 | 0.3667 | ✅ | ❌ | ❌ | 32 | — |
| 2 | `g37_i1` | 37 | tier1_EUR_JPY | EUR_JPY | 0.3337 | 0.3667 | ✅ | ❌ | ❌ | 32 | — |
| 3 | `g35_i38` | 35 | tier1_EUR_JPY | EUR_JPY | 0.3185 | 0.3535 | ✅ | ❌ | ❌ | 30 | — |
| 4 | `g36_i1` | 36 | tier1_EUR_JPY | EUR_JPY | 0.3185 | 0.3535 | ✅ | ❌ | ❌ | 30 | — |
| 5 | `g32_i73` | 32 | tier1_EUR_JPY | EUR_JPY | 0.1364 | 0.1559 | ✅ | ❌ | ❌ | 68 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.03741052870489712 |
| 1 | -0.026181668391569306 |
| 2 | -0.025843950569319395 |
| 3 | -0.024663668632529365 |
| 4 | -0.024663668632529365 |
| 5 | -0.024663668632529365 |
| 6 | -0.024663668632529365 |
| 7 | -0.02319672304721488 |
| 8 | -0.023187890954564527 |
| 9 | -0.023187890954564527 |
| 10 | -0.023187890954564527 |
| 11 | -0.023187890954564527 |
| 12 | -0.023187890954564527 |
| 13 | -0.023187890954564527 |
| 14 | -0.023187890954564527 |
| 15 | -0.006188862503919607 |
| 16 | -0.006188862503919607 |
| 17 | -0.006188862503919607 |
| 18 | -0.006188862503919607 |
| 19 | -0.006188862503919607 |
| 20 | -0.006188862503919607 |
| 21 | -0.006188862503919607 |
| 22 | -0.006188862503919607 |
| 23 | -0.006188862503919607 |
| 24 | -0.006188862503919607 |
| 25 | -0.006188862503919607 |
| 26 | -0.006188862503919607 |
| 27 | -0.006188862503919607 |
| 28 | -0.006188862503919607 |
| 29 | 0.0033876884677901432 |
| 30 | 0.0033876884677901432 |
| 31 | 0.0033876884677901432 |
| 32 | 0.13643610360308386 |
| 33 | 0.13643610360308386 |
| 34 | 0.13643610360308386 |
| 35 | 0.3184713382916929 |
| 36 | 0.3337268401338254 |
| 37 | 0.3337268401338254 |
| 38 | 0.01538238862103568 |
| 39 | 0.01538238862103568 |
| 40 | 0.04253947812793852 |
| 41 | 0.06653947812793852 |
| 42 | 0.04253947812793852 |
| 43 | 0.05275499262986065 |
| 44 | 0.03938238862103568 |
| 45 | 0.052228870877543555 |
| 46 | 0.056728870877543545 |
| 47 | 0.056728870877543545 |
| 48 | 0.06348877881350244 |
| 49 | 0.056728870877543545 |
| 50 | 0.07172887087754355 |
| 51 | 0.12210600770255181 |
| 52 | 0.05170505099037514 |
| 53 | 0.0659423519021689 |
| 54 | 0.04790423075554702 |
| 55 | 0.06831039261756759 |
| 56 | 0.07034654518183232 |
| 57 | 0.07634654518183231 |
| 58 | 0.067153831781092 |
| 59 | 0.12909092890559468 |
| 60 | 0.12909092890559468 |

## 分析

### analysis-claude.md

# RUN run_20260513_120619 (Run 75) 分析（Claude 自己分析）

## 前提差分

なし。archive Parquet / summary.json / scripts/codex / docs 全て揃っている。

注: dsr_audit.json は Run 75 で生成されていない (= Run 74 までは生成、 Run 75 は audit script 実行されず or 新規 reason codes 対応中)。

---

## 観察事実（Facts）

### 1. RUN メタ
- run_id: `run_20260513_120619` / run_number: 75 / instrument: EUR_JPY
- dataset: 2025-04-01 〜 2026-02-19、bars 328,883 (A:86,400 / B:242,483 / holdout:60,232)
- ga_config: pop=96, gen=60, seed=**60**, max_workers=2, mutation_rate=0.5
- **stage_b_gate_kind: profit_safe_pfr** (T099 cycle 22 で導入、 Run 75 初実行)
- profit_safe_pfr_threshold=0.4, profit_safe_pfr_min_n_fold=20
- 完走 202 分 (3h22m)

### 2. Stage 通過数 (archive 5,856 行)

| Stage | Run 74 (legacy) | **Run 75 (profit_safe_pfr)** | 変化 |
|-------|----------------|------------------------------|------|
| Stage A pass | 1,723 | 1,291 | **-25%** |
| Stage B pass | 96 | **827** | **+760%** |
| Stage C pass | **0** | **217** | **0 → 217 (18 RUN 累積初突破)** |
| graduated | 0 | 0 | 不変 |

### 3. Best 個体 (g60_i46)

- name: `g60_i46` @ gen 60 / parent: g59_i52 × g59_i83
- fitness_pen: 0.177 / fitness_raw: 0.190
- stage_a/b/c: **True/True/True**
- trade_count: **51** / total_pnl: **+51,540** / max_dd: **3.74%** / sharpe (trade-level): 0.190
- trade_sharpe_stage_b: 0.104 / trade_sharpe_stage_c: 0.184
- median_oos_total_pnl: 9,270 / sum_oos_total_pnl: 329,940 / pfr_eff: 0.735 / n_fold_eff: 34
- n_nodes: 3 / active_clause: 1 / stage_b_gate_kind: profit_safe_pfr

### 4. live_criteria 結果 (best = g60_i46)

| metric | value | threshold | pass |
|--------|-------|-----------|------|
| sharpe | 0.190 | ≥ 1.0 | ❌ |
| total_pnl | +51,540 | ≥ 50,000 | ✅ |
| max_drawdown_pct | 3.74% | ≤ 20% | ✅ |
| trade_count | 51 | [50, 5000] | ✅ |

→ **3/4 pass**、 sharpe のみ未達。 cycle 22 history (Run 74 1/4 pass) から **+200% 改善**。

### 5. Stage B 通過群 (n=827) の構造変化

| 指標 | Run 74 (legacy) | **Run 75 (profit_safe_pfr)** |
|------|----------------|------------------------------|
| n | 96 | 827 |
| total_pnl (min/max/mean/median) | -16670/-6940/-8813/-7950 | **-86590/+91950/+27675/+38520** |
| trade_sharpe_stage_b (mean) | -0.033 | +0.055 |
| median_oos_total_pnl (mean) | (新規) | 7,761 |
| sum_oos_total_pnl (mean) | (新規) | 226,466 |
| positive_fold_ratio_eff (mean) | 0.62 | 0.66 |
| n_fold_eff (mean) | 34.0 | 33.99 |
| active_clause (mean) | **1.01** | **1.47** |
| unique fp (%) | 6.2% | **60.0%** |

**重要観察**:
- Stage B 通過群の median total_pnl が **-7,950 → +38,520** (**+46,470 改善**)
- active_clause mean 1.01 → 1.47 (multi-clause 復活)
- unique fp diversity 6.2% → 60% (**10 倍改善**)
- profit_safe_pfr 条件 4 つすべて satisfied (= 設計通り)

### 6. Stage C 通過群 (n=217、 累積初突破!) の構造

| 指標 | min | max | mean | median |
|------|-----|-----|------|--------|
| trade_count | 51 | 62 | 51.3 | 51 |
| total_pnl | **50,340** | 91,950 | 55,453 | 53,580 |
| trade_sharpe_stage_c | (negative も含む) | (max) | 0.197 | 0.189 |
| max_drawdown_pct | 1.98 | 4.17 | 3.60 | — |
| n_nodes | 1 | 8 | 4.18 | — |
| active_clause | 1 | 2 | 1.41 | — |
| unique fp | 77 / 217 = **35.5% diversity** | | | |

**Stage C 通過 217 個体全員**:
- trade_count >= 50 ✅
- total_pnl >= 50,000 ✅ (min=50,340 ですら満たす)
- max_dd <= 20% ✅
- sharpe (trade-level) は分布広い、 mean 0.197

→ Stage C 通過 = live_criteria 4 中 3 自動達成 (sharpe のみ未達)。

### 7. live_criteria.sharpe の単位問題 (Critical)

**観察**: summary.json で best.metrics.sharpe = "0.1904..." だが、 これは **trade-level sharpe** (= `trade_sharpe_raw` v2)。
live_criteria.sharpe_min = 1.0 は **annualized** であるべきだが、 比較値が trade-level → **単位不整合**。

T042 Phase 0 換算 (docs/alpha_factory/sharpe-rescale.md):
```
S_annual ≈ S_trade × sqrt(λ_day × 252)
λ_day = trade_count / window
```

best の場合: λ_day = 51 / 60 = 0.85 → S_annual ≈ 0.184 × sqrt(0.85 × 252) ≈ **0.184 × 14.6 ≈ 2.69**

実際、Run 75 log には `legacy_sharpe=2.6922303421755363` と annualized 値が出力されている (canonical_five 経由)。

→ live_criteria.sharpe 比較が **trade-level vs annualized 1.0** で行われていれば、 trade_sharpe 1.0 は annualized 14.6 相当 (= 現実的に達成不能)。 これは **構造的 bug or 設計意図的に厳しい閾値** の可能性。

### 8. 18 RUN + Run 75 累積 (Run 57-75)

- best Stage B pass: **13/19** (68%)
- best Stage C pass: **1/19** (Run 75 のみ)
- mission 達成 (live_criteria all_pass): **0/19** (Run 75 は 3/4 pass)
- DSR proxy pass: 0/19 (= 過去 audit、 Run 75 は audit 未実施)

---

## 解釈・推論（Interpretations）

C6 Fact/Interpretation 分離: ここから推論。

### I1. T099 profit_safe_pfr 仮説の **完全支持** [大成果]

**観察**: Run 75 で Stage C pass = 217 (累積初)、 Stage B 通過群 median pnl 大幅黒字化、 multi-clause 復活、 多様性 10 倍改善。

**解釈**: cycle 22 で立てた仮説「Stage B 閾値が curve-fit + 赤字許容構造」が完全に支持された。 profit_safe_pfr の 4 条件 (pfr_eff + median_pnl + sum_pnl + n_fold) で:
- median_oos_sharpe gate 除去 → curve-fit 個体排除
- median_oos_total_pnl + sum_oos_total_pnl 追加 → 赤字許容を構造的に解消
- 結果: Stage C 通過が dramatic に増加

**反証**: 18 RUN 累積で Stage C pass=0 だったのが Run 75 で 217 → 反証可能性は閉じている (= 支持確定)。

### I2. **sharpe 単位不整合 [Critical]** — live_criteria.sharpe_min 1.0 の解釈

**観察**: summary.json では trade-level sharpe (0.19) と live_criteria.sharpe_min 1.0 が比較されている。 annualized 換算なら 2.69 で達成済。

**仮説**: live_criteria.sharpe 比較が trade-level で行われている (= bug or 意図的厳しい設計)。 別経路 (canonical_five log の `legacy_sharpe=2.69`) では annualized 値が出ているが、 live_criteria 比較に使われていない。

**反証**: 
- 仮説 A (bug): live_criteria.sharpe を annualized 比較に変更すれば best g60_i46 で 1.0 を満たす → **mission 達成個体になる**
- 仮説 B (意図的): trade-level 1.0 を要求 = 達成不能 (= 「mission は最初から達成不能設計」)

確認方法: `live_criteria` 比較の実装 (src/alpha_factory/) で sharpe を trade-level / annualized どちらで比較しているかを grep。

### I3. multi-clause 復活と多様性 [副次効果]

**観察**: active_clause mean 1.01 → 1.47 (Stage B 通過群)、 unique fp 6% → 60%。

**仮説**: profit_safe_pfr で gate が `positive_fold_ratio_effective` 中心になることで、 multi-clause 個体が evaluation で生き残りやすくなった (clause 数増加でも pfr_eff は劣化しない設計のため)。 結果として多様性も回復。

**反証**: 仮説否定なら active_clause / unique fp が legacy と同じになるはず → 大幅改善で支持。

### I4. **graduation_count=0 維持** [Warning]

**観察**: Stage C pass=217 でも graduation_count=0。 これは selection_score の selection が最終的に「graduation 候補」を選出しなかった (= selection_score の v3_3 schema で全条件 satisfy だが graduation 判定が別途厳しい?)。

**仮説**: graduation 判定が live_criteria.all_pass を要求する設計 (sharpe 1.0 達成必須) なので、 Stage C pass 217 でも graduation には届かない。 これは I2 (sharpe 単位不整合) と connected。

---

## 次サイクル候補

### [Critical] C23-1: live_criteria.sharpe 単位整合性確認 + 修正

**仮説**: sharpe 比較が trade-level vs annualized 1.0 で行われている → bug。 修正で best g60_i46 が live_criteria all_pass する可能性。

**具体策**:
- Phase 2 で `live_criteria` 比較経路を grep して、 trade-level / annualized どちらで比較しているかを **verify**
- bug なら annualized 比較に修正 (= T042 換算を live_criteria 比較に適用)
- 意図的なら docs に明記、 別の sharpe 向上施策を検討

**反証実験**: Run 76 で同設定 (profit_safe_pfr seed=61) を実行し、 修正後の live_criteria.all_pass を確認。

### [Warning] C23-2: profit_safe_pfr 再現性 (seed=61 sweep)

**観察**: Run 75 (seed=60) のみで結論を出すと variance risk。 Codex Round 2 推薦の保守案 (cycle 23-24 で legacy / profit_safe_pfr 各 1 RUN 比較) を踏襲。

**具体策**:
- cycle 23 Run 76 (seed=61): profit_safe_pfr 継続実行で再現性確認
- (legacy 再現は cycle 24 以降に回す or 完全省略)

### [Warning] C23-3: graduation 判定の見直し

**観察**: graduation_count=0 維持。

**仮説**: graduation 判定が live_criteria.all_pass を要求。 sharpe 単位修正後に graduation 出現するか確認。

---

## 全体判定

**MAJOR_BREAKTHROUGH** — Run 75 で T099 profit_safe_pfr が dramatic success。 残課題は live_criteria.sharpe の単位整合性確認のみ。 これが解決すれば **mission 達成個体 (live_criteria all_pass)** が cycle 23 Run 76 で出現する可能性が高い。

---

## 未接続 hook

- `zenigame-fx-post-run-review`: improve-cycle Phase 1 末尾 launcher。 30 RUN ループのリソース管理上 skip (前 cycle と同方針)。
- `zenigame-fx-analyze-genome-archive`: 未移植。

### analysis-codex.md

**Facts**
- Run 75 実データ確認: `A/B/C/graduated = 1291/827/217/0`（archive 5,856 行）。
- `profit_safe_pfr` 効果は再現: Run 74 比で Stage B 通過が `96 → 827`、Stage C 通過が `0 → 217`。
- Stage C 通過 217 の Sharpe は trade-level だと低い一方、年率換算では全件 `>=1.0`。
  - 実測: 年率換算 Sharpe `min=2.596, median=2.764, mean=2.883, max=5.023`（trade_count/60日で換算）。
- `summary.json` の live_criteria 判定は trade-level の `trade_sharpe_raw` をそのまま `>=1.0` 比較している。  
  参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:916), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:924), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:935), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:950)
- 一方で Stage C 本体は「trade-level → annualized に換算してから」live_criteria.sharpe 判定している。  
  参照: [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1670), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1902), [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1911), [stage-gates.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md:26)
- best `g60_i46` はログ上 `legacy_sharpe=2.7286`（C_base）で、`summary` の `sharpe=0.1904` と単位不一致。  
  参照: [.cache run log](/Users/ishitoya/repository/zenigame-fx/.cache/alpha_factory/runs/run_20260513_120619.log), [summary.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-75/summary.json:1320)
- `graduation_count=0` は構造要因:
  - 卒業条件は `Stage C pass AND cross_pair pass`。cross_pair が `None/skipped` なら必ず不合格。  
    参照: [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:408), [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:410), [swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py:977)
  - Run 75 は `pair_bars={}` で `cross_pair_runtime_mode=skipped_single_instrument`。  
    参照: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1674), [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1681), [run-75.md](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-75.md:138)
- Stage C 通過群は trade_count が下限近傍に集中（`51件が173/217`）。境界張り付きが強い。
- 禁止事項観点:
  - イントラデイ逸脱: Stage C pass については `intraday_constraint_violation` があれば落ちる設計なので、通過217は少なくとも C 判定上は逸脱なし。
  - ショート偏重: archive に long/short 集計列が無く、**INCONCLUSIVE**。
  - スワップ・スプレッド純利益: stress 判定は通過条件に含まれるが、swap 内訳の十分性は本データだけでは **INCONCLUSIVE**。

**Interpretations**
- Q1（A/B仮説）: **A（bug/不整合）支持**。  
  理由は「Stage C 本体は annualized 判定で217通過」「report/live_criteria だけ trade-level 判定で失敗表示」という二重基準が同時に存在するため。B（意図的にtrade-level 1.0要求）なら Stage C pass=217 と両立しない。
- Q2（graduation=0）: **selection_score 問題ではなく graduation 条件の構造**。cross_pair が skip の運用では卒業が原理的に0。
- Q3（再現性）: n=1 seed（60）のみなので因果主張は不可。`profit_safe_pfr` の効果は大きいが、variance 未測定。

**次サイクル候補**
1. **Critical**: `summary/live_criteria` の sharpe 単位を Stage C と同じ annualized に統一（もしくは trade-level と annualized を明示して別キーで併記し、`all_pass` は annualized SSOT へ）。  
   影響先: `analyze_run.py` など `summary.live_criteria.all_pass` 依存処理。
2. **Warning**: `graduation_count` KPI の解釈を修正。single-instrument で cross_pair skip の間は「卒業0は仕様通り」。KPI を `stage_c_pass_count` と分離して監視。
3. **Warning**: seed sweep で再現性評価（例: seed 61-70 の10本）。最小限メトリクス: Stage B/C pass数、best annualized Sharpe、C通過率、trade_count下限張り付き率。
4. **Warning**: 禁止事項の deceit 検知を可能にするため、archive か sidecar に `long/short件数`、`overnight_violations`、`swap_cost`、`spread_cost` の集計列を追加（現状は判定不能項目が残る）。

**全体判定**
- **CONCERN**  
  `profit_safe_pfr` 自体は有望（Stage B/C は明確改善）だが、`live_criteria.sharpe` 表示系の単位不整合と、cross_pair skip 下で卒業が不可能なKPI設計が意思決定を歪めるリスクが高いです。

### analysis-merged.md

# マージ分析: Run 75 → Run 76 (cycle 23)

## 合意事項 (Claude + Codex 一致)

1. **profit_safe_pfr 効果 完全支持 [MAJOR_BREAKTHROUGH]**:
   - Stage B pass 96 → 827 (+760%), Stage C pass 0 → 217 (累積初突破)
   - Stage B 通過群の median total_pnl -7,950 → +38,520 (黒字化)
   - active_clause 1.01 → 1.47 (multi-clause 復活), unique fp 6% → 60% (10 倍改善)
   - cycle 22 で立てた仮説 (Stage B が curve-fit + 赤字許容) は完全に支持

2. **🚨 Critical bug: live_criteria.sharpe 単位不整合**:
   - `scripts/alpha_factory/run_ga.py:934-952` `_check_live_criteria` で trade-level `trade_sharpe_raw` を annualized `sharpe_min=1.0` と直接比較 → 常に False
   - 一方 `evaluate_stage_c` (stage_gate.py:1902) では `_annualize_trade_sharpe` で annualized 換算後に判定 → 217 個体が pass
   - 結果: Stage C pass=217 だが summary.json live_criteria.all_pass=False という矛盾
   - Codex 実測: Stage C 通過 217 個体の annualized sharpe **min=2.596, median=2.764, mean=2.883, max=5.023** → **全件 ≥ 1.0**

3. **graduation_count=0 の構造要因 (新発見)**:
   - 卒業条件 = `Stage C pass AND cross_pair pass`
   - Run 75 は `pair_bars={}` (single-instrument) で `cross_pair_runtime_mode=skipped_single_instrument`
   - → single-instrument 運用では卒業が **原理的に 0**
   - graduation_count KPI 解釈の修正が必要 (= stage_c_pass_count を別 KPI として監視)

4. **trade_count 下限張り付き**: Stage C 通過 217 個体中 **173 個体が trade_count=51** (= 79.7%)。境界張り付きが強い → 「取引回数最適化への寄り」の懸念は残る

## Claude 独自の発見

- best 個体 (g60_i46) の特徴: trade_sharpe_stage_c=0.184、 annualized 換算で ~2.69 → live_criteria.sharpe.value=0.190 (summary 出力) は **trade-level 値が誤って annualized 1.0 と比較されている**
- multi-clause 復活 (1.01→1.47) は profit_safe_pfr の副次効果 (gate が positive_fold_ratio 中心になり、 clause 数増加でも pfr 劣化しない)

## Codex 独自の発見

- **ショート偏重 / overnight / swap / spread 集計** が archive 列にないため、 イントラデイ逸脱・ショート偏重・コスト未反映の deceit 検知が INCONCLUSIVE
- Stage C 通過 217 個体の annualized sharpe を実測 (min=2.596, median=2.764, mean=2.883, max=5.023) — **全件 live_criteria.sharpe_min=1.0 を超過**
- graduation 条件の structural 分析 (`swim_lane.py:408,410,977` 参照、 cross_pair skip で卒業不可能)

## 矛盾・要議論

なし。 両者は完全に同方向。

## 統合改善提案 (優先度順)

| # | 提案 | 優先度 | 出所 | target_metric | failure_mode | 期待効果 |
|---|------|--------|------|--------------|-------------|---------|
| **1** | **🚨 `_check_live_criteria` を annualized 換算に統一** (Stage C 内部判定と一致) | **Critical** | Claude + Codex (両者一致) | live_criteria.sharpe.pass / mission達成個体数 | trade-level vs annualized 単位不整合で sharpe pass=False に固定 | Run 75 best g60_i46 が mission 達成 (= 217 個体相当)、 過去 19 RUN 累積でも再評価で多数の mission 達成個体が発見される可能性 |
| 2 | graduation KPI 解釈修正 / stage_c_pass_count 分離 | Warning | Codex | KPI の意思決定影響 | 卒業条件に cross_pair pass を含むため single-instrument で原理的に 0 → KPI 誤読 | KPI ダッシュボード正常化、 mission 達成定義の再認識 |
| 3 | seed sweep で profit_safe_pfr 再現性確認 | Warning | Codex | Stage B/C pass 数 variance / best annualized Sharpe | seed=60 のみで variance 未測定 | Run 75 の 217 通過が lucky draw でないことを確認 |
| 4 | 禁止事項 deceit 検知列追加 (long/short / overnight / swap / spread) | Warning | Codex | INCONCLUSIVE 解消 | archive に列がなく検知不能 | イントラデイ逸脱・ショート偏重・コスト未反映の構造的検出 |
| 5 | trade_count 境界張り付き (173/217=51 trade) の構造分析 | Suggestion | Claude (新) | 取引回数最適化偏り | live_criteria.trade_count_min=50 を狙い撃ちで稼ぐ個体が支配 | 真の利益最大化が起きていない構造 |

## 次フェーズへの申し送り

- **cycle 23 で施策 #1 (Critical bug fix) のみ実装** → Run 76 (seed=61 profit_safe_pfr) で reproduce + mission 達成個体数測定
- #2 (KPI 修正) は docs 更新のみで実装容易、 #1 と併せて 1 commit
- #3-#5 は次サイクル以降の TODO 候補

### Codex 合議で確認したい点

- **施策 #1 の最小実装**: `_check_live_criteria` 内で `_annualize_trade_sharpe` を呼ぶ minimal change (~20 行) で十分か? それとも archive 列に `trade_sharpe_annualized` を新規追加してから比較する大きな変更が必要か?
- **mission 達成の定義変更影響**: live_criteria fix で過去 19 RUN の archive を再評価したとき、 mission 達成個体が大量に発見されるシナリオ → これは GA selection 経路 / archive 集計経路への波及はあるか?

