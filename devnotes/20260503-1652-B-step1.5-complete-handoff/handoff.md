# B step 1.5 Complete (Stage B IS / Stage C base dual-path 拡張) + step 2 引き継ぎ Handoff

**作成日時**: 2026-05-03 16:52 JST
**Session**: B Phase 2 切替コミット step 1.5 完了 (= 概念設計 3 round + 詳細設計 4 round + 実装 3 round Codex APPROVED + main マージ)
**前 handoff**: `devnotes/20260503-1414-B-step1-complete-handoff/handoff.md`
**次セッション**: **B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合) または step 1.6 (= Stage B per-fold dual-path 拡張)**

---

## 0. 現在地

```
T081 step 1 (ABDivergenceMetric 実値配線)        ████████████████████ 100% ✨ (Closed、 main マージ済 commit 27acfb3)
T081 step 2-6                                     ░░░░░░░░░░░░░░░░░░░░  Deferred
T082 (TradeRecord.spread_cost 伝搬経路配線)      ⚠ Obsoleted (前提誤認)
B step 1 (canonical_metrics → main flow 統合)    ████████████████████ 100% ✨🎉 (前 session、 main マージ済 commit 9bc6a02)
B step 1.5 (Stage B IS / Stage C base dual-path) ████████████████████ 100% ✨🎉 (本セッション、 main マージ済 commit 6276d58)
B step 1.6 (Stage B per-fold dual-path)          ░░░░░░░░░░░░░░░░░░░░    0% ← 次選択肢 A
B step 2 (stage_bc_evaluator main flow 統合)     ░░░░░░░░░░░░░░░░░░░░    0% ← 次選択肢 B (推奨)
B step 3-7                                        ░░░░░░░░░░░░░░░░░░░░    0%
T081 step 2-6 再開 (B 完了後)                     ░░░░░░░░░░░░░░░░░░░░    0%
GA 動作確認 (smoke 5 Run + 実 GA)                ░░░░░░░░░░░░░░░░░░░░    0%
```

---

## 1. 本セッション完了内容

### 1.1 B step 1.5 設計 (概念設計 + 詳細設計、 Codex 7 round 議論)

