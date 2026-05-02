# Cascade Port v2 Follow-up — Session Handoff (T077-T080 完了 ✨ + 残 T081 / T082 + B + GA)

**作成日時**: 2026-05-02 23:23 JST、 **更新**: 2026-05-02 23:35 JST (= impl-review devnotes 追補 + commit 一覧更新)
**Session**: cascade port v2 follow-up 4 件 (T077-T080) のうち T080 / T078 / T077 / T079 完了 + T081 / T082 を skeleton design + Open 登録
**前セッション**: T076 synthesis Round 22 改訂 完了 (`devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md`)
**次セッション**: **T081 → T082 → Phase 2 切替コミット → smoke 5 Run / 実 GA 動作確認**

---

## 0. 現在地 — cascade port v2 follow-up 4 件のうち 4/4 一次対応完了 (T081 / T082 で残実装段階)

```
T076 synthesis Round 22 改訂              ████████████████████ 100% ✨ (前セッション)
T077 applied_from_run_id v2 必須化        ████████████████████ 100% ✨🎉 (本セッション)
T078 TradeRecord schema 拡張              ████████████████████ 100% ✨🎉 (本セッション)
T079 DST/holiday 連携 (option A 採用)     ████████████████████ 100% ✨🎉 (本セッション、 既実装で close)
T080 T071 caller stub 配線 (first step)   ████████████████████ 100% ✨🎉 (本セッション、 stub builder 経路確立)
T081 RunObservabilityReport 9 metric 実値配線 (T080 follow-up、 6 step) ░░░░░░░░░░░░░░░░░░░░   0%
T082 TradeRecord.spread_cost 伝搬経路配線 (T078 follow-up)               ░░░░░░░░░░░░░░░░░░░░   0%
Phase 2 切替コミット (旧実装削除等)       ░░░░░░░░░░░░░░░░░░░░   0% (T081 / T082 完了後)
GA 動作確認 (smoke 5 Run / run_ga 実行)   ░░░░░░░░░░░░░░░░░░░░   0% (Phase 2 切替後)
```

**達成内容 (本セッション)**:
- T080 (T071 caller 注入式 Phase 2 配線 first step) 完了: stub builder + JSON 出力経路確立、 9 metric 全件 stub で smoke 観測経路の足場確保 (Codex Round 1 APPROVED + Warning 2 取込)
- T078 (TradeRecord schema 拡張 + apply_spread_stress 重複解消) 完了: spread_cost / holding_cost field 追加 + skeleton 削除 + broker 経路 (Decimal) との代数等価性 test (Codex Round 2 APPROVED)
- T077 (applied_from_run_id v2 必須化 + T058 docstring 改訂 + calibrate_freeze hot-fix 削除) 完了: type level fail-fast + defense-in-depth 再検証 (Codex Round 2 APPROVED)
- T079 (DST/holiday 連携、 option A 採用) 完了: 現状調査で「既実装」 確定 (= T072 で完了済)、 docs 注記のみで close
- T081 (RunObservabilityReport 9 metric 実値配線、 6 step 内包) を T080 follow-up として skeleton + Open 登録
- T082 (TradeRecord.spread_cost 伝搬経路配線) を T078 follow-up として skeleton + Open 登録

---

## 1. 本セッション完了 TODO 詳細 (4 件 + 2 件後続登録)

### 1.1 T080 (T071 caller stub 配線、 commit `de9b7d7` + `f034d63` + `3b828d8`)

T080a として first step を完了:
- `src/alpha_factory/observability/run_metrics.py`: `build_stub_run_observability_report` + `serialize_run_observability_report` 追加
- `scripts/alpha_factory/run_ga.py`: main 関数末尾で stub builder 呼出 + `reports/run-reports/{run_id}/observability.json` 出力
- 9 metric (= ABDivergence / QForceRecommendation / ArchiveChurn / BypassRatio / SessionEntropy / FeasibleRatio / Selection / InflowConsistency / Failure) を全件 valid status / default 値で構築 (= dataclass invariant 全 PASS)
- test 22 件追加 (= stub builder 13 + serializer 9、 含む dict Decimal/int キー / frozenset 混在 / broker Decimal 等価)
- T081 (= 9 metric 実値配線 6 step 内包) を後続別 TODO で登録

Codex review: Round 1 APPROVED ([Critical] なし、 [Warning] 3 件のうち 2 件取込)。

### 1.2 T078 (TradeRecord schema 拡張、 commit `857eb82` + `1b44e40` + `261a74b`)

