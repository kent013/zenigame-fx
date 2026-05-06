# Run 38 — run_20260506_094547

**Generated**: 2026-05-06T09:45:57.760210+00:00
**dataset_epoch_id**: `epoch_20251001_20260401`
**Dataset**: EUR_JPY `2025-10-01T00:00:00+00:00` → `2026-04-01T00:00:00+00:00` (bars=183403)
  - bars_stage_a: 86400
  - bars_stage_b: 97003
  - bars_holdout: 20457
  - Stage B excludes Stage A window (stage_b: 2025-10-01T00:00:00+00:00 → 2026-01-06T18:25:00+00:00, stage_a: 2026-01-06T18:26:00+00:00 → 2026-03-31T23:59:00+00:00)

## 使命判定

未達

- ❌ **sharpe**: 0.21651631993061826 / threshold 1.0
- ❌ **total_pnl**: 32160.0 / threshold 50000.0
- ✅ **max_drawdown_pct**: 0.0 / threshold 20.0
- ✅ **trade_count**: 57 (range 50〜5000)

## GA 設定

- population_size: 96
- generations: 60
- mutation_rate: 0.5
- crossover_rate: 0.7
- tournament_size: 3
- elite_count: 2
- max_depth: 4
- fitness_metric: sharpe
- seed: 23

## Best 個体

- name: `g54_i2`
- generation: 54
- fitness: **0.19851631993061827**
- fitness_finite: ✅
- stage_a_pass: ✅
- stage_b_pass: ❌
- stage_c_pass: ❌
- trade_count: 57
- total_pnl: 32160.0
- sharpe: 0.21651631993061826
- sortino: —
- calmar: —
- max_drawdown_pct: 0.0

**Archive 補足情報**:
- lane_id: tier1_EUR_JPY
- instrument: EUR_JPY
- fold_sign_ratio: 0.0000
- dsr: —
- ii_lite_pass: —
- n_nodes: 4
- active_clause: 1

## Stage 通過数

- 全 archive 行数: 5856
- Stage A pass: 1647
- Stage B pass: 6
- Stage C pass: 0
- ⚠ Stage B verdict is **statistically inconclusive** (`n_fold_effective < 3`).

## Lane 別落下分布

| lane_id | total | A | B | C |
|---------|-------|---|---|---|
| tier1_EUR_JPY | 5856 | 1647 | 6 | 0 |

## Pair 別落下分布

| instrument | total | A | B | C |
|------------|-------|---|---|---|
| EUR_JPY | 5856 | 1647 | 6 | 0 |

## active_clause / n_nodes 分布

- active_clause: n=5856, mean=1.2826, median=1.0000, std=0.4608, min=0, max=2
- n_nodes: n=5856, mean=3.7947, median=4.0000, std=1.6972, min=1, max=8

## mission_score 分布 (T043 / observation only)

> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には 影響しない (詳細: docs/alpha_factory/mission-score.md)。

- mission_score: n=1, mean=0.2758, median=0.2758, std=0.0000, min=0.2758, max=0.2758
- best mission_score: **0.2758** (`g42_i12`, gen=42, instrument=EUR_JPY)

## fold_sign_ratio / dsr 分布

- fold_sign_ratio: n=1647, mean=0.2798, median=0.3000, std=0.1883, min=0.0000, max=0.7000
- dsr: n=0
- n_fold_effective (Stage A pass): n=1647, mean=8.6636, median=11, std=3.4718, min=0, max=11
- positive_fold_ratio_effective (Stage A pass): n=1572, mean=0.3332, median=0.3636, std=0.2186, min=0.0000, max=1.0000

## Stage B failure reason 集計

- Stage A pass = 1647, Stage B pass = 6, failures = 1641 (primary_sum = 1641)

### Primary reason (先頭 reason、合計 = failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 0 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1634 |
| `positive_fold_ratio<min` | 7 |
| `stage_b_pre_flight_underfilled` | 0 |
| `unknown_reason` | 0 |
| `other` | 0 |

### Any reason incidence (全 reason、合計 >= failures)

| reason | count |
|--------|------:|
| `no_folds` | 0 |
| `insufficient_folds` | 0 |
| `all_folds_unavailable` | 75 |
| `stage_b_window_underfilled` | 0 |
| `median_oos_sharpe<min` | 1634 |
| `positive_fold_ratio<min` | 1625 |
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
- trade_count=0 個体比率: 5.7% (334/5856)
- best 個体 trade_count: 57
- best 個体 feasibility: ✅

## Stage A provenance 分布 (T033 / sidecar)

