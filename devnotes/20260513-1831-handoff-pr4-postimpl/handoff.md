# Handoff: PR1-PR4 完了、 残 PR5 / smoke / Phase 2 統合

## Executive summary

zenigame-fx Alpha Factory 改善で 12 段統合 TODO の最初 4 段 (PR1-PR4) を main マージ完了。 PR4 は **初の行動変更 PR** で、 Stage A fitness に opt-in flag を導入 (default OFF で行動完全不変、 user が `--fitness-mode legacy_pnl_smoke` で活性化)。 次は **PR4 smoke 検証** (= ユーザー実行、 60-487 分) または **PR5 (Stage B gate pfr_only opt-in)** または並走 docs/scripts。

## 現在地 (2026-05-13 18:31 JST)

- **PR1 完了** (`e81dc85`): source_stage 値入力
- **PR2 完了** (`c18551e`): persistence_score_shadow 列追加
- **PR3 完了** (`dcec109` → merge `85d1dc8`): canonical/mission shadow 6 列追加 (52→58 列)
- **PR4 完了** (`86c7940` → merge `bee43fa`): legacy_pnl_smoke fitness opt-in + anti-luck guard
- 残 8 段 (PR5-PR6 + docs / scripts / Stage C allocation / warmstart / Phase 2 統合 / primitive 拡張)
- main は origin/main から **12 commit ahead**、 **push 未実行**

## PR4 の中身 (= 初の行動変更、 default OFF で安全 merge)

### 追加内容

- **Phase4Config** (5 field): `fitness_mode` (legacy / legacy_pnl_smoke) / `beta` / `persistence_weight` / `lucky_hard_penalty` / `lucky_soft_penalty`
- **`_compute_clipped_pnl_slack` helper**: 二層 PnL target (short 12k 主圧 0.7 + long 50k 方向付け 0.3)、 Codex Y Round 3-5 確定
- **`_compute_lucky_run_penalty` helper**: 二段 anti-luck guard (hard `max_dd<=1e-9` + soft `max_dd<0.5% AND trade_count<80`)、 Codex Y Round 4 確定
- **`evaluate_stage_a` fitness 分岐**: `below_threshold` 経路のみ発火、 sentinel 3 経路 (system_failure / no_exposure / metric_unavailable) は不変契約
- **`--fitness-mode` CLI 引数**: yaml `phase4.fitness_mode` を override
- **payload 7 fields**: fitness_mode + pnl_slack + lucky_penalty + config snapshot 4

### default 行動

- yaml default: `phase4.fitness_mode: legacy` (= 完全行動不変)
- 既存 GA / Stage A 動作 0 regression、 2366 tests pass で確認済

### smoke 検証 (= ユーザー実行待ち)

```bash
uv run python scripts/alpha_factory/run_ga.py \
  --instrument EUR_JPY \
  --population-size 96 \
  --generations 60 \
  --seed 60 \
  --max-workers 2 \
  --fitness-mode legacy_pnl_smoke
```

**所要時間**: 60-487 分 / 1 RUN。 **baseline**: 直近 5 RUN の archive 累積値 median (= 詳細設計 § smoke 条件 § Baseline 定義 SSOT)。

**合格条件** (= Codex Y Round 3-5 確定):
- Stage B pass 数 ≥ baseline × 80%
- Stage C pips/day p99 ≥ 5.0 (= absolute)
- Stage C total_pnl p95/p99 ≥ baseline
- trade_count median が 50-70 に潰れない
- max_dd=0.0% 比率 ≤ baseline
- canonical_gate_pass_b_shadow True 比率 ≥ baseline (= PR3 shadow 活用)

**rollback 条件**:
- Stage B pass 数 < baseline × 50%
- lucky 比率 (max_dd<0.3% && PnL≥12k) > baseline × 1.5
- top decile trade_count=50 張り付き
- pips/day 上昇が trades/day 増加だけで説明される

rollback 時の対応: yaml の `phase4.fitness_mode: legacy` に戻すだけ (= flag off で即時復旧)

