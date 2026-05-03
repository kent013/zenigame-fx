# B step 1.6 Complete (Stage B per-fold dual-path 拡張) + step 2 引き継ぎ Handoff

**作成日時**: 2026-05-03 21:55 JST
**Session**: B Phase 2 切替コミット step 1.6 完了 (= 概念設計 2 round + 詳細設計 2 round + 実装 2 round Codex APPROVED + main マージ)
**前 handoff**: `devnotes/20260503-1652-B-step1.5-complete-handoff/handoff.md`
**次セッション**: **B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合)**

---

## 0. 現在地

```
T081 step 1 (ABDivergenceMetric 実値配線)        ████████████████████ 100% ✨ (Closed、 main commit 27acfb3)
T081 step 2-6                                     ░░░░░░░░░░░░░░░░░░░░  Deferred
T082 (TradeRecord.spread_cost 伝搬経路配線)      ⚠ Obsoleted (前提誤認)
B step 1 (canonical_metrics → main flow 統合)    ████████████████████ 100% ✨🎉 (main commit 9bc6a02)
B step 1.5 (Stage B IS / Stage C base dual-path) ████████████████████ 100% ✨🎉 (main commit 6276d58)
B step 1.6 (Stage B per-fold dual-path)          ████████████████████ 100% ✨🎉 (本セッション、 main commit 1dadc8b)
B step 2 (stage_bc_evaluator main flow 統合)     ░░░░░░░░░░░░░░░░░░░░    0% ← 次推奨
B step 3-7                                        ░░░░░░░░░░░░░░░░░░░░    0%
T081 step 2-6 再開 (B 完了後)                     ░░░░░░░░░░░░░░░░░░░░    0%
GA 動作確認 (smoke 5 Run + 実 GA)                ░░░░░░░░░░░░░░░░░░░░    0%
```

---

## 1. 本セッション完了内容

### 1.1 B step 1.6 設計 (Codex 4 round)

設計ファイル: `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/`

#### 概念設計 (Codex Round 1-2、 Round 2 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] 3 件 (step 2 前提主張過剰 / dual-path が fold outer try 内で例外時に fold 判定干渉 / 前提表混在) + [Warning] 多数 |
| 2 | **APPROVED** | scope を「Stage B side calibration data 拡充」に下げる、 dual-path を別 try で物理隔離、 前提表を 4 段階 (Verified/Unverified/False) で分解 |

#### 詳細設計 (Codex Round 1-2、 Round 2 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] 3 件 (5 fold 固定前提誤り / D3 test の helper 無条件 raise が B_IS と衝突 / 5 fold 固定 log content test 不整合) |
| 2 | **APPROVED** | 全表記を `n_fold` 動的記述に変更、 D3 test を `stage_label='B_fold'` 限定 raise wrapper に変更、 9 ケース → 表記整合 patch で確定 |

設計の主要決定:
- **scope**: Stage B per-fold OOS (= n_fold 動的、 各 fold) の dual-path 観測拡張のみ (= 任意・有益、 step 2 を block しない)
- **adapter / helper 凍結**: step 1 / 1.5 の helper を完全再利用、 `_log_canonical_dual_path` のみ optional kwarg `fold_index` 追加
- **per-fold thresholds**: per-fold 個別構築 (Option 1)、 同入力 → 同出力 deterministic
- **物理隔離**: dual-path を **legacy fold 計算後** の **別 try ブロック**、 fold_sharpe / fold_reason / reason_counts 完全不変
- **stage_label**: `"B_fold"` + `fold` kwargs key (= `0..n_fold-1`)、 `fold_index=None` で B_fold は ValueError

### 1.2 B step 1.6 実装 + Codex 実装 review (Round 2 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Warning] D1 log helper isolation の deep equality 不足、 [Suggestion] B_IS / C_base no-fold-kwarg test |
| 2 | **APPROVED** | log helper isolation を disabled baseline deep equality 比較に強化、 B_IS / C_base no-fold-kwarg test 追加 (= 10 ケース目)、 表記「9 ケース」→「10 ケース」 patch |

主要変更 (= worktree commit `7c9c06d`、 main merge commit `1dadc8b`):

#### `_log_canonical_dual_path` 拡張 (stage_gate.py:170-235)
- optional kwarg `fold_index: int | None = None` 追加
- B_fold で必須 (= `stage_label=='B_fold' and fold_index is None` で `ValueError` raise)
- canonical_skipped=True path でも fold key 出力
- 既存 33 caller (= Stage A / B_IS / C_base) は完全互換

