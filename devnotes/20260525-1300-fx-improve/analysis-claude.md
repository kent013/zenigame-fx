# 分析 (cycle 19): dd厳格化 3%→2% (binding 開始点で selection-pivotal 化を検証)

## 前提
cycle17-18: dd20%→5%→3% は全て R98 とビット同一 (selection non-pivotal、hollow)。達成 StageC dd max 2.676%。

## 観察事実（Facts）
- R98/R99/R100 (dd20%/5%/3%, seed70) = 完全ビット同一 (A/B/C 2577/2010/634、best g48_i14)。**dd_max は GA 選抜に non-pivotal** (profit_safe_pfr Stage B gate dd非依存・Stage A低dd・selection_score dd軸非順位)。
- post-hoc sweep (進化不変前提、dd non-pivotal なら正確): dd≤2.0%:621 / ≤1.8%:587 / ≤1.5%:405 / ≤1.2%:**0** (崖、min dd~1.4%)。
- 達成 StageC dd: median 1.483 / p90 1.794 / p99 2.077 / max 2.676。

## 解釈・推論（Interpretations）
### 1. dd2% は binding 開始点
dd2% は p90(1.794%)超〜max(2.676%)の達成個体 13 個 (634→621) を初めて拘束。dd5%/3% (誰も拘束せず) と異なり「binding」開始。
### 2. ★ selection-pivotal 化の検証
dd5%/3% は non-pivotal (ビット同一)。dd2% で selection_score の dd 軸 (dd_lower=0.02) が進化途中個体を初めて有意にペナルティ → **pivotal 化して funnel が変わるか** が論点。
- 仮説A (依然 non-pivotal): dd2% でもビット同一進化 → StageC=621 (post-hoc 的中)。dd は Stage C フィルタとして安全 (pnl と違い崩壊しない) が確定。
- 仮説B (pivotal 化): dd2% で進化分岐 → 新 funnel、StageC≠621。dd が binding 域で selection に効き始める境界を特定。
### 3. mission 整合
dd は GA が自然に低く保つ軸 (達成 median 1.48%)。dd2% 厳格化は緩和でなく引き上げ、in-loop 崩壊リスク低 (non-pivotal 履歴)。dd1.5% (median 付近、36%フィルタ) が次の真に意味ある引き上げ候補。

## 次サイクル候補
- **[Critical] dd3%→2%、R101 seed70 反実仮想**。判定: StageC≈621 (≥400) ∧ mission_candidate(dd2%)≥10 なら安全採用 → dd1.5% へ。ビット同一なら dd non-pivotal 確定 (post-hoc 有効)、分岐なら pivotal 境界特定。崩壊 (StageC激減) なら dd2% 棄却し dd3% へ revert。
- post-hoc 信仰禁止だが、dd は non-pivotal 履歴 (3 run ビット同一) ゆえ post-hoc 予測の妥当性自体を R101 で検証する点が新しい。

## 全体判定
dd は selection non-pivotal で dd5%/3% hollow。dd2% は達成 tail を初めて拘束する binding 開始点 → R101 (seed70) で dd の selection-pivotal 化境界を検証。安全なら dd1.5% (median付近=真の意味ある robustness 引き上げ) へ前進。
