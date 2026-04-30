# Selection Cascade Port — Session Handoff (M4 進行中、 T068 完了時点)

**作成日時**: 2026-04-30 16:51 JST
**Session**: M4 (Loop+緊急) 進行中、 T067 + T068 設計 APPROVED + TODO 登録、 T069 残
**前セッション**: M2 完了 → 本セッションで synthesis Round 21 改訂 + M3 (T065-T066) + M4 半分 (T067-T068)
**次セッション**: M4 残 (T069 Calibrate-gate scope) → M5 (T070-T072) へ

---

## 0. 現在地 (Where we are)

### 完了済 (M1 + M2 + M3 全完了 + M4 半分)

**M1 基盤層** (前セッション完了):
- T058 schema-v2-contract / T059 epoch-window-manager / T060 partition-fold-generator

**M2 評価層** (前セッション完了):
- T061 canonical-five-engine / T062 mission-inf-gap-engine / T063 stage-a-evaluator / T064 stage-bc-evaluator

**synthesis Round 21 改訂** (本セッション完了):
- archive CA #5 を `mission_signed_margin = min(slack_*)` に SSOT 昇格
- mission_margin は BACKWARD COMPAT 整理
- § 6.4 / § 6.5 / § 8.3 / § 15 / § 17 / § 21 改訂、 実装影響なし
- 改訂 PR rationale: `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/`

**M3 GA 中核** (本セッション完了):
- **T065 NSGA-II core + 主選抜 (B-pooled)**: 概念 4 round + 詳細 2 round APPROVED
  - constrained-domination (Deb 2000) + non_dominated_sort + crowded-comparison binary tournament
  - Pareto 軸 source: f1=b_pooled_cf.net_pnl_after_cost / f2=pooled_dd_per_fold_max / f3=mission_inf_gap
  - deterministic tie-break (rank, -crowding, genome_hash, index) 4-tuple
  - blake2b stable seed (`int.from_bytes(blake2b(json.dumps([run_id, gen_no, "selection"]))...)`)
  - A-fail / B-invariant-fail 個体 Pareto 圧除外
- **T066 CPPS 2-state FSM + CA/DA archive**: 概念 4 round + 詳細 2 round APPROVED
  - PushPullState (push/pull 一方向) + CA/DA capacity (push 84/108 / pull 120/72 for pop=192)
  - ArchiveCandidate / ArchiveMember 2 層モデル + CA admission only (DA は T067 warmstart 経路)
  - CA lex 9 段 / DA lex 8 段 (末尾 genome_id deterministic)
  - genome_id 一意制約 (upsert merge) + dataset_epoch_id epoch reset + run_history 先反映
  - selected/admitted カウント分離

**M4 Loop+緊急** (本セッションで T067 / T068 完了、 T069 残):
- **T067 Loop closure (Warmstart + Emergency mode)**: 概念 5 round + 詳細 3 round APPROVED
  - EmergencyState mode + boost_consumed_run_id 2 変数分離 (synthesis § 8.5「1 run のみ」 厳密準拠)
  - best_mission_signed_margin SSOT (大が良、 -1.0e6 sentinel 置換)
  - WarmstartReuseRecord.recent_use_run_indices で rolling/cooldown/max_reuse 全て導出
  - build = filter / select = selection 責務分離
  - prev_epoch 20% global budget cap (CA + DA 合計、 DA は ca_ids 除外後評価)
  - admit_warmstart_to_da_with_eviction (1 API 完結)
- **T068 Failure handling**: 概念 4 round + 詳細 4 round APPROVED
  - EvaluationOutcome[T] で `(result, failure_record, should_skip_downstream)` 統一
  - ValueError → contract_violation / Exception → exception_raised の 2 段 catch
  - BaseException 系透過 (SystemExit / KeyboardInterrupt / GeneratorExit)
  - exception_message 500 文字切詰め + fingerprint dedup
  - FailureSummary stage-local + n_failed_genomes ベース abort
  - state invariant check (§ 8.4) で T062 sentinel 整合性検証
  - degraded builder + caller 除外契約 (finite cap 不要、 § 10.4 最終契約)
  - _iter_float_fields_check で typing.get_type_hints + Annotated 対応

