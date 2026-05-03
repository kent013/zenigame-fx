# T082 Obsoleted + B Phase 2 切替コミット step 1 skeleton 着手 Handoff

**作成日時**: 2026-05-03 10:23 JST、 **更新**: 2026-05-03 10:35 JST (= B step 1 skeleton 設計 commit)
**Session**: T081 Closed (step 1 only) → T082 構造的 blocker 発見 → T082 Obsoleted → B Phase 2 切替コミット step 1 (canonical_metrics) skeleton 設計 commit
**前 handoff**: `devnotes/20260503-0918-T081-closed-handoff/handoff.md`
**次セッション**: **B Phase 2 切替コミット step 1 を本格化 → Codex review APPROVED → 実装 → main マージ → step 2 へ**

---

## 0. 現在地

```
T081 step 1 (ABDivergenceMetric 実値配線)        ████████████████████ 100% ✨ (Closed、 main マージ済 commit 27acfb3)
T081 step 2-6                                     ░░░░░░░░░░░░░░░░░░░░  Deferred (= 上流 T063-T068 未統合)
T082 (TradeRecord.spread_cost 伝搬経路配線)      ████████████████████ 100% ⚠ (Obsoleted、 前提誤認、 commit ac4ad5f)
B Phase 2 切替コミット (= T063-T068 + canonical_metrics 統合) ░░░░░░░░░░░░░░░░░░░░    0% ← 次主作業
T081 step 2-6 再開 (= B 完了後)                   ░░░░░░░░░░░░░░░░░░░░    0%
GA 動作確認 (smoke 5 Run + 実 GA)                 ░░░░░░░░░░░░░░░░░░░░    0%
```

---

## 1. 本セッション内容 (= T082 着手 → 構造的 blocker 発見 → Obsoleted)

### 1.1 T082 設計再読 + 経路調査

T082 概念設計は 「broker `Trade` → alpha_factory `TradeRecord` 変換箇所」 を前提としていた。

### 1.2 grep 調査結果

```bash
# TradeRecord 構築箇所
find src -type f -name "*.py" -exec grep -l "TradeRecord(" {} \;
→ 結果: 0 file (= test fixture のみ)

# stage_bc_evaluator (= TradeRecord を使う module) の main 経路呼出
grep -rn "evaluate_stage_b_pooled\|evaluate_stage_c_lite\|BCEvaluationInput" src/ scripts/ \
  | grep -v stage_bc_evaluator
→ 結果: 0 件 (= main flow から呼ばれていない)

# stage_gate.py の trade 経路
grep -n "compute_metrics" src/alpha_factory/stage_gate.py
→ 5 箇所、 全て broker.Trade を直接消費 (TradeRecord 経由ではない)
```

**結論**: T082 の前提 「broker Trade → TradeRecord 変換箇所」 は **存在しない**。 該当配線は B Phase 2 切替コミット の範疇。

### 1.3 commit

- `f5586b0` docs(T082): blocker finding (= devnotes/20260503-1020-T082-blocker-finding/finding.md)
- `ac4ad5f` docs(TODO): T082 obsolete (Open → Obsoleted)

---

## 2. 構造的観察 — Phase 1 / Phase 2 の整理

cascade port v2 で導入した **8 module は library-only**、 main flow への統合 (= B Phase 2 切替コミット) が次の必須作業。

| module | library 状態 | main 統合状態 | 統合時期 |
|---|---|---|---|
| canonical_metrics (TradeRecord 等) | ✅ | ❌ | B Phase 2 切替 |
| cpps_archive (ArchiveState, archive_admit, AdmissionReport) | ✅ | ❌ | B Phase 2 切替 |
| nsga2_selection (GenerationSelectionResult) | ✅ | ❌ | B Phase 2 切替 |
| loop_closure (WarmstartReport, warmstart_apply) | ✅ | ❌ | B Phase 2 切替 |
| failure_handling (RunFailureSummary) | ✅ | ❌ | B Phase 2 切替 |
| stage_a_evaluator (T063 StageAControllerState) | ✅ | ❌ | B Phase 2 切替 |
| stage_bc_evaluator (BCEvaluationInput, evaluate_stage_b_pooled, evaluate_stage_c_lite, apply_spread_stress) | ✅ | ❌ | B Phase 2 切替 |
| observability (T071 RunObservabilityReport) | ✅ | ✅ stub builder で main 統合 (T080a) + ABDivergence のみ実値 (T081 step 1) | 残 8 metric は B 完了後 |

