# B step 1.7 Complete (Stage C stress dual-path 拡張) + 次 step 引き継ぎ Handoff

**作成日時**: 2026-05-04 00:03 JST
**Session**: B Phase 2 切替コミット step 1.7 完了 (= 概念設計 2 round + 詳細設計 2 round + 実装 1 round Codex APPROVED + main マージ)
**前 handoff**: `devnotes/20260503-2155-B-step1.6-complete-handoff/handoff.md`
**次セッション**: **B Phase 2 切替コミット step 1.8 (= Stage C cross_pair dual-path) または step 2 (= stage_bc_evaluator main flow 統合)**

---

## 0. 現在地

```
T081 step 1 (ABDivergenceMetric 実値配線)        ████████████████████ 100% ✨ (Closed、 main commit 27acfb3)
T081 step 2-6                                     ░░░░░░░░░░░░░░░░░░░░  Deferred
T082 (TradeRecord.spread_cost 伝搬経路配線)      ⚠ Obsoleted (前提誤認)
B step 1 (canonical_metrics → main flow 統合)    ████████████████████ 100% ✨🎉 (main commit 9bc6a02)
B step 1.5 (Stage B IS / Stage C base dual-path) ████████████████████ 100% ✨🎉 (main commit 6276d58)
B step 1.6 (Stage B per-fold dual-path)          ████████████████████ 100% ✨🎉 (main commit 1dadc8b)
B step 1.7 (Stage C stress dual-path)            ████████████████████ 100% ✨🎉 (本セッション、 main commit e3a428b)
B step 1.8 (Stage C cross_pair dual-path)        ░░░░░░░░░░░░░░░░░░░░    0% ← 次選択肢 A (mission 必須軸)
B step 2 (stage_bc_evaluator main flow 統合)     ░░░░░░░░░░░░░░░░░░░░    0% ← 次選択肢 B (規模 大)
B step 3-7                                        ░░░░░░░░░░░░░░░░░░░░    0%
T081 step 2-6 再開 (B 完了後)                     ░░░░░░░░░░░░░░░░░░░░    0%
GA 動作確認 (smoke 5 Run + 実 GA)                ░░░░░░░░░░░░░░░░░░░░    0%
```

---

## 1. 本セッション完了内容

### 1.1 B step 1.7 設計 (Codex 4 round)

設計ファイル: `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/`

#### 概念設計 (Codex Round 1-2、 Round 2 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] 2 件 (step 2 calibration 充足主張過剰、 C_stress canonical は stress hard gate の shadow ではない / C_base/C_stress diff 比較データ・sharpe_degradation の canonical 版表現は事実と不一致) + Warning 多数 |
| 2 | **APPROVED** | scope を「Stage C stress canonical metric 観測追加」に下げる、 C_stress は別ゲート観測 (= live_criteria ベース) であることを明文化、 C_base/C_stress 比較は後段集計の `(genome, stage)` join で descriptive のみ、 sharpe 読み替え表 § 2.5 追加、 前提表 4 段階分解 |

#### 詳細設計 (Codex Round 1-2、 Round 2 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | CHANGES_REQUESTED | [Critical] D2 反証 test 不足 (= test #2/#3 で `stage_c.stress_failure` 非出力 assert なし) + [Warning] `run_backtest` 2 回目 raise 方式が脆い (= call count 依存) + [Suggestion] golden 1 ケース言及との SSOT 整合 |
| 2 | **APPROVED** | test #2/#3 に capsys 追加で D2 反証強化、 `max_spread_bps` 値で stress 経路同定 (= call count 依存廃止)、 golden 1 ケース追加 (= 計 8 ケース) |

設計の主要決定:
- **scope**: Stage C stress 区画の dual-path canonical metric 観測追加のみ (= 任意・有益、 step 2 を block しない optional observability step)
- **C_stress canonical は別ゲート観測**: 既存 stress hard gate (= `spread_stress_min_total_pnl` 等) の shadow ではなく、 `live_criteria` ベースの 60d window scaled threshold 観測。 mission 判定にも切替判定にも使わない
- **物理隔離**: stress backtest 完了後の別 try ブロック、 stress_payload / reasons に絶対干渉しない (= step 1.6 と同型)
- **skip 整合**: max_spread_bps is None / stress 例外時は dual_path / canonical_five.skipped 両 event 0 件
- **disabled mode**: stress 成功時のみ `canonical_skipped=True` の dual_path event emit (= step 1.6 B_fold と同型)