### 未着手 (M4 残 + M5 以降)

- **T069 Calibrate-gate scope** (M4 最後): epoch key + 凍結窓 3 Run + Δ <= 0.03
- T070 Backtest engine 拡張 (session bucket / spread_cost / cross-pair)
- T071 Observability (A→B 乖離 / archive churn / front1 cardinality / FailureSummary 消費)
- T072 DST/holiday boundary contract
- T073-T075 (Audit / Graduation / Smoke)

### 重要: 設計のみ完了、 実装はまだ

T058-T068 全 11 TODO は **devnotes/ の概念 + 詳細設計のみ完了**、 src/ に新規コードは未実装。 既存 stage_gate.py / archive.py / cross_pair.py / swim_lane.py / run_ga.py には**一切 touch していない**。

---

## 1. 全体ロードマップ

| Milestone | TODO 範囲 | 進捗 |
|---|---|---|
| **M1: 基盤層** | T058-T060 | ✅ 完了 |
| **M2: 評価層** | T061-T064 | ✅ 完了 |
| **synthesis Round 21 改訂** | mission_signed_margin SSOT | ✅ 完了 |
| **M3: GA 中核** | T065-T066 | ✅ 完了 (本セッション) |
| **M4: Loop+緊急** | T067-T069 | 🟡 2/3 完了 (T067/T068 完了、 T069 残) |
| **M5: Engine+DST+Observability** | T070-T072 | ⏳ 未着手 |
| **M6: Audit+Graduation+Smoke** | T073-T075 | ⏳ 最終 |

---

## 2. 本セッション完了内容詳細

### 2.1 commit 一覧 (本セッション、 計 6 commit)

| commit | 内容 |
|---|---|
| `93d38fd` | docs(devnotes): cycle 1-11 + bug-hunt + investigation 過去未コミット devnotes アーカイブ |
| `3c2c038` | docs(cascade-port): M1+M2 設計完了 (T058-T064) + synthesis Round 21 改訂 |
| `8b25c61` | docs(T065): NSGA-II core + 主選抜 (B-pooled) 設計完了 + TODO 登録 (M3 開始) |
| `14f9aad` | docs(T066): CPPS 2-state FSM + CA/DA archive 設計完了 (M3 完了) |
| `2b69aff` | docs(T067): Loop closure (Warmstart + Emergency) 設計完了 (M4 開始) |
| `56b036f` | docs(T068): Failure handling 設計完了 (M4 残 2/3) |

### 2.2 Codex review 統計 (本セッション)

| TODO | 概念 (gpt-5.4 medium) | 詳細 (gpt-5.3-codex high) |
|---|---|---|
| synthesis 改訂 | (rationale only) | (rationale only) |
| T065 | 4 round (C6/W8/S5 → APPROVED) | 2 round (C2/W8/S5 → APPROVED) |
| T066 | 4 round (C12/W12/S13 → APPROVED) | 2 round (C5/W6/S6 → APPROVED) |
| T067 | 5 round (C11/W13/S11 → APPROVED) | 3 round (C9/W9/S9 → APPROVED) |
| T068 | 4 round (C8/W12/S11 → APPROVED) | 4 round (C9/W9/S9 → APPROVED) |
| **合計** | **17 round** | **11 round** |

合計 28 Codex review round、 重要 modification は全反映済。

### 2.3 主要な設計判断 (本セッションで確立)

