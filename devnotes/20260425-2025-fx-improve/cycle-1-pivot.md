# Cycle 1 Pivot: T031 implementation deferred

## 経緯

cycle 1 Phase 3 (implement) で T031 の SSoT 詳細設計を Read した結果、以下の齟齬が判明:

1. **selection_score 要素数の齟齬**: SSoT 設計は「5要素 → 6要素化」だが、現行 `scripts/alpha_factory/run_ga.py` L111 の `selection_score` は 4要素 `tuple[int, int, int, float]`。設計と実装に乖離があり、即座の実装には設計修正が必要。

2. **`run_args` の存在しない flag**: state file 初期値に含めていた `--load-winners`, `--load-candidates`, `--llm-mutation`, `--llm-cooldown`, `--warmstart-auto` は run_ga.py CLI に未実装。30 cycle 自走前に修正済み。

## 対応

cycle 1 Phase 3 (implement) を **defer**:
- T031 を `selected_todos` から外し、`skip_todos: [{id: "T031", reason: "SSoT design vs current code mismatch (selection_score arity); needs design refresh before implement"}]` 扱い
- cycle 1 は **calibrate-gate（実施済: stage_a threshold 0.0→0.5）+ GA RUN（現コード, 調整 gate）** で進む
- T031 は cycle 2 以降の plan-and-design で再選定（その時点で SSoT を refresh するか、5要素化 fallback で実装するか合議）

## 影響

- improvement-plan.md / detailed-design.md は cycle 1 では「実装スキップ」相当で運用
- state file の `selected_todos` は空に更新
- `cycle_focus` を `"ga_improvements"` に変更（gate calibration の効果測定が cycle 1 の主目的）
- 30 RUN バッチ自体は継続（最優先目標）

## 申し送り

cycle 2 の plan-and-design で:
- T031 SSoT 設計を 4→5 要素化（feasibility 先頭追加）に書き直す PR を別途切る
- または T031 を取り下げて T035 (stats-completeness-gate-stage-b) を Critical 採用、B reason_codes 集計で B 全滅の根本原因可視化を先に進める