**main flow の現状 SSOT** (= 評価フロー):
1. `swim_lane.py` Tier1Lane evaluate ループで `evaluate_stage_a` / `evaluate_stage_b` / `evaluate_stage_c` (= stage_gate.py wrapper) を呼ぶ
2. それぞれが `run_backtest` (broker engine) → `compute_metrics(broker.Trade)` で `BacktestMetrics` 生成
3. `StageResult` (= stage_gate.py の wrapper) を `archive.collect_stage_*` で Parquet に記録
4. `_breed_next_gen` (elite + crossover/mutate) で次世代生成

**Phase 2 完成形** (= B 完了後の SSOT):
1. `evaluate_stage_a` / `evaluate_stage_b_pooled` / `evaluate_stage_c_lite` を canonical_metrics ベース (= TradeRecord) で評価
2. `archive_admit` で AdmissionReport 生成 + ArchiveState 永続化
3. `select_next_generation` (NSGA-II) で次世代生成
4. `warmstart_apply` で DA-from-CA inflow
5. T071 observability 9 metric 全実値で記録

= 大規模な orchestration 切替。 individual TODO で対応するのは構造的に困難。

---

## 3. 次セッション着手フロー: B Phase 2 切替コミット

### 3.1 推奨着手戦略

option 1: **大型 1 セッションで一気に切替**
- 全 module 統合を 1 commit で実施
- 規模感: 1000+ 行変更、 多数 test 修正、 数日セッション
- リスク: regression 重大、 1 commit が大きすぎてレビュー困難

option 2: **段階的 7 step 切替** (= 1 module / 1 step、 cascade port v2 同型)
- step 1: canonical_metrics → main flow (= compute_metrics の TradeRecord 化)
- step 2: stage_bc_evaluator → main flow (= evaluate_stage_b_pooled / evaluate_stage_c_lite の運用)
- step 3: cpps_archive → main flow (= archive_admit / AdmissionReport 経路)
- step 4: stage_a_evaluator (T063) → main flow (= StageAControllerState 永続化)
- step 5: nsga2_selection → main flow (= _breed_next_gen 置換)
- step 6: loop_closure (warmstart) → main flow
- step 7: failure_handling → main flow
- 各 step: 1 worktree commit、 Codex 設計 + 実装 review、 test 全 PASS、 regression 0
- 完了後: T081 step 2-6 を順次再開可能化

→ **option 2 推奨** (= 既存 cascade port v2 / T077-T080 / T081 step 1 と同型のリズム)

### 3.2 各 step の Codex 設計 / 実装 review fence

step 1-7 全てで:
1. zenigame-fx-alpha-design で skeleton → Codex review (gpt-5.3-codex / high) APPROVED
2. zenigame-fx-implement で worktree todo/B-step{N} で実装 → Codex impl-review APPROVED
3. main マージ → 次 step

### 3.3 step 1 (canonical_metrics → main flow) の着手前調査

```bash
# 既存 compute_metrics の signature
grep -n "def compute_metrics" src/backtest/metrics.py

# canonical_metrics の TradeRecord / CanonicalFiveResult の signature
grep -n "class TradeRecord\|class CanonicalFiveResult" src/alpha_factory/canonical_metrics.py

# stage_bc_evaluator.evaluate_canonical_five
grep -n "def evaluate_canonical_five\|class BCEvaluationInput" src/alpha_factory/stage_bc_evaluator.py
```

着手フロー:
- 設計: 既存 `compute_metrics(broker.Trade)` を壊さず、 並列に `compute_metrics_canonical(BCEvaluationInput)` を追加 → caller 側で段階的切替
- LOG_ONLY モードで dual-path 並走 (= 既存と新規両方計算 + 結果 diff log)
- 安定確認後に LOG_ONLY → FAIL_CLOSED 切替 (= 旧実装削除)

= 「Phase 2 切替コミット」 の本質はこの dual-path → FAIL_CLOSED 切替。

---

## 4. 累積 commit 一覧 (本セッション、 main 10 個)