1. **synthesis Round 21 改訂**: archive CA #5 = `mission_signed_margin = min(slack_*)` を SSOT 昇格、 旧 `mission_margin = -mission_inf_gap` の数式・命名乖離を解消
2. **constrained-domination (Deb 2000)** with finite domain: T065 で `effective_constraint_violation = constraint_violation + 1.0e6 × invariant_count` の sum 合成、 +inf は ValueError raise (defense-in-depth)
3. **deterministic completeness**: T065/T066/T067 全てで lex 末尾 `genome_id` 追加、 sort_keys 4-tuple `(rank, -crowding, genome_hash, index)`、 blake2b stable seed
4. **CA admission only (T066)**: synthesis § 8.2 の 3 層流入を CA admission に集中、 DA admission は T067 warmstart 経路で別途 (synthesis Round 22 改訂候補)
5. **EmergencyState mode + boost_consumed 2 変数分離 (T067)**: synthesis § 8.5「1 run のみ動作」 厳密準拠、 mode は解除条件成立まで保持、 boost は 1 run 限定
6. **prev_epoch 20% global budget cap (T067)**: CA + DA 合計で必ず cap 以下、 DA は ca_ids 除外後評価で予算消費歪み防止
7. **EvaluationOutcome[T] (T068)**: `should_skip_downstream` で degraded 個体伝搬を caller 除外契約に統一、 finite cap 等の事前変換は T068 で行わない (§ 10.4 最終契約)
8. **stage-local FailureSummary (T068)**: `n_failed_genomes` (一意 genome) ベース abort 判定、 record 数では判定しない (synthesis § 7.7 厳密準拠)

---

## 3. 次セッションの開始手順

### 3.1 まず読むもの (15 分)

1. **本ハンドオフ** (`devnotes/20260430-1651-cascade-port-handoff-m4-progress/handoff.md`)
2. **synthesis 全体** (`devnotes/20260428-2300-cascade-port-debate/synthesis.md`、 Round 21 改訂後)
3. **TODO リスト** (`docs/alpha_factory/TODO.md`、 T058-T068 が Open に登録済)
4. **直近 4 TODO 設計** (T065-T068):
   - `devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/`
   - `devnotes/20260430-1200-todo-T066-cpps-fsm-and-archive/`
   - `devnotes/20260430-1310-todo-T067-loop-closure-warmstart-emergency/`
   - `devnotes/20260430-1430-todo-T068-failure-handling/`
5. **過去 handoff** (履歴参照のみ): `devnotes/cascade-port-handoffs-historical/`

### 3.2 T069 開始時のチェックリスト

T069 (Calibrate-gate scope) は M4 最後の TODO:

- synthesis § 8.6 厳密準拠:
  - 凍結窓 3 Run、 4 Run 目で更新
  - 更新幅制限 `|Δ| <= 0.03`
  - スコープキー: `dataset_epoch_id` (epoch 跨ぎ再利用禁止)
- 既存 zenigame-fx の `scripts/alpha_factory/calibrate_gate.py` (T054 state file 経由の自動適用) と統合方針:
  - 案 A: 既存 calibrate_gate.py の置換 (big-bang)
  - 案 B: 既存と並行、 cascade port 用 dataset_epoch_id scope を追加
  - 詳細設計で確定
- T058 schema v2 の `dataset_epoch_id` スコープキー必須化 + history JSONL に schema_version=2 反映
- 過去履歴 (history.jsonl) との migration policy: synthesis § 9.3 「big-bang のため migration なし」 採用、 v2 で空 history から start

参考:
- synthesis § 8.6 / § 9.2 (schema v2 全経路必須)
- AGENTS.md `## calibrate-gate と state file 経由の自動適用 (T054)`
- 既存 `scripts/alpha_factory/calibrate_gate.py`

### 3.3 T070 以降の準備 (M5)

- **T070 Backtest engine 拡張**: session bucket label per bar / session block PnL / spread_cost field 追加
  - T064 で「TradeRecord.spread_cost 不在のため Phase 1 で skeleton (NotImplementedError)」 と申し送り済、 T070 で正式実装
- **T071 Observability**: T065 GenerationSelectionResult / T066 AdmissionReport / T067 WarmstartReport / T068 FailureSummary を消費して構造化 metric emit
- **T072 DST/holiday boundary contract**: FX 専用 UTC 基準 + 祝日カレンダ + 週末 gap 処理

