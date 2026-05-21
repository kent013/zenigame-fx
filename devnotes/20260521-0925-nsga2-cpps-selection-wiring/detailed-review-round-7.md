**P3 判定: `APPROVE`**

Round 6 の修正で、前回の残課題は閉じています。

- `BCEvaluationInput` / `stage_bc_evaluator.evaluate_stage_b` を production Stage B に差さず、fold artifact 専用 helper に分離したため、契約ずれと dummy input 問題は解消。
- period 再フィルタを避け、既存 `canonical_trades/canonical_bars/canonical_universe` を直 concat するため、fold 境界 off-by-one と最終 bar/trade 欠落リスクは解消。
- `try_build_pareto_lite_from_stage_b_fold_artifacts(...)` を no-raise 境界にしたことで、LOG_ONLY 隔離は十分。
- archive schema 不変テストを入れるため、観測値の archive 逆流リスクも閉じています。

実装時の確認点は 1 つだけです。`StageBResult` 既存契約に合わせ、`any fold canonical_cf_result.invariants.is_feasible is False` の場合は `b_pooled_cf_result=None` / `pooled_dd_per_fold_max=None` / `is_feasible_invariant=False` / `pareto_axis_usable=False` にしてください。これは新規 Warning ではなく、既存 contract の実装確認です。

**他施策**
- P5a: `APPROVE`
- P5b: `APPROVE`

**全体判定**
`APPROVED`