### Codex 議論経緯 (PR4 設計)

- Round 1 (設計): **CHANGES_REQUESTED** ([Critical] 2 件: sentinel 不変性 / 境界等号テスト)
- Round 2 (設計): **APPROVED + GO** ([Critical] 反映 + [Warning] payload 監査項目拡張 + smoke baseline 定義明確化)
- Round 1 (impl): **APPROVED** ([Warning] 1 件: NaN/Inf 防御 → 反映済)

## 12 段統合 TODO 順 (Codex Z Round 5 最終推奨)

| 順 | TODO | 規模 | 状態 |
|---|---|---|---|
| 1 | PR1: source_stage 値入力 | S | ✅ Completed (`e81dc85`) |
| 2 | PR2: persistence_score_shadow | S | ✅ Completed (`c18551e`) |
| 3 | PR3: canonical/mission shadow 配線 | S | ✅ Completed (`dcec109` → `85d1dc8`) |
| 4 | PR4: legacy_pnl_smoke fitness opt-in + anti-luck guard | M | ✅ **Completed (`86c7940` → `bee43fa`)** |
| 5 | **PR5: Stage B gate pfr_only opt-in A/B** | M | ⏳ 未着手 (= **PR4 smoke 後 / 並走可**) |
| 6 | docs: progress_criteria 明文化 | S | ⏳ 未着手 |
| 7 | scripts: out-of-cluster audit | M | ⏳ 未着手 (PR3 shadow 列活用) |
| 8 | PR6: F6 grammar soft downweight opt-in | S | ⏳ 未着手 (PR4 smoke で F6 増幅確認時のみ) |
| 9 | Stage C stratified allocation | M | ⏳ 未着手 |
| 10 | Run 71/63 系統 warmstart 検討 | M | ⏳ 未着手 |
| 11 | Phase 2 統合 Step 3-7 | L | ⏳ 未着手 |
| 12 | primitive 拡張 | L | ⏳ 将来 |

## 確定事実 (前 handoff から変化)

PR3 完了後 handoff (`devnotes/20260513-1511-handoff-pr3-postimpl/handoff.md`) § 確定事実 を base。 PR4 で追加:

- **Stage A fitness opt-in 機構成立**: `phase4_fitness_mode` config + `--fitness-mode` CLI で 2 mode (legacy / legacy_pnl_smoke) 切替可能、 mode = legacy で legacy 経路と完全同値
- **二層 PnL target 仕様確定** (SSOT in stage_gate.py): short=12k 主圧 0.7 + long=50k 方向付け 0.3、 short clip [-1, +2]、 long clip [-1, +1]、 値域 [-1.0, 1.7]
- **二段 anti-luck guard 仕様確定** (SSOT in stage_gate.py): trigger `total_pnl > 12000`、 hard `max_dd <= 1e-9` (= 数値誤差込みゼロ判定)、 soft `max_dd < 0.5% AND trade_count < 80`
- **境界等号値の SSOT** (詳細設計 § 2.3.2): `total_pnl==12000` / `max_dd_pct==0.5` / `trade_count==80` 免責、 `max_dd_pct==1e-9` hard 対象
- **sentinel 3 経路不変契約**: system_failure / no_exposure / metric_unavailable では mode 関係なく fitness_pen 同値、 phase4_pnl_slack / phase4_lucky_penalty が None で記録

## 未解決 INCONCLUSIVE (前 handoff から継承、 PR4 smoke で解ける可能性)

- mission 達成個体が出るか (= **PR4 smoke で実証必要**)
- F6 抑制必要性 (= PR4 smoke で F6 増幅確認時のみ PR6 着手)
- Run 71/63 系統の primitive 組合せが別 seed で再現するか
- 真の robust 500 pips/60日 戦略空間が存在するか
- Phase 2 統合の bug 再演リスク

## 撤退条件 (前 handoff と同一)