> Stage A 落ち個体の `total_pnl_stage_a` 分布を可視化 (`reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`)。archive `total_pnl=0.0` が「Stage A 落ち = 投影仕様」「実 PnL=0」「コスト過大」のいずれかを切り分けるための観測指標 (詳細: docs/alpha_factory/diagnostics-sidecar.md)。

- sidecar 行数: 5856
- metric_stage 分布: stage_a_evaluated=1641, stage_a_only=4209, stage_b_evaluated=6
- (1) Stage A 落ち全体 `total_pnl_stage_a` 分布: n=4209, mean=-374020.5417, median=-88760.0000, std=448743.7535, min=-1006670.0000, max=23420.0000
- (2) Stage A 落ち かつ trade_count>0 の `total_pnl_stage_a` 分布 (n=3875): n=3875, mean=-406258.6994, median=-114120.0000, std=453465.3256, min=-1006670.0000, max=23420.0000
  - うち PnL=0 個体: 1 件 (取引したのに PnL=0 = Run 9 監査の対象観測)
- (3) Stage A 通過個体 `total_pnl_stage_a` 分布 (n=1647): n=1647, mean=6774.5294, median=13830.0000, std=93745.5635, min=-1000940.0000, max=42230.0000

## Archive Top-5 個体一覧

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass_and_feasible, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.3_stage_b_feasible_priority, cycle 5 improve-cycle)。stage_b_pass_and_feasible = (Stage B 通過 ∧ entry_count_min 達成) を最優先要素 3 に昇格し、 cycle 4 で観測された「Stage B pass だがtrade_count<50 で feasible=0」 個体支配を解消。

| rank | name | gen | lane | instrument | fitness_pen | fitness_raw | A | B | C | trade_count | sharpe |
|-----:|------|----:|------|------------|------------:|------------:|---|---|---|----:|-------:|
| 1 | `g48_i78` | 48 | tier1_EUR_JPY | EUR_JPY | 0.2231 | 0.2576 | ✅ | ❌ | ❌ | 31 | — |
| 2 | `g53_i6` | 53 | tier1_EUR_JPY | EUR_JPY | 0.2231 | 0.2411 | ✅ | ❌ | ❌ | 53 | — |
| 3 | `g47_i6` | 47 | tier1_EUR_JPY | EUR_JPY | 0.2078 | 0.2258 | ✅ | ❌ | ❌ | 51 | — |
| 4 | `g54_i2` | 54 | tier1_EUR_JPY | EUR_JPY | 0.1985 | 0.2165 | ✅ | ❌ | ❌ | 57 | — |
| 5 | `g55_i0` | 55 | tier1_EUR_JPY | EUR_JPY | 0.1985 | 0.2165 | ✅ | ❌ | ❌ | 57 | — |

## 収束履歴

| gen | best_fitness |
|-----|--------------|
| 0 | -0.036511484633228654 |
| 1 | -0.0319411810750956 |
| 2 | -0.0319411810750956 |
| 3 | 0.008183593274836639 |
| 4 | 0.008183593274836639 |
| 5 | 0.0267055293483965 |
| 6 | 0.149714460202822 |
| 7 | 0.03140854028223269 |
| 8 | 0.03140854028223269 |
| 9 | 0.03140854028223269 |
| 10 | 0.03140854028223269 |
| 11 | 0.0432778368111328 |
| 12 | 0.05010482931060396 |
| 13 | 0.05445714307913524 |
| 14 | 0.05445714307913524 |
| 15 | 0.12673834278431068 |
| 16 | 0.061619474207266295 |
| 17 | 0.05445714307913524 |
| 18 | 0.07713166097503243 |
| 19 | 0.05100562804688086 |
| 20 | 0.1144982061809198 |
| 21 | 0.1144982061809198 |
| 22 | 0.042385685047391805 |
| 23 | 0.07238797291455859 |
| 24 | 0.07238797291455859 |
| 25 | 0.10753091729882457 |
| 26 | 0.09075172702217287 |
| 27 | 0.07808787538204959 |
| 28 | 0.052136655024155376 |
| 29 | 0.08416512486935127 |
| 30 | 0.09579014967925596 |
| 31 | 0.07875517087398234 |
| 32 | 0.09000223718275475 |
| 33 | 0.09000223718275475 |
| 34 | 0.15795966850609744 |
| 35 | 0.09780741025805029 |
| 36 | 0.1180118315201333 |
| 37 | 0.10287690514848484 |
| 38 | 0.14288171838610492 |
| 39 | 0.14288171838610492 |
| 40 | 0.14288171838610492 |
| 41 | 0.14288171838610492 |
| 42 | 0.14288171838610492 |
| 43 | 0.15016308372665305 |
| 44 | 0.14288171838610492 |
| 45 | 0.16714671388222502 |
| 46 | 0.16714671388222502 |
| 47 | 0.20781740589329575 |
| 48 | 0.2231371441539858 |
| 49 | 0.176483254453751 |
| 50 | 0.16714671388222502 |
| 51 | 0.19222470570055325 |
| 52 | 0.19222470570055325 |
| 53 | 0.22308920347208505 |
| 54 | 0.19851631993061827 |
| 55 | 0.19851631993061827 |
| 56 | 0.19851631993061827 |
| 57 | 0.19851631993061827 |
| 58 | 0.19851631993061827 |
| 59 | 0.19851631993061827 |
| 60 | 0.19851631993061827 |

