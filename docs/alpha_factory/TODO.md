# Alpha Factory TODO

zenigame-fx Alpha Factory の改善タスク一覧。

## Open

| ID | タイトル | テーマ | 概要 | 優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|-------|----------|------|---------|
| T075 | T075-bigbang-cleanup-smoke | infrastructure | Big-bang cleanup + smoke (synthesis § 12 / § 18.2 T918 / § 18.3): cascade port v2 切替最終 PR の設計フェーズ。 純ライブラリ src/alpha_factory/smoke.py 新規。 synthesis local projection (= 親 SSOT 再定義しない、 Round 22 改訂 blocked-by 5 件)。 DoD 二層分離 (PerRun DoD1-DoD7 / CrossRun DoD8)、 EvidenceClass threshold-free 4 値、 Severity 4 値 (= EvidenceClass 同型)、 AggregateEvidence 二軸 (severity + has_inconclusive + InconclusiveReason 構造化)。 classify_smoke_outcome (事実認定) + decide_release_action (運用判断 hint、 自動切替不可) 2 段階分離。 review_hint = no_blocker_observed / hold_for_delay / hold_for_review (= hint only、 reviewer 手動承認必須)。 EvidenceClassifierProtocol (caller-supplied、 supported_metric_names + __call__、 unsupported は inconclusive 必須)。 DeletionTarget / MigrationTarget 分離、 change_group_id 命名規則 ^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$ + supersedes。 SmokeObservabilityProjection typed (5 metric class + epoch_consistency)、 CrossRunSmokeObservabilityProjection (cross_run_epoch_pollution_class)。 dual-path enforce 4 経路 (source/scripts/config/docs runbook) + allowlist + path normalization (PurePosixPath, repository-root relative, no symlink follow)。 FailureModeKind 5 値 (FM1-FM5、 synthesis § 16 enum 紐付け、 数値 threshold T075 不在)。 select_rollback_relevant_failure_modes は Phase 1 NotImplementedError raise (Phase 2 別 TODO)。 collider bias non-goal (= stratified audit / 因果解釈 / 比率差判定 を T075 で判定しない、 Phase 2 で T071 経由)。 既存 src / scripts / config / runbook / PR template / CI meta check は Phase 2 申し送り。 cascade port 設計 18 件中 18 件目 (M6 完了) | Critical | incremental | [設計](devnotes/20260501-0136-todo-T075-bigbang-cleanup-smoke/) | 2026-05-01 02:48 |

## Conditional

| ID | タイトル | テーマ | 概要 | トリガー条件 | 昇格時優先度 | 実装モード | 設計 | 追加日時 |
|----|---------|-------|------|------------|------------|----------|------|---------|