- 継続: PR1-PR6 後 5 RUN 平均 best が 20k 超 or out-of-cluster で Z-2 が複数 RUN に分散
- 停止 1: PR1-PR6 後 10 RUN で Stage C 20k+ が 0 かつ best/p95 不変
- 撤退: 20 RUN 相当で Stage C 30k+ が 0 かつ 20k+ artifact のまま → primitive 拡張 or 目標水準再設定

## 重要な落とし穴 (前 handoff から 2 件追加、 PR4 経験から)

1-8. 前 handoff § 重要な落とし穴 を参照 (= archive false-positive、 4 段接続、 sentinel 経路、 等)

9. **行動変更 PR は事前に Codex 設計レビュー必須**: PR4 で Codex Round 1 が [Critical] 2 件 (sentinel 不変性 / 境界等号) を検出。 PR1-PR3 (S 規模 行動不変) は impl-review のみで足りたが、 行動変更 PR (M 規模) は設計レビューを挟む方が安全。 同じ workflow を PR5 にも適用
10. **境界等号値は SSOT で固定**: `total_pnl > 12000` (厳密) vs `max_dd_pct <= 1e-9` (等号含む) のような微妙な境界は実装と test で同期、 詳細設計に「等号方向 + 根拠」 を明示しないと future 改修で齟齬

## 既存問題 (PR4 と無関係、 前 handoff と同一、 別 TODO 候補)

- `test_t058_integration.py::test_end_to_end_writes_v2_summary_json` (T092 fold guard fixture)
- `test_run_ga_parallel.py` 14 件失敗 (= 同根)
- `archive.py:335` mypy 1 件 (PR2 由来 narrowing 不足)

## テスト実行単位ガイド (前 handoff と同一)

## 次のアクション (= 次の Claude セッション開始時の判断)

### Option A: PR4 smoke 検証 (= 1 RUN smoke 実行、 user 主導)

- 規模: 1 RUN 実行 (= 60-487 分)
- ユーザー or autopilot が実行
- 完了後に baseline 5 RUN median と比較 → 合格なら PR5 着手 / rollback 条件成立なら fitness_mode を legacy に戻す

### Option B: PR5 着手 (Stage B gate pfr_only opt-in A/B)

- 規模: M
- 行動変更: median_oos_sharpe を gate から外す、 positive_fold_ratio_effective ベース化
- 1 RUN smoke 必須
- PR4 smoke 後に着手するのが筋 (= Codex Y Round 5 dependency 順序)
- ただし PR4 smoke と並走で着手しても整合性問題なし (= 独立した opt-in flag)

### Option C: docs / scripts 並走 (= PR4 smoke を回す間)

- 順 6 docs/progress_criteria 明文化 (S、 行動不変)
- 順 7 scripts out-of-cluster audit (M、 PR3 shadow 列活用)
- 順 9 Stage C stratified allocation (M)

### Option D: push 先行

- 現在 main は origin/main から **12 commit ahead**
- push して GitHub 上で PR1-PR4 をまとめてレビュー可能化

### Option E: 既存問題修正

- T092 fold guard fixture (= 14 件 + 1 件 まとめ修正)、 中規模
- archive.py mypy fix、 小規模

### 推奨

PR4 smoke 検証 (Option A) を user が実行する時間に余裕があるタイミングで実施。 並行して docs/scripts (Option C) で観測基盤を強化。 PR5 (Option B) は PR4 smoke の合否を見てから判断。 push (Option D) は適宜。

## 関連 commit 履歴

```
bee43fa Merge branch 'todo/T094'
4cdd762 docs(devnotes): PR4 impl-review-round-1 + prompt 追加
ed73ea8 docs(todo+devnotes): T094 (PR4 legacy_pnl_smoke fitness opt-in) Closed + 設計ノート
86c7940 feat(stage_gate): legacy_pnl_smoke fitness opt-in + anti-luck guard (PR4)
63038ab docs(devnotes): PR3 完了後 引き継ぎ書
85d1dc8 Merge branch 'todo/T093'
259a0bf docs(todo+devnotes): T093 Closed + 設計ノート
dcec109 feat(archive): canonical/mission shadow 6 列追加 (PR3)
642866f docs(devnotes): PR1/PR2 完了後 引き継ぎ書
c18551e feat(archive): persistence_score_shadow 列追加 (PR2)
e81dc85 feat(archive): source_stage 値入力 (PR1)
```