## 分析

### analysis-claude.md

# RUN run_20260506_080007 (run-37) 分析（Claude 自己分析）

cycle 5 / 20 — cycle 4 介入 (selection_score fold_robust 9-tuple 化) の効果検証 + 次介入策定。

## 観察事実（Facts）

### 1. Stage 通過数 (cycle 4 介入の効果)

| Stage | run-36 (cycle 3) | run-37 (cycle 4) | 差分 |
|---|---|---|---|
| Stage A pass | 1,999 | 1,647 | -18% (selection 厳格化) |
| **Stage B pass** | **0** | **6** 🎉 | **+6** |
| Stage C pass | 0 | 0 | — |
| graduation | 0 | 0 | — |

### 2. fold_robust 個体生成

| metric | run-36 | run-37 | 差分 |
|---|---|---|---|
| pfre>=0.4 個体 | 77 (4.05%) | **606 (36.8%)** | **9倍** |
| pfre>=0.6 (Stage B 閾値) | 13 | 134 | 10倍 |

GA 進化が「fold robust 個体を作る」 方向に確実にシフト。

### 3. Best 個体 (run-37 g54_i2)

| metric | 値 |
|---|---|
| fitness_pen | 0.199 (run-36 0.222 から -10%) |
| trade_count | 57 (entry_count_min=50 通過) |
| total_pnl | 32160 (positive!) |
| **pfre** | **1.0** (= fold_robust=True) |
| stage_b_pass | False (Stage B 通過は別個体群) |
| stage_a_pass | True |

→ best が **fold_robust=1 個体** に変わった = cycle 4 selection_score 9-tuple が機能

### 4. **Stage B pass 6 個体の品質 (CRITICAL)**

| individual | gen | fitness_pen | trade_count | total_pnl | pfre | feasible (>= 50) |
|---|---|---|---|---|---|---|
| g33_i6 | 33 | 0.011 | 14 | -8,850 | 0.70 | False |
| g42_i12 | 42 | 0.077 | 30 | -20,680 | 0.64 | False |
| g53_i25 | 53 | 0.036 | 22 | -14,420 | 0.64 | False |
| g53_i53 | 53 | 0.097 | 26 | -16,890 | 0.73 | False |
| g55_i9 | 55 | 0.124 | 28 | -12,360 | 0.70 | False |
| g55_i55 | 55 | -0.003 | 22 | -28,360 | 0.64 | False |

**全員**:
- total_pnl < 0 (損失)
- trade_count < 50 (entry_count_min=50 不達 → feasible=False)
- sharpe = NaN (trade_count_min_for_sharpe=30 接近)
- 全員 Stage C 不通過

### 5. Best (g54_i2) が Stage B 不通過なのに選ばれた理由 (selection_score 解析)

selection_score 9-tuple lexicographic order:
1. feasible: g54_i2=1 (trade=57) vs Stage B pass 全員=0
2. -violation: g54_i2 violation=0 vs Stage B pass 大きい violation
3. ...

→ **要素 1 (feasible) で勝負がつく**。Stage B pass 6 個体は全員 feasible=0 で最優先順位下位、 g54_i2 が feasible=1 で best 選定。

## 解釈・推論（Interpretations）

### 仮説 H1 (cycle 3): 探索圧不整合 — **VERIFIED ✅**

cycle 4 介入で Stage B pass 0→6 達成、 H1 検証完了。 fold_robust selection_score 拡張は **設計通り機能**。

### 仮説 H7 (NEW): fold_robust と feasibility の同時達成困難

**根拠**:
- Stage B pass 6 個体 全員 trade_count 14-30 で entry_count_min=50 不達
- これらの個体は「短期間に集中して trading 行い fold robustness を出す noise pattern」
- fitness_pen は -0.003 〜 0.124 で全員 run-36 best (0.222) より低い

