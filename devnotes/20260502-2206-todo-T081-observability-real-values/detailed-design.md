# 詳細設計 (skeleton): T081 — RunObservabilityReport 9 metric 実値配線

**作成日時**: 2026-05-02 22:06 JST
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化、 6 step segmentation)**

---

## 1. 使命・制約

T080a で確立した stub 配線経路を、 9 metric すべての実値に置換。 cross-run history (= state file) を含む大規模拡張。

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-2206-todo-T081-observability-real-values/conceptual-design.md`

## 3. 改訂対象一覧 (= 6 step segmentation、 各 step 1 worktree commit)

| step | 内容 | 変更箇所 | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | ABDivergenceMetric 実値配線 | run_ga.py Run loop + 末尾配線 + test | 中 | High |
| 2 | ArchiveChurn / BypassRatio 実値配線 + admission-history state file | run_ga.py + state file 経路 + test | 中 | High |
| 3 | SessionEntropy / FeasibleRatio 実値配線 | run_ga.py + StageAControllerState 抽出 + test | 中 | Medium |
| 4 | Selection 実値配線 | run_ga.py + GenerationSelectionResult 経路 + test | 中 | Medium |
| 5 | InflowConsistency / Failure 実値配線 | run_ga.py + WarmstartReport / RunFailureSummary 経路 + test | 中 | Medium |
| 6 | QForceRecommendation 実値配線 + cross-run state file + T063 配線 | run_ga.py + stage_a_evaluator.py + state file + test | 重 | High |

## 4. 詳細実装方針 (skeleton、 後続詳細化)

### 4.1 各 step 共通方針

- 1 step = 1 worktree commit (= incremental)
- 各 step 完了後に `pytest tests/alpha_factory/ -x` 全 PASS 確認
- 各 step 完了後に `uv run mypy src/` clean 確認
- run_ga.py 末尾の `build_stub_run_observability_report` を `build_run_observability_report` に置換 (= 各 step で該当 metric を実値に切替)
- stub builder は touch なし (= debug / fallback 用途で残存)

### 4.2 step 1: AB Divergence

- run_ga.py の Stage A 評価ループで a_proxy_scores を収集
- Stage B pooled 評価で b_pooled_scores を収集
- Run 終了時に `compute_ab_divergence_on_b_evaluated(a_proxy_scores, b_pooled_scores)` 呼出

### 4.3 step 2: Archive Churn / Bypass Ratio

- T066 archive admission で `AdmissionReport` を生成 (= 既存)
- 当 Run の `AdmissionReport` を `reports/admission-history/{run_id}.json` に atomic write
- Run 終了時に直近 N Run (max 3) の AdmissionReport を読込
- `compute_archive_churn(recent_admission_reports)` 呼出
- `compute_bypass_ratio(当 Run AdmissionReport)` 呼出

### 4.4 step 3: Session Entropy / Feasible Ratio

- archive members から session_pass_pattern (= 3 bit string) を caller 計算
- `compute_session_entropy(pattern_list, n_archive_members=..., n_runs_aggregated=...)` 呼出
- T063 StageAControllerState から feasible_ratio_ema / fsm_state / counts を抽出
- `FeasibleRatioMetric(...)` 直接構築

### 4.5 step 4: Selection Metric

- T065 GenerationSelectionResult を最終世代で取得
- caller 側で feasible_ratio / mean_constraint_violation / generation を計算
- `extract_selection_metrics(result, ...)` 呼出

### 4.6 step 5: Inflow Consistency / Failure

- T067 WarmstartReport を取得
- T066 AdmissionReport を渡す
- `extract_inflow_consistency(warmstart_report, admission_report, warmstart_share_target=..., per_source_run_violations=...)` 呼出
- T068 RunFailureSummary を取得
- `extract_failure_metrics(summary, fingerprint_top_n_by_stage=...)` 呼出

### 4.7 step 6: Q Force Recommendation

- 連続乖離 Run カウントを `reports/q-force-state/q-force-state.json` で permanence
- `recommend_q_force_adjust(current_q_force, divergence, consecutive_divergent_runs)` 呼出
- T063 StageAControllerState の next q_force update に配線

## 5. 機械検証手順 (skeleton)

各 step ごとに:
- run_ga.py の build_run_observability_report 呼出が build_stub_* ではなく実値版になっていることを grep
- 各 metric の status が "ok" or 適切な status になることを test で確認
- pytest / ruff / mypy 全 PASS

## 6. テスト計画 (skeleton)

- 各 step に integration test 追加 (= run_ga.py の Run 終了で生成される observability.json の metric 値検証)
- cross-run history (state file) の atomic write 動作確認 test

## 7. リスク (= 概念設計と同じ)

## 8. 実装モード

**incremental** (= 6 step を 1 worktree 内で順次 commit)、 worktree todo/T081

## 9. 後続セッションでの本格化手順

1. zenigame-fx-alpha-design skill で各 step の元値取得経路詳細化
2. cross-run history (state file) の atomic write 設計詳細化
3. Codex 概念 + 詳細レビュー → APPROVED まで
4. zenigame-fx-implement で worktree todo/T081 で 6 step 順次実装
5. 各 step 完了後に impl-review (gpt-5.3-codex / high) 実施
6. main no-ff merge

## 10. T080 follow-up との関係

T080 (= T080a で stub builder 経路確立、 close 済) の後継として T081 を新規登録。 handoff の T080b-g 申し送りは T081 の 6 step として吸収。 後続 B Phase 2 切替コミット の前提条件 (= 9 metric 実値配線完了) を T081 で達成する。
