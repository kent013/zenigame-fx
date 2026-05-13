# Phase 2 統合 Step 3-7 詳細設計

## sub-TODO 分割案

| step | 内容 | 規模 | smoke | 依存 |
|---|---|---|---|---|
| step 3 | BCEvaluationResult dual-path (stage_bc_evaluator) | M | 必須 | step 1-2 (PR3) |
| step 4 | stage_a_evaluator (T063) main flow | M | 必須 | step 3 |
| step 5 | nsga2_selection (T065、 _breed_next_gen 置換) | L | 必須 | step 3-4、 PR4 smoke |
| step 6 | loop_closure (warmstart、 T067) main flow | M | 必須 | step 5 |
| step 7 | failure_handling main flow | S | 不要 (= 観測経路) | step 3-6 |

合計 5 sub-TODO。 各 sub-TODO で別途 conceptual + detailed 設計 → todo-add → implement → smoke の cycle。

## 各 step の概略

### step 3: BCEvaluationResult dual-path

stage_bc_evaluator (T064) を swim_lane に dual-path 接続。 LOG_ONLY mode で BCEvaluationResult を payload 添付 (= PR3 同型)。 archive 列追加は別 sub-TODO で。

### step 4: stage_a_evaluator (T063)

StageAControllerState を main flow に持ち込む。 q_force_recommendation 経路。

### step 5: nsga2_selection (T065)

`_breed_next_gen` を NSGA-II + CPPS に置換。 Pareto 3 軸 (= f1=net_pnl / f2=max_dd / f3=mission_inf_gap) で selection。 **最大規模、 PR4 smoke 後**。

### step 6: loop_closure (T067、 warmstart)

archive_admit / AdmissionReport 経路。 PR (run71-63-warmstart) と関連 (= 統合層レベルで実装)。

### step 7: failure_handling

T064 follow-up の failure_memory main flow 統合。 観測経路で行動不変。

## 受入基準

- [ ] 5 sub-TODO の各 conceptual + detailed 設計
- [ ] 各 PR で Codex 設計 + 実装 review
- [ ] 各 step 後に 1 RUN smoke (= step 7 除く)
- [ ] cascade port v2 Phase 2 配線完了 = T075 切替前提整備

## smoke 全体方針 (Codex Y Round 5)

- step 3 PR4 smoke 成功時のみ進む
- step 5 NSGA-II + CPPS は同時に入れない (= 別 PR に分離)
- step 6 warmstart は step 5 完了後

## コミット計画

- 5 sub-TODO に分割、 各 PR 1 commit
- 本 TODO は umbrella (= 各 sub-TODO を todo-add で個別登録するためのトラッカー)

## 関連 TODO 候補 (sub-TODO の素案)

1. T??: Phase 2 step 3 BCEvaluationResult dual-path
2. T??: Phase 2 step 4 stage_a_evaluator main flow
3. T??: Phase 2 step 5 nsga2_selection (= _breed_next_gen 置換)
4. T??: Phase 2 step 6 loop_closure (warmstart)
5. T??: Phase 2 step 7 failure_handling main flow

本 TODO は **umbrella tracker**、 各 sub-TODO は plan-and-design で別途設計時に切る。