## 重要ファイル参照

### 設計議論ログ

- `tmp/codex-debate-round2/` (新 X/Y/Z 議論、 closeout)
- `devnotes/20260513-0400-todo-pr1-source-stage/` (PR1 設計)
- `devnotes/20260513-1223-todo-pr2-persistence-score-shadow/` (PR2 設計)
- `devnotes/20260513-1419-todo-pr3-canonical-mission-shadow/` (PR3 設計)
- **`devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/`** (PR4 設計 + 2 round design review + impl-review)
- `devnotes/20260513-1402-handoff-pr1-pr2-postdebate/` (PR1/PR2 後 handoff)
- `devnotes/20260513-1511-handoff-pr3-postimpl/` (PR3 後 handoff)

### 実装本体 (PR1-PR4 累積)

- `src/alpha_factory/config.py` (PR4 で Phase4Config 追加、 loader 拡張)
- `src/alpha_factory/archive.py` (PR1-PR3 で更新、 schema 58 列)
- `src/alpha_factory/stage_gate.py` (PR3 で _canonical_shadow_summary、 **PR4 で _compute_clipped_pnl_slack / _compute_lucky_run_penalty / fitness 分岐 / payload 拡張**)
- `src/alpha_factory/canonical_metrics.py` (T061、 PR3 で配線)
- `src/alpha_factory/mission_inf_gap.py` (T062、 PR3 で配線)
- `scripts/alpha_factory/run_ga.py` (PR4 で `--fitness-mode` CLI 追加)
- `config/alpha_factory/default.yaml` (PR4 で phase4 section 追加)

### docs

- 既存 (`docs/alpha_factory/{stage-gates,mission-score,cross-pair,swim-lane}.md`)
- AGENTS.md / CLAUDE.md

### zenigame (参考)

- 前 handoff と同一

## このセッションでの学び (= プロセス改善材料)

1. **行動変更 PR は事前 Codex 設計レビューが価値高い**: PR4 で Round 1 [Critical] 2 件発見 (sentinel 不変性 / 境界等号)。 これらは設計時点で明文化して SSOT 化することで実装と test の齟齬を未然防止。 PR1-PR3 (行動不変) は省略可だが、 PR5 以降 (行動変更) は必須にすべき
2. **境界等号値の SSOT 化が future-proof**: 「`total_pnl > 12000` 厳密 vs `max_dd <= 1e-9` 等号含む」 のような微妙な境界は実装者の判断で揺れる。 詳細設計に「等号方向 + 根拠」 を明示することで future 改修で再現可能
3. **NaN/Inf 防御は config 層で SSOT**: `not 0.0 <= x <= 1.0` だけでは nan を取り逃がす (= 比較が False になる)。 `math.isfinite` を範囲チェックの前に置く。 Codex 指摘で初めて気付いたパターン
4. **opt-in default OFF + CLI override + sentinel 不変** の三層で「初の行動変更 PR」 も安全に merge 可能: smoke 検証は user 主導、 PR merge 自体は regression 0 (= legacy mode のみで GA 動作)
5. **既存 dual-path test の更新パターン**: PR3 で 8 件、 PR4 で 0 件 (= dual_path test は Stage A fitness を直接検証していないため、 sentinel 経路の追加 test 5 件で新規網羅)

## ユーザーへの確認待ち

- PR4 smoke 検証を回すタイミング (= 60-487 分、 EUR_JPY 1 RUN、 baseline 5 RUN median 比較)
- PR5 を PR4 smoke 前に着手するか、 smoke 後に判断するか
- push 先行 (= 12 commits ahead) を行うか
- Phase 2 統合 PR (PR11) の分割方針 (= 10 箇所同時更新の大規模化への対応)
- 既存問題 (T092 fold guard fixture / archive.py mypy) の分離 TODO 化タイミング