設計ファイル: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/`

#### 概念設計 (Codex Round 1-3、 Round 3 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] 3 件 (step 2 前提主張過剰 / smoke 5 calibration 根拠不足 / メモリ概算甘い) + [Warning] 8 件 |
| 2 | CHANGES_REQUESTED | [Critical] Stage A 挙動変更 (= window_days を business day 基準化) は step 1.5 の B/C 観測拡張スコープを越える |
| 3 | **APPROVED** | Stage A 挙動変更撤回、 全 Stage で step 1 と同じ calendar day 基準維持に scope を limit |

#### 詳細設計 (Codex Round 1-4、 Round 4 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] 5 件 (helper 入力契約明文化不足 / 広域 except / ゴールデン比較不足 / test 計画不足 / archive schema 伝搬漏れ) |
| 2 | CHANGES_REQUESTED | logger kwargs key `genome_name` vs `genome` 契約不一致 / A1 と §7.5 不一致 / テストケース数揺れ |
| 3 | CHANGES_REQUESTED | § 7.6 に `genome_name + stage` 残存 / A1 と § 7.5 分離不足 / § 10 に「新規 10 ケース」残存 |
| 4 | **APPROVED** | 残 Warning は実装時の細部修正範囲 |

設計の主要決定:
- **scope**: Stage B IS monitor + Stage C base evaluation のみ dual-path 配線追加 (= Stage A は step 1 から完全不変)
- **adapter 凍結**: `canonical_adapter.py` は変更なし (step 1 で凍結済)
- **window_days**: step 1 と同じ calendar day 基準維持 (= 全 Stage 統一の business day 基準化は別 step)
- **commit 分離**: commit A (= rename pure refactor) + commit B (= behavioral wiring)

### 1.2 B step 1.5 実装 + Codex 実装 review (Round 3 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] A5 (fixture-locked golden) が `finite` チェック程度で固定値比較していない、 [Warning] 2 件 (canonical raise 時の deep equality / log 検証文字列ベース弱い) |
| 2 | CHANGES_REQUESTED | reports/calibrate-gate/history.jsonl と reports/run-reports/run-1/diagnostics/stage_a_provenance.parquet が staged に混入 (= scope 外) |
| 3 | **APPROVED** | reports/ unstage で scope 外混入解消、 step 1.5 完了 |

主要変更 (= worktree commit 1f85f4e (commit B) + 15a9803 (commit A)、 main merge commit 6276d58):

#### commit A (15a9803): pure refactor
- `_build_stage_a_canonical_thresholds` → `_build_canonical_thresholds_for_window` rename
- 1 caller のみ更新、 動作不変、 既存 12 ケース全 PASS

#### commit B (1f85f4e): behavioral wiring
- `evaluate_stage_b` の IS monitor 区画 (= L824-L862) に dual-path 配線追加 (`stage_label="B_IS"`、 `window_days=stage_b_window_months * 30`)
- `evaluate_stage_c` の base evaluation 区画 (= L1162-L1209) に dual-path 配線追加 (`stage_label="C_base"`、 `window_days=stage_c_holdout_days`)
- log 呼出も try/except で完全隔離 (= step 1 と同型)
- canonical_sidecar は payload 非添付 (= archive Parquet schema 不変)

key design (= 詳細設計 § 5-6 反映):
- step 1 で凍結した adapter / helper を完全再利用 (= adapter / helper 凍結維持)
- LOG_ONLY mode で既存判定経路完全に不変 (= regression 0)
- Stage A は step 1 から完全不変 (= 既存 12 ケース PASS で確認)

テスト追加 (= 21 ケース、 計 33 ケース全 PASS、 regression 0):
- Stage B IS dual-path 7 ケース (regression / log isolation × 2 / propagation / log key 含有 / 異常系空 / 単一 trade)
- Stage C base dual-path 7 ケース (Stage B IS と同型)
- ゴールデン回帰 6 ケース (= acceptance A5、 fixture-locked 期待値比較、 `pytest.approx(abs=1e-9)`)
- 並列 log key 一意性 1 ケース

最終 test 結果: **33 passed** (= step 1 12 + step 1.5 21) / ruff / mypy clean

### 1.3 main マージ + worktree クリーンアップ

- worktree commit `15a9803` (commit A) + `1f85f4e` (commit B) を main に no-ff merge (`6276d58`)
- worktree `todo-T083` クリーンアップ + branch 削除済
- worktree `todo-T081` は引き続き保持 (= 引き継ぎ)

---

## 2. 累積 commit 一覧 (本セッション、 main 6 個)

```
6276d58 Merge branch 'todo/T083'                                                 ← main マージ
3822b24 docs(TODO): T083 B-phase2-step1.5 Closed (impl-review Round 3 APPROVED)  ← TODO クローズ
1f85f4e feat(B step 1.5): Stage B IS monitor + Stage C base に dual-path 配線追加 (Codex impl-review Round 3 APPROVED)  ← 実装 commit B
15a9803 refactor(B step 1.5): rename _build_stage_a_canonical_thresholds → _build_canonical_thresholds_for_window  ← 実装 commit A
dc98f0c docs(TODO): T083 B-phase2-step1.5 (Stage B IS / Stage C base dual-path) Open 追加
1ccb26d docs(B-phase2-step1.5): Stage B IS / Stage C base dual-path 拡張 設計完了
```

本セッション commit 計 6 個 (= 設計 1 + TODO 登録 1 + commit A 1 + commit B 1 + TODO クローズ 1 + merge 1)。 cascade port v2 全体 commit 累計 ~72 個。

### 2.1 補足資料

- 概念設計 review: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/conceptual-review-round-{1,2,3}.md`
- 詳細設計 review: `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-review-round-{1,2,3,4}.md`
- 実装 review: `devnotes/20260503-1610-todo-T083/impl-review-round-{1,2,3}.md`

---

## 3. 次セッション着手フロー

### 3.1 推奨次着手: 2 つの選択肢

#### 選択肢 A: B step 1.6 (= Stage B per-fold dual-path 拡張)

**scope**: Stage B 5 fold それぞれで dual-path log を追加。 per-fold thresholds 構築方法 (= per-fold or pooled) の検討要。

- 追加実装: `evaluate_stage_b` の per-fold OOS 区画 (= stage_gate.py L859-L913) に同型 dual-path 配線
- adapter は変更なし (= step 1 で凍結再利用)
- per-fold thresholds は Stage B 特有 (= 5 fold それぞれで thresholds を構築 or pooled で 1 つ)
- 注意: `B_fold` stage_label を新設、 既存 `B_IS` と log 系列が独立

**規模**: 中 (= per-fold thresholds 構築方法を検討する分の設計コスト追加)

#### 選択肢 B: B step 2 (= stage_bc_evaluator main flow 統合) — **推奨**

**scope**: stage_bc_evaluator の `evaluate_stage_b_pooled` / `evaluate_stage_c_lite` を main flow から呼出 (= LOG_ONLY mode で legacy と並走、 step 1.5 までで dual-path 観測点が 3 軸 (A / B_IS / C_base) で揃ったため、 ここから判定切替の前提 calibration が始められる)。

- step 1.6 を skip して step 2 で同時に Stage B/C 統合する選択
- archive Parquet schema 拡張時に Parquet writer direct test 追加 (= Codex Round 3 [Suggestion] 取込、 step 1 から継続課題)

**規模**: 大 (= stage_gate.py の Stage B/C ハンドラを stage_bc_evaluator caller に置換)

### 3.2 選択基準

- 段階的価値最大化なら **選択肢 A** (= step 1.6) を先に: Stage B fold 単位の dual-path 観測を早期 main 化
- 全 Stage 一気に統合するなら **選択肢 B** (= step 2 で全 Stage 切替): step 1.6 は skip、 step 1.5 の dual-path 観測 (= A / B_IS / C_base) で十分な calibration 起点

