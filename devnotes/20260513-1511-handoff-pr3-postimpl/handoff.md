# Handoff: PR1 + PR2 + PR3 完了、 残 PR4 行動変更を控える

## Executive summary

zenigame-fx Alpha Factory 改善で 12 段統合 TODO の最初 3 段 (PR1 source_stage、 PR2 persistence_score_shadow、 PR3 canonical/mission_inf_gap shadow) を **行動不変** で実装・main マージ完了。 archive Parquet schema は 50 列 → 52 列 → 58 列 と漸増。 次は **初の行動変更 PR** = PR4 (legacy_pnl_smoke fitness 切替 + anti-luck guard、 1 RUN smoke 必須、 60-487 分)、 または PR5 (Stage B gate pfr_only opt-in)、 または push 先行。

## 現在地 (2026-05-13 15:11 JST)

- **PR1 完了** (commit `e81dc85`): T058 contract の半実装解消、 source_stage 値入力
- **PR2 完了** (commit `c18551e`): persistence_score_shadow 列追加、 Stage B 持続性予測 shadow audit
- **PR3 完了** (commit `dcec109` → merge `85d1dc8`): canonical_metrics / mission_inf_gap shadow 6 列追加 (Stage B IS + Stage C base 各 3 列)
- 残 9 段 (PR4-PR6 + docs / scripts / Stage C allocation / warmstart / Phase 2 統合 / primitive 拡張)
- main は origin/main から **6 commit ahead**、 **push 未実行**

## PR3 の中身 (= 30 Codex 議論で確立した「観測基盤を整えてから行動変更」 方針の最後の観測 PR)

### 追加 6 列 (archive Parquet schema 52 → 58)

