# step 2.1 保留 + 軸転換: 「実 GA 走らせ + 死にコード解消」 引き継ぎ Handoff

**作成日時**: 2026-05-04 12:09 JST
**Session**: B step 2.1 (= stage_bc_evaluator main flow shadow integration) 詳細設計 max round 5 で APPROVED 不能 → ユーザ判断で **軸を転換**: 「dual-path 観測拡充」 から **「全体の GA を走らせられるところまで作り込む + 死にコードを解消」** へ
**前 handoff**: `devnotes/20260504-1018-B-step1.8-complete-handoff/handoff.md`
**次セッション**: **GA 実走可否確認 + 死にコード調査・解消**

---

## 0-pre. 一連の実装の出発点 (= 「そもそも何のために始まったのか」 想起)

**究極目標 (= synthesis § 1.1)**:
> zenigame-fx Alpha Factory の使命は **live_criteria** (`config/alpha_factory/default.yaml`) を全て満たす FX イントラデイ戦略ゲノム個体を 1 つ見つけ出すこと。

**起点**: 2026-04-28 `devnotes/20260428-2300-cascade-port-debate/` の Codex × 20 round 議論
→ zenigame の selection cascade 思想 (T508/T509/T511/T513) を zenigame-fx に **big-bang 導入** する設計上位文書 (= synthesis Round 22 SSOT) を確立。

**big-bang 方針 (= synthesis § 1.4 Round 19-20 確定)**:
- 後方互換性・段階導入は **不要**
- これまでの実装はベースラインにすらしない
- NSGA-II と CPPS の切り替え機構 (fallback flag) は不要、 純 CPPS のみ

**カスケードした流れ** (= 起点から本セッション保留まで):

```
2026-04-28  cascade port debate Round 1-20 (= big-bang 方針確定、 synthesis SSOT 化)
2026-05-02  T076 synthesis Round 22 改訂 完了 (= Phase 2 配線完了に伴う SSOT 同期)
            ├─ Phase 1 設計 18 件 (T058-T075) APPROVED 完了
            └─ Phase 2 配線 18 件 (T058-T075) main merge + Closed 完了
2026-05-02  T077-T080 follow-up 完了 (= applied_from_run_id 必須化 / TradeRecord schema 拡張 / DST / T071 caller stub 配線)
            ├─ T080a で 9 metric stub builder 経路確立 (= reports/run-reports/{run_id}/observability.json 出力)
            └─ T081 (9 metric 実値配線、 6 step) Open 登録、 T082 (spread_cost 伝搬) Open 登録
2026-05-03  T081 step 1 (ABDivergenceMetric 実値配線) のみ完了
            └─ T081 step 2-6 blocker 発覚: 上流 T063-T068 module が main flow 未統合
2026-05-03  T082 Obsoleted: TradeRecord 経路が main flow に未統合で前提誤認
            └─ blocker の根本対応として 「B Phase 2 切替コミット」 = canonical_metrics → main flow 直接統合 へ転換
2026-05-03  B step 1 (canonical_metrics → main flow 統合) 完了 (commit 9bc6a02)
2026-05-03  B step 1.5 (Stage B IS / Stage C base dual-path) 完了 (commit 6276d58)
2026-05-03  B step 1.6 (Stage B per-fold dual-path) 完了 (commit 1dadc8b)
2026-05-03  B step 1.7 (Stage C stress dual-path) 完了 (commit e3a428b)
2026-05-04  B step 1.8 (Stage C cross_pair dual-path) 完了 (commit c3ee70a)
2026-05-04  B step 2.1 (stage_bc_evaluator main flow shadow integration) 設計 R5 max → SSOT 不成立 → 保留
            └─ ★ 本セッション末尾で軸転換: 「実 GA 走らせ + 死にコード解消」
```

**何が問題か** (= 振り返り):

big-bang 方針で出発したが、 T081 blocker 以降「上流 module 未統合」 を解消する過程で:
- B step 1 で canonical_metrics 1 経路を main 配線
- step 1.5-1.8 で dual-path 観測 (= 旧 API + 新 API 並走) を 4 段重ねた
- step 2 で shadow integration → 詳細設計 5 round で SSOT 不成立

= **観測の精緻化 (dual-path) が膨らみすぎ、 「走らせて live_criteria 個体を 1 つ見つける」 という究極目標から遠ざかっていた**。

