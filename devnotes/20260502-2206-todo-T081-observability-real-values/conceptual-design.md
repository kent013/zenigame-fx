# 概念設計 (skeleton): T081 — RunObservabilityReport 9 metric 実値配線 (T080 follow-up)

**作成日時**: 2026-05-02 22:06 JST
**起源**: T080a (commit `de9b7d7`) 完了で stub builder 経路確立、 残 9 metric の実値配線が必要
**性質**: run_ga.py 全面拡張 (= T065-T068 / T058 RunContext / T071 extract / compute 関数の caller 注入)
**位置付け**: cascade port v2 Phase 2 配線の **本格的最終段** (= 「Phase 2 切替コミット (B)」 と本質的に分離不可)
**status**: **skeleton (= 後続セッションで zenigame-fx-alpha-design による Codex review で詳細化、 6 step に segmentation 済)**

---

## 背景・課題

### T080a で確立した経路

T080a (`commit de9b7d7`) で以下が完了:
- `build_stub_run_observability_report`: 9 metric を valid status / default 値で構築する stub builder
- `serialize_run_observability_report`: dataclass → JSON 変換
- `run_ga.py` main 関数末尾で stub builder 呼出 + `reports/run-reports/{run_id}/observability.json` 出力

= **配線経路が確立**、 ただし全 9 metric が **stub 値のまま**。

### 残課題: 9 metric を実値配線

T071 module には各 metric の **既存 compute / extract 関数** が用意済 (= T080a 調査結果):

| metric | 取得関数 | 必要な caller-supplied 元値 |
|---|---|---|
| ABDivergenceMetric | `compute_ab_divergence_on_b_evaluated` | a_proxy_scores / b_pooled_scores (cross-run history) |
| QForceRecommendation | `recommend_q_force_adjust` | current_q_force / divergence / 連続乖離 Run カウント (state file) |
| ArchiveChurnMetric | `compute_archive_churn` | recent_admission_reports (= 直近 N Run の AdmissionReport sequence) |
| BypassRatioMetric | `compute_bypass_ratio` | 当 Run の AdmissionReport |
| SessionEntropyMetric | `compute_session_entropy` | session_pass_pattern list (caller 計算、 archive members から 3 bit string) |
| FeasibleRatioMetric | (= 直接構築) | feasible_ratio_ema / fsm_state / counts (StageAControllerState) |
| SelectionMetric | `extract_selection_metrics` | GenerationSelectionResult + feasible_ratio / mean_violation / generation |
| InflowConsistencyMetric | `extract_inflow_consistency` | WarmstartReport / AdmissionReport + caller-supplied target |
| FailureMetric | `extract_failure_metrics` | RunFailureSummary + fingerprint top-N |

= 各 metric の元値を run_ga.py が GA Run loop 中で収集 → Run 終了時に extract / compute を呼ぶ流れ。

### 影響範囲

- run_ga.py の Run loop 内で T065 GenerationSelectionResult / T066 AdmissionReport / T067 WarmstartReport / T068 RunFailureSummary を **収集・蓄積**
- cross-run history (= AB divergence / q_force / archive churn) は **state file 経由** で永続化
- 各 metric の元値は **caller-supplied 引数** で extract 関数に渡される (= caller injection 規範、 T080 設計遵守)

---

## 改善アイデア (= 6 step に segmentation)

### Step 1 (T081-step1): ABDivergenceMetric 実値配線

- run_ga.py で a_proxy_scores (= Stage A の各個体 score) と b_pooled_scores (= Stage B pooled score) を収集
- cross-run history 不要 (= 当 Run 内のみ)
- `compute_ab_divergence_on_b_evaluated` を呼出
- stub の `ABDivergenceMetric(status="insufficient_data")` を実値置換

### Step 2 (T081-step2): ArchiveChurnMetric / BypassRatioMetric 実値配線

- T066 archive operations (= admission / eviction) で `AdmissionReport` を生成 + 直近 N Run の sequence を state file に永続化
- `compute_archive_churn(recent_admission_reports)` で N Run 集計 (= 1/2/3 Run で status 自動判定)
- `compute_bypass_ratio(当 Run AdmissionReport)` で当 Run 値

### Step 3 (T081-step3): SessionEntropyMetric / FeasibleRatioMetric 実値配線

- archive members の session_pass_pattern (= 3 bit string "[01]{3}") を caller 側で計算 (= T064 result から)
- `compute_session_entropy(pattern_list, n_runs_aggregated, ...)` で集計
- T063 StageAControllerState から feasible_ratio_ema / fsm_state / counts を抽出 → `FeasibleRatioMetric(...)` 直接構築

### Step 4 (T081-step4): SelectionMetric 実値配線

- T065 GenerationSelectionResult を最終世代で取得
- caller 側で feasible_ratio / mean_constraint_violation / generation を計算
- `extract_selection_metrics(result, feasible_ratio=..., mean_constraint_violation=..., generation=...)` で構築

### Step 5 (T081-step5): InflowConsistencyMetric / FailureMetric 実値配線

