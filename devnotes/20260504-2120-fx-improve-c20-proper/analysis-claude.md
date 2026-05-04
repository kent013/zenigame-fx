# cycle 20 Phase 1 analyze-run (Run-46 + cycle 6-19 cross-run)

**作成日時**: 2026-05-04 21:25 JST
**前提**: cycle 1-5 正規 improve-cycle、 cycle 6-19 batch RUN (Codex 合議省略)
**主目的**: cycle 20 から正規 improve-cycle 復帰、 batch RUN の累積成果を活用

## 観察事実 (Facts、 cycle 6-19 全 14 RUN)

### F1. **Stage B 突破個体既に出現** (= cycle 13 で 2 個)

| cycle | run_id | seed | stage_b_pass | best_fp |
|---|---|---|---|---|
| 13 | run_20260504_111153 | 23 (mut=0.5) | **2** | 0.110 |
| 全他 | — | — | 0 | — |

**stage_b_pass=True 個体詳細** (cycle 13):
- g8_i33: trade_count=**16**, fitness_pen=0.061, sb=0.036, pos_fr=0.667
- g12_i17: trade_count=**17**, fitness_pen=0.002, sb=-0.006, pos_fr=0.667
- = trade_count <<< live_criteria.trade_count_min=50 (= mission 基準未達)
- ただし Stage B 判定 (median_oos_sharpe>=0.05 AND positive_fold_ratio>=0.60) は通過

### F2. archive 列 vs 判定 logic 不一致の疑い

cycle 7 (seed=7) AND 突破個体集計:
- 27 個体が `trade_sharpe_stage_b >= 0.05 AND positive_fold_ratio_effective >= 0.60` 満たす
- うち stage_b_pass=True: **0 個体**

= archive 列 `trade_sharpe_stage_b` と Stage B 判定で使う `median_oos_sharpe` が **異なる量** の可能性。 SSOT 監査必要。

### F3. archive fitness_pen max (= 視点違い) で global best 更新

- cycle 14 archive 内 fitness_pen max=**0.3934** (g14_i36, gen 14, trade_count=32) ← cycle 8 0.293 を超え
- ただし selection_score 由来 best (= summary.json) は fitness_pen=0.099 (g14_i32, trade_count=52)
- = archive 視点の高 fitness 個体は infeasible (= trade_count<50) で selection 下位

### F4. cycle 6-19 全体集計

- 累計 a_pass: 1849 個体
- AND 突破 (analytical = sb>=0.05 ∧ pos_fr>=0.60): 168 個体
- stage_b_pass=True (= 実判定): **2 個体のみ** (cycle 13)
- = analytical AND と stage_b_pass の **判定基準が異なる**

### F5. mut=0.5 vs mut=0.3 比較 (selection_score best fitness_pen 視点)

- mut=0.3 (10 RUN): best max=0.293 (cycle 8), positive 6/10
- mut=0.5 (5 RUN): best max=0.110 (cycle 13), positive 2/5
- = mut=0.5 で selection best は劣る、 ただし stage_b_pass 出現は mut=0.5 のみ

## 解釈 (Interpretations)

### I1 (Critical, 反証可能性 高): Stage B 判定 SSOT 監査が必須

archive `trade_sharpe_stage_b` (max=0.10-0.21) と Stage B 判定 `median_oos_sharpe>=0.05` の **対応関係が不明確**:
- 168 個体 analytical AND を満たすのに stage_b_pass=False
- 別経路 cycle 13 の 2 個体は stage_b_pass=True だが trade_count<<50

**反証**: src/alpha_factory/stage_gate.py:1140-1180 の Stage B 判定実装を Read で確認。 `oos_sharpes_imputed` と archive `trade_sharpe_stage_b` の関係を SSOT で確定。

### I2 (Warning): mut=0.5 で stage_b_pass 出現は偶然 or signal

cycle 13 の 2 個体は trade_count=16/17 = mut=0.5 で **小 genome / low-trade individual** が生まれやすい?
- mut=0.5 = 高 mutation = small / atypical genome 生成多
- low-trade で fold 内 trade も少 → 一部 fold で sharpe 高 (= median 押上げ) → stage_b_pass

= **「low-trade attractor で偶然 Stage B 突破」 = 禁止事項 #6 違反の構造**

### I3 (Notable): live_criteria 整合性

cycle 13 stage_b_pass=2 個体は trade_count=16/17 << live_criteria.trade_count_min=50:
- = Stage B 通過しても mission 達成不可
- = Stage C 評価で live_criteria.trade_count_min<50 で reject 想定

## 次サイクル候補 (cycle 20+)

### [Critical] Stage B 判定 SSOT 監査 (= I1 対応)

stage_gate.py:1140-1180 (= evaluate_stage_b) と archive 列 (`trade_sharpe_stage_b`, `median_oos_sharpe`, `positive_fold_ratio_effective`) の対応関係を Codex C1 で監査。

具体的に:
- `oos_sharpes_imputed` の median = archive `trade_sharpe_stage_b` か?
- `positive_ratio` の母数 (n_fold) = archive `positive_fold_ratio_effective` (effective fold のみ) か?
- 不一致なら archive 列の意味を明確化、 もし bug なら fix

### [Warning] cycle 13 stage_b_pass 個体の構造分析

trade_count=16/17 で stage_b_pass=True の構造的原因。 fold-level sharpe の median が 0.05 を超えた条件 (= fold 数効果?) を確認。

## 全体判定: **PROGRESSING**

cycle 6-19 batch RUN で:
- selection_score best fitness_pen 累計 max=0.293 (cycle 8)
- archive 視点 fitness_pen max=0.393 (cycle 14)
- AND 突破 (analytical) 168 個体
- stage_b_pass=True 2 個体 (= live_criteria 未達)

= 「Stage B AND 同時達成」 は構造的に到達可能、 ただし **Stage B 判定基準と archive 列の対応関係が不明瞭** = 監査が次の打ち手。