**big-bang 方針への回帰** (= ユーザ指示の精神):

走らせ可能な土台を確立 → 走らせる → 結果を見る → live_criteria 達成への距離を測る → 改善方向を判断、 が本来の loop。 観測拡充も dual-path 切替も、 この loop の **手段** であって目的ではない。

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

## 6.5 本セッション末尾の追加実証 (= 軸転換後の即時着手結果)

### 6.5.1 GA 実走可否確認 ✅ 達成

**smoke run (= pop=8 / gen=2 / max_workers=1)**: **35 秒で完走**
```
$ uv run python -m scripts.alpha_factory.run_ga \
    --population-size 8 --generations 2 --max-workers 1 --no-report
[done] run_id=run_20260504_032021 run_number=27 best=g1_i5 fitness_pen=-0.060712561910847986 stage_c=False report=skipped(--no-report)
```

**default run (= pop=40 / gen=15 / max_workers=2)**: **7 分で完走** (run-27)
```
[done] run_id=run_20260504_032451 run_number=27 best=g11_i3
       fitness_pen=-0.007865665750332627 stage_c=False
       report=reports/run-reports/run-27
```
- 全 15 世代 stage_a_pass=0 / stage_b_pass=0 / stage_c_pass=0 / graduation_count=0
- best fitness_pen=-0.0079 (negative = 損失方向)、 過去 Run-22-26 と同傾向 (= live_criteria 達成個体未出現)
- ABDivergenceMetric は status="insufficient_data" (n_pairs=0) = b_evaluated 個体ゼロのため計算不能

**確認できた事実**:
- aux データ preflight 全 PASS (= VIXCLS 94% / DTWEXBGS 91% / EUR_USD M1 67% / USD_JPY M1 67% / GC_F 92% / WTI 90% / Copper 85% / Pall 85% / SP500 92%)
- Stage A bars 86400 / dataset_epoch_id=epoch_20251001_20260401 で正常動作
- stage_gate.effective_threshold = 0.0 (config 由来、 history 適用なし)
- B step 1-1.8 で配線した dual-path log (`stage_gate.canonical_five.dual_path`) が世代毎に emit されている
- backtest engine から TradeRecord 構築 → canonical_metrics 5 metric 計算 → legacy 値と並走 log の経路が機能

**= 「全体の GA を走らせられる」 = ユーザ要件 1 達成**。

### 6.5.2 死にコード調査 — dormant chain 検出 (~5000+ 行)

**検証手順**:
1. `grep -rn "BCEvaluationResult|evaluate_bc_for_a_pass|evaluate_bc_safe" src/ scripts/` → production caller 0 件 (= test only)
2. 各下流 module の caller を再 grep → import chain は残存、 production 経由は不到達

**検出した dormant chain (=「死にコード」)**:

| module / function | 行数 | production caller | 死にコード判定 |
|---|---:|---|---|
| `src/alpha_factory/stage_bc_evaluator.py` 全体 | 1419 | 0 件 | ✅ 完全 dormant |
| `src/alpha_factory/failure_handling.evaluate_bc_safe` + 関連 BCEvaluationResult helper | ~600 | 0 件 | ✅ dormant |
| `src/alpha_factory/loop_closure.py` 全体 | ~1100 | 0 件 (= run_ga.py から不到達) | ✅ dormant |
| `src/alpha_factory/cpps_archive.determine_archive_role` + `compute_inflow_targets` | ~150 | loop_closure 経由のみ (= dormant 連鎖) | ✅ dormant |
| `src/alpha_factory/nsga2_selection.py` 全体 | ~700 | observability/run_metrics 経由のみ + extract_selection_metrics は run_ga.py で **未呼出** (build_default_selection_metric を使用) | ✅ dormant |
| `src/alpha_factory/observability/run_metrics.extract_*` / `compute_*` 8 関数 | ~800 | run_ga.py は build_default_*_metric を使う (= ABDivergence のみ実値、 残 8 metric stub) | ✅ dormant (= T081 step 2-6 未着手) |

**累計推定: ~5000+ 行が dormant** (= production runtime で 1 回も呼ばれない)。