#### `evaluate_stage_b` per-fold dual-path 配線 (stage_gate.py:920-1010)
- legacy fold 計算と dual-path を **2 つの別 try ブロック** で物理分離
- legacy 計算成功時のみ dual-path 試行 (= `fold_bt is not None` ガード)
- dual-path の二重 try (= helper 例外 + log 例外) で多層防御
- `fold_sharpe` / `fold_reason` / `reason_counts` は legacy try 内のみ書き換え

key design (= 詳細設計 § 5 反映):
- step 1 / 1.5 で凍結した adapter / helper を完全再利用
- LOG_ONLY mode で既存判定経路完全に不変 (= regression 0)
- per-fold thresholds は同 live_criteria + 同 wf_test_days で n_fold 回構築 (= deterministic equality)

テスト追加 (= 10 ケース、 計 43 ケース全 PASS、 regression 0):
- regression 0 (= legacy payload 完全不変、 acceptance A1)
- log isolation × 2 (canonical raise: stage_label='B_fold' 限定 wrapper / log helper raise: deep equality 比較)
- propagation (= disabled mode で skip)
- log content (= n_fold_expected 動的取得、 各 fold 別 entry)
- ValueError on B_fold without fold_index (= acceptance D5)
- golden 値固定 (= 1 fold 代表、 acceptance A5)
- 後方互換 × 2 (= Stage A / Stage B IS / Stage C base の fold= 不在確認)
- C5 (canonical_skipped=True path でも fold kwarg 必須)

最終 test 結果: **43 passed** (= step 1 12 + step 1.5 21 + step 1.6 10) / ruff / mypy clean、 alpha_factory 全 2172 passed (= step 1.5 比 +9 ケース)

### 1.3 main マージ + worktree クリーンアップ

- worktree commit `7c9c06d` を main に no-ff merge (`1dadc8b`)
- worktree `todo-T084` クリーンアップ + branch 削除済
- worktree `todo-T081` は引き続き保持

---

## 2. 累積 commit 一覧 (本セッション、 main 5 個)

```
1dadc8b Merge branch 'todo/T084'                                            ← main マージ
caaf912 docs(TODO): T084 B-phase2-step1.6 Closed (impl-review Round 2 APPROVED)
7c9c06d feat(B step 1.6): Stage B per-fold dual-path 配線追加 (Codex impl-review Round 2 APPROVED)  ← worktree commit
3c22317 docs(TODO): T084 B-phase2-step1.6 (Stage B per-fold dual-path) Open 追加
86ea6ae docs(B-phase2-step1.6): Stage B per-fold dual-path 拡張 設計完了
```

本セッション commit 計 5 個 (= 設計 + TODO 登録 + 実装 + TODO クローズ + merge)。 cascade port v2 全体 commit 累計 ~77 個。

### 2.1 補足資料

- 概念設計 review: `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/conceptual-review-round-{1,2}.md`
- 詳細設計 review: `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-review-round-{1,2}.md`
- 実装 review: `devnotes/20260503-2129-todo-T084/impl-review-round-{1,2}.md`

---

## 3. 次セッション着手フロー

### 3.1 推奨次着手: B step 2 (= stage_bc_evaluator main flow 統合)

step 1.5 / 1.6 で **dual-path 観測点が 4 系列 (= A / B_IS / B_fold / C_base) で揃った** ため、 stage_bc_evaluator の main flow 統合に進む準備が整った。

ただし、 Stage C cross_pair (ii-lite) は依然として未観測 (= step 2 以降の mission 必須軸として残る)。

#### scope 候補

**選択肢 X: B step 2 (= stage_bc_evaluator main flow 統合)** — 推奨
- stage_bc_evaluator の `evaluate_stage_b_pooled` / `evaluate_stage_c_lite` を main flow から呼出
- LOG_ONLY mode で legacy と並走 (= step 1.5 / 1.6 の dual-path log と calibration data として比較)
- 規模: 大 (= stage_gate.py の Stage B/C ハンドラを stage_bc_evaluator caller に置換)
- archive Parquet schema 拡張時に Parquet writer direct test 追加 (= step 1 から継続課題)

**選択肢 Y: Stage C stress / cross_pair の dual-path 拡張**
- Stage C の stress test (= spread_stress_multiplier 適用後 backtest) に dual-path 配線
- Stage C cross_pair (= shadow only) に dual-path 配線
- 規模: 中 (= stage_gate.py の Stage C stress / cross_pair 区画拡張)
- step 2 着手前により完全な calibration data が揃う

**選択肢 Z: T081 step 2-6 再開**
- B step 1-1.6 で前提条件達成、 T081 ABDivergenceMetric の後続 step 再開可能化
- 規模: 中〜大

#### 推奨判断