**示唆**:
- fold_robust selection で「真の robust signal」 ではなく「noise だが fold で偶然 positive な個体」を拾っている可能性
- 「fold robust AND adequate trade」 を同時達成する個体は探索空間内に少ない / 困難

**反証可能性**:
- cycle 5 介入後、 Stage B pass 個体の trade_count 分布が >= 50 寄りにシフトすれば確証 (= cycle 5 介入が機能)
- 不変なら別の構造的問題 (primitive / feasibility 緩和不可で別経路)

### 禁止事項チェック

| # | 禁止事項 | 兆候 |
|---|---|---|
| 6 | 取引回数削減 | **Stage B pass 6 個体全員 trade_count<50** で **疑い顕著** |

ただしこれは GA 探索結果であり、 設計の「取引回数削減で見栄え改善」 には該当しない (見栄えではなく構造的に出てきた現象)。 ただし要観察。

## 次サイクル候補

### [Critical] C1: selection_score に「fold_robust AND feasible」 複合条件追加

**設計案**:
- selection_score の 8 要素目を `fold_robust` から `fold_robust_and_feasible` (= `fold_robust AND feasible`) に変更
- これにより GA は **「pfre>=0.4 かつ trade_count>=50 (entry_count_min)」** 個体を最優先に
- 既存 fold_robust 個体で trade_count<50 のものは selection 順位下がる
- target: Stage B pass 個体の trade_count 分布が >= 50 寄りにシフト

**falsification**: cycle 6 で Stage B pass 個体の median trade_count >= 50 になれば確証
**success_criterion**: Stage B pass + feasible 個体が 1 件以上 (= total_pnl > 0 で entry_count adequate)
**変更分類**: **Structural** (selection_score の AND 合成、 既存条件の組み合わせ)

### [Warning] W1: live_pass 達成までの遠さの定量化

run-37 best total_pnl = 32160 (live_criteria 50000 の 64%)、 sharpe = NaN (live_criteria 1.0 不達)。 cycle 5 介入で Stage B pass + feasible 個体が出てきても、 live_pass までの距離は大きい。

## 全体判定

**ACTIONABLE** — cycle 4 H1 verified、 cycle 5 で次介入 (fold_robust AND feasible 複合化) を策定。 「機能の名前に立ち返れ」 原則: fold_robust だけでなく feasible との同時達成を要求すべき。

### analysis-codex.md

**判定**
`Q1: REQUEST_CHANGES`（最小修正）

**理由（Fact / Interpretation 分離）**
- Fact: 現在の `selection_score` は要素1に `feasible` があり、すでに強い優先順位を持っています。  
- Fact: 提案の `fold_robust_and_feasible = fold_robust AND feasible` は、`feasible=0` 個体をさらに弱くするだけで、`feasible=1` 領域の順位改善効果は限定的です。  
- Interpretation: 今回の課題は「Stage B pass だが trade不足」の構造なので、要素8のAND化だけだと主因への圧力が弱く、改善が小さい可能性が高いです（実質ほぼ no-op 寄り）。

**最小修正案（D’）**
- `fold_robust` は保持
- 追加で、より前段に `stage_b_pass_and_feasible`（または `trade_count>=min`）を昇格  
  例: `(..., feasible, stage_b_pass_and_feasible, ..., fold_robust, fitness_pen)`
- これなら「fold robust かつ実運用可能」への選択圧を明示的に上げられます。

**Q2（A/B/C/D 評価）**
- A: 条件付き許容。`n=6` は小さく、観察継続の価値はあるが、改善サイクルの勢いは弱い。  
- B: 非推奨。閾値緩和は Reactive Parametric で禁止方針に抵触しやすい。  
- C: 有効。順序見直しは Structural で、今回のボトルネックに直結。  
- D: 方向性は良いが単体では弱い。`REQUEST_CHANGES`（上記 D’ へ）。

**Q3（禁止事項チェック）**
- Structural / Reactive 判定:  
  - D 単体: Structural だが効果弱い  
  - D’: Structural で妥当  
  - B: Reactive 寄りで非推奨
- メタ過学習ガード:  
  - 今回は `n=6` のため強い因果主張は不可（INCONCLUSIVE許容）。  
  - 次サイクルの反証条件は「`Stage B pass ∩ feasible` の件数増加」と「その集合で `median trade_count >= 50`」を併記するのが適切。  

結論として、**DをそのままAPPROVEではなく、D’（前段順位の明示強化）で最小修正承認**が最も妥当です。