### 3.4 設計フローのテンプレート (T065-T068 と同じ)

```
1. devnotes/{YYYYMMDD-HHMM}-todo-T{NNN}-{topic}/ ディレクトリ作成
2. 概念設計 → Codex 概念レビュー (gpt-5.4 / medium) → APPROVED まで Round
3. 詳細設計 → Codex 詳細レビュー (gpt-5.3-codex / high) → APPROVED まで Round
4. /zenigame-fx-todo-add で TODO 登録
5. commit (devnotes + TODO.md)
```

### 3.5 重要な原則 (本セッションで確立、 継続適用)

- **Phase 1 / Phase 2 分離**: 各 TODO PR は単体テストのみで runtime 未組込
- **Phase 2 申し送りを設計時に明示**: 後段で同時更新が必要な箇所を漏らさず列挙
- **C2 parallel-path 5 段階 grep**: 直 import / alias / relative / 再エクスポート / runtime シンボル
- **C4 前提検証**: 設計書冒頭で `main@<commit>` 基準を明示
- **synthesis 確定値を変えない**: 安易な変更禁止、 矛盾発見時は synthesis 改訂 PR を別途 (Round 21 改訂と同じ手順)
- **概念設計の Round で確定**: SSOT 不整合は概念設計で必ず潰す (詳細設計送りにしない)、 Codex レビューでよくある指摘
- **§ 11.2 SSOT 規約**: 概念設計の API シグネチャを唯一の正本とし、 他節は同期。 詳細設計内も SSOT 注記で固定

### 3.6 T069-T072 が消費する依存先 module

- **T058 schema v2**: dataset_epoch_id / archive_role / source_stage / schema_version=2 全経路必須
- **T060 Partition+Fold**: Period / Fold dataclass
- **T061 canonical_metrics**: CanonicalFiveResult / log_pf_clip / InvariantFlags
- **T062 mission_inf_gap**: MissionGapResult / mission_signed_margin / constraint_violation
- **T063 stage_a_evaluator**: StageAControllerState / a_pass_indices
- **T064 stage_bc_evaluator**: BCEvaluationResult / shadow_robustness_score / c_pass_depth (Phase 0 follow-up 後)
- **T065 nsga2_selection**: GenerationSelectionResult / IndividualEvaluation
- **T066 cpps_archive**: ArchiveState / ArchiveCandidate / ArchiveMember / AdmissionReport
- **T067 loop_closure**: WarmstartState / EmergencyState / EvaluationOutcome (T068 の)
- **T068 failure_handling**: FailureRecord / FailureSummary / RunFailureSummary / EvaluationOutcome

### 3.7 注意事項 (本セッションで発生した重要な設計決定)

- **synthesis Round 22 改訂候補 (T067 PR と同時)**: synthesis § 8.2 を「3 層流入 = CA admission、 DA admission = warmstart 経路」 と明文化
- **T064 follow-up Phase 0**: BCEvaluationResult に `c_pass_depth: float` field 追加が必須 (T066/T067/T068 共通依存)。 計算式 (案):
  - `c_pass_depth = c_lite_n_pass_windows × 0.25 + (1.0 if c_result.mission_pass==PASS else 0.5 if PENDING else 0.0)`
  - 値域 [0, 1.75]、 Phase 2 で T064 follow-up PR と同時に着地
- **degraded 個体の伝搬規約 (T068 § 10.4)**: should_skip_downstream=True 個体は caller (Phase 2 run_loop) が T065/T066/T067 入力から除外、 T068 は finite cap 等の事前変換を行わない
- **Codex 詳細レビューの Critical 多発**: T067 詳細 Round 1 で Critical 3、 T068 詳細 Round 1-3 で Critical 9 件発生。 数式・契約・SSOT 統一の指摘が頻出、 概念設計で潰せるものは概念で

---

## 4. リソース / Contact 点

### 4.1 重要 docs / devnotes

