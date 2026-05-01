# Selection Cascade Port — Session Handoff (cascade port v2 Phase 2 配線 18/18 TODO 全完了 ✨🎉)

**作成日時**: 2026-05-02 07:10 JST
**Session**: cascade port v2 Phase 2 配線実装、 **T075 (Big-bang cleanup + smoke) を 1 PR で完了 → 18/18 TODO 全完了**
**前セッション**: T074 完了 (`devnotes/20260502-0612-cascade-port-T074-complete-handoff/handoff.md`)
**次セッション**: **T076 (synthesis Round 22 改訂) 着手** または **Phase 2 切替コミット (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替) の別 PR 着手**

---

## 0. 現在地 ✨🎉 cascade port v2 Phase 2 配線 全完了

```
Phase 1 設計 18 件 (T058-T075)            ████████████████████ 100% (前セッションで完了)
T064 Follow-up                            ████████████████████ 100%
Phase 2 配線 18 件 (T058-T075)            ████████████████████ 100% ✨🎉 (本セッションで完了)
synthesis Round 22 改訂 (T076)            ░░░░░░░░░░░░░░░░░░░░   0%
Phase 2 切替コミット (旧実装削除 + 切替)  ░░░░░░░░░░░░░░░░░░░░   0% (T076 後に実施)
```

**達成内容**:
- cascade port v2 設計 18 件 全件 Codex APPROVED (前セッション)
- cascade port v2 Phase 2 配線 18 件 全 PR main merge + Closed 移動完了 (本セッション系列)
- 全 TODO で regression 0 件
- Codex impl-review 累計 N+ round 全 APPROVED

**残作業**:
- T076 synthesis Round 22 改訂 (= 5 改訂候補: new_cascade 採用しない / FM SSOT / DoD 分離 / threshold / stable clause anchor)
- **Phase 2 切替コミット**: T076 完了後に旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消の big-bang 1-shot

---

## 1. T075 PR 1 (commit `09bd56d`、 1 PR 完結 + Codex 2 round)

主要追加:
- `src/alpha_factory/smoke.py` 新規 (1127 LOC、 概念 § 5 全 SSOT)
- `tests/alpha_factory/test_smoke.py` 新規 (1437 LOC、 75 振る舞いテスト F1-F40 + happy path + conformance fixture)

DoD: pytest 2050 + 1 xfailed (regression 0)、 ruff/mypy clean.

### T075 で実装した中核要素

1. **DoD 二層分離**: PerRunSmokeDoDResult (DoD1-DoD7、 1 Run) / CrossRunSmokeDoDResult (DoD8、 5 Run 集約) + scope/dod_id 整合 invariant
2. **EvidenceClass threshold-free 4 値**: 数値 threshold は T075 で SSOT 化しない (= synthesis Round 22 別 TODO + smoke 後再校正)
3. **classify_smoke_outcome (事実認定) と decide_release_action (運用判断 hint) を 2 段階分離**: 自動 rollback / proceed 判定廃止、 manual review に委ねる
4. **AggregateEvidence 二軸保持**: severity 4 値 + has_inconclusive 別軸、 invariant 強制
5. **review_hint 3 値**: no_blocker_observed / hold_for_delay / hold_for_review (= hint only、 自動切替指示ではない)
6. **EvidenceClassifierProtocol**: caller-supplied、 supported_metric_names + __call__ 2 method、 unsupported metric_name は inconclusive 必須 (fail-closed)
7. **typed projection**: SmokeObservabilityProjection (5 metric class + epoch_consistency) / CrossRunSmokeObservabilityProjection (cross_run_epoch_pollution_class)、 untyped Mapping 排除
8. **DeletionTarget / MigrationTarget 分離**: cleanup と migrate を別 manifest、 change_group_id 命名規則 `^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$` + supersedes
9. **dual-path operational definition**: 並走 (= runtime 到達 OR feature flag OR 二経路出力、 禁止) と同居 (= source tree のみ、 許容) の境界明確化
10. **dual-path enforce 4 経路 + path normalization**: source / scripts / config / docs runbook、 PurePosixPath + repository-root relative + symlink follow なし、 allowlist 5 件
11. **collider bias 規範継承 (T072-T074)**: AST grep DoD 10 検索語 0 件確認 (`archive` / `swim_lane` / `cross_pair` / `stage_gate` / `calibrate_gate` / `calibrate_state` / `holiday` / `DST` / `observability_flags` / `stratified`)
12. **select_rollback_relevant_failure_modes は Phase 1 NotImplementedError raise**: synthesis Round 22 改訂後の Phase 2 別 TODO で実装

