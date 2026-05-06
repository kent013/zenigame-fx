# Run 37 — run_20260506_080007

**Generated**: 2026-05-06T08:01:45.834606+00:00
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

- selection_score schema: `v3_2_fold_robust`
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

> Best とは別物です。`fitness_pen` 単独降順。Best は (feasible, -violation, stage_b_pass, stage_c_feasible, stage_c_pass, stage_b_pass, stage_a_pass, fold_robust, fitness_pen) の辞書式 (v3.2_fold_robust, cycle 4 improve-cycle)。fold_robust = (positive_fold_ratio_effective >= fold_robust_threshold) で、GA selection 圧を Stage B 閾値到達可能な fold robust 個体に向ける。

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

# RUN run_20260506_054244 (run-36) 分析（Claude 自己分析）

cycle 4 / 20 — improve-cycle 自走ループ。 cycle 3 で導入した stage_a_top_fold_robustness sidecar データを用いて、 Codex 仮説 H1 (探索圧不整合) を verified/falsified 判定する。

## 前提差分

なし。

- archive Parquet: `.cache/alpha_factory/runs/genomes_run_20260506_054244.parquet` (5856 rows)
- summary.json: `reports/run-reports/run-36/summary.json`
- **cycle 3 sidecar**: `reports/run-reports/run-36/diagnostics/stage_a_top_fold_robustness.parquet` (58 rows、 18 列)
- 前 Run (run-35) との完全比較可能

## 観察事実（Facts）

### 1. Deterministic 再現確認 (cycle 3 副作用検証)

| 列 | run-35 vs run-36 一致率 |
|---|---|
| fitness_pen | **100.0%** |
| stage_a_pass | **100.0%** |

→ cycle 3 介入 (Stage A top-fold sidecar) は GA に **副作用なし**。 確実な観察データ生成のみと verified。

### 2. Best 個体 (selection_score 6 要素辞書式 SoT)

| metric | run-34 | run-35 | run-36 | 差分 |
|---|---|---|---|---|
| best_name | g48_i70 | g56_i28 | g56_i28 | 35→36 同一 |
| fitness_pen | 0.171 | 0.222 | 0.222 | 同 |
| sharpe | 0.189 | 0.242 | 0.242 | 同 |
| total_pnl | 40,140 | 28,590 | 28,590 | 同 |
| trade_count | 54 | 53 | 53 | 同 |
| Stage A/B/C | T/F/F | T/F/F | T/F/F | 同 |

cycle 2 で確定した best 個体 (g56_i28, fitness=0.222) が cycle 3 でも変わらず。 **GA 進化は完全に同じ軌道を再現**。

### 3. Stage 通過数

| Stage | run-35 | run-36 | 差分 |
|---|---|---|---|
| Stage A pass | 1999 | **1999** | 同 |
| Stage B pass | 0 | **0** | 同 |
| Stage C pass | 0 | 0 | 同 |

### 4. **cycle 3 sidecar 解析: Stage A 上位 20% の世代別 fold robustness 推移**

| gen | pop_n | top_n | fitness_pen_mean | fold_sign_mean | pfre_mean | fold_sign_nonzero_ratio | n_fold_effective_mean |
|---|---|---|---|---|---|---|---|
| 3 | 3 | 1 | 0.008 | 0.000 | 0.000 | 0.00 | 11.0 |
| 5 | 4 | 1 | 0.027 | 0.300 | 0.273 | 1.00 | 1.0 |
| 10 | 5 | 1 | 0.031 | 0.300 | 0.273 | 1.00 | 11.0 |
| 15 | 14 | 3 | 0.084 | 0.167 | 0.157 | 0.67 | 6.7 |
| 20 | 30 | 6 | 0.074 | 0.250 | 0.172 | 0.83 | 10.0 |
| 25 | 42 | 9 | 0.131 | 0.256 | 0.196 | 0.89 | 9.7 |
| 30 | 42 | 9 | 0.146 | 0.256 | 0.230 | 0.89 | 9.7 |
| 35 | 39 | 8 | 0.164 | 0.250 | 0.169 | 0.88 | 9.6 |
| 40 | 42 | 9 | 0.178 | 0.167 | 0.117 | 0.67 | 7.1 |
| 45 | 47 | 10 | 0.208 | 0.260 | 0.313 | 0.90 | 7.3 |
| 50 | 66 | 14 | 0.207 | 0.264 | 0.268 | 1.00 | 7.4 |
| 55 | 51 | 11 | 0.198 | 0.209 | 0.279 | 1.00 | 7.1 |
| 60 | 55 | 11 | 0.217 | 0.245 | 0.231 | 1.00 | 6.5 |