| 場所 | 内容 |
|---|---|
| `devnotes/20260428-2300-cascade-port-debate/synthesis.md` | 設計上位文書 21 章 + Round 21 改訂済 |
| `devnotes/20260429-1912-todo-T058-schema-v2-contract/` 〜 `20260430-0230-todo-T064-stage-bc-evaluator/` | M1 + M2 設計 (T058-T064) |
| `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/` | synthesis Round 21 改訂 PR rationale |
| `devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/` | T065 設計 |
| `devnotes/20260430-1200-todo-T066-cpps-fsm-and-archive/` | T066 設計 |
| `devnotes/20260430-1310-todo-T067-loop-closure-warmstart-emergency/` | T067 設計 |
| `devnotes/20260430-1430-todo-T068-failure-handling/` | T068 設計 |
| `devnotes/20260430-1651-cascade-port-handoff-m4-progress/handoff.md` | **本ハンドオフ (T068 完了時点、 canonical な引き継ぎ)** |
| `devnotes/cascade-port-handoffs-historical/` | 過去 handoff (M1 完了 / M2 中間 / M2 完了 履歴参照のみ) |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T068 が Open に登録済) |
| `AGENTS.md` | プロジェクト全体規約 |

### 4.2 zenigame コード参照 (T069-T072 で参考)

| 機構 | zenigame ファイル |
|---|---|
| Calibrate gate (T054) | `/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/calibrate_gate.py` (既存 fx 側、 fxx で確認) |
| 失敗 genome 扱い | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/core.py:1026-1095` (T068 で参照済) |
| Backtest engine | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_runner.py` (T070 で参考) |
| Observability metrics | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_dsr.py` 等 (T071 で参考) |

### 4.3 Codex 呼び出し方 (T065-T068 と同じ)

- 概念レビュー: `gpt-5.4` / `medium`、 label `conceptual-review`
- 詳細レビュー: `gpt-5.3-codex` / `high`、 label `detailed-review`
- skill: `zenigame-fx-codex-review`
- **重要**: Codex は file read を「コマンド実行禁止」 と誤解釈して拒否することがある。 Round 1 で本文を inline で貼り付けるのが確実 (本セッションで全 Round で確認)

### 4.4 TODO 登録方法

```bash
uv run python scripts/alpha_factory/todo_manager.py add \
  --id "T0XX" \
  --title "T0XX-{topic}" \
  --theme "{stage-gate|infrastructure|ga-architecture|...}" \
  --summary "..." \
  --priority "Critical" \
  --mode "incremental" \
  --design-link "[設計](devnotes/{dir}/)" \
  --added-at "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
