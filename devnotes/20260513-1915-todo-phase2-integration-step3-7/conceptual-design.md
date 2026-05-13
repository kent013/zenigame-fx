# Phase 2 統合 Step 3-7 (BCEvaluationResult + NSGA-II / CPPS / warmstart 配線)

## 背景

cascade port v2 で導入した 8 module は Phase 1 (pure function) 実装完了 + main flow 配線:
- T058-T067 系: Phase 1 完了
- B Phase 2 切替コミット 7 step segmentation:
  - **step 1**: canonical_metrics → main flow (= LOG_ONLY dual-path、 完了)
  - **step 2 (= PR3)**: canonical/mission shadow archive 列化 (完了)
  - step 3: BCEvaluationResult dual-path (= stage_bc_evaluator)
  - step 4: stage_a_evaluator (T063) main flow
  - step 5: nsga2_selection (T065) main flow (= _breed_next_gen 置換)
  - step 6: loop_closure (warmstart、 T067) main flow
  - step 7: failure_handling main flow

## 目的

Phase 2 切替コミットの step 3-7 を順次実施 (= **L 規模、 multi-PR**)。 各 step:
- 1 PR / 1 worktree commit
- Codex 設計 + 実装 review
- dual-path LOG_ONLY 維持 (= 既存判定不変)
- 1 RUN smoke 計画

## 期待効果

- cascade port v2 Phase 2 完了 = T075 切替コミット (= 最終、 旧 BacktestMetrics 経路削除) への足場
- NSGA-II / CPPS / warmstart の main flow 統合
- T076 synthesis Round 22 改訂の前提整備

## スコープ

- step 3-7 を 5 PR に分割 (= 5 sub-TODO 候補)
- 各 step ごとに別 PR、 別 smoke 検証
- 同時 1 PR は効果検証とバグ切り分けが混ざる、 順次実施

## 非目的

- T075 big-bang 切替コミット (= 別 TODO、 step 3-7 完了後)
- step 3-7 を 1 PR にまとめる (= 規模 L で破綻リスク)

## 参考

- handoff § 12 段 TODO 順 11
- `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/conceptual-design.md` § 8 (7 step segmentation 全体俯瞰)
- cascade port v2 完了 handoff series (`devnotes/20260501-*-cascade-port-T*-complete-handoff/`)
