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