### 5. 早期 (gen 5-15) vs 後期 (gen 50-60) 比較

| metric | 早期 mean | 後期 mean | 変化 |
|---|---|---|---|
| fitness_pen_mean | 0.051 | 0.207 | **+306%** (4x) |
| fold_sign_mean | 0.297 | 0.237 | **-20%** |
| pfre_mean | 0.241 | 0.296 | +23% |
| fold_sign_nonzero_ratio | 0.879 | 0.985 | +12% |
| n_fold_effective_mean | 7.6 | 7.0 | -8% |

### 6. Stage B 閾値との乖離 (run-36)

| 指標 | Stage B 閾値 | run-36 後期 (Stage A 上位) mean | 達成度 |
|---|---|---|---|
| positive_fold_ratio_effective | ≥ 0.6 | 0.296 | 49% |
| median_oos_sharpe | ≥ 0.05 | (archive 不在、 stage_b_reason 経路でのみ判明) | — |

Stage A 上位群の pfre_mean 0.30 が Stage B 閾値 0.6 の **半分** で天井。

## 解釈・推論（Interpretations、 C9 反証可能性付き）

### 仮説 H1 (Codex C1): 探索圧不整合 — **VERIFIED**

**根拠**:
- fitness_pen が世代と共に **4 倍に伸びる** (0.051 → 0.207)
- 同期間の **fold_sign_mean は減少** (0.297 → 0.237、 -20%)
- pfre_mean は微増 (0.241 → 0.296、 +23%) だが Stage B 閾値 0.6 の **半分で天井**

**示唆**:
- GA 探索圧は「fitness_pen を最大化する方向」 で進化、 つまり 「Stage A 内部評価 (size_norm 控除後 sharpe)」 を伸ばす
- しかし fold robustness (fold_sign / pfre) は **同期して伸びない** どころか fold_sign は **減少**
- → Stage A 目的関数 (fitness_pen = sharpe - α·size_norm) は **WF 頑健性をシグナルとして含んでいない**
- → 進化が進むほど Stage A 評価で勝つが、 Stage B では再現しない 「見かけ最適化」 個体に偏る

**反証可能性 (cycle 5 以降の検証経路)**:
- fitness_pen に fold-aware penalty を追加した A/B RUN で fold_sign_mean が世代と共に上昇するなら H1 確証
- 上昇しなければ別の構造的問題 (primitive / data / fold 設計) を疑う

**判定**: cycle 3 sidecar データで H1 は **VERIFIED** (=確認)。 cycle 4 で対応介入を策定する。

### 仮説 H2: max_clause=2 拡張は依然として Stage A 通過率に逆効果 — UNCHANGED

run-35 と run-36 が deterministic に同じ結果なので、 active_clause=2 の Stage A 通過率は run-35 と同じ 11.6%。 cycle 3 では最小介入 (sidecar 観察のみ) のため当然。

### 仮説 H3: best 個体 trade_count attractor — STILL ACTIVE

best trade_count 53-54 が cycle 1, 2, 3 で連続 → cycle 4 でも変わる契機なし (deterministic 再現)。

### 禁止事項違反チェック (C4)

| 禁止事項 | 兆候 | 注 |
|---|---|---|
| 1. 期間延長 | なし | dataset 不変 |
| 2. 見た目数値改善 | **疑い** | best fitness_pen 0.222 維持、 ただし cycle 3 介入 = 観察のみで GA 影響なし、 数値改善ではない |
| 3. GA ハック | なし | 観察 sidecar のみ |
| 4. 閾値緩和 | なし | 不変 |
| 5. 複雑化 | なし | C1 = 1 ファイル + 1 hook + 11 tests、 観察のみ |
| 6. 取引回数削減 | **継続疑い** | best trade_count 53、 cycle 4 で観測継続 |
| 7. オーバーナイト | 未測定 | 別 sidecar が必要 |

## 次サイクル候補 (cycle 4 → run-37)

### [Critical] C1: Stage A 目的関数 fold-aware penalty 追加 (Structural)

