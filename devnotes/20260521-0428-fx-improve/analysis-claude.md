# RUN run_20260520_180757 (Run 84) 分析（Claude 自己分析）

## 前提差分
なし。R84 は cycle 2 の再現性検証 run（seed=69、R83 から seed のみ変更、コード変更なし）。

## 観察事実（Facts）

### Stage 通過数の seed variance（R82/R83/R84）
| Run | seed | A | B | C | mission |
|-----|------|---|---|---|---------|
| R82 | 67 | 2687 | 941 | 0 | 0 |
| R83 | 68 | 717 | 436 | **43** | **43** |
| R84 | 69 | 391 | 62 | 0 | 0 |

- 同一設定（EUR_JPY/pop96/gen60/profit_safe_pfr）で seed のみ変えた 3 連続 run。**Stage A は 7 倍（391-2687）、Stage B は 15 倍（62-941）、Stage C は 0-43 と極端に変動**。
- R84 best（summary, selection_score）= g53_i8: a/b/c=T/T/F, live 1/4（sharpe-1.03/pnl-7170/tc45/dd1.57%pass）。
- R84 best（fitness_pen max）= g38_i77: a/b/c=T/F/F, tc45, pnl31310。
- R84 Stage B pass 62 個体: median_oos_total_pnl=1810（gate 正常動作）、total_pnl（Stage C holdout）median=-7170。
- R84 gap diagnostic（Stage C 評価 62 個体）: both_pnl_count=60, sharpe_involved=2（pass=0）。

## 解釈・推論（Interpretations）

### 1. R83 の mission 達成は seed-lucky（H84 REJECTED 確定）
seed=68 で 43 mission 個体、seed=67/69 で 0。profit_safe_pfr の seed sensitivity は前ループ（Run 75 lucky）でも観測され、本 3 連続 run で定量的に再確認。**mission は「出ることがある」が「頑健に出る」段階にない**。閾値引き上げは時期尚早（North Star: robustness 確認後）。
- 反証可能性: もし seed を変えても Stage C>0 が安定して出るなら variance は許容範囲。実測は 3 run 中 1 run のみ C>0 → 高 variance 確定。

### 2. cycle 3 の最優先は P2（Stage C stress の cost-robustness 化）— 整合性問題の修正
cycle 2 で確定: Stage C の「spread×1.5 stress」は max_spread_bps（spread フィルタ閾値、broker が spread>閾値 の trade を skip）を緩めるだけで per-trade コストを増やさず、stress_pnl_degradation が全個体 0（R83 436 件・R84 でも同様）。「stress」が名前通りの役割（高コスト耐性検証）を果たしていない。
- これは「仕組みが機能していない」状態。R83 の mission 個体も真の cost-stress を通過していない（gate が toothless）。
- P2 で per-trade コスト割増 stress を導入し、stress を名前通りの機能にする。これにより将来の mission 達成が「真に cost-robust」と保証される。
- 反証可能性: P2 導入後も stress_pnl_degradation が 0 のままなら実装/定義不整合が継続。

### 3. seed variance は cycle 3 の射程外（より深い GA dynamics 課題）
Stage A/B が seed で 7-15 倍変動するのは GA 探索の不安定性。これは multi-seed 評価や population 安定化など大きな構造課題で、P2（gate 整合性修正）とは別レーン。cycle 3 では P2 に集中し、variance は将来サイクルの課題として記録。
- 反証可能性: P2 導入で variance が変わるか（変わらないはず＝直交）を R85 で観測。

### 4. 禁止事項違反の兆候
なし。R84 は seed 変更のみで mission 未達も正味の結果。閾値緩和・取引回数操作なし。

## 次サイクル候補
- **[Critical] P2: Stage C stress の cost-robustness 化**（事前登録、cycle 2 consensus でキュー化）。spread filter 緩和でなく per-trade コスト割増 stress を導入。stress_pnl_degradation が非ゼロ化し、cost 環境下での mission 生存率を測定可能にする。Structural（整合性修正）。
- **[Warning] seed variance の構造対処**（将来）: multi-seed 評価 / population 安定化。Stage A/B の 7-15 倍変動を低減。
- **[Warning] cross-pair ii-lite の gate 化**（P3、将来）: graduation 配線。

## 全体判定
**CONCERN** — R83 mission は seed-lucky と確定（再現せず）。最優先は P2（stress 整合性修正、「仕組みが機能していない段階で値を弄るな」原則に従い gate を名前通りに直す）。seed variance は別レーンの大課題として記録。
