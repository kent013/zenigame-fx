# 分析 (cycle 20): dd厳格化 2%→1.5% (median付近、さらなる品質向上を検証)

## 前提
cycle17-19: dd20%→5%→3% は non-pivotal (ビット同一)。dd2% で初めて pivotal 化、だが改善方向 (StageC 634→723、ann 5.205→5.582、dd≤1.962%)。

## 観察事実（Facts）
- R98-R100 (dd20/5/3%) ビット同一 StageC634。**R101 (dd2%) pivotal 化・分岐**: A/B/C 2560/2170/723、ann med5.582、dd max1.962%、best g58_i73。
- dd pivotal 境界 = 2-3% 間。dd2% pivotal の効果は**改善方向** (StageC +89、ann +0.38)。
- ★ dd 軸特性: pivotal 化しても mission 整合 (低dd 選抜圧→robustness=高品質)。pnl(74k pivotal→holdout 犠牲) と正反対。
- 達成 StageC dd (R101): max 1.962% (dd2% gate 当然)、median ~1.66%。dd1.5% は median 付近で約半分を拘束。

## 解釈・推論（Interpretations）
### 1. dd 厳格化は「品質を実際に向上させる」閾値引き上げ
dd2% で StageC 増・ann 向上 = hollow でなく真の品質前進 (North Star 整合)。低dd 個体は holdout robust ゆえ Stage C 通過率も高い好循環。
### 2. dd1.5% の二仮説
- 仮説A (継続改善): dd1.5% でさらに低dd良個体 basin へ、StageC 維持/増・ann 向上。
- 仮説B (過度絞り崩壊): median 付近の強制で探索が狭まり StageC 急減 (dd in-loop 実用下限到達)。
- post-hoc 予測 (無効、pivotal ゆえ): dd≤1.5% は R101 StageC 723 のうち約半分? だが pivotal で進化分岐ゆえ予測不能 → run 必須。
### 3. dd in-loop 下限の探索
dd を下げ続けると、いずれ「低dd だが他基準 (pnl/sharpe) を犠牲」or「探索枯渇」で StageC 減少に転じるはず。dd1.5% (median) はその境界探索。

## 次サイクル候補
- **[Critical] dd2%→1.5%、R102 seed70**。判定: StageC≥400 ∧ mission_candidate(dd1.5%)≥10 ∧ ann 維持/向上なら安全採用 → dd1.2%付近(実用下限探索)へ。StageC急減(<400)なら dd1.5% は過度→dd2% を validated frontier 確定、別軸(sortino等)へ。
- post-hoc 無効 (pivotal)・in-loop 検証必須。

## 全体判定
dd2% は pivotal だが改善方向 (品質向上した真の閾値引き上げ)。dd1.5% (median付近) でさらなる品質向上 or 実用下限到達を R102 で検証。dd 軸は pnl と異なり厳格化が mission 整合に働く好軸。
