# 分析 (cycle 17): pnl gate 引き上げの in-loop 構造的限界の確定 + 次の閾値引き上げ軸の戦略的再考

## 前提
cycle15 R97 (seed70, 74k) StageC=0 → cycle16 R98 (seed70, 70k) で反実仮想。

## 観察事実（Facts）

### ★ 決定的判定: 74k 過大 = in-loop gate 効果 (仮説A 確定)
同一 seed70 で total_pnl_min だけ 74k→70k:
| run | gate | A/B/C | mission_cand | StageB holdout pnl med | ii_lite |
|-----|------|-------|-------------|----------------------|---------|
| R97 | 74k | 2189/1889/0 | 0 | 33020 | 188 |
| R98 | 70k | 2577/2010/**634** | **634** | **66740** | 0 |
- R98 成功基準全充足。**seed70 無罪** (70k で 634 個体 = R95 378/R96 209 を上回る最良 seed)。74k は GA 探索 funnel を崩壊 (低holdout-pnl + cross-pair basin、cycle13 trade_count_min=100 同型の in-loop 到達困難)。
- **70k = R95/R96/R98 の 3 seed validated frontier** → 74k 正式棄却 (cycle13 precedent、緩和でなく未検証引き上げ撤退)。

### ★ 3 閾値すべてが in-loop (Stage A + selection_score + mission gate) に作用
grep 確認: `sharpe_min` / `total_pnl_min` / `max_drawdown_max` は全て
- Stage A 評価器 (stage_a_evaluator.py:330) — window-scaled hard gate
- selection_score 連続値 (stage_gate.py:1809 付近) — sharpe_target/pnl_target/dd_lower の axis 正規化
- mission gate boolean (stage_gate.py:1983)
→ **どの閾値を引き上げても pnl 74k と同型の funnel 崩壊リスク**。「事後フィルタ安全」は in-loop 安全を保証しない (74k の教訓)。

### ★ R98 で達成された StageC 分布 (n=634) は gate を大きく上回る
| 指標 | p10 | median | p90 | max | gate |
|------|-----|--------|-----|-----|------|
| ann_sharpe | 4.70 | 5.20 | 6.10 | — | 1.5 (hollow) |
| max_dd_pct | 1.45 | 1.48 | 1.79 | 2.68 | 20% (hollow) |
| total_pnl | 71270 | 82420 | 92430 | — | 70000 |
- 全 634 個体が ann≥4.70・dd≤2.68%。sharpe_min=1.5 / dd_max=20% は極端に hollow。**達成分布 (sharpe5.2/dd1.5%/pnl82k) が実質的 frontier**で、gate は遥か下の calibration floor。

### ii_lite=188 (R97) の解釈確定
74k 引き上げの副作用 (探索が cross-pair basin へ移動、holdout pnl 犠牲)。70k では 0。**cross-pair 汎化は holdout 品質と逆相関** = 現フレームで mission 両立不可 (過去7サイクル ii_lite=0 の構造的理由を補強)。

## 解釈・推論（Interpretations）

### 1. ★ 戦略的岐路: 「意味ある引き上げ」が in-loop 壁に当たった
North Star = 達成後に閾値引き上げ。pnl の意味ある引き上げ (70k→74k) は in-loop で構造崩壊。3 閾値とも selection funnel に作用するため、同じリスク。**達成品質 (sharpe5.2/dd1.5%/pnl82k) は優秀だが、gate を意味ある幅で上げると探索が壊れる**。

### 2. 次の引き上げ軸の候補と risk
- **(A) sharpe_min 1.5→3.0/4.0**: 最も hollow (p10 4.70 で全個体クリア)。sharpe は GA primary fitness で GA が自然に最大化 → funnel 崩壊リスク最小の見込み。だが「hollow=情報価値低」。
- **(B) max_drawdown_max 20%→5%/3%**: 達成 dd max 2.68% で margin 大。dd tightening は robustness 直結。dd_lower が selection に入る (tightening で dd 軸圧縮) → 中リスク。
- **(C) pnl の小刻み増分 (72k)**: in-loop 天井を二分探索。だが 70→74 で崩壊した以上、72k も崩壊しうる + 7h コスト。
- **(D) 非 selection-gate の新品質次元**: 例 fold 一貫性要件強化 / 新 robustness metric を additive に。gate 引き上げでなく次元追加 → funnel 非干渉だが実装コスト。
- **(E) 70k/1.5/20% を frontier と認め、達成分布が gate を大きく超える事実を mission robust 達成として確定**し、別の改善 (探索効率/cross-pair 別framework 等) へ。

### 3. 多変数同時変更は回避 (cycle13 教訓)
失敗要因切り分けのため 1 サイクル 1 軸。

## 次サイクル候補
- **[Critical] Codex 戦略合議**: (A)-(E) を mission 整合・情報価値・in-loop 安全・コストで 1 つに収束。特に「hollow 引き上げ (sharpe/dd) に意味があるか」「in-loop 安全な意味ある引き上げは存在するか」を判定。
- **[Warning] 運用ルール明文化**: 閾値引き上げ採用は (1) 独立2seed以上で mission_candidate>0 再現 (2) in-loop 検証必須 (post-hoc sweep 禁止) — 74k 教訓。

## 全体判定
**CONCERN→戦略的岐路**: pnl gate 引き上げは in-loop で構造的に不可と 3 seed 反実仮想で確定。70k=validated frontier。3 閾値とも selection funnel 作用で同型リスク。達成分布 (sharpe5.2/dd1.5%/pnl82k) は gate を大きく超え優秀。「意味ある閾値引き上げ」が in-loop 壁に当たった今、(A) hollow だが安全な sharpe/dd 引き上げ vs (D) 新品質次元 vs (E) frontier 確定+方針転換 を Codex 戦略合議 (high reasoning) で決定。post-hoc sweep 無効・in-loop 検証必須を運用ルール化。