### 1.2 B step 1.7 実装 + Codex 実装 review (Round 1 APPROVED)

| Round | 判定 | 主要取込 |
|---|---|---|
| 1 | **APPROVED** | Critical なし、 Suggestion 2 件のみ (= multiplier != 1 の早期検知 / dual_path / canonical_five.skipped 個別カウント) |

主要変更 (= worktree commit `06bb0c4`、 main merge commit `e3a428b`):

#### `_log_canonical_dual_path` docstring 更新 (stage_gate.py:170-235)
- `stage_label` の SSOT に **C_stress 追加** (= A / B_IS / B_fold / C_base / **C_stress** / C_cross_pair)
- `fold_index` の他 stage 列挙に **C_stress 追加**
- 動作不変、 既存 43 caller は keyword 呼出で完全互換

#### `evaluate_stage_c` stress dual-path 配線 (stage_gate.py:1398-1497)
- legacy stress 計算と dual-path を **2 つの別 try ブロック** で物理分離
- legacy 計算成功時のみ dual-path 試行 (= `stress_bt is not None` ガード)
- dual-path の二重 try (= helper 例外 + log 例外) で多層防御
- `stress_payload` / `reasons` (= spread_stress.* reasons) は legacy try 内のみ書き換え
- canonical_sidecar は payload 非添付 (= archive Parquet schema 不変)

key design (= 詳細設計 § 5 反映):
- step 1 / 1.5 / 1.6 で凍結した adapter / helper を完全再利用 (= 改変ゼロ)
- helper シグネチャ変更なし (= step 1.6 で確立した `fold_index=None default` をそのまま使う、 C_stress では None default)
- LOG_ONLY mode で既存判定経路完全に不変 (= regression 0)

テスト追加 (= 8 ケース、 計 51 ケース全 PASS、 regression 0):
- regression 0 (= legacy stress_payload + reasons 完全不変、 acceptance A1)
- log isolation (canonical raise: stage_label='C_stress' 限定 wrapper、 deep equality + D2 反証 (= stage_c.stress_failure 非出力 assert))
- log isolation (log helper raise: deep equality + D2 反証)
- propagation (= disabled mode で stress 成功時 canonical_skipped=True dual_path 1 entry emit、 fold key 不在)
- log content (= stage='C_stress' / genome / interpretation_note / canonical_* / legacy_*、 fold key 不在)
- skip 整合 max_spread_bps is None (= C_stress event 0 件)
- skip 整合 stress backtest 例外 (= max_spread_bps 値で stress 経路同定、 call count 依存廃止)
- golden 値固定 (= 1 ケース、 acceptance A5)

最終 test 結果: **51 passed** (= step 1 12 + step 1.5 21 + step 1.6 10 + step 1.7 8) / ruff / mypy clean、 alpha_factory 全 2181 passed (= step 1.6 比 +9 ケース)

### 1.3 main マージ + worktree クリーンアップ

- worktree commit `06bb0c4` を main に no-ff merge (`e3a428b`)
- worktree `todo-T085` クリーンアップ + branch 削除済
- worktree `todo-T081` は引き続き保持

---

## 2. 累積 commit 一覧 (本セッション、 main 5 個)

```
e3a428b Merge branch 'todo/T085'                                            ← main マージ
e9255c7 docs(TODO): T085 B-phase2-step1.7 Closed (impl-review Round 1 APPROVED)
06bb0c4 feat(B step 1.7): Stage C stress dual-path 配線追加 (Codex impl-review Round 1 APPROVED)  ← worktree commit
d5d9010 docs(TODO): T085 B-phase2-step1.7 (Stage C stress dual-path) Open 追加
22d26b9 docs(B-phase2-step1.7): Stage C stress dual-path 拡張 設計完了
```

本セッション commit 計 5 個。 cascade port v2 全体 commit 累計 ~82 個。

### 2.1 補足資料

