# RUN run_20260521_143444 (Run 88) 分析（Claude 自己分析）

## 前提差分
なし。R88 は T115 cross-pair in-loop selection pressure (bool tie-break) + warmstart(0.1) + seed=68 の検証 run。R87(OFF) との A/B baseline。

## 観察事実（Facts）

### T115 動作確認
- selection_key_schema=v3_4_cross_pair_pressure、pressure_effective=True、cross_pair_runtime_mode=enabled。本番動作。
- Stage A/B/C = 2541/1930/619 (R87: 2495/1970/599、同等)。

### ★ 汎化結果と飽和の定量（cycle 7 の核心）
- Stage C ii_lite_pass=True: **0/619** (R87: 0/599)。受入基準 (汎化個体>0) 未達。
- cross_pair_aggregate_fitness (Stage B 通過 1930 個体): min -0.036 / p25 0.015 / **median 0.022** / p75 0.025 / **max 0.0485**。>0: 1874/1930。**>=0.15 (pass mean_sharpe_cross_min): 0**。
- ★ **gen 別 median 推移: gen0=0.0271 → gen60=0.0216 (上昇せず、むしろ微減・平坦)**。

## 解釈・推論（Interpretations）

### 1. bool tie-break は勾配を与えていない（飽和でなく無勾配）
当初「圧で >0 へ移動し飽和」と解釈したが、gen 別推移は **gen0 から既に ~0.027 で平坦**。warmstart motif が gen0 から僅か正の aggregate_fitness を持ち、bool tie-break (>0) は **gen0 から全個体=1 で飽和し勾配ゼロ**。∴ 圧は実質的に上昇圧を与えていない。
- 反証可能性: 連続値化で median が 0.022→max(0.0485)方向へ上昇すれば「bool だから無勾配」が確認される。上昇しなければ別要因。

### 2. ★ より深い構造的天井: 単一ペア学習の cross-pair fitness 上限 ~0.05 << pass 0.15
**max aggregate_fitness=0.0485** = 全 1930 個体中の最良でも pass 閾値 0.15 の 1/3。EUR_JPY 単一ペア in-sample 最適化で得られる戦略は、anchor ペアへの転移 fitness が構造的に低い (~0.05 天井)。
- これは「選択圧の弱さ」でなく「探索空間 (EUR_JPY 学習個体) の cross-pair 転移天井」の問題。連続値化で天井 ~0.05 まで登れても pass 0.15 には届かない可能性が高い。
- 反証可能性: 連続値化 R89 で max/median が 0.05 を大きく超え 0.15 方向へ向かえば天井仮説は棄却。0.05 付近で頭打ちなら天井確定 → multi-pair training 必須。

### 3. 根本解の方向: multi-pair training（fitness を複数ペアで評価）
cross-pair mean_sharpe≥0.15 の個体を得るには、GA が **複数ペアで学習**する必要がある (EUR_JPY 単一学習 → 稀な転移個体を選抜、では天井 ~0.05)。multi-pair training は本質的だが大規模 (fitness 評価が複数ペア分、メモリ/速度大)。

### 4. 禁止事項違反の兆候
なし。

## 次サイクル候補
- **[Critical] T115 連続値化 (cheap falsification 先行)**: selection_key に bool でなく cross_pair_aggregate_fitness 連続値を反映し勾配付与。R89 で median が天井 ~0.05 方向へ上昇するか・ii_lite_pass>0 が出るかを安価に検証。**天井仮説の falsification を兼ねる** (0.05 で頭打ちなら multi-pair へ)。低リスク (既存 T115 最小拡張、default OFF)。
- **[Warning] multi-pair training**: 連続値化が天井 ~0.05 で頭打ちなら本命。大規模のため連続値化の結果を見てから。
- **[Warning] 閾値引き上げ**: 汎化未達のため時期尚早。

## 全体判定
**CONCERN→CRITICAL_DRIFT (Codex、受入 KPI 0 のまま実効改善なし)** — T115 は動作したが bool tie-break は gen0 から飽和し上昇圧ゼロ。次は連続値化で勾配を与えつつ天井仮説を安価に falsification、頭打ちなら multi-pair training へ。

### 【Codex Round1 訂正反映】
- 「天井 ~0.05」は**言い過ぎ**: aggregate_fitness = mean_sharpe − 0.5·std なので max aggregate=0.0485 では **mean_sharpe_cross の上限を直接証明できない**。正しい主張は「aggregate 軸で pass 0.15 到達ゼロ + 現選択圧 (aggregate>0) が pass 基準 (mean_sharpe_cross≥0.15 ∧ min_sharpe≥-0.20 ∧ ratio≥0.8) と未整合の可能性」。
- → cycle 7 で **mean_sharpe_cross / min_sharpe_cross / ratio (pass 3 条件の実値) を archive 観測列に追加**し、(b1) 実 max mean_sharpe_cross が 0.15 近傍か (天井検証)、(b2) aggregate proxy が pass 基準と整合するか、を世代別記録 (Codex Warning1 メタ過学習ガード=代理目的ミスアライン検知)。
- 選択圧の連続値も aggregate_fitness でなく **mean_sharpe_cross (pass 基準直結)** を使う方が整合的か Codex 合議で確定。
- Codex Warning2: multi-pair training の最小 spike (2ペア短窓) でコスト/改善幅を先に見積もる (フル導入前)。
- まず gen 別 P(aggregate>0) 比率を確認し「bool 飽和」を確証 (反証: 比率が世代変動するなら飽和主因棄却)。
