[Critical]
- 指摘なし。

[Warning]
1. `NaN/Inf` の防御が `lucky_*_penalty` で不足しています。  
事実: `>=0` と `hard>=soft` は検証されていますが、有限値チェックがありません。`nan` は比較をすり抜け、`inf` も許容され得ます。  
解釈: 異常設定時に `fitness_pen` が `nan/-inf` 化し、GA 選抜の順序性を壊すリスクがあります（設計の「NaN/inf 経路回避」要件と緊張）。  
参照: [config.py:334](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/src/alpha_factory/config.py:334), [stage_gate.py:718](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/src/alpha_factory/stage_gate.py:718)

[Suggestion]
1. sentinel 不変契約のテストは `no_exposure` 以外（`system_failure`, `metric_unavailable`）も mode 間同値を固定化すると、Critical 契約の将来退行検知が強化されます。  
参照: [test_stage_gate_phase4.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/tests/alpha_factory/test_stage_gate_phase4.py)

**ファイルごと判定**
- [config.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/src/alpha_factory/config.py): 条件付きOK（4段接続・HARD>=SOFT・loader 5項目伝搬は設計一致。`NaN/Inf` 防御のみWarning）
- [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/src/alpha_factory/stage_gate.py): 条件付きOK（sentinel不変、境界等号、payload 7項目、mode分岐は設計一致。`NaN/Inf` 防御のみWarning）
- [run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/scripts/alpha_factory/run_ga.py): OK（`--fitness-mode` → override 経路は設計一致）
- [default.yaml](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/config/alpha_factory/default.yaml): OK（phase4 5項目・default legacy）
- [test_stage_gate_phase4.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T094/tests/alpha_factory/test_stage_gate_phase4.py): OK（35件構成は妥当。上記Suggestionで契約固定をさらに強化可能）

**前提 (C4)**
- diff全文・提示テスト結果が正であることを前提に評価。
- `_deep_merge None skip` は既存仕様どおり動作する前提（提示情報ベース）。

**全体判定**
- **APPROVED**（上記 Warning はフォローアップ推奨、現PRの設計適合性は満たしています）。