### Codex Round 1-2 経緯

- Round 1: NEEDS_REVISION (1 Critical / 2 Warning / 1 Suggestion)
  - C-01: PerRunSmokeDoDResult.overall_evidence_class 集約 invariant 不在 → `_aggregate_evidence_class` helper + `__post_init__` で再集約強制
  - W-01: F35/F36 トレーサビリティ差分 → `scripts/**/*.py` AST 走査 + `config/**/*.yaml` dot-notation 走査追加
  - W-02: 5 metric 厳密検証不足 → 完全一致アサーション追加
  - S-01: decide fail-closed 明示化 → severity 範囲外 → `hold_for_review` 分岐
- Round 2: APPROVED (残 Suggestion: F35 import 形 robust 化も対応)

---

## 2. cascade port v2 Phase 2 配線 全 18 TODO サマリ

| TODO | 完了 commit | 主要追加 |
|---|---|---|
| T058 (PR1) | a4bf1bf | schema_contract / RunContext / SchemaContractConfig 基盤層 |
| T058 (PR2) | f810c24 | archive.py GENOMES_SCHEMA v2 4 field + flush lint |
| T058 (PR3) | 2a75de8 | calibrate_gate_history v2 + calibrate_state scope key |
| T058 (PR4) | a9733f3 | diagnostics_sidecar v2 + fsp_updater propagate |
| T058 (PR5) | ba11aaa | run_ga RunContext 完成 + sieve mode + Archive.load 拡張 (中核 PR) |
| T058 (PR6) | 2bd339a | Tier 2 軽量ガード (display 系 4 scripts) |
| T058 (PR7) | 15f3ab6 | 統合テスト + DoD 全項目確認 + docs / SKILL.md 更新 |
| T059 | d835824 | EpochManager + make_epoch_id deterministic + run_ga.py で stub 置換 |
| T060 | 01af827 | partition.py (Period / Partition / Fold) |
| T061 | 88b2eb8 | canonical_metrics.py (canonical 5 metric + GATE_PASS_TOLERANCE + invariants) |
| T062 | 4ddfa9b | mission_inf_gap.py (GA Pareto f3) |
| T063 | 99b861f | stage_a_evaluator.py (Stage A pass + StageAControllerState + q_force_recommendation) |
| T064 | 46041ba | stage_bc_evaluator.py (Stage B/C-lite/C 評価層 + cross-pair shadow) |
| T065 | 95acf09 | nsga2_selection.py (NSGA-II core + Pareto 3 軸 + crowding distance) |
| T066 | 869ff6d | cpps_archive.py (CPPS 2-state FSM + CA/DA archive admission/eviction) |
| T067 | de255ab | loop_closure.py (warmstart + emergency + LOG_ONLY → FAIL_CLOSED 切替) |
| T068 | 808b467 | failure_handling.py (graceful failure 伝搬 + safe-default fallback) |
| T069 | 874a0ff | calibrate_freeze.py + 3 Run freeze + Δ≤0.03 contract |
| T070 | fcc9746 | session_block.py + Trade.spread_cost/holding_cost + BacktestResult.session_blocks |
| T071 | 89e4d11 | observability/run_metrics.py (RunObservabilityReport hub) |
| T072 | 1e77a5a | BrokerTradingSchedule + MarketHolidayCalendar 完全分離 + DST table |
| T073 | f59bd79 (+6fb9322 docs) | audit.py (DSR + PBO/SPA scaffold + AuditNullModel SSOT) |
| T074 | a9a1b1e | graduation.py (graduation lane scaffold) |
| T075 | 09bd56d | smoke.py (Big-bang cleanup + smoke = 最終 PR) |
| T064 follow-up | 874e287 | c_pass_depth field + n_pass_windows field + compute_c_pass_depth helper |

