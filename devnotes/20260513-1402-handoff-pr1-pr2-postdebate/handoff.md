# Handoff: 30 Codex 議論 + 4 回 false-positive 監査 + PR1/PR2 完了

## Executive summary

zenigame-fx の Alpha Factory 改善で「ここからできること」 を **30 Codex 議論セッション + 4 回 false-positive 監査** (旧 A/B/C 15 ラウンド空振り → 新 X/Y/Z 15 ラウンド) で徹底検討。 12 段統合 TODO の最初 2 段 (PR1 source_stage 値入力、 PR2 persistence_score_shadow 列追加) を **行動不変** で実装・コミット完了。 次は PR3 (canonical_metrics / mission_inf_gap shadow 配線) または「行動変更」 を伴う PR4 (fitness 切替) の判断段階。

## 現在地 (2026-05-13 14:02 JST)

- **PR1 完了** (commit `e81dc85`): T058 contract の半実装解消、 source_stage 値入力
- **PR2 完了** (commit `c18551e`): persistence_score_shadow 列追加、 Stage B 持続性予測 shadow audit
- 残 10 段 (PR3-PR6 + docs/scripts + Stage C allocation + warmstart + Phase 2 統合 + primitive 拡張)
- main は origin/main から 2 commit ahead、 **push 未実行**

## 議論の経緯 (= 重要、 ここを理解しないと次の Claude が同じ罠を踏む)

### 経緯 1: 旧 A/B/C 15 ラウンド議論は空振り

旧議論論点:
- A: NSGA-II 多目的化の是非
- B: DSR (Deflated Sharpe Ratio) を hard-gate 化するか
- C: zenigame の failure_memory / TC Stage / warmstart を移植するか

→ **完全空振り**。 理由:
1. zenigame-fx に **既に Cascade Port v2 (T064-T067) の Phase 1 実装完了 + main merge 済** で、 NSGA-II / CPPS / warmstart 移植は議論する以前に存在
2. cpps_archive.py の docstring に「Phase 1 (本 TODO = T066 PR 1): 単体実装 + テストのみ、 GA / archive 未変更. Phase 2 (別 PR): T067 / T070 / T071 と同時、 **10 箇所同時更新**」 と明記、 配線が漏れているだけ
3. 私 (Claude) が Codex に zenigame-fx 内部の事情を伝えていなかったため Codex は zenigame からの移植案を出し続けた

旧議論ログ: `tmp/codex-debate-impl-diff/` (Round 1-5、 15 セッション)

### 経緯 2: false-positive 監査 4 回 (重大訂正)

**監査 1 (parent-child fitness 相関)**:
- Agent 2 主張「parent-child fitness ρ = -0.0008 → GA は学習していない」
- 実態: sentinel fitness (-1e9 等の system_failure 個体) を除外せずに計算したミス
- 訂正: sentinel 除去後 **Pearson ρ=+0.585、 Spearman ρ=+0.450、 GA は明確に学習している**
- parent top 10% → child mean fitness = +1.49、 bottom 10% → -0.15 = 明確な信号伝搬

**監査 2 (mission_score の Stage C 代理疑惑)**:
- 旧主張: 「mission_score を fitness に使うと data leak リスク」
- 実態: mission_score は **Stage C 評価後にしか書き込まれない** (archive.py:650)、 設計上 fitness 用途は impossible (= 過大評価)
- ただし audit 専用列として残すべきは依然真

**監査 3 (Neither 群 n=64 最強疑惑)**:
- 旧主張: 「F4/F6/P2 を含まない Neither 群が Stage C 最強 (median +20,650, C>0% 100%)」
- 実態: **全 64 個体が Run 71 (1 RUN) のみから** + 同じ primitive 集合 (F5/F8/M2/P7/P12/P1 を 100% 含む) = **同一系統の派生個体集合** (Codex C7 = sample size 違反)
- 訂正: 「群」 として扱うべきではない、 1 戦略の複製

**監査 4 (F9/F14 真の signal 疑惑)**:
- 旧主張: 「F8/F5/M2/P1/P7/P12 が真の Stage C 持続性 primitive」
- 実態: archive で Run 71/63 以外で F8∧F5∧P1 含む = **0 個体**。 28 RUN のうち **Run 71 + Run 63 の 2 RUN cluster のみ**、 primitive 組合せは互いに無関係 (Run 71: F5+P1+M2+F8+P7+P12、 Run 63: P2+F14)
- 訂正: H_Z' (= F8/F5/P1/P12 が persistence signal) は **REJECTED**、 真の signal は archive 単独では特定不能

