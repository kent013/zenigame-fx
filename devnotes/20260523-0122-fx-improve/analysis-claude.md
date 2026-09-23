# RUN run_20260522_160436 (Run 90) 分析（Claude 自己分析）

## 前提差分
R90 = T117 multi-pair training **min 集約** spike (Stage A fitness を EUR_JPY+USD_JPY で min 集約)、pop48 gen20 seed68 + cross-pair-enable。vs R89 (single-pair, pop96 gen60)。

## 観察事実（Facts）
- multi_pair_training.enabled (aggregate=min, anchors=['USD_JPY'], scope=stage_a) 本番動作。wall-time **13.5 分** (軽量=full 可)。
- ★ **A/B/C = 0/0/0** (R89: 2606/2142/892)。stage_a_pass=False が全 1008 個体。
- fitness_pen (min 集約後): gen0 max -0.058 → gen20 max -0.028。**全 gen で Stage A 閾値 -0.0172 未達**。
- **fitness_raw (観察 sharpe) max = 0.0** (median -0.069)。集団が target でも全く改善せず。
- threshold=-0.0172 (R89 と同一、calibration 差なし)。anchor metric_unavailable=0 (anchor データ問題なし)。

## 解釈・推論（Interpretations）

### 1. ★ min-collapse: min 集約が target 改善への選抜圧を消した
fitness = min(target_fp, anchor_fp)。anchor (USD_JPY) は EUR_JPY 学習の random/未成熟 genome では普遍的に低性能 (fp ~-0.1〜-0.9)。→ min は常に anchor を拾う → **selection fitness ≈ anchor で、target を改善しても min は上がらない** → GA は target 改善を報酬されず、集団が target でも改善しない (fitness_raw max 0.0)。
- R89 (single-pair) は fitness=target_fp で target 改善を直接報酬 → 集団進化 → 2606 passes。R90 は target 信号が min で消失 → 0 passes。
- stage_a_pass=0 の理由: passed=target の判定だが、集団が target-good 個体を進化させられず target_fp も閾値未達 (fitness_raw max 0.0 が傍証)。
- 反証可能性: mean 集約で target 改善が報酬される (mean は target/2 の重みで上昇) なら A/B/C>0 回復 → min-collapse 仮説が正。

### 2. mean 集約が min-collapse を回避する理論
fitness = (target_fp + anchor_fp)/2。target を改善すると mean が target/2 の重みで上昇 → **target 改善が報酬される** → 集団が target-good 個体を進化 (R89 同様)。かつ anchor も従重みで報酬 → anchor も nudge。target-good 個体は high target が mean を閾値上に持ち上げ生存 (min なら anchor で殺される)。
- 懸念: mean でも anchor が極端に低い (-0.9) と mean を閾値下に引きずる個体あり。だが target が十分高ければ (R89 best target fp は閾値を大きく超過) mean 救済。Codex で確認。

### 3. Codex 予測リスクの顕在化
cycle8 Codex consensus は min を「全ペアで機能強制」として推奨も、「tie 多発回避に mean 併記監視」と留保。R90 で min が過酷すぎ集団崩壊 = 予測リスク顕在化。mean (実装済) が次の自然な検証。

### 4. 禁止事項違反の兆候
なし。multi-pair は評価拡張 (緩和でない)。

## 次サイクル候補
- **[Critical] mean 集約 R91**: aggregate=mean で min-collapse 回避を検証。T117 実装済だが CLI に aggregate 渡す経路なし (現状 yaml default min) → `--multi-pair-aggregate` CLI 最小追加。R91 (mean, pop48 gen20 同条件) で A/B/C>0 回復 + pair_failure=0 比率 + cross_pair_mean_sharpe を R90 min/R89 single と A/B。
- **[Warning] weighted blend / NSGA2 多目的**: mean も不十分なら target+λ·anchor (target 主) or 既存 nsga2_selection で target/anchor を別目的 Pareto (集約せず両立)。
- **[Warning] 閾値引き上げ**: 汎化未達のため時期尚早。

## 全体判定
**CONCERN→負の結果が次施策を明確化** — R90 min 集約 spike は A/B/C 0/0/0 で min-collapse (min が target 改善への選抜圧を消し集団崩壊)。但しコスト軽量 (13.5 分)・anchor データ健全を確認。**mean 集約 (target 信号を半重みで保持) が min-collapse を回避する**理論的見込みで、T117 の aggregate=mean を CLI 経由で R91 検証 (最小実装) が次の Critical。
