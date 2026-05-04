# step 2.1 保留 + 軸転換: 「実 GA 走らせ + 死にコード解消」 引き継ぎ Handoff

**作成日時**: 2026-05-04 12:09 JST
**Session**: B step 2.1 (= stage_bc_evaluator main flow shadow integration) 詳細設計 max round 5 で APPROVED 不能 → ユーザ判断で **軸を転換**: 「dual-path 観測拡充」 から **「全体の GA を走らせられるところまで作り込む + 死にコードを解消」** へ
**前 handoff**: `devnotes/20260504-1018-B-step1.8-complete-handoff/handoff.md`
**次セッション**: **GA 実走可否確認 + 死にコード調査・解消**

---

## 0. ユーザの新しい指示 (= 本セッション末尾)

> 「全体の GA を走らせられるところまで来たら教えて欲しい。 死にコードがない状態まで作り込んで、 走らせて...という」

要点:
- **当面の優先**: 全体の GA を実走させられる状態の確立
- **死にコード解消**: 配線されていない module / 偽 placeholder / 未到達経路 を解消
- **走らせる → 結果を見る** が次の improvement loop の起点

これまでの軸 (= step 1.5-1.8 dual-path 観測拡充、 step 2 切替) は、 GA 実走前に過剰 build していた可能性。 観測ループは GA を実走できる土台が確立してから回す。

---

## 1. step 2.1 の保留状況

### 1.1 設計フェーズの結果

| Round | 判定 | 主要発見 |
|---|---|---|
| 概念設計 R1-R5 | **R5 APPROVED** | 案 B 段階分割確定 (= step 2.1a feasibility + 2.1b shadow logging + 2.2 switch + 2.3 deprecation)、 「Phase 2 切替コミット完了」 呼称は 2.2 完了時のみ |
| 詳細設計 R1 | CHANGES_REQUESTED | builder signature 不一致 / shadow_pairs eager materialization メモリ反証 / schema key 不整合 / pool 経路 collector 集約不能 など Critical 多数 |
| 詳細設計 R2 | CHANGES_REQUESTED | StageBCShadowIdentity 必要 / GenomeStageResult.shadow_event_payload は archive 漏洩リスク / pool 経路 run_summary 未実装 |
| 詳細設計 R3 | CHANGES_REQUESTED | 「現設計は SSOT として不成立」 = 改訂対応マトリクスと本文 snippet が衝突 |
| 詳細設計 R4 | **APPROVE_WITH_CHANGES** | 構造方向 OK (= WorkerEvaluationResult / capture sink / anchor_plus_shadow 母集団分離)、 残は本文 SSOT 化 |
| 詳細設計 R5 (max round) | CHANGES_REQUESTED | 構造方向採用可能、 本文 SSOT 完全書き直しが必須 (= R6+ で対応) |

### 1.2 規模感が過大であることの判明

step 2.1 (= shadow integration LOG_ONLY) のはずが、 設計だけで:
- 概念設計 5 round + 詳細設計 5 round = **累計 10 round の Codex review**
- 新規 dataclass 3 種: `StageBCShadowContext` / `StageBCShadowIdentity` / `WorkerEvaluationResult`
- 新規 module 2 種: `bc_evaluator_shadow.py` / `bc_evaluator_shadow_collector.py`
- caller 改修 4 ファイル: `stage_gate.py` / `parallel_eval.py` / `swim_lane.py` / `run_ga.py`
- test 40 ケース

