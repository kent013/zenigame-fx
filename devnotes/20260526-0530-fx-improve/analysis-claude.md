# 分析 (cycle 21): live_criteria 4軸特性把握完了 → 次の品質軸の戦略選択

## 前提
cycle14-20 で live_criteria 4軸を全て特性把握。dd軸はcycle17-20でdd2%最適確定。

## 観察事実（Facts）

### ★ live_criteria 4軸の特性 (cycle 14-20 で確立)
| 軸 | 現値 | 特性 | in-loop挙動 |
|----|------|------|------------|
| sharpe_min | 1.5 | hollow (達成 ann med 5.2-5.6 >> 1.5) | 引き上げても飽和、形式的 |
| total_pnl_min | 70000 | frontier (3seed validated R95/96/98) | **74k は pivotal→funnel崩壊** (holdout犠牲) |
| max_drawdown_max | 2% | **最適確定** (dd20%→2%でStageC634→723/ann5.205→5.582向上) | dd2%pivotal改善、dd1.5%over-tightening(StageC398/ann低下) |
| trade_count_min | 50 | floor最適 (cycle13で100到達不能確定) | 100はStageC=0崩壊 |

→ 4軸全て in-loop 特性把握済。pnl/dd は最適点確定、sharpe hollow、trade floor。**既存4軸でのさらなる引き上げ余地は乏しい**。

### ★ 新品質軸候補の archive データ状況 (R101 dd2% StageC 723)
- sortino / calmar / dsr / bootstrap_ci_lower: **全 NaN/inf (未計算)** → gate化には stage_gate での計算実装 (feature work) 必要。
- fold_sign_ratio: p50 0.303 / max 0.364 (低値)。
- **positive_fold_ratio_effective**: p10 0.588 / p50 0.618 / min 0.500 / max 0.676 (n=723)。fold一貫性=OOS robustness、データあり、gate化可能。

## 解釈・推論（Interpretations）

### 1. 既存4軸は飽和、新軸が必要
sharpe/pnl/dd/trade の引き上げ余地は出尽くした (pnl/dd 最適確定、sharpe hollow、trade floor)。North Star の継続的引き上げには**新品質次元**の追加が必要。

### 2. 新軸候補の評価
- **(A) positive_fold_ratio_effective gate 追加**: fold-CV 一貫性 (OOS robustness 直結)。データ即用。達成 min 0.500/median 0.618 → gate 0.55 等で過半 fold 正を要求。selection への影響は要 in-loop 検証 (dd と同様 pivotal 可能性)。低コスト。
- **(B) sortino/calmar 計算実装 + gate**: 下方リスク調整 (sortino) は sharpe より洗練。但し全 NaN = stage_gate で計算追加の feature work + Codex 設計レビュー必要。中コスト。
- **(C) consolidate**: frontier (sharpe1.5/pnl70k/dd2%/trade50、R101で723個体 ann5.582/pnl82k) を確定成果とし、閾値引き上げキャンペーン総括。cross-pair等の別研究へ。

### 3. dd軸の成功知見の一般化
dd厳格化が mission整合だったのは「GAが自然に低く保つ軸を選抜圧で更に促進」したため。positive_fold_ratio も同様に「GAが既にある程度高い軸」なら厳格化が安全に効く可能性 (dd2%パターン)。一方 fold一貫性が GA fitness と逆相関なら 74k 型崩壊リスク。

## 次サイクル候補
- **[Critical] Codex 戦略合議 (high)**: (A) fold一貫性gate / (B) sortino実装 / (C) consolidate を mission整合・情報価値・コスト・in-loop安全性で1つに収束。特に「既存4軸飽和後の North Star 継続方法」を判定。
- 運用ルール: 新軸も dd と同様 seed70 反実仮想で in-loop pivotal/崩壊を検証 (post-hoc信仰禁止)。

## 全体判定
**戦略的節目**: live_criteria 4軸 (sharpe/pnl/dd/trade) 全特性把握完了、dd2%が最後の有意な引き上げ (StageC634→723向上)。既存軸は飽和。North Star 継続には新品質次元 (fold一貫性 or sortino) が必要だが、sortino等は未計算 (feature work)。Codex 戦略合議で (A) fold一貫性gate即追加 vs (B) sortino実装 vs (C) frontier確定+総括 を決定。