| 列名 | 型 | 由来 |
|---|---|---|
| `canonical_gate_pass_b_shadow` | bool nullable | Stage B IS canonical gate_pass (4 metric 全達成かつ invariants feasible) |
| `mission_inf_gap_b_shadow` | float nullable | Stage B IS から導出した mission_inf_gap (0 = 達成、 正値 = 未達、 +inf は None 正規化) |
| `mission_signed_margin_b_shadow` | float nullable | Stage B IS から導出した mission_signed_margin (= archive CA #5 ordering SSOT、 -inf sentinel は None 正規化) |
| `canonical_gate_pass_c_shadow` | bool nullable | Stage C base 同等 |
| `mission_inf_gap_c_shadow` | float nullable | Stage C base 同等 |
| `mission_signed_margin_c_shadow` | float nullable | Stage C base 同等 |

### データフロー

```
stage_gate.py
  evaluate_stage_b()
    canonical_sidecar_b_is = _try_evaluate_canonical_five_safe(...)
    payload["canonical_shadow_b_is"] = _canonical_shadow_summary(canonical_sidecar_b_is)
      # = {"gate_pass": ..., "mission_inf_gap": ..., "mission_signed_margin": ...} or None

archive.py
  collect_stage_b()
    payload = stage_result.metrics["payload"]
    (gate_pass, gap, margin) = _extract_canonical_shadow(payload, "canonical_shadow_b_is")
    row["canonical_gate_pass_b_shadow"] = gate_pass
    row["mission_inf_gap_b_shadow"] = gap            # ±inf → None
    row["mission_signed_margin_b_shadow"] = margin    # ±inf → None
```

Stage C も対称。 `_finite_or_none` で ±inf / NaN / bool / None / 非数値を一括 None 正規化。

### Codex impl-review

- model: gpt-5.3-codex / reasoning: high / label: impl-review
- **Round 1 APPROVED** (= [Critical] 0 / [Warning] 1 / [Suggestion] 1、 両方反映済)
  - [Warning] → `_canonical_shadow_summary` の except を `ValueError` から `Exception` に broaden (= future-proofing、 想定外例外でも gate 判定経路に波及しない)
  - [Suggestion] → ValueError + AttributeError 両分岐の直接テスト 2 件追加

### テスト

- PR3 関連: 17 件追加 (archive 11 + stage_gate 6)
- 既存テスト影響: `test_stage_gate_canonical_dual_path.py` の 8 件で「LOG_ONLY vs DISABLED の payload 等価性」 assertion から `canonical_shadow_*` key を skip 追加 (= PR3 で意図的に異なる値が入る)
- `tests/alpha_factory/`: 2329 pass + 1 skipped + 1 deselected (= T092 fold guard 既存失敗) + 1 xfailed
- ruff / mypy: PR3 touch 範囲 clean (= mypy 1 件 archive.py:335 は PR2 由来既存問題、 main にも存在)

## 12 段統合 TODO 順 (Codex Z Round 5 最終推奨)

| 順 | TODO | 規模 | 状態 |
|---|---|---|---|
| 1 | PR1: archive_role / source_stage 値入力 | S | ✅ Completed (`e81dc85`)、 source_stage のみ、 archive_role は PR7+ |
| 2 | PR2: Stage B persistence_score_shadow 追加 (gate 不変) | S | ✅ Completed (`c18551e`) |
| 3 | PR3: canonical_metrics / mission_inf_gap shadow 配線 | S | ✅ **Completed (`dcec109` → `85d1dc8`)** |
| 4 | **PR4: legacy_pnl_smoke opt-in + anti-luck guard** | M | ⏳ 未着手 (= **初の「行動変更」 PR**、 fitness 関数 opt-in 切替、 1 RUN smoke 必須 60-487 分) |
| 5 | PR5: Stage B gate pfr_only opt-in A/B | M | ⏳ 未着手 (= median_oos_sharpe を gate から外す、 行動変更) |
| 6 | docs: progress_criteria 明文化 (Z-1 10k / Z-2 20k / Z-3 30k / Z-4 50k、 live=50k 不変) | S | ⏳ 未着手 (docs/alpha_factory/) |
| 7 | scripts: out-of-cluster audit (= novel cluster artifact 検出) | M | ⏳ 未着手 (毎 RUN 後の archive 横断 audit、 **PR3 shadow 列を活用可能**) |
| 8 | PR6: F6/F10/F4/F7 grammar soft downweight opt-in | S | ⏳ 未着手 (PR4 smoke で F6 増幅確認時のみ) |
| 9 | Stage C stratified allocation (Stage B decile + primitive 多様性) | M | ⏳ 未着手 (**PR3 shadow 列で stratification 候補 stratifier に**) |
| 10 | Run 71/63 系統 warmstart 検討 (= candidate motif として 10% pool) | M | ⏳ 未着手 |
| 11 | Phase 2 統合 Step 3-7 (= BCEvaluationResult + NSGA-II / CPPS / warmstart 配線) | L | ⏳ 未着手 (10 箇所同時更新、 **PR3 で step 2 完了**) |
| 12 | primitive 拡張 (zenigame 82 primitive 相当の FX 用拡充) | L | ⏳ 将来 |

## 確定事実 (前 handoff から変化なし、 PR3 で 1 件追加)

### archive 実測 (= 362K 行、 72 RUN 累積、 PR3 で新 6 列、 過去 row は欠損で読み出し可能)

旧 handoff `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` § 確定事実 を参照。 PR3 で追加分:

- **shadow 列の選択哲学**: canonical 5 軸 / mission_inf_gap の中で「最も diagnostic に効く 3 要素」 を選定 (= gate_pass / inf_gap / signed_margin)。 invariants_feasible / per_metric_shortfall / sr_session_worst 等は将来追加候補
- **±inf / -inf sentinel の取り扱い**: archive Parquet float64 は技術的に ±inf 書込可能だが、 downstream 解析の単純化のため `_finite_or_none` で None 正規化。 invariants_feasible の有無を別列で記録するか否かは future PR で判断
- **Stage A / Stage B fold / Stage C stress / Stage C cross_pair の shadow 化** は PR3 範囲外 (= 列肥大化リスク回避)、 必要なら別 PR で追加

## 未解決 INCONCLUSIVE (前 handoff と同一)

- mission 達成個体が出るか (= 1 RUN smoke で実証必要)
- F6 抑制必要性 (= PR4 smoke で F6 増幅確認時のみ実施)
- Run 71/63 系統の primitive 組合せが別 seed で再現するか
- 真の robust 500 pips/60日 戦略空間が存在するか
- Phase 2 統合の bug 再演リスク

## 撤退条件 (前 handoff と同一)

- 継続条件: PR1-PR6 後 5 RUN 平均 best が 20k 超 or out-of-cluster で Z-2 が複数 RUN に分散
- 停止 1 / 停止 2 / 撤退条件詳細は前 handoff § 撤退条件 を参照

## 重要な落とし穴 (前 handoff から 1 件追加)

1. **archive 実測で結論を急ぐな**: 4 回の false-positive 検出経験 (handoff § 経緯 2)
2. **archive 列の意味を毎回確認**: `total_pnl` は Stage A only と Stage C 評価済個体で意味が違う
3. **「zenigame に X がある → fx にも X が必要」 短絡禁止**
4. **「行動不変」 PR と「行動変更」 PR を区別**: PR1-PR3 は行動不変、 PR4+ は **1 RUN smoke 必須**
5. **Codex に投げる前に事実を完全提示**
6. **orphan 列に依存するな**: mission_score / dsr / fsp_* / **新規追加の canonical_shadow_*** も埋まる確率が低いことに留意 (= 個体の多くは Stage A で fail し B/C に進まない)
7. **「同一 row 群」 と「独立サンプル」 を混同するな**
8. **`__SCHEMA_NAMES` vs `_TEMPLATE_KEYS` の整合性**: schema 列追加時は template + import-time assert + 既存 column count test (= `test_schema_has_*_columns` / `test_schema_nullable_attributes`) もセットで更新必須

## 既存問題 (PR3 と無関係、 別 TODO 候補)

### `tests/alpha_factory/test_t058_integration.py::test_end_to_end_writes_v2_summary_json` (handoff § 既存問題と同一)

- 原因: T092 Stage B fold guard が `compute_max_folds=4 < wf_min_safe_folds=5` で fail-closed
- 対応案: fixture の fold 数増 (= n_unique_dates_b ≥ 7) または fixture only override
- 優先度: 中、 別 TODO で扱う

### `tests/scripts/test_run_ga_parallel.py` (14 件失敗)

- 原因: **同じ T092 fold guard 起因** (= test_run_ga_parallel の fixture も `n_unique_dates_b=6` で fail)
- main 上で既に失敗 (PR3 由来ではない、 PR3 実装中に verify 済)
- 対応案: 上記と同じ fixture 拡張、 まとめて 1 TODO で解消可能
- 優先度: 中

### `src/alpha_factory/archive.py:335` mypy 1 件 (PR2 由来)

- 原因: `_compute_persistence_score_shadow` で `if positive_fold_ratio is None and fold_sign_ratio is None: return None` の後、 mypy が `float | None` を `float` に narrow できない
- 対応案: 明示的 `if v is None` チェック追加 or `assert v is not None`、 1 行 fix
- 優先度: 低、 別 TODO で扱う

## テスト実行単位ガイド (前 handoff と同一)

- 編集中: `uv run pytest tests/alpha_factory/test_archive.py -q` (~1-3 秒)
- PR 完成時 / commit 前: `uv run pytest tests/alpha_factory/ -q --deselect ...` (~13 秒)
- push 前 / マージ前: `uv run pytest tests/ -q` (~1-2 分、 T092 関連 14 件は deselect 必要)

## 次のアクション (= 次の Claude セッション開始時の判断)

### Option A: PR4 着手 (= 初の行動変更 PR)

- 規模: M
- 行動変更: fitness 切替 (legacy_pnl_smoke opt-in)
- 推奨式 (Codex Y Round 5):
  ```
  fitness_pen = legacy + β × clipped_pnl_slack × persistence_weight
              - tc_penalty - lucky_run_penalty
  ```
- β = 0.05 初回、 anti-luck guard 二段
- **1 RUN smoke test 必須** (= 60-487 分)
- baseline 比較で Stage B pass 数 / Stage C pips/day / lucky 比率 / **新規追加された canonical_shadow / mission_inf_gap_shadow の分布** を確認

### Option B: PR5 着手 (Stage B gate pfr_only opt-in)

- 規模: M
- 行動変更: median_oos_sharpe を gate から外す、 positive_fold_ratio_effective ベース化
- 1 RUN smoke 必須

### Option C: docs / scripts 並走 (PR4 を回す間)

- 順 6 docs/progress_criteria 明文化 (= S 規模、 行動不変、 並行作業可能)
- 順 7 scripts out-of-cluster audit (= M 規模、 PR3 shadow 列活用)
- 順 9 Stage C stratified allocation (= M 規模、 PR3 shadow 列活用)

### Option D: push 先行

- 現在 main は origin/main から **6 commit ahead**
- push して GitHub 上でレビュー可能化

### Option E: 既存問題 (test fixture / mypy) 修正

- T092 fold guard fixture (1 TODO で test_t058_integration + test_run_ga_parallel まとめ修正)、 中規模
- archive.py:335 mypy fix、 小規模

### 推奨

PR3 で観測基盤完成 (= shadow 列で Stage B IS / Stage C base の canonical / mission 値が見える)。 次は **PR4 着手** (Option A) で初の行動変更に進む。 1 RUN smoke 必須なので時間に余裕があるタイミングで着手。 push (Option D) は適宜。 既存問題 (Option E) は分離 TODO で。

## 関連 commit 履歴

```
85d1dc8 Merge branch 'todo/T093'
259a0bf docs(todo+devnotes): T093 (PR3 canonical/mission shadow) Closed 移動 + 設計ノート
dcec109 feat(archive): canonical/mission shadow 6 列追加 (PR3 = T061/T062 main flow shadow 配線)
642866f docs(devnotes): PR1/PR2 完了後 引き継ぎ書 (30 Codex 議論 + 4 回監査 + 12 段 TODO)
c18551e feat(archive): persistence_score_shadow 列追加 (PR2 = Stage B 持続性予測 shadow audit)
e81dc85 feat(archive): source_stage 値入力 (PR1 = T058 contract 半実装解消)
fdb2a66 chore(git): worktrees/ を .gitignore に追加
99b5e8c docs(devnotes): commit untracked dev notes (T088/T090, JIT/cache 検討、fx-improve 2 セッション)
```

## 重要ファイル参照

### 設計議論ログ (前 handoff から継承)

- `tmp/codex-debate-impl-diff/` (旧 A/B/C 議論、 空振り)
- `tmp/codex-debate-round2/` (新 X/Y/Z 議論、 closeout)
- `devnotes/20260513-0400-todo-pr1-source-stage/` (PR1 概念・詳細設計)
- `devnotes/20260513-1223-todo-pr2-persistence-score-shadow/` (PR2 概念・詳細設計)
- **`devnotes/20260513-1419-todo-pr3-canonical-mission-shadow/`** (PR3 概念・詳細設計 + impl-review)
- `devnotes/20260512-1000-cross-repo-debate/` (cross-repo 議論、 cascade port v2 方針確定)
- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/handoff.md` (PR1/PR2 完了後の引き継ぎ書 = 前 handoff)

### 実装本体 (前 handoff から継承、 PR3 で 2 file 更新)

- `src/alpha_factory/archive.py` (PR1/PR2/**PR3** で更新、 schema 58 列)
- `src/alpha_factory/stage_gate.py` (**PR3 で _canonical_shadow_summary helper + Stage B IS / Stage C base payload 追加**)
- `src/alpha_factory/canonical_metrics.py` (T061、 Phase 1 完了、 PR3 で main flow shadow 配線完了)
- `src/alpha_factory/mission_inf_gap.py` (T062、 Phase 1 完了、 PR3 で main flow shadow 配線完了)
- `src/alpha_factory/cpps_archive.py` (T066、 Phase 1 完了、 配線未実施)
- `src/alpha_factory/nsga2_selection.py` (T065、 Phase 1 完了、 配線未実施)
- `src/alpha_factory/loop_closure.py` (T067、 Phase 1 完了、 配線未実施)
- `src/alpha_factory/stage_bc_evaluator.py` (T064、 Phase 1 完了、 配線未実施)
- `scripts/alpha_factory/run_ga.py` (GA 実行 entry、 Phase 2 統合で BC 配線対象)
- `config/alpha_factory/default.yaml` (live_criteria = 50,000、 不変)

### docs (前 handoff と同一)

- `docs/alpha_factory/stage-gates.md` / `docs/alpha_factory/mission-score.md` / `docs/alpha_factory/cross-pair.md` / `docs/alpha_factory/swim-lane.md`
- AGENTS.md / CLAUDE.md (プロジェクト全体規約)

### zenigame (参考、 前 handoff と同一)

- `/Users/ishitoya/repository/zenigame/docs/alpha-factory/selection-cascade-design.md`
- `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/`

## このセッションでの学び (= プロセス改善材料)

1. **PR2 同型パターンで実装速度 up**: PR2 (persistence_score_shadow、 同 S 規模、 同 archive 列追加) の概念・詳細設計を参考に PR3 を 1 セッションで完遂 (= 既存 pattern の活用が効く)
2. **既存 dual-path テスト群との衝突は予測可能**: LOG_ONLY と DISABLED の payload 等価性 assertion は「shadow 値を追加する」 PR で必ず壊れる。 PR3 では予測通り 8 件失敗、 「`canonical_shadow_*` key のみ skip」 で機械的に修正可能
3. **Codex impl-review の Warning は意外と価値ある**: Round 1 で `ValueError` のみ catch → broader `Exception` catch に変更を提案された。 future-proofing 観点で重要、 採用すべき
4. **既存問題 (T092 fold guard) の影響範囲**: test_t058_integration 1 件と思っていたが、 実は test_run_ga_parallel 14 件も同根。 まとめて 1 TODO で fix 可能。 1 件失敗を見たら同根 fail がないか必ず広く検索する
5. **main 上で TODO close 操作 + worktree 上でコード変更** の協調: TODO close は main を直接更新、 コード変更は worktree、 最後に merge --no-ff で統合。 順序: ①worktree commit → ②main で TODO close & devnotes commit → ③main で worktree branch merge

## ユーザーへの確認待ち (= 次セッション開始時に確認すべき項目)

- PR4 進める or PR5 進める or docs / scripts 並走 or push 先行 or 既存問題修正
- 1 RUN smoke を回すタイミング (PR4 以降、 60-487 分)
- Phase 2 統合 PR (PR11) の大規模化への対応 (= 分割するか、 PR11a/b/c のように)
- PR3 で追加した shadow 列を実際に audit する script の必要性 (= 順 7 scripts out-of-cluster audit の優先度)