これは **「過度な複雑化」 (= AGENTS.md 禁止事項 #5)** のシグナル。 「ゆっくり・確実に」 リズム尊重の観点で一旦立ち止まり、 軸を転換する判断。

### 1.3 設計成果物の保存場所

すべて main にコミット済 (commit `77fc45b` = 概念設計):

- `devnotes/20260504-1026-B-phase2-step2-stage-bc-evaluator-main-flow-integration/`
  - `conceptual-design.md` (= R5 APPROVED、 案 B 段階分割確定)
  - `conceptual-review-round-{1,2,3,4,5}.md`
  - `detailed-design.md` (= R5 で本文 SSOT 未完成、 改訂対応マトリクスのみ蓄積)
  - `detailed-review-round-{1,2,3,4,5}.md`

詳細設計の本文は **R2/R3 の断片が混在し SSOT 不成立**、 ただし Codex は構造方向を「採用可能」 と判定。 実装着手は本文 SSOT 完全書き直し後 (= R6+ で対応) が望ましい。

### 1.4 step 2.1 の TODO / commit 状態

- TODO 登録: なし (= 概念設計のみコミット、 step 2.1 用の TODO は登録していない)
- main commit: `77fc45b docs(B-phase2-step2.1): Stage BC evaluator main flow shadow integration 概念設計 APPROVED`
- worktree: なし (= 実装フェーズ未着手)

step 2.1 を再開する際は、 **詳細設計 Round 6+ で本文 SSOT 完全書き直し → APPROVED → TODO 登録 → worktree 実装** の経路を辿る。

---

## 2. 新しい軸: 「実 GA 走らせ + 死にコード解消」

### 2.1 着手前調査 (= 次セッション必須)

**目標**: 現状で全体の GA Run が実走できるか確認、 走れない場合は最小修正で走らせる。

#### 調査 A: GA 実走の現状確認
1. `scripts/alpha_factory/run_ga.py` を素読 → 起動経路の把握
2. `config/alpha_factory/default.yaml` を読み → 必須 aux データ / 設定の前提条件確認
3. **smoke run** (= 最小規模) を試行: `uv run python -m src.alpha_factory.run_ga --config config/alpha_factory/default.yaml --smoke` 等で実走確認
4. エラーが出たら原因切り分け (= aux データ不足 / 配線漏れ / config 値不整合)

#### 調査 B: 死にコード (= dormant code) の特定

本セッションの step 2.1 着手前調査で発覚した dormant code 群:

| dormant 対象 | 状態 | 影響 |
|---|---|---|
| `src/alpha_factory/stage_bc_evaluator.py` (1419 行) | T064 PR1 で実装済、 production caller **0 件** | 「Phase 2 で main flow へ反映」 と明記されたが未配線。 step 2.1 で配線予定だったが保留 |
| `src/alpha_factory/failure_handling.py:evaluate_bc_safe` | wrapper 実装済、 production caller **0 件** | step 2.1 isolation boundary として再利用予定だったが未配線 |
| `src/alpha_factory/loop_closure.py` | `BCEvaluationResult` 型 import あり | bc_result が常に None で走っている可能性 (= step 2.1 着手前調査で「detail 確認すべき」 と note) |
| `src/alpha_factory/nsga2_selection.py` | `BCEvaluationResult` 型 import あり、 docstring に「a_pass のみ非 None、 a_fail は」 | 同上、 a_pass 経路でも bc_result=None で走っている可能性 |
| `src/alpha_factory/cpps_archive.py` | `BCEvaluationResult` / `StagePassStatus` import あり | archive 経路で bc_result の有無による分岐挙動を確認すべき |

**死にコード調査の手順** (= 次セッション着手前):
1. `grep -rn "BCEvaluationResult\|evaluate_bc_for_a_pass\|evaluate_bc_safe" src/ scripts/` で全使用箇所を再列挙
2. 各使用箇所で「caller が non-None で渡しているか」「常に None で走っているか」 を Read で確認
3. dormant 経路を「production runtime に到達していない」 ものとして列挙
4. 起動した GA 実走で「実際にどの経路が呼ばれるか」 を log で trace

#### 調査 C: 既存コード全体の配線確認

step 1-1.8 で確立した dual-path log は configurable (= `phase2_canonical_metrics_mode`)。 default 設定で:
- どの dual-path log event が emit されるか
- どの evaluator (= stage_gate.py 旧 API or stage_bc_evaluator 新 API) が走るか
- どの post-evaluation 経路 (= GA selection / archive / loop closure) が活発か

を実走 log で確認する。

### 2.2 「死にコードがない状態」 の定義

GA 実走時に **production runtime で 1 回も呼ばれない module / 経路** は dormant とみなす。 step 2.1 で見つけた以下の dormant code は段階的に解消:

1. **stage_bc_evaluator 系**: step 2.1 で配線予定だったが保留。 GA 走らせるためには **必須ではない** (= 旧 API stage_gate.py 経路で動作する)。 step 2.1 を再開して配線するか、 不要なら削除候補 (= ただし削除は議論必要、 T064 で実装した synthesis § 5.2 確定式を捨てることになる)
2. **failure_handling.evaluate_bc_safe**: stage_bc_evaluator 用 wrapper、 同様に保留 / 削除候補
3. **その他 (= 調査 B / C で発覚するもの)**: 都度判断

死にコード解消の基本方針:
- **削除前に必ず確認**: 「何のために実装されたか」 を git log + devnotes で追跡 (= C1 Design-first)
- **将来必要なら維持**: T064 の stage_bc_evaluator は synthesis § 5.2 確定式の参照実装、 削除は Phase 切替計画と整合させる
- **配線可能なら配線**: step 2.1 を再開する余地があるなら配線、 ただし設計 SSOT を rigorous に確立してから

### 2.3 GA 実走後の improvement loop

GA を 1 回走らせて結果を見る → 何を改善すべきかが見える形になる。 そこから:
- step 2.1 (= shadow integration) を本当に必要とするのか再判断
- step 1.5-1.8 で確立した dual-path log が calibration data として有用か実 data で確認
- 別軸の優先 (= primitive 改善 / config 調整 / aux データ拡張等) が浮上するか

---

## 3. 累積 commit 一覧 (本セッション、 main 1 個)

```
77fc45b docs(B-phase2-step2.1): Stage BC evaluator main flow shadow integration 概念設計 APPROVED
7348887 docs(handoff): B step 1.8 完了 + step 2 (stage_bc_evaluator 統合) 引き継ぎ  ← 前セッション handoff
c3ee70a Merge branch 'todo/T086'                                                    ← step 1.8 main merge
```

詳細設計は本文 SSOT 不成立のためコミットしない (= 改訂対応マトリクスと本文 snippet 衝突状態のため)。 次セッションで再開する場合、 R6 で本文書き直してから commit する。

cascade port v2 全体 commit 累計: ~89 個。

---

## 4. 7 step segmentation の現状

| step | 内容 | 状態 |
|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (Stage A dual-path) | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS + Stage C base dual-path | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | **完了** (commit 1dadc8b) |
| step 1.7 ✨ | Stage C stress dual-path | **完了** (commit e3a428b) |
| step 1.8 ✨ | Stage C cross_pair (ii-lite) dual-path | **完了** (commit c3ee70a) |
| step 2 = B Phase 2 Integration Program | (= 段階分割) | **保留** (= 軸転換) |
| └ step 2.1a + 2.1b | shadow integration | 概念設計 APPROVED、 詳細設計 R5 max で SSOT 不成立で **保留** |
| └ step 2.2 | switch | 後続 |
| └ step 2.3 | deprecation | 後続 |
| step 3-7 | (詳細はハンドオフ § 4) | 後続 |

**新しい優先軸** (= ユーザ指示):
- **GA 実走可否確認 + 死にコード解消** ← 次セッション
- 実走できたら「走らせて → 結果を見る」 サイクルへ
- step 2.1 / 2.2 / 2.3 は GA 実走 + improvement loop の中で必要性を再判断

---

## 5. 次セッション first prompt 例

```
引き継ぎは devnotes/20260504-1209-step2.1-suspended-handoff/handoff.md 読んで。

軸転換に従い、 まず「全体の GA を走らせられるところまで」 を確認する。

調査 A: GA 実走の現状確認
1. scripts/alpha_factory/run_ga.py を素読 → 起動経路把握
2. config/alpha_factory/default.yaml を読み → 必須 aux データ / 設定の前提条件確認
3. smoke run (= 最小規模) を試行 → 実走可否確認
4. エラーが出たら原因切り分け

調査 B: 死にコード (= dormant code) 特定
1. grep -rn "BCEvaluationResult|evaluate_bc_for_a_pass|evaluate_bc_safe" src/ scripts/
2. 各使用箇所で caller が non-None / None を確認
3. dormant 経路を列挙
4. GA 実走で実際の経路を log で trace

調査 C: 既存コード全体の配線確認
- step 1-1.8 dual-path log の emit 状況
- stage_gate.py 旧 API vs stage_bc_evaluator 新 API のどちらが走るか
- post-evaluation 経路 (GA selection / archive / loop closure) の活発度

GA 実走できたら、 結果を見て次の improvement 方向を判断する。

step 2.1 の保留設計成果物 (= devnotes/20260504-1026-B-phase2-step2-...) は将来再開時の参照、 即時対応不要。
```

---

## 6. 残課題 (= 軸転換後の follow-up)

1. **step 2.1 設計成果物の整理**: detailed-design.md は R2/R3 の断片混在で SSOT 不成立、 再開時に本文書き直し or 削除して再着手 を判断
2. **死にコード判定基準の明文化**: 「何を死にコードと呼び、 削除 or 配線するかの判断基準」 を docs に追加 (= 例: T064 の参照実装は将来必要なら維持、 step 2.1 で配線するか議論)
3. **GA 実走 baseline の確立**: 1 回目の GA 実走結果を `reports/run-reports/run-N/` に保存、 step 1.5-1.8 dual-path log の data sample として next-step calibration の基礎にする
4. **AGENTS.md の更新**: 軸転換の経緯と現方針 (= 「dormant code を増やさず、 走らせ可能な状態を維持」) を反映するか検討

---

## 7. ユーザ指示の精神 (= 改めて)

> 「死にコードがない状態まで作り込んで、 走らせて...という」

これは「完成品を build する」 のではなく:
- 動く最小単位を維持しつつ
- 走らせて結果を見る → 改善する loop を回す
- 観測拡充 (= step 1-1.8) も dual-path 切替 (= step 2) も、 「実 GA 走らせ + 結果から学ぶ」 サイクルの **手段** であり目的ではない

設計フェーズで Codex review を 10 round 重ねるよりも、 走らせて見えてきた問題を解決する方が価値が高い。 「ゆっくり・確実に」 リズムは、 round 数を重ねることではなく、 走らせ可能な土台を確実に維持することで実現する。
