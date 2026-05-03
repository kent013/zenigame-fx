# T081 step 2-6 Blocker Finding — 上流モジュール未統合の構造的問題

**作成日時**: 2026-05-03 09:10 JST
**判定**: T081 step 2-6 は **現状 main 実装では実値配線不可能** (= 上流の T063-T068 モジュールが run_ga.py に未統合)

---

## 1. Fact (調査結果、 grep ベース)

T081 概念設計が **「T066 archive operations で AdmissionReport を生成 (= 既存)」** と前提していたが、 grep 検証の結果 **既存ではない**。

### 1.1 各 step 依存モジュールの統合状態

| step | 必要 SSOT | run_ga.py 統合状態 |
|---|---|---|
| step 1 ✅ 完了 | `evaluate_stage_a/b` payload (= fitness_pen / median_oos_sharpe) | **統合済** (= swim_lane 経由) |
| step 2 | `archive_admit(...) → AdmissionReport` (cpps_archive) | **未統合** (= cpps_archive の `archive_admit` は cpps_archive.py 内でのみ呼出、 run_ga.py / swim_lane.py 経路に存在しない) |
| step 3 | T063 `StageAControllerState` + T064 `session_pass_pattern` | **未統合** (= run_ga.py に StageAControllerState 参照なし、 archive Parquet schema に session_pass_pattern field なし) |
| step 4 | T065 `GenerationSelectionResult` (NSGA-II selection) | **未統合** (= run_ga.py は `_breed_next_gen` で elite + crossover/mutate を使用、 NSGA-II の `select_next_generation` 未呼出) |
| step 5 | T067 `WarmstartReport` (loop_closure) + T068 `RunFailureSummary` (failure_handling) | **未統合** (= run_ga.py に loop_closure / warmstart import なし、 failure_handling 経路も未配線) |
| step 6 | step 1 の AB divergence + cross-run state file | **依存元 (step 1) は OK、 但し state file 単体配線は意味薄** (= AB 乖離を q_force へ反映する側 = T063 が未統合) |

### 1.2 検証 grep コマンド結果

```bash
# step 2: archive_admit 呼出
grep -rn "archive_admit\b" src/ scripts/ | grep -v cpps_archive.py
→ 結果: tests/alpha_factory/test_loop_closure.py の hasattr 確認のみ (= 本番経路ゼロ)

# step 3: StageAControllerState
grep -n "StageAControllerState" scripts/alpha_factory/run_ga.py
→ 結果: 0 件

# step 4: GenerationSelectionResult / nsga2 import
grep -n "nsga2\|GenerationSelectionResult" scripts/alpha_factory/run_ga.py
→ 結果: 0 件 (= observability/run_metrics.py の type 参照のみ)

# step 5: loop_closure / WarmstartReport / RunFailureSummary
grep -n "loop_closure\|WarmstartReport\|RunFailureSummary" scripts/alpha_factory/run_ga.py
→ 結果: 0 件
```

---

## 2. Interpretation (解釈)

### 2.1 概念設計の前提誤認

T081 概念設計 (`devnotes/20260502-2206-todo-T081-observability-real-values/conceptual-design.md`) は以下を前提としていた:

> 「T066 archive operations (= admission / eviction) で `AdmissionReport` を生成 + 直近 N Run の sequence を state file に永続化」

ここで **「= 既存」** と暗黙的に主張されているが、 grep 結果はこれが **誤認** であることを示す。 cpps_archive.py の `archive_admit` 関数は library として存在するが、 run_ga.py / swim_lane.py / GenomeArchive (archive.py) の orchestration に **wired in されていない**。

### 2.2 T063-T068 は library-only モジュール

これらは Phase 1 (= 設計 + 単体テスト) で作られた library 群で、 Phase 2 (= run_ga.py 統合) は handoff で 「Phase 2 切替コミット (B)」 と呼ばれている残作業に含まれる。 即ち T081 の前提とした「Phase 2 配線済」 は実際には未完了。

### 2.3 step 1 だけが独立して可能だった理由

step 1 (ABDivergenceMetric) は:
- `evaluate_stage_a` payload の `fitness_pen` (= Stage A 評価の existing output)
- `evaluate_stage_b` payload の `median_oos_sharpe` (= Stage B 評価の existing output)

の 2 つしか使わない。 これらは **既に main flow で生成されている値** なので、 swim_lane 経由で集約するだけで実値を取得できた。

step 2-6 は逆に T063-T068 の **新規 module output** を要求するため、 まず module 統合が必要。

---

## 3. 影響と選択肢