合計 PR 数: 25 PR (= T058 7 PR + T059-T075 各 1 PR + T064 follow-up 1 PR + T073 docstring 同期 1 commit). 全 main fast-forward merge、 regression 0 件.

---

## 3. T058-T075 完了で確立した規範 (累積)

各 TODO 完了 handoff に記載済の規範を集約:

### 3.1 設計規範

1. 既存 caller signature 完全維持 (= default 値、 既存 test 互換)
2. status field 方式 (= 明示分岐 + 未知値 ValueError raise、 None 経路完全排除)
3. collider bias 独立性 (T072-T075 継承、 holiday/DST/observability に依存しない、 stratified audit は T071 RunObservabilityReport 経由)
4. SSOT 厳密性 (= enum 値経由参照、 文字列リテラル散在禁止、 mission_signed_margin SSOT)
5. 半開区間 [start, end) 統一
6. no-raise contract (= 評価系 pure function は no-raise + structured result、 InfeasibleReasonCode 経由で violation 報告)
7. MappingProxyType による immutability 強化 (= 評価系結果 dataclass の dict / list field)
8. NaN fail-fast の順序規範 (= 「異常値 fail-fast → 正常値判定」)
9. default-deny 契約 (= pass 集合のみ保持、 fail 集合は導出可能なら持たない)
10. state を input dataclass に含めない single source of truth
11. keyword 引数注入規範 (= validator / provider は keyword 引数で注入)
12. xfail で後段契約を予約 (= T065 で実装される caller 契約は xfail で予約)
13. scaffold は status + calc_version のみ (= 数値 field なし、 将来 MINOR bump で実装値置換)
14. dual-path operational definition (= 並走 = runtime 到達 OR feature flag OR 二経路出力、 同居 = source tree のみ)
15. synthesis local projection (= 親 SSOT を子 TODO で再定義しない、 改訂は別 PR)

### 3.2 実装フロー規範

1. 軽量 TODO は 1 PR で完結、 大規模 TODO (= 12 施策超) は 5-7 PR に分割
2. worktree + subagent + Codex impl-review (gpt-5.3-codex / xhigh) + ff-merge フロー継承
3. **Codex model `gpt-5.3-codex` 厳守** (= `gpt-5.5-codex` は OpenAI 側未登録 = 404)
4. Codex prompt は「ファイル読み込みは許可」 を明示 + 必要なら本文 inline 提示
5. subagent 中断時の main conversation 直接対応経路 (= SendMessage tool 不在で通信不可な場合)
6. 進捗報告 inline 指示 (= 中断防止)
7. 詳細設計 vs main 実装の整合性検査 (= 不一致なら main 実装を SSOT、 設計改訂は別 PR で同期)
8. ファイル配置規範 (= 既存 flat module との一貫性優先、 新規 sub-package は別 PR)
9. ruff B905 `zip(strict=True)` 規範
10. main merge 時の untracked file 衝突対応 (= subagent worktree 経由で main 側にも書込される現象、 ff-merge 前に rm -f + 削除)
11. worktree commit に Codex review files 全 git add (= main merge 衝突防止、 T067/T068 経験)
12. monkeypatch 経由の評価経路テスト規範 (= dataclass 直接構築 + 評価経路通過の 2 経路で test)
13. 5 段階 grep DoD (= PR スコープ外ファイルへの touch を構造的に防止、 source / alias / relative / re-export / runtime シンボル)

---

## 4. 次セッション着手フロー

### 4.1 推奨: T076 (synthesis Round 22 改訂) 着手 → Phase 2 切替コミット