H1 verified に基づく構造的介入。

**設計案**:
- fitness_pen 計算式を `fitness_raw - α·size_norm - β·max(0, 0.4 - pfre_clamped)` に変更
- pfre_clamped = clip(positive_fold_ratio_effective, 0, 1)、 NaN は 0 として扱う
- β は initial 0.05 程度 (α=0.03 と整合、 効果検証で調整)
- これにより GA 進化方向が WF robustness を考慮するようになる

**target_metric**: Stage B pass count (現状 0)、 fold_sign_mean / pfre_mean の世代上昇
**failure_mode**: fitness_pen 4 倍に伸びるが fold robustness は伸びない (定量的に verified)
**causal_path**: GA 目的関数の robustness シグナル欠落 → 進化方向の不整合
**falsification**: cycle 5 sidecar データで「fitness_pen 上昇に同期して fold_sign / pfre が上昇」 が verified なら確証、 上昇しなければ別の構造的問題
**success_criterion**: Stage B pass > 0 (1 件でも) または pfre_mean 後期 > 0.4 (Stage B 閾値 0.6 への 接近)

**禁止事項チェック**:
- ❌ 数値弄りではない: fitness_pen の構造的拡張 (新項追加)、 Reactive Parametric ではなく Structural
- ❌ 閾値緩和ではない: 既存閾値は不変
- ❌ ステージ飛ばしではない: Stage A の selectivity を**強化** する方向 (より厳格)
- ✅ メタ過学習ガード: Structural 分類で APPROVE 可

### [Warning] W1: max_clause=2 維持/戻し判断 — 引き続き保留

cycle 3 plan-and-design で C1 (Stage A 目的関数強化) と独立性無し (両方共 Stage A 通過率に影響) のため cycle 4 で C1 のみ実装、 max_clause 議論は cycle 5 以降。

### [Warning] W2: best trade_count attractor 引き続き観察

50-55 帯固定が cycle 1-3 で 連続 (run-34 trade=54、 run-35/36 trade=53)。 cycle 4 で fold-aware penalty 投入後の trade_count 分布変化を観察。

## 全体判定

**ACTIONABLE**

cycle 3 sidecar は機能、 H1 verified、 cycle 4 で構造的介入を適用する用意が整った。 「仕組みが機能していない段階で値を弄るな」 「機能の名前に立ち返れ」 の原則に従い、 cycle 4 では fitness_pen の構造的拡張 (fold-aware penalty 追加) を **唯一の介入** として実装する。 max_clause / Stage A threshold 等の数値弄りは cycle 5 以降に保留。

### analysis-codex.md

## 前提差分 (C4)
- 前提1: `run-35` と `run-36` は `fitness_pen` / `stage_a_pass` 一致率 100.0% で、cycle 3 介入は純観察だった（verified）。
- 前提2: 今回の主データは「Stage A 上位20% sidecar」であり、**条件付き集団**の観察である（C3）。
- 前提3: 早期 `top_n=1,3` を含むため、単点世代の解釈は弱く、世代帯平均（5–15 vs 50–60）を主根拠にする（C7）。
- 前提4: 判定対象H1は「探索圧が Stage B 要件（fold頑健性）と不整合か」であり、「絶対性能改善」自体ではない。

## 観察事実 (Facts、 C6)
- 後期で `fitness_pen_mean` は `0.051 -> 0.207`（+306%）。
- 同期間で `fold_sign_mean` は `0.297 -> 0.237`（-20%）。
- `pfre_mean` は `0.241 -> 0.296` と上がるが、Stage B 閾値 0.6 の約49%に留まる。
- `fold_sign_nonzero_ratio` は上昇（0.879 -> 0.985）だが、`n_fold_effective_mean` は微減（7.6 -> 7.0）。
- Best個体（g56_i28）は run-35/36 同一で Stage B pass=0 のまま。

## 仮説 H1 verified/falsified 判定
- **判定: verified（条件付き・中〜高信頼）**  
  Stage A 上位群で「`fitness_pen` 改善圧が強まる一方、fold頑健性指標が Stage B 閾値に収束しない」ため、探索圧不整合の観察と整合。