**run_ga.py の現実経路** (= 確認済):
```
run_ga.py:1683  compute_ab_divergence_on_b_evaluated(...)        ← 実値配線 (T081 step 1)
run_ga.py:1687  build_run_observability_report(
                  ab_divergence=ab_divergence_metric,             ← 実値
                  q_force_recommendation=...default...,           ← stub
                  archive_churn=...default...,                    ← stub
                  bypass_ratio=...default...,                     ← stub
                  session_entropy=...default...,                  ← stub
                  feasible_ratio=...default...,                   ← stub
                  selection=...default...,                        ← stub (= GenerationSelectionResult 不到達)
                  inflow_consistency=...default...,               ← stub (= WarmstartReport 不到達)
                  failure=...default...,                          ← stub (= RunFailureSummary 不到達)
                )
```

= **production runtime は ABDivergence 1/9 metric のみ実値**。 残 8 metric は stub default、 関連する T065-T068 module 配線も全て unreachable。

### 6.5.3 構造的バグ発見 — TradeRecord exit==entry 同時刻エラー多発

smoke 観察:
```
[warning] stage_gate.canonical_five.skipped
  error='TradeRecord.exit_time_utc (2026-02-06 11:26:00+00:00)
         must be > entry_time_utc (2026-02-06 11:26:00+00:00)'
  error_type=TradeRecordInvalidError genome=g0_i2 stage=A
```

**頻度**: pop=8 で複数個体 (= g0_i2, g0_i4, g0_i5, g0_i6, g1_i0, g1_i1, g1_i4, g1_i5, g1_i7, g2_i0-g2_i5 ...)、 default smoke 観察でも g2 世代で 1/3 程度の個体で発生

**現象**:
- backtest engine が同一 bar (1 分 bar) 内で entry/exit する trade を生成
- canonical_metrics.TradeRecord (`canonical_metrics.py:272`) で `exit_time_utc <= entry_time_utc` を fail-fast invariant としており、 該当 trade が 1 個でも含まれると **canonical_five 全体が skip**
- legacy 評価は同一 trade を許容して走るので Stage A pass 判定は legacy 側のみで決まる

**インパクト**:
- canonical_metrics 経路で個体半数が skip → step 1.5-1.8 で苦労して配線した dual-path log が「両系で同時に値が見える個体」 が半分しかない状態
- big-bang 切替 (= step 2 完了で legacy 廃止) を強行すると **個体半数が「skip 扱いで Stage A 不通過」** になる構造的問題

**根本原因候補 (= 未確定、 要追跡)**:
- backtest engine 側の 0-bar holding trade を canonical_metrics 構築前に filter すべきか
- canonical_metrics.TradeRecord invariant を緩和して 0-bar trade を許容すべきか (= synthesis SSOT 観点で要議論)
- 上記いずれを採るか = step 2 切替前に確定すべき問題、 dormant chain 解消より優先度高

### 6.5.4 死にコード解消の選択肢 (= 次セッション判断)

dormant chain 5000+ 行に対する対応:

| 案 | 工数 | リスク | big-bang 方針 (synthesis § 1.4) との整合 |
|---|---|---|---|
| **A. 完成配線**: step 2.1-2.3 + T081 step 2-6 を完走 | 数週間 | 設計 R5 で SSOT 不成立、 過去 round 経緯で品質懸念 | ◯ (= cascade port v2 設計の最終段) |
| **B. 完全削除**: stage_bc_evaluator + loop_closure + 関連 helper / metric extract を big-bang で削除 | 数日 | synthesis § 5.2 確定式・§ 8.2 archive_role 設計を捨てる | △ (= big-bang 方針だが設計を捨てる) |
| **C. 段階削除 + 配線維持**: 完全 dormant の stage_bc_evaluator のみ削除、 nsga2_selection / observability の extract 経路は将来 metric 拡張に備えて維持 | 数日 | extract 関数群の dormant 状態は残る | ◯ (= 走らせ可能性維持 + 大物 dormant 削減) |
| **D. 現状維持 + dormant 明示**: docstring / README に「dormant、 将来 step 2 で配線」 を明示、 即時削除なし | 数時間 | 死にコード「ない状態」 にはならない | × (= ユーザ要件 2 未達) |

**推奨**: **案 C 段階削除** が big-bang 方針と「走らせ可能性維持」 の両立として最も合理的。 ただし TradeRecord exit==entry 構造的バグ (§ 6.5.3) を先に解決しないと、 dormant chain 削除後の big-bang 切替で個体半数が skip 扱いになる致命的問題が表面化する。