T076 は cascade port v2 全完了の **前提条件**. 5 改訂候補:
1. § 12.4 「new_cascade 名前空間」 文言 → 「採用しない、 直接 src/alpha_factory/* で実装」 と明文化
2. § 12.4 「FM1/FM4」 ロールバック条件 → T075 FailureModeKind enum と紐付けて確定
3. § 18.3 Smoke DoD 8 項目 → per-run / cross-run 分離形式 (= DoD1-DoD7 / DoD8) で明文化
4. § 16 Risk Top 5 と FM1-FM5 の数値 threshold → 別 TODO で確定 (= smoke 後再校正)
5. stable clause anchor 体系 → synthesis 全文に `synthesis_schema_version: 22` を冒頭 metadata block に追加 + 旧 1-21 round の遡及付与

T076 着手後、 **Phase 2 切替コミット** (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消) を別 PR で実施 → cascade port v2 完全完了.

### 4.2 次セッションの最初の指示テンプレート

#### T076 着手 (推奨)
> 引き継ぎは `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` 読んで。 T076 (synthesis Round 22 改訂) を概念設計から起こす (zenigame-fx-alpha-design skill or 手動). 5 改訂候補を synthesis に反映後、 Phase 2 切替コミット (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替) を別 PR で実施.

#### Phase 2 切替コミット先行
> 引き継ぎは `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` 読んで。 T076 を後回しにして Phase 2 切替コミット (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消) を着手. T075 で確立した DUAL_PATH_ENFORCE_TARGETS / DeletionTarget / MigrationTarget 規範に従う.

---

## 5. 累積 commit 一覧 (cascade port v2 Phase 2 配線、 直近 5 件)

```
09bd56d feat(T075 PR1): smoke.py 新規 (Big-bang cleanup + smoke = 概念 § 5 全 SSOT、 cascade port v2 Phase 1 設計 18 件全件完了) ← 本セッション
6b9f6d6 docs(handoff): T074 完了 + Closed 移動 handoff
a9a1b1e feat(T074 PR1): graduation lane scaffold (evaluate_graduation_trigger + 6 batch pair frozenset + GraduationEpochSummary + Phase 4 NotImplementedError)
c883cfd docs(handoff): T073 完了 + Closed 移動 handoff
f59bd79 feat(T073 PR1): audit layer (DSR + PBO/SPA scaffold + AuditNullModel SSOT + stratification API guard)
```

cascade port v2 Phase 2 配線 commit 計 27 個 (= T058 7 + T059-T075 各 1 + T064 follow-up 1 + T073 docstring 1 + handoff 2)。

---

## 6. 残作業 / 未解決事項

1. **T076 synthesis Round 22 改訂** (推奨次着手、 5 改訂候補)
2. **Phase 2 切替コミット** (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消、 T076 後)
3. T070 follow-up (BLOCK_BUCKET_RANGES_UTC への DST 例外連携)
4. T071 caller 注入式 Phase 2 配線 (= run_ga.py で必要な値を計算して T071 関数に注入)
5. T058 detailed-design 改訂依頼 (HistoryRecord.applied_from_run_id v2 必須化)
6. T064 follow-up 申し送り (apply_spread_stress を T070 import 経由に置換)
7. SessionBlock mode 必須化に伴う既存 caller 更新 (= test_session_block.py 7 caller / engine.py 1 caller)
8. select_rollback_relevant_failure_modes 実装 (= synthesis Round 22 後の Phase 2 別 TODO)
9. Run-26 崩壊原因: 未調査 (= yaml threshold revert のみで未追跡)
10. untracked reports: 別 TODO で .gitignore 候補

---

## 7. cascade port v2 完了に至るまでの全体経緯

1. **Phase 1 設計** (前セッション): 18 件全件 Codex APPROVED (= T058-T075 + T064 follow-up = c_pass_depth)
2. **Phase 2 配線** (本セッション系列): 18 TODO 全完了 + 25 PR 全 main fast-forward merge + regression 0 件
3. **T076 synthesis Round 22 改訂** (次): 5 改訂候補
4. **Phase 2 切替コミット** (T076 後): 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消の big-bang 1-shot

cascade port v2 設計 + Phase 2 配線が 100% 完了し、 残るは synthesis Round 22 改訂と切替コミットのみ. cascade port v2 完了は目前.