→ archive verify を繰り返すたびに主張が次々と覆る。 **「実コード + 実データに当たって false-positive を取り除く」 ことを徹底**しないと議論が空振り。

### 経緯 3: 新 X/Y/Z 15 ラウンド議論 (closeout 達成)

新論点:
- X: GA 信号伝搬失敗 (parent-child fitness ρ≈0) の真因 → REJECTED、 派生 H_X' (= fitness が mission AND と非整合) CONFIRMED、 H_X'' (= Stage B gate が curve-fit 選好) PARTIAL
- Y: Cascade Port v2 Phase 2 配線 + mission_shortfall 移植 → 6 PR 段階分け確定
- Z: 目標水準妥当性 + 戦略空間 → H_Z reframed CONFIRMED ("50k 不可能" ではなく "現行 GA は 50k 領域探索していない")、 H_Z' (F8/F5/P1/P12 signal) REJECTED

新議論ログ: `tmp/codex-debate-round2/` (Round 1-5、 15 セッション)

## 確定事実 (= 動かない、 verify 済)

### 実装・設計

- archive 51 列 (現在 PR2 で 52 列に) のうち 14 列が完全 orphan (= 値が一度も書き込まれない): sortino, calmar, dsr, bootstrap_ci_lower/upper, fsp_*(6 列), archive_role (PR3+ で対応), source_stage (PR1 で解消), ii_lite_pass
- Stage 期間順序: Stage B (古 18 ヶ月) < Stage A (60 日) < Stage C holdout (60 日) で disjoint (stage_partition_guard.py で fail-closed 検証)
- `fitness_pen = sharpe − α×size − tc_penalty` (Stage A 評価のみ、 Stage B/C 混入なし)
- archive の `total_pnl` / `max_drawdown_pct` / `trade_count` は **Stage C 評価で上書き** (= Stage A only と Stage C 評価済個体で意味が違う、 落とし穴)
- `mission_score` は Stage C 評価後のみ書き込み (= fitness 用途 impossible)
- T064-T067 (Cascade Port v2): Phase 1 実装完了 + main merge 済、 **main flow 配線未実施** (run_ga.py / swim_lane.py 側)
- zenigame の CPPS = Cascade-PPS-2Archive (Push-Pull + Two-Archive + 適応閾値)、 T509 で導入し T518/T519 で圧バランス整合化、 R1351-R1363 (13 RUN) で C-PASS 実証済

### archive 実測 (= 362K 行、 72 RUN 累積)

- mission 0/72 RUN、 Stage C pass = 0/3,251 個体
- mission 唯一の bottleneck = **total_pnl ≥ 50,000** (sharpe 11% / max_dd 100% / trade_count 60% は通過)
- Stage C 評価集団 (n=1,284) の total_pnl max = 25,580 円 / pips/day max = 4.26 (必要 8.33 pips/日 の半分)
- fitness_pen ↔ slack_sharpe ρ=+0.85 / slack_pnl ρ=+0.59 / slack_trade ρ=-0.27 (= sharpe 偏重、 PnL volume 副次、 trade_count 逆相関)
- parent-child fitness ρ=+0.585 (= GA は学習)
- Stage A → Stage B top 10% retention = 46.8% (= 持続性は存在、 ランダム期待 20%)
- mission_shortfall_proxy top 1% で all 4 pass = 165 個体、 ただし全部 max_dd=0.0% の **lucky run** (持続性ゼロ)

### Stage B → Stage C 関連

- Stage B lift 上位: F9 (10.65x) / F14 (2.27x) / P5 (2.21x)
- Stage C 20k+ 出現率: F9 = **0%** / F14 = 43.2% / F8/F5/P1/P12 = 各 56.8% (ただし Run 71 cluster artifact)
- Stage A only で total_pnl ≥ 30k = 10,646 個体 (2.9%、 持続性なし lucky run)
- Stage C 評価まで進んだ集団で total_pnl ≥ 30k = **0/1,284**

## 未解決 INCONCLUSIVE