**順序提案**:
1. **TradeRecord 0-bar trade 構造問題の解決** (= backtest filter or invariant 緩和) ← 最優先
2. **default GA 実走完走実証 + 結果分析** (= 1 回目の RUN baseline 確立)
3. **死にコード解消 (案 C)** ← legacy + canonical 両系で同等個体数が走るようになってから

---

## 6.6 improve-cycle 1 の経過 (= /loop ではなく単発実行)

**起動**: 2026-05-04 12:36 JST、 引数 `--repeat`
**tmp_dir**: `devnotes/20260504-1236-fx-improve/`

### Phase 1 analyze-run (Run-27 = run_20260504_032451)
- archive 全 640 個体で stage_a_pass=0、 best fitness_pen=-0.0079
- Codex 独立分析が C1 (Design-first) と C2 (X 無い=バグ禁止) で重要修正
  - 「primitive 拡充を即 Critical」 = 仕組み未検証で値弄り違反
  - 「archive NaN = 死にコード断定」 = C2 違反、 切り分け監査が先

### Phase 2 plan-and-design
- consensus Round 2 で APPROVED: 「Run-28 = (c) diagnostic instrumentation のみ」
- design-review Round 3 で APPROVED (= 3 round 合議): run-effective config 取得経路の確定
- 反証可能仮説: Stage A pass=0 の root cause は (P1) primitive / (P2) penalty / (P3) 探索 dynamics のいずれか

### Phase 2.5 calibrate-gate
- decision: **loosen**, threshold 0.0 → **-0.0172** (= 200 行集計、 q_target=-0.0172)

### Phase 3 implement (= TODO 不在のため Claude 直接、 main commit `f6c7c43`)
- 新規 `scripts/alpha_factory/analyze_stage_a_diagnostic.py` (~450 行)
- 新規 `tests/scripts/test_analyze_stage_a_diagnostic.py` (16 テスト全 PASS)
- Run-27 適用結果: **diagnosis=INCONCLUSIVE confidence=low** (= 設計予測 P1 high が外れた、 improvement loop の典型)
  - **P1 match**: raw_max=0.0011 < 0.005 ✓
  - **P2 match**: penalty_killed=30 (= 全 raw>0 個体 30 個が penalty で潰されている) ✓
  - **P3 N/A**: summary.run_id ≠ archive run_id 検出で degrade

### Phase 3 副次発見: archive write vs summary write の run_id 不一致
- archive parquet 名: `run_20260504_032451`
- summary.json run_id: `run_20260504_032436` (= 15 秒前)
- = production runtime で archive と summary の run_id 生成タイミングがズレる構造的問題候補
- **別 cycle で扱う題材 (= 今 cycle の C1 で偶然検出)**

### 重要な学び (= Run-27 diagnostic からの観察)
- raw_positive_count=30 (= 想定 1 個体ではない、 = primitive は positive sharpe を生成可能)
- 全 30 個体が penalty で潰されている = **P2 (penalty / config 設計) が真の支配的要因の可能性**
- = Codex 予測 (P1 high) を archive が反証 = improvement loop が機能した好例

### Phase 4-6 (= 進行中 / 後続 cycle)
- Phase 4 Run-28: BG 実行中 (threshold=-0.0172 適用済)
- Phase 5: Run-28 完了後に diagnostic 適用 + run-report 生成
- Phase 6: --repeat なので次 cycle へ (Run-28 結果次第で P2 仮説 = penalty / config 設計打ち手の検討)

---

## 7. ユーザ指示の精神 (= 改めて)

> 「死にコードがない状態まで作り込んで、 走らせて...という」

これは「完成品を build する」 のではなく:
- 動く最小単位を維持しつつ
- 走らせて結果を見る → 改善する loop を回す
- 観測拡充 (= step 1-1.8) も dual-path 切替 (= step 2) も、 「実 GA 走らせ + 結果から学ぶ」 サイクルの **手段** であり目的ではない

設計フェーズで Codex review を 10 round 重ねるよりも、 走らせて見えてきた問題を解決する方が価値が高い。 「ゆっくり・確実に」 リズムは、 round 数を重ねることではなく、 走らせ可能な土台を確実に維持することで実現する。