- T067 WarmstartReport を取得 + caller-supplied warmstart_share_target / per_source_run_violations
- T066 当 Run AdmissionReport を渡す
- `extract_inflow_consistency(warmstart_report, admission_report, ...)` で構築
- T068 RunFailureSummary を取得 + caller-supplied fingerprint_top_n
- `extract_failure_metrics(summary, fingerprint_top_n_by_stage=...)` で構築

### Step 6 (T081-step6): QForceRecommendation 実値配線

- 連続乖離 Run カウントを state file (`reports/q-force-state/q-force-state.json` 等) で永続化
- `recommend_q_force_adjust(current_q_force, divergence, consecutive_divergent_runs, ...)` 呼出
- StageAControllerState 更新へ配線 (= 次 Run の q_force に反映、 = T063 配線も含む)

---

## 期待効果

- **smoke 5 Run で DoD 観測 SSOT 元値が実値で取得可能** (= cascade port v2 完全完了の前提条件、 数値 threshold 確定別 TODO の calibration data 取得)
- **observability 経路の最終配線完了** (= T071 SSOT が runtime で活用される、 9 metric すべて実値)
- **A→B 乖離自動補正経路確立** (= q_force 自動調整、 cross-run history 経由)

### live_criteria 達成への寄与経路

- 直接的: 各 metric が実値で記録されると、 GA の selection 機構の挙動を観察可能 (= 探索の SN 比評価)
- 間接的: A→B 乖離が観測されると q_force 自動引き上げ → Stage A 通過率調整 → Stage B/C 評価の信頼性向上 → live_criteria 達成個体の探索 SN 比改善

---

## 実装方針 (概要)

### 変更ファイル候補

1. `scripts/alpha_factory/run_ga.py`: 各 step で Run loop 内に metric 収集ロジック追加 + 末尾 build_run_observability_report 呼出を build_stub_run_observability_report から差し替え
2. `src/alpha_factory/stage_a_evaluator.py` (T063): q_force_recommendation の StageAControllerState 配線 (= step 6)
3. state file 系: `reports/q-force-state/q-force-state.json` / `reports/admission-history/{run_id}.json` 新規 (= step 2 / 6 の cross-run history)
4. tests/: 各 step の Run loop 経路 test
5. docs: stage-gates.md の Phase 2 申し送り箇所を「完了」 マーク

### 影響範囲

- run_ga.py が **大規模拡張** (= T065-T068 module の output を収集する経路を追加)
- cross-run history のための state file 設計 (= permanence + atomic write)
- StageAControllerState 配線で T063 module も touch (= step 6)

---

## 制約・前提

- 各 step は **incremental** (= 個別 step を 1 worktree commit で完了、 後続 step に影響なし)
- stub builder (T080a) は不変保持 (= debug / test / fallback 用途で残存)
- LOG_ONLY → FAIL_CLOSED 切替は **本 TODO スコープ外** (= 後続 B Phase 2 切替コミット で実施)

---

## スコープ外

1. LOG_ONLY → FAIL_CLOSED 切替 (= B Phase 2 切替コミット)
2. 旧実装削除 (= B Phase 2 切替コミット)
3. dual-path 並走解消 (= B Phase 2 切替コミット)
4. 数値 threshold 確定 (= 別 TODO、 smoke 後再校正)
5. RunObservabilityReport の Markdown 表現 + 監視運用ガイド docs (= 別 TODO)
6. 6 sub-TODO 化 (= 本 TODO 内で 6 step として進める運用)

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| 各 step が独立して進められず先行 step の完了待ちで進捗停滞 | 中 | step 1-5 は基本独立 (= 当 Run 内のみ)、 step 6 のみ cross-run history 必要 |
| state file 設計が不適切で cross-run history 不整合 | 中 | T058 RunContext + dataset_epoch_id 経由で run boundary を厳密化、 atomic write 必須 |
| run_ga.py の Run loop が大規模化して可読性低下 | 中 | 各 step で helper 関数化、 metric 収集ロジックは別 module に分離 |
| 各 metric の元値計算で N Run 分のデータが揃わず status="insufficient_*" になりがち | 低 | これは expected、 stub 配置を維持して fallback で対応 |
| smoke 5 Run でも archive churn 等で n=3 不足 → status="insufficient_runs" のまま | 中 | 期待動作、 数値 threshold 確定別 TODO で smoke 5 Run 経過後の calibration data から再評価 |

---

## 参考資料

- T080a 完了 commit: `de9b7d7` (= stub builder 経路確立)
- T080a 設計: `devnotes/20260502-1130-todo-t080-t071-caller-injection/`
- T071 module: `src/alpha_factory/observability/run_metrics.py` (= compute / extract 関数全件、 1240 LOC)
- handoff: `devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md` § 3.5

---

## skeleton から本格設計への昇格手順

1. zenigame-fx-alpha-design skill 起動 (= topic="t081-observability-real-values")
2. 各 step の元値取得経路詳細調査 (= grep で AdmissionReport / WarmstartReport / GenerationSelectionResult / RunFailureSummary の生成箇所特定)
3. cross-run history (= state file) の atomic write 設計
4. Codex 概念 + 詳細設計レビュー → APPROVED まで
5. zenigame-fx-implement で worktree todo/T081 実装 (= 6 step を 1 worktree 内で順次 commit、 各 step 後に test / Codex review)
6. main fast-forward / no-ff merge
