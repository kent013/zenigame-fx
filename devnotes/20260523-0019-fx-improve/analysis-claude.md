# RUN run_20260522_055538 (Run 89) 分析（Claude 自己分析）

## 前提差分
なし。R89 は T116 連続値選択圧 + warmstart(0.1) + seed=68。R88(bool)/R87(OFF) と A/B。

## 観察事実（Facts）

### T116 連続値化動作 + A/B
- selection_key_schema=v3_5_cross_pair_pressure_continuous、effective=True。Stage A/B/C = 2606/2142/892 (R88 bool: 2541/1930/619、Stage C 増)。
- aggregate_fitness (Stage B): median 0.026 / max 0.055 (R88: 0.022/0.0485、微増)。
- ii_lite_pass=True: **0/892** (R88 0/619、R87 0/599)。

### ★ pass binding 制約の精密診断（cycle 8 の核心、T116 観測列で判明）
Stage B 2142 個体の pass 3 条件 + pair_failure:
| 指標 | 値 |
|------|-----|
| cross_pair_mean_sharpe | median 0.089 / **max 0.143** (pass≥0.15: **0**) |
| cross_pair_min_sharpe | median 0.000 / max 0.021 (pass≥-0.20: **2141/2142**、ほぼ全達成) |
| cross_pair_target_ratio | **全 NaN** (sharpe_target_single 未提供で opt-in 除外、binding でない) |
| **cross_pair_pair_failure_count** | **median 2 / max 3 / =0 はわずか 7/2142** |

mean_sharpe 上位 5 個体すべて: min_sharpe=0.000, ratio=NaN, **pair_failure=2**。

## 解釈・推論（Interpretations）

### 1. ★ 真の binding 制約 = anchor での取引枯渇 (pair_failure)、利益過学習でない
`passed = base_all and not pair_failures` (cross_pair.py:360) のため、pair_failure>0 で **強制 passed=False**。ほぼ全個体 (2135/2142) が pair_failure≥1。pair_failure の原因は `_run_pair_sharpe` の **metric_unavailable** (trade_count < min → sharpe=0.0)。
- pair_failure=2 = target EUR_JPY は取引するが **両 anchor (EUR_USD, USD_JPY) で取引不足** (sharpe=0.0 が 2 つ)。
- mean_sharpe ≈ fmean([target_sharpe, 0, 0]) = target_sharpe/3 → max 0.143 は target_sharpe≈0.43 の希釈。
- ∴ ii_lite_pass=0 の真因は「mean<0.15 (利益不足)」でなく **「EUR_JPY 特化の entry トリガーが anchor で発火せず 0/僅少取引 → metric_unavailable → pair_failure → 強制 fail」**。
- 反証可能性: anchor で取引数を確保する施策 (multi-pair training) で pair_failure→0 になれば本診断が正。

### 2. cycle 7 までの「in-sample 利益過学習の天井」診断を精緻化
T116 観測列以前は「cross-pair fitness 天井 ~0.05」「mean<0.15」と解釈したが、実態は **anchor 取引枯渇 (pair_failure)** が支配的。選択圧 (bool/連続) で aggregate を僅かに上げても、anchor で取引しない構造は変わらず pair_failure が残る → gen 平坦・汎化 0。

### 3. 根本解 = multi-pair training (fitness を複数ペアで評価)
anchor で取引する戦略を得るには、GA が **学習時に複数ペアで評価** (取引+利益を全ペアで報酬) する必要がある。EUR_JPY 単一学習 → anchor 0 取引、では構造的に pair_failure。
- 規模大 (fitness 評価が複数ペア分、メモリ/速度)。Codex 推奨の最小 spike (2 ペア短窓でコスト見積) 先行。

### 4. 禁止事項違反の兆候
なし。

## 次サイクル候補
- **[Critical] multi-pair training**: GA fitness を EUR_JPY + anchor の複数ペアで評価し、anchor でも取引する汎化戦略を進化させる。anchor 取引枯渇 (pair_failure) を根本解消。最小 spike (2 ペア短窓) でコスト/効果見積を先行 (Codex)。
- **[Warning] pair_failure の trade_count_min 緩和は不可** (取引枯渇を隠蔽 = 禁止事項 6 の逆、見かけ改善)。あくまで取引する戦略を進化させる。
- **[Warning] 閾値引き上げ**: 汎化未達のため時期尚早。

## ★ falsification 結果 (Codex Critical: pair_failure=0 個体の mean_sharpe を確認)
pair_failure=0 (全ペアで取引する) 個体は **わずか 7**。その mean_sharpe = [-0.146, 0.012, 0.024, 0.038, 0.038, 0.045, **0.087**] → **0/7 が mean≥0.15** (max 0.087)。1/7 は min<-0.20 も不達。
pair_failure 別 mean_sharpe median: pf=0→0.038, pf=2→0.090(target希釈), pf=3→0.000。

→ **両 failure mode が binding と確定**:
1. 大半 (2103/2142) は anchor で取引せず pair_failure=2 (mean は target 希釈で見かけ 0.09-0.143 だが強制 fail)。
2. anchor で取引する 7 個体も **anchor 成績が低く mean 0.087 max << pass 0.15**。
∴ 「anchor 取引枯渇」と「anchor 低性能」の両方。anchor 再選定や trade_count 緩和 (cheap 代替) だけでは不十分 (取引する個体も利益不足)。**EUR_JPY 学習戦略は anchor で取引しないか、取引しても低性能** = 真の in-sample 特化。

## 全体判定
**CRITICAL_DRIFT (Codex)、根本原因完全特定** — T116 連続値化は部分前進 (max mean_sharpe 0.143) も gen 平坦・汎化 0。falsification で確定: cross-pair 0 汎化は (1)anchor 取引枯渇 (pair_failure) + (2)取引する個体も anchor 低性能 (mean 0.087<<0.15) の両方。EUR_JPY 単一学習の構造的限界。根本解は **multi-pair training** (進化時に全ペアで取引+利益を fitness 評価) のみ。Codex 推奨: full 実装前に 2-pair 軽量 in-loop の最小 spike でコスト/効果見積 + out-of-run 固定期間で再現確認 (メタ過学習ガード)。