- mission 達成個体が出るか (= 1 RUN smoke で実証必要)
- F6 抑制必要性 (= PR4 smoke で F6 増幅確認時のみ実施)
- Run 71/63 系統の primitive 組合せが別 seed で再現するか
- 真の robust 500 pips/60日 戦略空間が存在するか (= 持続性のある戦略空間の存在検証)
- Phase 2 統合の bug 再演リスク (= zenigame で 13 件 bug 発生、 FX 移植で類似発生可能性)

## 12 段統合 TODO 順 (Codex Z Round 5 最終推奨)

| 順 | TODO | 規模 | 状態 |
|---|---|---|---|
| 1 | PR1: archive_role / source_stage 値入力 | S | ✅ Completed (e81dc85)、 source_stage のみ実装、 archive_role は PR7+ |
| 2 | **PR2: Stage B persistence_score_shadow 追加** (gate 不変) | S | ✅ Completed (c18551e) |
| 3 | PR3: canonical_metrics / mission_inf_gap shadow 配線 | S | ⏳ 未着手 (T061/T062 を main flow に shadow mode で接続、 既存 LOG_ONLY 経路と重複なきよう注意) |
| 4 | PR4: legacy_pnl_smoke opt-in + anti-luck guard | M | ⏳ 未着手 (= **初の「行動変更」 PR**、 fitness 関数 opt-in 切替、 1 RUN smoke 必須) |
| 5 | PR5: Stage B gate pfr_only opt-in A/B | M | ⏳ 未着手 (= median_oos_sharpe を gate から外す、 行動変更) |
| 6 | docs: progress_criteria 明文化 (Z-1 10k / Z-2 20k / Z-3 30k / Z-4 50k、 live=50k 不変) | S | ⏳ 未着手 (docs/alpha_factory/) |
| 7 | scripts: out-of-cluster audit (= novel cluster artifact 検出) | M | ⏳ 未着手 (毎 RUN 後の archive 横断 audit) |
| 8 | PR6: F6/F10/F4/F7 grammar soft downweight opt-in | S | ⏳ 未着手 (PR4 smoke で F6 増幅確認時のみ) |
| 9 | Stage C stratified allocation (Stage B decile + primitive 多様性) | M | ⏳ 未着手 |
| 10 | Run 71/63 系統 warmstart 検討 (= candidate motif として 10% pool) | M | ⏳ 未着手 |
| 11 | Phase 2 統合 Step 3-7 (= BCEvaluationResult + NSGA-II / CPPS / warmstart 配線) | L | ⏳ 未着手 (10 箇所同時更新) |
| 12 | primitive 拡張 (zenigame 82 primitive 相当の FX 用拡充) | L | ⏳ 将来 |

## 撤退条件 (改善ロードマップ無効化判定)

- **継続条件**: PR1-PR6 後 5 RUN 平均 best が 20k 超 or out-of-cluster で Z-2 が複数 RUN に分散
- **警戒**: 20k+ が再び 1-2 RUN cluster に集中 (= cluster artifact 再発)
- **停止 1**: PR1-PR6 後 10 RUN で Stage C 20k+ が 0 かつ best/p95 不変
- **停止 2**: 20k+ が単一 cluster で out-of-cluster 再現なし
- **撤退**: 上記対策後 20 RUN 相当で Stage C 30k+ が 0 かつ 20k+ artifact のまま → primitive 拡張 or 目標水準再設定議論

## 重要な落とし穴 (= 次の Claude が踏まないために)

1. **archive 実測で結論を急ぐな**: 4 回連続で false-positive 検出。 サンプル数 / cluster / 因果関係を毎回確認 (Codex C7 = sample size、 C3 = collider bias、 C6 = Fact/Interpretation 分離)
2. **archive 列の意味を毎回確認**: `total_pnl` 列は Stage A only 個体と Stage C 評価済個体で意味が違う (Stage C 上書き)。 同一列名で異なる意味の場合あり
3. **「zenigame に X がある → fx にも X が必要」 短絡禁止**: zenigame-fx に既に Phase 1 実装あるか確認 (= `src/alpha_factory/` 全 module の docstring を読む)
4. **「行動不変」 PR と「行動変更」 PR を区別**: PR1/PR2 は行動不変 (= archive 観測列追加のみ)、 PR4 以降は行動変更 (= fitness 切替、 gate 修正)。 行動変更は **1 RUN smoke test 必須**
5. **Codex に投げる前に事実を完全提示**: 旧 15 ラウンド議論が空振りした主因は事実不足。 archive 実測 + 実コード verify + Phase 1 実装の存在を Codex に明示してから議論を始める
6. **mission_score / dsr / fsp_* 等の orphan 列に依存するな**: archive で値が None 多数 → 分析で除外、 「F9 = signal」 を archive 全体で見たら n=4 でしか出ない、 など
7. **「同一 row 群」 と「独立サンプル」 を混同するな**: Run 71 から 64 個体 = 1 戦略の派生、 独立試行ではない
8. **`__SCHEMA_NAMES` vs `_TEMPLATE_KEYS` の整合性**: GENOMES_SCHEMA に列追加時は `_create_row_template` にも追加必須 (= import-time assert で検証されるが、 試験テスト追加もセット)

