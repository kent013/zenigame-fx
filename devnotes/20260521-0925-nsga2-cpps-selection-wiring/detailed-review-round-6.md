**Fact**
- 現コードに `evaluate_stage_b_pooled` は見当たらず、該当する実装は [stage_bc_evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_bc_evaluator.py:606) の `evaluate_stage_b(individual_input: BCEvaluationInput, ...)` です。
- その `evaluate_stage_b` は `BCEvaluationInput.trades/bars/business_day_universe/folds` を fold ごとに `filter_to_period` し、各 fold の canonical を再評価してから pooled canonical を作ります。既存 `fold_trades/fold_equity/test_bars` を直接消費する契約ではありません。
- Production 側の [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1377) は fold を `(train_bars, test_bars)` として持ち、`stage_bc_evaluator` 側は `Fold.test: Period[start,end)` 前提です。

**P3: 訂正後スコープ**
判定: `REQUEST_CHANGES`

- [Critical] 「既存 per-fold 結果を pool して b_pooled_cf を得る」方針自体は正しいですが、`BCEvaluationInput` に adapt して `stage_bc_evaluator.evaluate_stage_b` を呼ぶ設計は契約がずれます。`evaluate_stage_b` は既存 fold backtest 結果を受け取らず、canonical trades/bars を fold period で再フィルタして fold canonical を再計算します。  
  修正案: production 用には新 helper を切ってください。例: `build_stage_b_pooled_result_from_fold_artifacts(fold_artifacts, live_criteria) -> StageBResult`。入力は各 fold の `canonical_trades`, `canonical_bars`, `canonical_universe`, `canonical_cf_result`, `fold_period` に限定し、backtest 再実行も `BCEvaluationInput` dummy 構築も不要にするのが安全です。

- [Critical] fold 境界の off-by-one リスクがあります。`stage_bc_evaluator.filter_to_period` は `[start, end)` で bar/trade を切るため、Stage Gate の `test_bars` から `Period.end` を雑に作ると最終 bar または最終 exit trade を落とします。  
  修正案: 既存 fold artifact を直接 concat する helper にして period 再フィルタを避けるか、`test_bars` 由来の `Period` 生成規約を明文化し、最終 bar/trade が落ちないテストを追加してください。

- [Warning] LOG_ONLY 隔離は、`_try_evaluate_canonical_five_safe` だけでは足りません。pooled build 側の fold 数、順序、overlap、empty bars、threshold 構築、pooled canonical 評価まで全体を no-raise 境界に入れる必要があります。  
  修正案: `try_build_pareto_lite_from_stage_b_fold_artifacts(...) -> ParetoFeaturesLite` を no-raise にし、失敗時は `pareto_axis_usable=False`、`source_stage=None`、WARN log のみにしてください。

- [Warning] `StageResult.metrics["payload"]` に pooled 値を載せる場合、archive collector が拾うかどうかを明示してください。観測のみなら diagnostics sidecar 専用に閉じ、archive schema へ流さないテストが必要です。  
  修正案: `archive.collect_stage_b` の schema 不変テスト、または新列を archive に持つなら schema 伝搬表を更新してください。

**確認事項への回答**
1. `BCEvaluationInput` 経由はそのままでは整合しません。新 backtest は増えませんが、fold canonical 再計算と period 再フィルタが発生します。既存 per-fold 結果を忠実に pool するなら artifact 専用 helper が必要です。
2. 隔離は設計追加が必要です。pooled canonical 全体を fail-soft 境界に入れれば十分です。
3. bit-exact は維持可能です。ただし条件は、既存 fold backtest を再実行しないこと、legacy fold 判定変数を一切変更しないこと、pooled 失敗を no-raise にすること、archive/schema へ意図せず流さないことです。

**他施策**
- P5a: `APPROVE` のまま。
- P5b: `APPROVE` のまま。

**全体判定**
`REQUEST_CHANGES`

P3 の方向性は正しいですが、既存 `BCEvaluationInput` / `evaluate_stage_b` をそのまま production Stage B に差す設計は危険です。fold artifact 直消費の pooled helper に切れば、観測のみ・bit-exact の前提は成立します。