- `src/alpha_factory/canonical_metrics.py`: TradeRecord に spread_cost / holding_cost field 追加 (default 0.0、 backward compat) + invariant (finite + >= 0 fail-fast)
- `src/alpha_factory/stage_bc_evaluator.py`: apply_spread_stress skeleton (NotImplementedError) → 正式実装、 broker 経路と代数的に等価
- test 18 件追加 (= TradeRecord 6 + apply_spread_stress 12 件、 含む broker Decimal 等価性 + overflow 境界)
- T082 (= spread_cost 伝搬経路配線、 silent no-op 解消) を後続別 TODO で登録
- docs/alpha_factory/stage-gates.md 更新 (= alpha_factory 経路追記)

Codex review: Round 1 INCONCLUSIVE → Round 2 APPROVED ([Suggestion] 2 件取込 = 文言精度 + broker 等価性 1 件で十分)。

### 1.3 T077 (applied_from_run_id v2 必須化、 commit `c137e09` + `eee05cb` + `4c13b02`)

- `src/alpha_factory/calibrate_gate_history.py`: HistoryRecord.applied_from_run_id を `str | None = None` → `str = ""` (= 必須化)、 __post_init__ T077 invariant (= type 非 str / 空文字 reject)
- `src/alpha_factory/calibrate_freeze.py`: hot-fix 経路 (L155-177) 削除 → set comprehension + defense-in-depth fail-fast、 input invariant 再検証
- T058 detailed-design.md 改訂 (= L930 schema 表で「Round 22 / T077 で必須化」 明記)
- test 7 件追加 (= TestHistoryRecordV2Contract 3 + test_calibrate_freeze T077_null/empty 2 + defense_in_depth 2)
- 既存 test 修正 (= helper sentinel _UNSET 導入、 旧 F15a/F15b 削除、 integration test に必須 field 追加)

Codex review: Round 1 CHANGES_REQUESTED ([Warning] 1 = defense-in-depth) → Round 2 APPROVED ([Suggestion] 1 取込 = defense_in_depth 単体 test 2 件)。

### 1.4 T079 (DST/holiday 連携、 commit `b347c68`)

- 現状調査結果: option A (= BLOCK_BUCKET_RANGES_UTC 固定 + observability_flags + open_minutes 別レイヤー) は **T072 で既に完了済**
  - `compute_observability_flags` (calendar.py L510): DST 検出 + holiday 検出 統合計算
  - `compute_bucket_open_minutes` (calendar.py L531): broker_schedule × BLOCK_BUCKET_RANGES_UTC overlap で open_minutes 計算
  - SessionBlock.observability_flags field: T072 で導入済
  - tests/backtest/test_calendar.py: observability_flags 関連 14 件カバー済
- option B (= dynamic shift) は partition contract 崩壊で不採用、 option C (= adjustment table) は抽象度上昇のみで効果薄
- handoff の申し送り解釈 (= 「BLOCK_BUCKET_RANGES_UTC への DST 例外連携」) が過剰、 既実装で完了
- 実装変更不要、 docs 注記のみで close

---

## 2. cascade port v2 follow-up 全 4 件 整理表

| TODO | 内容 | 状態 | 完了 commit |
|---|---|---|---|
| T077 | applied_from_run_id v2 必須化 | **完了 ✨** | `c137e09` + `4c13b02` (merge) |
| T078 | TradeRecord schema 拡張 + apply_spread_stress 重複解消 | **完了 ✨** | `857eb82` + `261a74b` (merge) |
| T079 | DST/holiday 連携 (option A 採用、 既実装) | **完了 ✨** | `b347c68` (main 直接) |
| T080 | T071 caller stub 配線 (first step、 9 metric stub) | **完了 ✨** | `de9b7d7` + `3b828d8` (merge) |

後続別 TODO (T080 / T078 follow-up):
- T081 (= T080 残 = 9 metric 実値配線 6 step) Open
- T082 (= T078 残 = spread_cost 伝搬経路配線) Open

---

## 3. 残作業 = T081 → T082 → B → GA

### 3.1 T081 (RunObservabilityReport 9 metric 実値配線、 6 step、 High)

設計: `devnotes/20260502-2206-todo-T081-observability-real-values/`
- step 1: ABDivergenceMetric 実値配線
- step 2: ArchiveChurn / BypassRatio + admission-history state file
- step 3: SessionEntropy / FeasibleRatio
- step 4: SelectionMetric
- step 5: InflowConsistency / Failure
- step 6: QForceRecommendation + cross-run state file + T063 配線

各 step を 1 worktree commit ずつ進める運用 (= cascade port v2 同型)。

### 3.2 T082 (TradeRecord.spread_cost 伝搬経路配線、 High)

設計: `devnotes/20260502-2300-todo-T082-spread-cost-propagation/`
- Trade(broker) → TradeRecord(alpha_factory) 変換箇所で float() 伝搬
- apply_spread_stress caller 側で WARN/FAIL ガード追加 (= silent no-op 解消)

### 3.3 B Phase 2 切替コミット (= T081 + T082 完了後)

旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消 (= T076 handoff § 4.1 / § 4.2 参照)。

### 3.4 GA 動作確認 (= B 完了後)

- smoke 5 Run 連続実行 (= DoD 観測経路活用)
- 数値 threshold 確定別 TODO (= calibration data 取得後)
- 実 GA 実行 → live_criteria 達成個体探索

---

## 4. 次セッション着手フロー

### 4.1 推奨次着手: T081 step 1 (ABDivergenceMetric 実値配線)

> 引き継ぎは `devnotes/20260502-2323-followup-progress-handoff/handoff.md` 読んで。 T081 (RunObservabilityReport 9 metric 実値配線、 6 step) の step 1 から実装着手。 `zenigame-fx-alpha-design` で skeleton 設計を本格化 → Codex review → `zenigame-fx-implement` で worktree todo/T081 で順次実装。 step 1 (ABDivergenceMetric) → step 2 (ArchiveChurn/BypassRatio) → step 3-6 と進める。 各 step 完了後に test / Codex review / commit。 全 6 step 完了で T081 close + T082 着手。

### 4.2 各 step の依存関係

- step 1 / 4 / 5 (= ABDivergence / Selection / Inflow+Failure) は **独立** (= 当 Run 内で完結)
- step 2 / 6 (= ArchiveChurn / QForce) は **cross-run state file** が必要 (= permanence + atomic write 設計)
- step 3 (= SessionEntropy / FeasibleRatio) は archive members + StageAControllerState 経路

→ 推奨実装順: step 1 → step 4 → step 5 → step 3 → step 2 → step 6 (= 軽量 → cross-run state file 系で重)

---

## 5. 累積 commit 一覧 (本セッション、 直近 13 件 = 2026-05-02 23:35 更新)

```
b5e9abf docs(devnotes): T077 / T078 / T080 Codex impl-review log を補足追加 (handoff 27b8056 補完)
27b8056 docs(handoff): T077-T080 完了 + T081 / T082 残実装の引き継ぎ handoff (本 handoff 自身)
b347c68 docs(T079): close (Open→Closed) — option A 採用 (= 既実装)
4c13b02 Merge branch 'todo/T077'
eee05cb docs(TODO): T077 close (Open→Closed)
c137e09 feat(T077 PR1): applied_from_run_id v2 必須化 + calibrate_freeze hot-fix 削除
261a74b Merge branch 'todo/T078'
1b44e40 docs(TODO): T078 close + T082 (spread 伝搬) skeleton + Open 登録
857eb82 feat(T078 PR1): TradeRecord schema 拡張 + apply_spread_stress 正式実装
3b828d8 Merge branch 'todo/T080'
f034d63 docs(TODO): T080 close + T081 (実値配線 6 step) skeleton + Open 登録
de9b7d7 feat(T080a PR1): T071 caller stub builder + JSON 出力経路確立
fe997de docs(handoff): T076 完了 handoff
```

本セッション commit 計 13 個 (= T080 3 + T078 3 + T077 3 + T079 1 + handoff 2 + devnotes 補完 1)。 cascade port v2 全体 commit 累計 50+ 個。

### 5.1 補足資料: Codex impl-review log

- T080 (commit `de9b7d7`): `devnotes/20260502-2105-todo-T080/impl-review-round-1.md` (= APPROVED + Warning 3 件のうち 2 件取込)
- T078 (commit `857eb82`): `devnotes/20260502-2213-todo-T078/impl-review-round-{1,2}.md` (= INCONCLUSIVE → APPROVED)
- T077 (commit `c137e09`): `devnotes/20260502-2246-todo-T077/impl-review-round-{1,2}.md` (= CHANGES_REQUESTED → APPROVED + Suggestion 取込)
- T079 (commit `b347c68`): worktree なし (= 現状調査だけで close、 review log なし)

---

## 6. cascade port v2 完了に至るまでの全体経緯 (累積)

1. **Phase 1 設計** (前々々セッション): 18 件全件 Codex APPROVED
2. **Phase 2 配線** (前々セッション系列): 18 TODO 全完了 + 25 PR 全 main fast-forward merge + regression 0
3. **T076 synthesis Round 22 改訂** (前セッション): 5 改訂 + ε で synthesis SSOT が T075 module 詳細設計と完全 1:1 整合
4. **T077-T080 cascade port v2 follow-up** (本セッション): applied_from_run_id 必須化 / TradeRecord schema 拡張 / DST option 確定 / T071 stub 配線 完了
5. **T081 / T082 残実装** (次セッション): 9 metric 実値配線 + spread 伝搬
6. **Phase 2 切替コミット** (T081 / T082 完了後): 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消
7. **smoke 5 Run / 実 GA 動作確認** (Phase 2 切替後): live_criteria 達成個体探索