- 概念設計 review: `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-review-round-{1,2}.md`
- 詳細設計 review: `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/detailed-review-round-{1,2}.md`
- 実装 review: `devnotes/20260503-2350-todo-T085/impl-review-round-1.md`

---

## 3. dual-path 観測点 (= step 1.7 完了時点)

per genome:
- Stage A: 1 entry
- Stage B IS: 1 entry
- Stage B fold: n_fold entries (動的、 ~8 fold 想定)
- Stage C base: 1 entry
- **Stage C stress: 1 entry (本セッションで追加、 stress 成功時のみ)**
- 合計: **4 + n_fold entries / genome**

GA Run 30 generations × 50 individuals × 6 pairs = 9000 genomes/Run、 n_fold = 8 想定で:
- ~108,000 dual-path log entries / Run (= 12 entries × 9000 genomes)

### 3.1 残未観測軸

- **Stage C cross_pair (ii-lite)**: mission 必須軸、 step 1.8 以降で対応必須
- canonical 5 metrics の数値 calibration 解釈: 別計画 (= n>>30 実 GA Run + collider bias 抑止条件下)

---

## 4. 次セッション着手フロー

### 4.1 推奨次着手: 2 つの選択肢

#### 選択肢 A: B step 1.8 (= Stage C cross_pair dual-path 拡張)

**scope**: evaluate_stage_c の cross_pair shadow 経路 (= stage_gate.py:1444-1494) に dual-path 配線追加。

- mission 必須軸 (= ii-lite 評価、 mission 達成条件) なので step 1.7 までより重要
- 規模 中〜大 (= cross_pair_evaluator の Protocol 実装と連携、 anchor pair 別 backtest 結果の dual-path)
- step 1.6 と同型 物理隔離 pattern を適用、 ただし cross_pair の特殊性 (= per anchor pair 別評価) で fold_index 同様の per anchor 識別子が必要かも (= step 1.6 fold_index と同型 pattern)

**規模**: 中〜大

#### 選択肢 B: B step 2 (= stage_bc_evaluator main flow 統合)

**scope**: stage_bc_evaluator (`evaluate_stage_b_pooled` / `evaluate_stage_c_lite`) を main flow から呼出。

- step 1.5 / 1.6 / 1.7 で dual-path 観測点が 5 系列で揃った
- ただし Stage C cross_pair (mission 必須軸) は依然未観測
- 規模 大 (= stage_gate.py の Stage B/C ハンドラを stage_bc_evaluator caller に置換)

**規模**: 大

### 4.2 推奨判断

**選択肢 A (= step 1.8、 cross_pair) を推奨**。 理由:
- mission 必須軸 (= ii-lite) を step 2 着手前に観測完成
- step 1.5-1.7 と同じ規模 中で「ゆっくり・確実に」リズム維持
- step 2 (規模 大) は cross_pair 観測完了後に着手するほうが calibration data 完全充足

ただし、 cross_pair は **interface only** で実装は別 TODO の状態 (= stage_gate.py:530 `class CrossPairEvaluator(Protocol)`)。 evaluate_stage_c で `cross_pair_evaluator: CrossPairEvaluator | None = None` を受け取る形で、 None のときは shadow only。

cross_pair の実装が **未配線** な現状で dual-path 配線を追加できるか、 着手前調査で確認が必要:
- 現実装: cross_pair_evaluator が None のとき `cross_pair_payload["skipped"]=True` で legacy 経路 skip
- step 1.8 では: cross_pair_evaluator が non-None で評価成功した場合のみ dual-path log emit (= skip 整合)
- ただし cross_pair_evaluator の実装が main flow 経路に統合されていない (= 通常 None で run) ため、 dual-path 配線は **interface ベースの設計のみ可能**、 実観測は cross_pair 実装完了後

→ step 1.8 で「skeleton 配線 + Protocol 互換性確保」 だけ先行する案、 または cross_pair 実装が main flow に来てから配線する案 (= step 2 と統合) のいずれか。

**着手前調査が重要**な step。

### 4.3 各 step の Codex 設計 / 実装 review fence

両選択肢で共通:
1. zenigame-fx-alpha-design で skeleton → Codex review APPROVED
2. zenigame-fx-implement で worktree todo/B-step{1.8,2} で実装 → Codex impl-review APPROVED
3. main マージ → 次 step