## 既存問題 (PR1/PR2 と無関係、 別 TODO 候補)

`tests/alpha_factory/test_t058_integration.py::test_end_to_end_writes_v2_summary_json` は **main 上の既存失敗**:
- 原因: T092 Stage B fold guard が `compute_max_folds=4 < wf_min_safe_folds=5` で fail-closed
- 問題: テスト fixture (n_unique_dates_b=6) が新 guard 閾値に達しない
- 確認: PR1/PR2 変更を退避しても再現するため、 PR1/PR2 と無関係
- 対応案: fixture の fold 数増 (= n_unique_dates_b ≥ 7) または fixture only override (`wf_min_safe_folds` を 2-3 に lowered)
- 優先度: 中、 別 TODO で扱う

## テスト実行単位ガイド

zenigame-fx には pytest 実行単位の明文ガイドがないが、 実装時の指針:

### 編集中 (= 1 ファイル修正中、 即フィードバック)
```bash
uv run pytest tests/alpha_factory/test_archive.py -q
# ~ 1-3 秒
```

### PR 完成時 / commit 前
```bash
uv run pytest tests/alpha_factory/ -q
# ~ 13 秒、 影響範囲 (= Stage A/B/C / archive / cross_pair / canonical 等) カバー
# 既存失敗 1 件 (test_end_to_end_writes_v2_summary_json) は --deselect で除外
```

### 行動変更 PR (PR4 以降) では追加で
- **1 RUN smoke**: `--instrument EUR_JPY --population-size 96 --generations 60 --seed 60 --max-workers 2` で 60-487 分
- 比較対象: baseline (= 直近 main commit) と同一 seed で実行し archive parquet を diff
- 監視指標: Stage B pass 数、 best 個体の trade_sharpe_stage_c、 lucky high-PnL 比率、 trade_count 集中、 F6 含有率

### push 前 / マージ前
```bash
uv run pytest tests/ -q
# 全テスト、 時間 ~ 1-2 分
```

### CI 連携
- `.github/workflows/` 確認 (現状未調査)
- 既存失敗 1 件は別 TODO で fix されるまで `--deselect` または `xfail` マーカーが妥当

## 重要ファイル参照

### 設計議論ログ
- `tmp/codex-debate-impl-diff/` (旧 A/B/C 議論、 15 セッション = 空振り、 反省材料として保持)
- `tmp/codex-debate-round2/` (新 X/Y/Z 議論、 15 セッション = closeout)
- `devnotes/20260513-0400-todo-pr1-source-stage/` (PR1 概念・詳細設計)
- `devnotes/20260513-1223-todo-pr2-persistence-score-shadow/` (PR2 概念・詳細設計)
- `devnotes/20260512-1000-cross-repo-debate/` (cross-repo 議論、 cascade port v2 方針確定)

### 実装本体
- `src/alpha_factory/archive.py` (PR1/PR2 で更新)
- `src/alpha_factory/stage_gate.py` (Stage A/B/C 評価、 PR4/PR5 で修正対象)
- `src/alpha_factory/swim_lane.py` (lane orchestrator、 Phase 2 統合で BC配線対象)
- `src/alpha_factory/cpps_archive.py` (T066、 Phase 1 完了、 配線未実施)
- `src/alpha_factory/nsga2_selection.py` (T065、 Phase 1 完了、 配線未実施)
- `src/alpha_factory/loop_closure.py` (T067、 Phase 1 完了、 配線未実施)
- `src/alpha_factory/stage_bc_evaluator.py` (T064、 Phase 1 完了、 配線未実施)
- `scripts/alpha_factory/run_ga.py` (GA 実行 entry、 Phase 2 統合で BC 配線対象)
- `config/alpha_factory/default.yaml` (live_criteria = 50,000、 不変)