```

---

## 5. 進捗状況サマリー

```
synthesis (Round 21 改訂済) ████████████████████ 100%
M1 (基盤)                   ████████████████████ 100% (T058-T060 完了)
M2 (評価)                   ████████████████████ 100% (T061-T064 完了)
M3 (GA)                     ████████████████████ 100% (T065-T066 完了)
M4 (Loop)                   █████████████░░░░░░░  67% (T067-T068 完了、 T069 残)
M5 (Eng)                    ░░░░░░░░░░░░░░░░░░░░   0% (T070-T072 未着手)
M6 (Fin)                    ░░░░░░░░░░░░░░░░░░░░   0% (T073-T075 未着手)
```

**全体進捗**: 設計 18 件中 11 件完了 (61.1%)、 実装は 0%

---

## 6. 次セッションの最初の指示テンプレート

ユーザが次セッションで以下のように指示すると即座に再開可能:

> 引き継ぎは `devnotes/20260430-1651-cascade-port-handoff-m4-progress/handoff.md` 読んで。 T069 (Calibrate-gate scope) から続行してください。 同じ flow (概念設計 → Codex レビュー APPROVED → 詳細設計 → Codex レビュー APPROVED → TODO 登録 → commit) で。

---

## 7. 未解決事項 / 次セッション最初に確認

1. **synthesis Round 22 改訂 PR のタイミング**: T067 PR と同時 / T067 後 - 推奨は T067 PR (Phase 2) と同時 (現状 Phase 1 設計のみなので Round 22 改訂もまだ着手不要)
2. **T064 follow-up PR (c_pass_depth field) のタイミング**: T066/T067/T068 詳細実装より先に着地必須 (Phase 2 配線時の前提)
3. **実装フェーズ移行戦略**: 全 18 設計完了後 (M6 まで) / M4 完了後 / M3 完了の今 - ユーザ判断保留
4. **T069 → T072 の優先順位**: T069 (M4 最後) が直近、 T070-T072 は M5 全体で並行可能 (T070 backtest engine が T064 spread_cost 申し送りに対応)

---

## 8. Codex Review 累積統計 (M1+M2+synthesis 改訂+M3+M4 部分)

### 全 11 TODO + synthesis 改訂 の Round 数集計

| TODO / 改訂 | 概念 Rounds | 詳細 Rounds | 合計 |
|---|---|---|---|
| T058 schema-v2-contract | 4 | 7 | 11 |
| T059 epoch-window-manager | 5 | 2 | 7 |
| T060 partition-fold-generator | 2 | 2 | 4 |
| T061 canonical-five-engine | 3 | 3 | 6 |
| T062 mission-inf-gap-engine | 2 | 2 | 4 |
| T063 stage-a-evaluator | 3 | 2 | 5 |
| T064 stage-bc-evaluator | 3 | 3 | 6 |
| synthesis Round 21 改訂 | (rationale) | — | — |
| T065 nsga2-core-and-main-selection | 4 | 2 | 6 |
| T066 cpps-fsm-and-archive | 4 | 2 | 6 |
| T067 loop-closure-warmstart-emergency | 5 | 3 | 8 |
| T068 failure-handling | 4 | 4 | 8 |
| **合計** | **39** | **32** | **71** |

### Codex review コスト (gpt-5.4 medium = 概念、 gpt-5.3-codex high = 詳細)

- 概念レビュー: 39 round × ~30K tokens/round ≈ 1,170K tokens
- 詳細レビュー: 32 round × ~50K tokens/round ≈ 1,600K tokens
- 合計: **~2.77M tokens** (gpt-5.4 / gpt-5.3-codex 混在)

---

## 9. 補足: 本セッションで学んだこと (T069-T072 で適用)

- **synthesis 内部矛盾の発見と対処 (Round 21 改訂)**: T062 で `mission_margin = -mission_inf_gap` 数式・命名矛盾を発見、 `mission_signed_margin = min(slack_*)` を新設して synthesis § 8.3 改訂。 T067 PR で同様に Round 22 改訂候補 (DA admission 経路)
- **EvaluationOutcome[T] による degraded 伝搬統一 (T068)**: should_skip_downstream フラグで caller 除外契約を明示、 downstream 各 module の入口契約 (finite domain) を無傷で保つ
- **stage-local 集計の重要性 (T068)**: 全 fail abort 判定の分母を Run 全体ではなく stage 単位 (eligible_count) にすることで、 Stage B 等の中間 stage で 「全 N 個体 fail で abort」 が正しく機能
- **§ 11.2 SSOT + 自動転記運用ルール**: 概念設計の API シグネチャを唯一の正本とし、 詳細設計内の擬似コードは § 11.2 から自動転記する運用 (T065 Round 3 [Suggestion] で確立、 T067/T068 でも継続)
- **typing.get_type_hints + Annotated 対応 (T068)**: `from __future__ import annotations` 下での dataclass field type 判定は、 文字列化されるため `typing.get_type_hints(include_extras=True)` + `get_origin/get_args` で正規化する必要
- **state invariant truth table (T068)**: T062 sentinel (mission_signed_margin=-inf 等) と is_feasible flag の整合性 invariant を明示的にコード化、 state_inconsistency reason で監査可能化

これらの教訓は次セッション (T069 以降) でも継続適用する。
