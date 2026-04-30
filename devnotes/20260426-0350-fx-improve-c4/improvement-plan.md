# 最終改善計画: Run 14 → Run 15 (cycle 4)

## 合議ステータス: CONSENSUS REACHED (Codex 案 A 採用)

Codex 全体判定: cycle 4 の最善は案 A (gate リセット + calibrate-gate skip)。仕組みが機能していない段階の値弄りではなく、**機能回復のためのベースライン復元**。

## cycle_focus
`ga_improvements`: gate baseline 復元 (cycle 3 の WF 変更で旧 gate が過剰になった現象を解消)

## 確定施策
| # | 施策 | 内容 | target_metric | falsification | success_criterion |
|---|------|------|--------------|---------------|-------------------|
| C1 | stage_a.threshold reset + calibrate skip | `0.4172 → 0.0`、cycle 4 では calibrate-gate を実行しない | Stage A pass率 ≥20% | gate=0 でも A_pass=0% なら原因仮説 (旧 gate 過剰) 棄却、WF 短縮側問題に焦点移行 | A_pass≥20%、Stage A 全滅再発なし |

## 副次行動
- cycle 5 以降: gate=0 で A_pass 回復確認後、新分布で 1 サイクル calibrate を回し直す
- T038 候補 (Stage B Feasibility Contract) は cycle 6+ で本格設計

## 申し送り
本 cycle は **Phase 2.5 (calibrate-gate) を意図的に skip** する。Codex 案 A の "1 サイクル calibrate-gate を凍結" を尊重。