### docs
- `docs/alpha_factory/stage-gates.md` (Stage A/B/C 仕様)
- `docs/alpha_factory/mission-score.md` (mission_score 仕様)
- `docs/alpha_factory/cross-pair.md` (cross-pair shadow)
- `docs/alpha_factory/swim-lane.md` (lane 構造)
- AGENTS.md / CLAUDE.md (プロジェクト全体規約)

### zenigame (参考)
- `/Users/ishitoya/repository/zenigame/docs/alpha-factory/selection-cascade-design.md` (CPPS 設計の歴史、 T508/T509/T518/T519 の経緯)
- `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/` (NSGA-II → CPPS 移行後の実装)

## 次のアクション (= 次の Claude セッション開始時の判断)

### Option A: PR3 着手 (canonical_metrics / mission_inf_gap shadow 配線)

- 規模: S
- 行動不変: 観測のみ
- 既存 LOG_ONLY 経路 (= stage_gate.py の `_try_evaluate_canonical_five_safe`) との重複に注意
- 中身: T061 canonical_metrics + T062 mission_inf_gap を swim_lane の collect_stage_b/c 経由で archive に書き込み

### Option B: PR4 着手 (= 初の行動変更 PR)

- 規模: M
- 行動変更: fitness 切替 (legacy_pnl_smoke opt-in)
- 推奨式 (Codex Y Round 5):
  ```
  fitness_pen = legacy + β × clipped_pnl_slack × persistence_weight
              - tc_penalty - lucky_run_penalty
  ```
- β = 0.05 初回、 anti-luck guard 二段
- **1 RUN smoke test 必須** (= 60-487 分)
- baseline 比較で Stage B pass 数 / Stage C pips/day / lucky 比率を確認

### Option C: push 先行

- 現在 main は origin/main から 2 commit ahead
- push して GitHub 上でレビュー可能化

### Option D: 既存問題 (test_end_to_end_writes_v2_summary_json) 修正

- T092 fold guard fixture 問題、 中規模

### 推奨

PR3 (Option A) を先に着手し、 観測基盤を整えてから PR4 (Option B) で行動変更に進む。 push (Option C) は適宜。 既存問題 (Option D) は分離 TODO で。

## 関連 commit 履歴

```
c18551e feat(archive): persistence_score_shadow 列追加 (PR2 = Stage B 持続性予測 shadow audit)
e81dc85 feat(archive): source_stage 値入力 (PR1 = T058 contract 半実装解消)
fdb2a66 chore(git): worktrees/ を .gitignore に追加
99b5e8c docs(devnotes): commit untracked dev notes (T088/T090, JIT/cache 検討、fx-improve 2 セッション)
d61b4f2 docs(reports): commit untracked run artifacts (run-35..52, run-64..74)
72bdb4b Merge branch 'todo/T092'
1657ede chore(todo): T092 (Stage B n_fold safe floor guard) Open → Closed
```

## このセッションでの学び (= プロセス改善材料)

1. **15 ラウンド議論を急がず、 事前に事実を全部出す**: 旧 A/B/C 議論は空振りだった。 議論前に「zenigame-fx に何が実装済み / 未実装か」 を Codex に明示すべき
2. **archive verify は 1 回で終わらせない**: 4 回の監査で次々と false-positive 検出。 結論を出す前に「これも実は cluster artifact では?」 を疑う
3. **Run 番号別の分布を必ず確認**: 「群」 として扱う前に「何 RUN にまたがるか」 を確認 (Codex C5 = 並列独立性)
4. **「実コード verify」 が最優先**: docstring / 設計議論 / archive 列名 を 信用しすぎない。 「列があるが値が書かれない」 は archive 14 列で起きていた
5. **PR は最小単位で行動不変から始める**: PR1/PR2 は行動完全不変で安全、 PR4 以降は行動変更で smoke test 必須

## ユーザーへの確認待ち (= 次セッション開始時に確認すべき項目)

- PR3 進める or PR4 進める or push 先行 or 既存問題修正
- 1 RUN smoke を回すタイミング (PR4 以降)
- Phase 2 統合 PR (PR11) の大規模化への対応 (= 分割するか、 PR11a/b/c のように)
