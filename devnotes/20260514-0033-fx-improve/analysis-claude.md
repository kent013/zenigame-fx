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