### 3.1 T081 完了の選択肢

| option | 内容 | コスト | 取得価値 | 推奨 |
|---|---|---|---|---|
| A: T081 を step 1 のみで close | step 2-6 を別 TODO として分離、 T081 は step 1 commit のみで close + main マージ | 小 | step 1 の AB divergence 観測値が main で利用可能になる | ✅ **推奨** |
| B: T081 scope を拡大して上流統合も含む | step 2-6 着手前に cpps_archive / nsga2_selection / loop_closure / failure_handling / stage_a_evaluator (T063) の統合を実施 (= Phase 2 切替コミット の前倒し) | 大 (5+ 統合 TODO 相当、 数セッション分) | T081 完了時に 9 metric 全実値、 Phase 2 切替も近づく | ⚠ 過大スコープ、 1 TODO 範疇外 |
| C: step 2-6 を stub 維持で close | 詳細設計の skeleton を「Phase 2 切替待ち」 と明記、 step 2-6 は別 TODO として登録 | 小 | step 1 と同じく観測経路の存在は保証 | △ A と本質同じ |

### 3.2 推奨: option A

理由:
1. **設計と実装の乖離を honest に認識**: 概念設計の「= 既存」 前提は調査不足だった、 main 実装と一致する形に scope を絞る
2. **段階的価値提供**: step 1 のみでも AB divergence が観測可能、 後続 Phase 2 切替コミットで残 8 metric を実値化
3. **次セッション以降の見通し**: B Phase 2 切替コミット (= T063-T068 統合) を T081 残部分のブロッカー解消として再定義
4. **過剰複雑化禁止 (使命書 禁止事項 5)**: 1 TODO で 5 module 統合 + 観測配線の同時実施は過剰

---

## 4. 推奨次アクション

### 4.1 即時 (本セッション残)

1. ✅ 本 finding を commit して durable に
2. T081 を step 1 commit (= worktree commit `35996b4`) で close する方針に切替
   - main マージ + `/zenigame-fx-todo-close T081`
3. step 2-6 の skeleton 設計は **再利用可能な形で残す** (= 後続 TODO で参照)
4. handoff を更新して step 2-6 のブロッカー状況を申し送り

### 4.2 後続セッション

1. **B Phase 2 切替コミット (handoff で既述)** を再構成:
   - T063 stage_a_evaluator 統合 → run_ga.py で StageAControllerState 保持
   - T064 session_pass_pattern 経路: archive Parquet schema 拡張 or sidecar 経路
   - T065 NSGA-II selection 統合 → run_ga.py の `_breed_next_gen` を `select_next_generation` で置換
   - T066 archive_admit 統合 → swim_lane / run_ga.py で archive_admit 呼出経路追加
   - T067 loop_closure / warmstart 統合
   - T068 failure_handling 統合
2. 各統合完了後、 対応する **T081 step 2-6 相当の観測配線** を別 TODO として実施

### 4.3 step 2-6 が再開可能になる条件

| step | 再開条件 |
|---|---|
| step 2 | archive_admit が run_ga.py 経由で呼び出され AdmissionReport が生成される |
| step 3 | StageAControllerState が run_ga.py で保持される、 archive members に session_pass_pattern field が追加される |
| step 4 | run_ga.py の selection が `select_next_generation(GenerationSelectionResult)` に置換される |
| step 5 | run_ga.py で WarmstartReport / RunFailureSummary が生成される |
| step 6 | step 2 完了 + T063 配線が完了 (= q_force 自動補正経路) |

---

## 5. 参考資料

- T081 詳細設計 (Codex 4 round APPROVED): `devnotes/20260502-2206-todo-T081-observability-real-values/detailed-design.md`
- T081 step 1 完了 commit: `35996b4` (worktree todo/T081)
- T081 step 1 完了 handoff: `devnotes/20260503-0132-T081-step1-complete-handoff/handoff.md`
- 前々セッション handoff (= Phase 2 切替コミット 申し送り): `devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md` § 4.1 / § 4.2

---

## 6. Codex / human review 観点

本 finding は **観察事実 (grep 結果)** と **解釈 (= 概念設計の前提誤認)** を分離して記載 (C6 規範)。
- Fact: § 1
- Interpretation: § 2

判定:
- T081 step 1: **APPROVED** (= 既に commit `35996b4` で完了)
- T081 step 2-6: **INCONCLUSIVE** (= 上流統合待ち、 ブロッカー)
- 推奨次アクション: option A (= step 1 のみで T081 close、 step 2-6 を後続別 TODO として整理)