**推奨**: **選択肢 B (= step 2)** を先に
- step 1.5 で dual-path 観測の主要 3 軸 (A / B_IS / C_base) が揃った
- step 1.6 (= per-fold) は別途観測軸であり、 step 2 (= 判定切替) と独立に着手可能
- step 2 完了後に step 1.6 を別 step として扱う方が、 1 step 1 commit のリズムを維持しやすい

### 3.3 各 step の Codex 設計 / 実装 review fence

両選択肢で共通:
1. zenigame-fx-alpha-design で skeleton → Codex review (gpt-5.4 / medium、 gpt-5.3-codex / high) APPROVED
2. zenigame-fx-implement で worktree todo/B-step{1.6,2} で実装 → Codex impl-review APPROVED
3. main マージ → 次 step

---

## 4. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path LOG_ONLY) | canonical_metrics | **完了** (commit 9bc6a02) |
| **step 1.5 (本)** ✨ | Stage B IS monitor + Stage C base dual-path 拡張 (adapter 凍結再利用) | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 | Stage B per-fold dual-path 拡張 (= per-fold thresholds 構築方法検討) | (stage_gate.py + canonical_metrics 連携) | 次選択肢 A |
| step 2 | stage_bc_evaluator → main flow (= evaluate_stage_b_pooled / evaluate_stage_c_lite 運用) | stage_bc_evaluator | **次選択肢 B (推奨)** |
| step 3 | cpps_archive → main flow (= archive_admit / AdmissionReport 経路) | cpps_archive | 後続 |
| step 4 | stage_a_evaluator (T063) → main flow (= StageAControllerState 永続化) | stage_a_evaluator | 後続 |
| step 5 | nsga2_selection → main flow (= _breed_next_gen 置換) | nsga2_selection | 後続 |
| step 6 | loop_closure (warmstart) → main flow | loop_closure | 後続 |
| step 7 | failure_handling → main flow | failure_handling | 後続 |

**完了後**: T081 step 2-6 順次再開可能化 + smoke 5 Run / 実 GA 動作確認

---

## 5. 次セッション first prompt 例

### B step 2 (推奨) 着手の場合

```
引き継ぎは devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合) を実装着手。

着手前調査:
1. src/alpha_factory/stage_bc_evaluator.py の signature と既存 API
   (= evaluate_stage_b_pooled / evaluate_stage_c_lite の引数 / 戻り値構造)
2. 現在の evaluate_stage_b / evaluate_stage_c (stage_gate.py:778-989, 1123-1378)
   が stage_bc_evaluator に置換可能な構造になっているかの調査
3. archive Parquet schema 拡張の必要性 (= canonical_sidecar 永続化要否)
   と既存 28+ カラム fixed schema との整合

設計:
4. step 1 / step 1.5 で凍結した canonical_adapter.py / helper を再利用
5. stage_bc_evaluator caller として stage_gate.py を簡略化
   (= legacy 評価ロジックを stage_bc_evaluator に委譲)
6. LOG_ONLY → FAIL_CLOSED 切替戦略の段階化

Codex review APPROVED → 実装 → main マージ → step 3 へ。
```

### B step 1.6 (選択肢 A) 着手の場合

```
引き継ぎは devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 1.6 (= Stage B per-fold dual-path 拡張) を実装着手。

着手前調査:
1. evaluate_stage_b の per-fold OOS 区画 (stage_gate.py:859-913) の構造確認
2. per-fold thresholds 構築方法の比較 (= per-fold で個別構築 vs pooled で 1 つ)
3. 5 fold × dual-path log の logging volume / pattern 検討

設計:
4. canonical_adapter.py は **改変禁止** (= step 1 で凍結維持)
5. _try_evaluate_canonical_five_safe / _log_canonical_dual_path を per-fold OOS にも適用
6. stage_label="B_fold" で B_IS と区別 (= § 4.6 ログ命名規約 SSOT 準拠)

Codex review APPROVED → 実装 → main マージ → step 2 へ。
```

---

## 6. 残課題・運用観測 follow-up (= step 1.5 から繰り越し)

詳細設計 § 12 follow-up 反映:

1. **canonical 失敗件数閾値ベースの fail-fast サーキットブレーカ**: 連続 N 回 canonical 計算失敗で GA Run を fail-fast。 step 1.5 では WARN log のみ
2. **CI メモリ閾値ガード**: smoke 5 Run の peak RSS / wall time を CI で監視。 step 1.5 では手動実測 (= acceptance B2)
3. **canonical sidecar archive Parquet schema 拡張**: 永続化層への canonical 値書き込み (= step 3 cpps_archive 統合と合わせて検討)
4. **Stage A/B/C 例外注入の同型性 meta-test**: 同 input fixture で A/B/C 全てで例外注入し出力同型性を比較
5. **smoke 5 Run の peak RSS 実測** (= acceptance B2): step 1.5 では未実測、 別計画で実 GA Run 時に確認
6. **smoke 5 Run の所要時間が step 1 比 ±20% 以内** (= acceptance B3): 同上