```
ff31f71 docs(B-phase2-step1): canonical_metrics → main flow 統合 skeleton 設計           ← 次主作業 skeleton
9881abe docs(handoff): T082 Obsoleted + B Phase 2 切替コミット を次主作業に再構成
ac4ad5f docs(TODO): T082 obsolete — TradeRecord 経路が main flow に未統合
f5586b0 docs(T082): blocker finding — TradeRecord 経路が main flow に未統合
c54936f docs(handoff): T081 Closed (step 1 only) + step 2-6 deferred + 残作業引き継ぎ
99b5558 docs(TODO): T081 close (Open→Closed)
27acfb3 Merge branch 'todo/T081'
1fffc4b docs(T081): step 2-6 blocker finding
35996b4 feat(T081 step 1): ABDivergenceMetric 実値配線
caeff88 docs(T081): 詳細設計 本格化 (Codex 4 round APPROVED)
```

本セッション commit 計 10 個。 cascade port v2 全体 commit 累計 ~60 個。

---

## 5. 次セッション first prompt 例 (B step 1 本格化 + 実装着手用)

skeleton 設計は本セッションで commit 済 (= `ff31f71`、 `devnotes/20260503-1024-B-phase2-step1-canonical-metrics/`)。 次セッションは **本格化 + Codex review + 実装** から。

```
引き継ぎは devnotes/20260503-1023-T082-obsolete-phase2-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 1 (= canonical_metrics → main flow) の skeleton 設計
(devnotes/20260503-1024-B-phase2-step1-canonical-metrics/) を本格化 → Codex review →
実装 → main マージ。

着手前調査 (= skeleton § 9 後続セッション昇格手順):
1. T070 calendar.py の関数 grep + 名称確認 (= assign_session_bucket_and_business_day_index /
   compute_business_day_universe の実存確認)
2. evaluate_canonical_five の signature 詳細確認 (= thresholds 必須か?)
3. broker.Trade の field 全件確認 (= entry_time / exit_time の TZ awareness)

本格化:
4. _try_evaluate_canonical_five_safe の例外 fallback ロジック詳細化
5. phase2.canonical_metrics_mode config の loader 経路詳細化

Codex review:
6. zenigame-fx-codex-review で gpt-5.3-codex / high、 label=design-review
   - 概念設計 + 詳細設計を Round 1 で APPROVED まで合議
   - LOG_ONLY mode で既存判定不変が担保されているか重点確認
   - dual-path 計算 overhead が許容範囲か確認

実装:
7. zenigame-fx-implement で worktree todo/B-step1
   - canonical_adapter.py 新規 + stage_gate.py に dual-path 配線追加
   - phase2.canonical_metrics_mode config 追加
   - adapter unit test + dual-path integration test
   - 既存 test 全 PASS (= regression 0)
   - ruff / mypy clean

完了:
8. impl-review (= gpt-5.3-codex / high、 label=impl-review) APPROVED → main マージ → step 2 へ
```

---

## 6. cascade port v2 完了に至るまでの全体経緯 (累積)

1. **Phase 1 設計** (前々々々々セッション): 18 件全件 Codex APPROVED
2. **Phase 2 配線** (前々々々セッション系列): 18 TODO 全完了 + 25 PR 全 main fast-forward merge + regression 0
3. **T076 synthesis Round 22 改訂** (前々々セッション): synthesis SSOT が T075 module 詳細設計と完全 1:1 整合
4. **T077-T080 cascade port v2 follow-up** (前々セッション): applied_from_run_id 必須化 / TradeRecord schema 拡張 / DST option 確定 / T071 stub 配線 完了
5. **T081 設計 + step 1 実装 + 部分 close** (前 + 本セッション): 詳細設計 4 round + 実装 2 round APPROVED、 step 2-6 は上流未統合により deferred
6. **T082 着手 → Obsoleted** (本セッション): TradeRecord 経路未統合により前提誤認、 Obsoleted 移動
7. **B Phase 2 切替コミット** (次セッション以降、 7 step segmentation 推奨): canonical_metrics / stage_bc_evaluator / cpps_archive / stage_a_evaluator (T063) / nsga2_selection / loop_closure / failure_handling を main flow に統合
8. **T081 step 2-6 再開** (B 完了後): 残 8 metric を実値配線
9. **smoke 5 Run / 実 GA 動作確認** (B 完了後): live_criteria 達成個体探索

---

## 7. worktree 状態

`worktrees/todo-T081` は **保持** (= 必要に応じて削除可、 B Phase 2 切替コミットでは新 worktree `todo/B-step1` 等を作成)。

```bash
# T081 worktree 削除する場合 (= 不要になったため)
git worktree remove worktrees/todo-T081
git branch -d todo/T081
```