---

## 5. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path) | canonical_metrics | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS + Stage C base dual-path | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | (stage_gate.py のみ) | **完了** (commit 1dadc8b) |
| step 1.7 ✨ | Stage C stress dual-path | (stage_gate.py のみ) | **完了** (commit e3a428b) |
| step 1.8 | Stage C cross_pair (ii-lite) dual-path | (stage_gate.py + cross_pair) | **次推奨 (mission 必須軸)** |
| step 2 | stage_bc_evaluator → main flow | stage_bc_evaluator | 後続 |
| step 3-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 6. 次セッション first prompt 例

### B step 1.8 (推奨) 着手の場合

```
引き継ぎは devnotes/20260504-0003-B-step1.7-complete-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 1.8 (= Stage C cross_pair dual-path 拡張) を実装着手。

着手前調査 (= 重要):
1. evaluate_stage_c の cross_pair 区画 (stage_gate.py:1444-1494) の構造確認
2. CrossPairEvaluator Protocol (= stage_gate.py:530) の signature と現実装状況
3. cross_pair_evaluator が main flow で None の場合のみか、 non-None で評価される
   ケースが存在するか
4. dual-path 配線が現実的に観測値を生成できるか (= cross_pair 実装が来ていない場合は
   skeleton 配線 + Protocol 互換性確保のみで先行する判断もあり)

設計:
5. step 1 / 1.5 / 1.6 / 1.7 で凍結した canonical_adapter.py / helper を再利用
6. 物理隔離 (= 別 try ブロック) で cross_pair_payload / cross_pair reasons に
   干渉しない pattern (= step 1.6 / 1.7 と同型)
7. stage_label="C_cross_pair" + per anchor pair 識別子の検討
   (= step 1.6 fold_index と同型 pattern が必要かも)

ゆっくり・確実に: cross_pair の現状把握が最重要、 着手前調査で「dual-path 配線可能か /
skeleton 先行か / step 2 と統合か」 を判断してから設計着手。

Codex review APPROVED → 実装 → main マージ → step 2 へ。
```

### B step 2 (選択肢 B) 着手の場合

```
引き継ぎは devnotes/20260504-0003-B-step1.7-complete-handoff/handoff.md 読んで。
B Phase 2 切替コミット step 2 (= stage_bc_evaluator main flow 統合) を実装着手。

着手前調査:
1. src/alpha_factory/stage_bc_evaluator.py の signature と既存 API
2. 現在の evaluate_stage_b / evaluate_stage_c (stage_gate.py) が
   stage_bc_evaluator に置換可能な構造か
3. step 1.5-1.7 の dual-path log で取れた calibration data が
   stage_bc_evaluator 統合後も継続観測可能か

注意: Stage C cross_pair (mission 必須軸) は依然未観測なので、
step 2 着手前に step 1.8 を先行する判断もあり。

ゆっくり・確実に: 規模 大の改修なので着手前調査充実 + 設計 2 段階で進める。

Codex review APPROVED → 実装 → main マージ → step 3 へ。
```

---

## 7. 残課題・運用観測 follow-up (= step 1.7 から繰り越し)

詳細設計 § 12 / 概念設計 follow-up 反映:

1. **canonical 失敗件数閾値ベースの fail-fast サーキットブレーカ**: step 1.7 では WARN log のみ
2. **CI メモリ閾値ガード**: smoke 5 Run の peak RSS / wall time / dual-path log bytes を CI で監視。 step 1.7 では手動実測 (= acceptance B2/B3)
3. **canonical sidecar archive Parquet schema 拡張**: 永続化層への canonical 値書き込み (= step 3 cpps_archive 統合と合わせて検討)
4. **smoke 5 Run の peak RSS 実測** (= acceptance B2): step 1.7 では概算で base 同等の低リスク仮説、 別計画で実 GA Run 時に確認
5. **smoke 5 Run の所要時間が step 1.6 比 ±20% 以内** (= acceptance B3): 同上
6. **Stage C cross_pair (ii-lite) dual-path**: mission 必須軸、 step 1.8 で必須
7. **stress hard gate との対応付け / calibration**: C_stress canonical の意味整合は step 2 か別 step で扱う