## 解釈・推論 (C9 反証可能性付き)
- 解釈: 現行目的は「利益/サイズ」寄りで、fold頑健性を十分に報酬化していない可能性が高い。
- 反証可能性:
  - 反証1: 同設定で複数runにて、後期 `fitness_pen_mean` 上昇と同時に `pfre_mean >= 0.4` が安定達成される。
  - 反証2: 上位20%だけでなく全体分布でも `pfre` が改善し、Stage B pass が自然発生（>0）する。
  - 反証3: 目的関数を変えずに、初期条件差だけで Stage B pass が再現的に出る。

## 次サイクル候補
- **採用候補（最有力）**: `fitness_pen` に fold-aware penalty 追加  
  `fitness_pen = fitness_raw - α·size_norm - β·max(0, 0.4 - pfre_clamped)`  
  `α=0.03` 維持、`β=0.05` 初期は妥当（最大追加ペナルティ0.02で過大ではない）。
- 検証基準（事前固定）:
  - 主KPI: `Stage B pass > 0`
  - 副KPI: 後期 `pfre_mean > 0.4`
  - ガード: trade数・overnight・複雑度の禁止事項を監視

## 全体判定: OK / CONCERN / CRITICAL_DRIFT / ACTIONABLE
- **ACTIONABLE**  
  問題は特定でき、単一介入で反証可能な次手が明確。

## Claude 分析との差分 (最後に確認)
- 現時点で Claude 側の独立分析本文が未提示のため、**厳密な差分照合は未実施**。  
- 暫定差分要約: 本判定は「H1 verified（条件付き）」かつ「cycle 4 は fitness_pen 拡張のみを唯一介入として承認」。

### analysis-merged.md

# マージ分析: Run 36 (run_20260506_054244) — cycle 4

## 合議ステータス: 完全一致 (Round 0、 analyze 段階で収束)

## 合意事項 (両者一致)

| # | 観察 / 仮説 | 信頼度 |
|---|---|---|
| M1 | run-35 vs run-36 fitness_pen 100% 一致 → cycle 3 介入は副作用なし、 純観察 | verified |
| M2 | 仮説 H1 (探索圧不整合) **VERIFIED**: fitness_pen +306% vs fold_sign_mean -20% (gen 5-15 → 50-60) | 中〜高信頼 |
| M3 | pfre_mean 後期 0.296 = Stage B 閾値 0.6 の 49% で天井 → 構造的限界 | verified |
| M4 | cycle 4 介入: fitness_pen に fold-aware penalty 追加が妥当 | 一致 |

## 統合改善提案 (cycle 4 → run-37)

| # | 提案 | 優先度 | 出所 | 変更分類 | target_metric | falsification | success_criterion |
|---|------|--------|------|---------|--------------|---------------|-------------------|
| **C1** | **fitness_pen に fold-aware penalty 追加** | **Critical** | Claude H1 + Codex 採用候補 | **Structural** (新項追加) | Stage B pass count、 pfre_mean 後期 | cycle 5 で fitness_pen 上昇に同期して fold_sign / pfre が上昇しなければ別構造的問題 | Stage B pass > 0 (主)、 pfre_mean 後期 > 0.4 (副) |

### C1 設計詳細 (両者合意済)

```python
fitness_pen = fitness_raw - α·size_norm - β·max(0, 0.4 - pfre_clamped)
```
- α = 0.03 (既存、 不変)
- β = 0.05 (initial、 最大追加ペナルティ = β × 0.4 = 0.02、 既存 α 寄与と同オーダー)
- pfre_clamped = clip(positive_fold_ratio_effective, 0, 1)、 NaN は 0 として扱う

### 禁止事項チェック (両者確認)

- ✅ 期間延長 (1): 該当なし
- ✅ 見栄え改善 (2): fitness_pen の構造的拡張、 数値弄りではない
- ✅ GA ハック (3): 該当なし
- ✅ 閾値緩和 (4): 既存閾値不変、 むしろ Stage A selectivity を強化
- ✅ 複雑化 (5): 1 行追加 (penalty 項)、 概念上の複雑度低い
- ✅ 取引回数削減 (6): pfre は trade_count 直接介入ではない、 ただし要観察
- ✅ オーバーナイト (7): 該当なし
- ✅ メタ過学習ガード: Structural 分類

## 全体判定

**ACTIONABLE** — 仮説 verified、 介入策定済、 cycle 4 implement へ直行。 Phase 2 plan-and-design は最小ラウンドで収束 (analyze 段階で両者合意のため Codex 改善策合議は省略可)。

