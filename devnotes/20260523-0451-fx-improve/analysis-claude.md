# 戦略的再考分析 (cycle 12): cross-pair 汎化 7 サイクルの総括

## 前提
cycle 12 は単一 run 分析でなく **R87-R93 の 7 サイクル総括 + 戦略的再考**。

## 観察事実（Facts）

### cross-pair 汎化追求の全 approach と結果 (ii_lite_pass=True 個体数)
| Run | 施策 | ii_lite_pass | pair_failure=0 比率 | mean_sharpe max |
|-----|------|-------------|---------------------|-----------------|
| R87 | cross-pair 観測 (T114) | 0/599 | – | – |
| R88 | 選択圧 bool (T115) | 0/619 | – | – |
| R89 | 選択圧 連続値 (T116) | 0/892 | 0.3% | 0.143 |
| R90 | multi-pair min, no-ws (T117) | 0/0 (崩壊) | – | – |
| R91 | multi-pair mean, no-ws (T118) | 0/0 (崩壊) | – | – |
| R92 | multi-pair mean, +ws | 0/133 | 0.3% | 0.109 |
| R93 | multi-pair min, +ws | 0/86 | 0.0% | 0.122 |

**全 7 run・全 approach で ii_lite_pass=True は 0**。pair_failure=0 比率は 0.3% 据置〜悪化、max mean_sharpe は pass 閾値 0.15 未達。

### ★ cross-pair の位置づけ (AGENTS.md L196-200)
- cross_pair は **shadow 観測機構** (「graduation 強制は別途」「汎化の壁を ii_lite_pass 分布で定量化する観測機構」)。
- **live_criteria 本体** (target sharpe≥1.0 / total_pnl≥50000 / max_dd≤20% / trades 50-5000) は **R83/R75 で達成済** (mission_candidates=217、top annualized sharpe 5.02、cycle 23 で bug 修正後実証)。
- single-instrument では graduation は cross-pair 必須で構造的に 0 (AGENTS.md L239 KPI 分離)。

## 解釈・推論（Interpretations）

### 1. multi-pair Stage A 訓練は cross-pair 汎化に無効 (2x2 確定)
真因 (1)scope mismatch (訓練 1 anchor=USD_JPY のみ、cross-pair eval は EUR_JPY+EUR_USD+USD_JPY 全 3 ペア要求 → EUR_USD 訓練外) (2)window mismatch (訓練 Stage A 窓 vs eval holdout 窓) (3)anchor aux 非整合。pair_failure 分布が pf=2 据置 (R93 296/302) = anchor 取引枯渇が訓練後も不変。

### 2. ★ 戦略的論点: cross-pair 汎化は North Star か、self-imposed な追加バーか
- North Star = 「live_criteria 全達成個体を 1 つ → 達成後に閾値引き上げ」。**live_criteria は R83 で達成済**。
- cross-pair 汎化 (ii_lite_pass) は graduation の追加 gate だが AGENTS.md 上 **shadow 観測**。7 サイクル追求して 0 = EUR_JPY 学習戦略の他ペア転移は構造的に極めて困難 (price-scale/regime 差、現 32-primitive の表現力)。
- これは「閾値引き上げ凍結 (汎化達成まで)」の前提自体を問い直すべき局面: 汎化が構造的に困難なら、凍結が North Star (閾値引き上げ) を不当に阻んでいる可能性。

### 3. 候補アプローチの評価
- **(A) multi-pair scope/window 整合**: 訓練 anchor を cross-pair eval と同一の全ペア (EUR_USD+USD_JPY) + 同窓に。最も直接的に mismatch 解消だが、2x2 が示す「anchor 取引枯渇」の根本 (EUR_JPY 特化 entry) は scope 整合でも残る懸念。中コスト。
- **(B) NSGA2 多目的**: target/anchor を別目的 Pareto。集約 collapse 回避だが、anchor で取引しない個体が Pareto 前線に乗らない限り効果薄。大コスト (NSGA2 配線)。
- **(C) anchor aux 整合**: spike 制約解消。anchor aux 非整合が anchor 低性能の主因なら有効だが、metric_unavailable=0 (データ健全) から主因でない可能性。
- **(D) ★戦略転換**: cross-pair を long-term 研究 observable に格下げし、North Star (達成済 live_criteria の閾値引き上げ) に回帰。閾値引き上げ凍結を解除し、達成済 mission の頑健性 (sharpe 1.0→1.5 等) を高める方向。cross-pair は並行観測継続。

## 全体判定
**戦略的岐路 (CONCERN)** — 7 サイクル・4 approach で cross-pair 汎化 0 は再現性ある負の結果。cross-pair が shadow 観測 (hard 要件でない) かつ live_criteria 本体は達成済である事実から、(A)-(C) の cross-pair 追求継続 vs (D) North Star (閾値引き上げ) 回帰 を **Codex 戦略合議で決定**。これまでの負の結果から「同じ multi-pair 小改良」は避け、本質的に異なる一手か戦略転換を選ぶ。

## 次フェーズ
Codex 戦略 consensus (reasoning=high): (A)-(D) を mission 整合・効果見込み・低リスクで 1 つに収束。

## ★ cycle 12 Phase 3 追記 (実装前の決定的発見): 閾値引き上げ軸の再特定
R89 Stage C 892 個体 post-hoc 分析:
- annualized sharpe: median **4.56** / max **5.60** → **sharpe≥1.5 は全 892 クリア (hollow、GA fitness が既に sharpe 最大化)**。
- trade_count: min 50 / median **51** / p75 53 / max **97** → **96% が ≤60 (floor 50 張り付き)、≥100 はゼロ**。
- live_criteria@(sharpe≥1.5, trade≥100): **0 個体**。

→ **真に binding/meaningful な閾値は sharpe でなく trade_count_min**。現 best は trade_count=51 (floor ギリギリ) で annualized sharpe 5.60 = lucky-few-trade 過学習の典型 (AGENTS.md cycle23 C4 既知)。
**refined 施策: trade_count_min 50→100 引き上げ** (取引を増やす方向=「取引削減禁止」と整合、robustness 向上、binding)。GA を高取引数へ押すため entry_count_min (Stage A、現 50) も 100 へ整合引き上げ要。sharpe_min は 1.0→1.5 併せて引き上げ可 (hollow だが North Star 整合)。

注意: trade_count_min=100 で現状 0 個体 → GA が高取引数戦略を探索する必要。entry_count_min 整合引き上げで Stage A 圧をかける。これは「狙い撃ち floor」を上げる正当な robustness 強化。Codex で引き上げ幅 (100 vs 150) + entry_count_min 整合を確認。