**選択肢 X (= step 2)** を推奨。 step 1.5 / 1.6 で観測 data が揃い、 step 2 calibration の基礎ができたため。 ただし step 2 は規模 大なので、 「ゆっくり・確実に」原則を守って:
- 着手前調査を充実させる (= stage_bc_evaluator の API / 既存 evaluate_stage_b/c の置換可能性)
- 設計を概念 → 詳細で 2 段階に分ける
- worktree で commit を細分化 (= 必要なら commit A/B/C で分離)

### 3.2 各 step の Codex 設計 / 実装 review fence

選択肢 X / Y で共通:
1. zenigame-fx-alpha-design で skeleton → Codex review (gpt-5.4 / medium、 gpt-5.3-codex / high) APPROVED
2. zenigame-fx-implement で worktree todo/B-step{2,1.7} で実装 → Codex impl-review APPROVED
3. main マージ → 次 step

---

## 4. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path) | canonical_metrics | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS monitor + Stage C base dual-path | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | (stage_gate.py のみ) | **完了** (commit 1dadc8b) |
| step 2 | stage_bc_evaluator → main flow | stage_bc_evaluator | **次推奨** |
| step 3 | cpps_archive → main flow | cpps_archive | 後続 |
| step 4 | stage_a_evaluator (T063) → main flow | stage_a_evaluator | 後続 |
| step 5 | nsga2_selection → main flow | nsga2_selection | 後続 |
| step 6 | loop_closure (warmstart) → main flow | loop_closure | 後続 |
| step 7 | failure_handling → main flow | failure_handling | 後続 |

---

## 5. 次セッション first prompt 例

### B step 2 (推奨) 着手の場合

```
引き継ぎは devnotes/20260503-2155-B-step1.6-complete-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合) を実装着手。

着手前調査:
1. src/alpha_factory/stage_bc_evaluator.py の signature と既存 API
   (= evaluate_stage_b_pooled / evaluate_stage_c_lite の引数 / 戻り値構造)
2. 現在の evaluate_stage_b / evaluate_stage_c (stage_gate.py)
   が stage_bc_evaluator に置換可能な構造か
3. archive Parquet schema 拡張の必要性 (= canonical_sidecar 永続化要否)
   と既存 28+ カラム fixed schema との整合
4. step 1.5 / 1.6 の dual-path log で取れた calibration data が
   stage_bc_evaluator 統合後も継続観測可能か

設計:
5. step 1 / 1.5 / 1.6 で凍結した canonical_adapter.py / helper を再利用
6. stage_bc_evaluator caller として stage_gate.py を簡略化
7. LOG_ONLY → FAIL_CLOSED 切替戦略の段階化 (= 次次 step)

ゆっくり・確実に: 規模 大の改修なので着手前調査を充実、 設計を 2 段階で、
worktree commit を細分化することを優先。

Codex review APPROVED → 実装 → main マージ → step 3 へ。
```

---

## 6. 残課題・運用観測 follow-up (= step 1.6 から繰り越し)

詳細設計 § 12 / 概念設計 follow-up 反映:

1. **canonical 失敗件数閾値ベースの fail-fast サーキットブレーカ**: 連続 N 回 canonical 計算失敗で GA Run を fail-fast。 step 1.6 では WARN log のみ
2. **CI メモリ閾値ガード**: smoke 5 Run の peak RSS / wall time / dual-path log bytes を CI で監視。 step 1.6 では手動実測 (= acceptance B2/B3)
3. **canonical sidecar archive Parquet schema 拡張**: 永続化層への canonical 値書き込み (= step 3 cpps_archive 統合と合わせて検討)
4. **smoke 5 Run の peak RSS 実測** (= acceptance B2): step 1.6 では概算で +~12 MB / worker の低リスク仮説、 別計画で実 GA Run 時に確認
5. **smoke 5 Run の所要時間が step 1.5 比 ±20% 以内** (= acceptance B3): 同上、 n_fold メトリクス併記
6. **Stage C cross_pair (ii-lite) dual-path**: mission 必須軸、 step 2 以降で必須

### 6.1 観測点の拡充状況 (= step 1.6 完了時点)

dual-path 観測点 (per genome):
- Stage A: 1 entry
- Stage B IS: 1 entry
- **Stage B fold: n_fold entries (= 動的、 step 1.6 で追加)**
- Stage C base: 1 entry
- Stage C cross_pair: 0 entry (= step 2 以降)
- **合計**: `3 + n_fold` entries / genome

GA Run 30 generations × 50 individuals × 6 pairs = 9000 genomes/Run、 n_fold = 8 (= 18m fixture 想定) で:
- ~99,000 dual-path log entries / Run (= 11 entries × 9000 genomes)
