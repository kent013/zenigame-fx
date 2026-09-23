# 分析 (cycle 16): R97 total_pnl_min=74000 で Stage C 崩壊 — in-loop funnel 効果の発見

## 前提
cycle15 で Codex 合議に基づき total_pnl_min 70000→74000 引き上げ (R95/R96 両seed再現後)。R97 (seed70) で検証 → ★Stage C pass=0。

## 観察事実（Facts）

### ★ R97 負の結果: Stage C pass=0
- A/B/C = 2189/1889/**0** (R95: 2585/2078/378、R96: 2163/1612/209)。
- R97 成功条件 (2)StageC>0・(3)mission_candidate≥10 ともに**未達**。best g36_i91 stage_c_pass=False。
- 条件(4) StageB trade≥100=4 は**充足** (R95/R96 では0、初の充足)。

### ★★ Stage B passer の holdout total_pnl 分布が大きく左シフト
| run | StageB total_pnl med | p90 | max | ≥74k | ≥70k | sum_oos_total_pnl med |
|-----|---------------------|-----|-----|------|------|----------------------|
| R95 70k | 56975 | 71856 | 95470 | 82 | 423 | 175420 |
| R96 70k | 49135 | 70677 | 80830 | 14 | 217 | 148810 |
| R97 74k | **33020** | **46172** | 81040 | 15 | 22 | **256930** |

- R97 の holdout pnl 中央値 33020 = R95/R96 (49-57k) より大幅に低い。**だが max 81040・≥74k は15個体存在** (R96の14と同等)。
- R97 の sum_oos_total_pnl (fold-CV合計) median 256930 = R95/R96 (148-175k) より**高い**。
- ★ ii_lite_pass (cross-pair shadow) 0→**188** 激増 (過去全run 0)。

### total_pnl_min は GA ループ内に作用 (事後フィルタでない)
grep で確認: `total_pnl_min` は
- `stage_a_evaluator.py:278` net_pnl_min_window = total_pnl_min × (window/baseline) ← **Stage A 評価器**
- `stage_gate.py:106` net_pnl_min = total_pnl_min × ratio ← **Stage B / canonical gate**
- `stage_gate.py:1809` pnl_target = total_pnl_min ← **選抜スコア連続値 (selection_score)**
- `stage_gate.py:1983` total_pnl ≥ total_pnl_min ← **mission ゲート boolean**

## 解釈・推論（Interpretations）

### 1. ★ cycle15 の事後 sweep は方法論的に無効だった
cycle15 で「R96 StageC個体を74kでfilter→12個体」と予測したが、これは **total_pnl_min を事後フィルタと誤認**。実際は Stage A 評価器・Stage B・選抜スコアに作用し、引き上げが**探索 funnel 全体と選抜 landscape を変える**。post-hoc sweep は「70k で選抜された個体群」を前提にした静的フィルタで、74k で選抜圧が変わった後の動的分布を予測できない。

### 2. ★ 74k 引き上げが GA を別 basin へ移動させた
選抜スコア (line 1809) の pnl_target が 70k→74k になり、cross_pair_selection_pressure と相互作用して、GA が **高 fold-sum-OOS pnl (256930) + cross-pair 汎化 (ii_lite 188) だが低 holdout pnl (med 33020)・StageC 0** の basin に収束。fold-CV では好成績だが特定 60日 holdout では pnl 不足 = Stage B(fold) vs Stage C(holdout) の乖離が拡大。
- ≥74k holdout 個体は15存在するが Stage C=0 → それら15は holdout sharpe/dd/spread-stress の他 Stage C 基準で落ちた (cross-pair 方向に最適化され holdout 品質が犠牲)。

### 3. ★ cycle13 trade_count_min=100 と同型の「in-loop 到達不能」候補
cycle13: trade_count_min 50→100 を引き上げ→R94 StageC=0 (構造的到達不能)→50へ revert (緩和でなく「品質最適帯の再許容」、precedent 確立)。R97 の 74k も同型の疑い: 引き上げが in-loop で探索を崩壊させる。**ただし seed70 単独の結果**で、seed 分散か gate 効果か未切り分け。

### 4. 判定の分岐 (seed vs gate)
- 仮説A (seed分散): seed70 がたまたま cross-pair basin に落ちた。別seed (71) の 74k なら StageC>0 回復。
- 仮説B (gate効果): 74k 引き上げが体系的に funnel を崩壊させる (post-hoc sweep が示した余地は幻)。別seedでも 74k は StageC≈0。
- 切り分け実験: **74k + 別seed(71) を再run** (閾値維持=緩和禁止と整合、seed のみ変更)。StageC>0 なら仮説A (74k は seed 良ければ可)、StageC≈0 なら仮説B (74k 過大、70k へ revert=trade_count precedent と同様 not 緩和)。

## 次サイクル候補
- **[Critical] 74k + 別seed(71) 再run で seed vs gate 切り分け** (閾値維持)。判定後:
  - 仮説A確定 → 74k 維持、複数seed で mission_candidate 確認 (頑健性)。
  - 仮説B確定 → 70k へ revert (last validated frontier、cycle13 trade_count precedent。緩和でなく失敗引き上げの撤退) + 別品質軸 (dd厳格化/sortino) を検討。
- **[Warning] cross-pair shadow**: ii_lite 0→188 は予期せぬ正の副作用。74k 選抜圧が cross-pair 汎化を促した可能性 (別途観測価値、ただし graduation 別)。

## 全体判定
**CONCERN→負の結果が方法論的誤りを露呈** — total_pnl_min は in-loop (Stage A/B/選抜) に作用し、cycle15 の post-hoc sweep は無効だった。R97 (seed70, 74k) は StageC=0 (GA が高fold-sum+cross-pair basin へ移動、holdout pnl 犠牲)。seed分散 vs gate効果は未切り分け → **74k+別seed(71) 再run** で決定。Codex 合議で実験設計と revert 判定基準を確定 (閾値維持・緩和禁止、cycle13 trade_count precedent 参照)。
