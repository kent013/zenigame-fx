# Selection Cascade Port — Session Handoff (cascade port v2 設計 18 件全件完了)

**作成日時**: 2026-05-01 02:53 JST
**Session**: M6 完了 (T073 / T074 / T075)、 **cascade port v2 設計 18 件 (T058-T075) 全件完了**
**前セッション**: M5 進行中 (T071 完了時点) → 本セッションで M5 残 T072 + M6 完了 (T073-T075) で全 18 件完了
**次セッション**: **設計フェーズ完了**、 **Phase 2 (= 配線実装) フェーズへ移行**

---

## 0. 現在地 (Where we are) ✨

### 完了済 (cascade port v2 設計 全 18 件)

```
synthesis (Round 21 改訂済) ████████████████████ 100%
M1 (基盤)                    ████████████████████ 100% (T058-T060)
M2 (評価)                    ████████████████████ 100% (T061-T064)
M3 (GA)                      ████████████████████ 100% (T065-T066)
M4 (Loop)                    ████████████████████ 100% (T067-T069)
M5 (Engine+DST+Observability)████████████████████ 100% (T070-T072)
M6 (Audit+Graduation+Smoke)  ████████████████████ 100% (T073-T075) ✨
```

**全体進捗**: 設計 18 件全件完了 (100%)、 実装は 0% (= **Phase 2 配線フェーズへ移行**)。

### 本セッション (M5 残 + M6) で完了した 4 TODO

| TODO | 概要 | 概念 round | 詳細 round | commit |
|---|---|---|---|---|
| **T072** | DST/holiday boundary contract: BrokerTradingSchedule (date-aware open_window + DST table + broker_full_close + date_overrides) と MarketHolidayCalendar 完全分離、 SessionBlock open_minutes primary | 5 round APPROVED (16 Critical / 28+ Warning / 22+ Suggestion) | 3 round APPROVED (9 Critical / 15 Warning / 15 Suggestion) | `975a7ea` |
| **T073** | Audit layer: DSR 先行 (既存 deflated_sharpe_ratio を v2 SessionBlock 駆動で wrap) + PBO/SPA scaffold (status="not_implemented" 固定、 数値 field なし)、 AuditNullModel SSOT、 stratification API guard | 3 round APPROVED (13 Critical / 10 Warning / 10 Suggestion) | 2 round APPROVED (2 Critical / 6 Warning / 3 Suggestion) | `323055b` |
| **T074** | Graduation lane scaffold: evaluate_graduation_trigger (epoch 基準、 caller 引数、 status field) + multi-pair aggregation sketch (worst_pair / mean、 status="not_implemented")、 6 batch pair frozenset、 GraduationEpochSummary 3 field、 LANE_PARALLELISM=1 | 3 round APPROVED (6 Critical / 16 Warning / 13 Suggestion) | 4 round APPROVED (1 Critical / 16 Warning / 16 Suggestion) | `b591988` |
| **T075** | Big-bang cleanup + smoke: synthesis local projection 限定、 DoD 二層分離 (PerRun DoD1-7 / CrossRun DoD8)、 EvidenceClass threshold-free、 classify (事実認定) / decide (運用判断 hint) 2 段階、 AggregateEvidence 二軸 (severity + has_inconclusive)、 EvidenceClassifierProtocol、 dual-path enforce 4 経路 + path normalization、 select_rollback_relevant_failure_modes は Phase 1 NotImplementedError | 4 round APPROVED (10 Critical / 23 Warning / 18 Suggestion) | 3 round APPROVED (4 Critical / 15 Warning / 13 Suggestion) | `1bc1a9a` |

合計: 概念 15 round + 詳細 12 round = **27 Codex review、 全 APPROVED**。

### 重要: 設計のみ完了、 実装はまだ 0%

T058-T075 全 18 TODO は **devnotes/ の概念 + 詳細設計のみ完了**、 src/ に新規コードは未実装。 既存 src (= stage_gate.py / archive.py / cross_pair.py / swim_lane.py / run_ga.py / broker/orders.py / backtest/engine.py / statistics.py / calibrate_gate.py 等) には**一切 touch していない**。

---

## 1. 全体ロードマップ (cascade port v2 完了)

| Milestone | TODO 範囲 | 進捗 |
|---|---|---|
| **M1: 基盤層** | T058-T060 | ✅ 完了 |
| **M2: 評価層** | T061-T064 | ✅ 完了 |
| **synthesis Round 21 改訂** | mission_signed_margin SSOT | ✅ 完了 |
| **M3: GA 中核** | T065-T066 | ✅ 完了 |
| **M4: Loop+緊急** | T067-T069 | ✅ 完了 |
| **M5: Engine+DST+Observability** | T070-T072 | ✅ 完了 |
| **M6: Audit+Graduation+Smoke** | T073-T075 | ✅ 完了 ✨ |

cascade port v2 設計フェーズ完了、 **Phase 2 (= 配線実装) フェーズへ移行**。

---

## 2. 本セッション完了内容詳細

### 2.1 commit 一覧 (本セッション、 計 4 commit)

| commit | 内容 |
|---|---|
| `975a7ea` | docs(T072): DST/holiday boundary contract 設計完了 (M5 完了) |
| `323055b` | docs(T073): Audit layer (DSR 先行 + PBO/SPA scaffold) 設計完了 (M6 開始) |
| `b591988` | docs(T074): Graduation lane batch evaluator scaffold 設計完了 (M6 中盤) |
| `1bc1a9a` | docs(T075): Big-bang cleanup + smoke 設計完了 (M6 完了、 cascade port 設計 18 件中 18 件完了) |

### 2.2 Codex review 統計 (本セッション)

| TODO | 概念 (gpt-5.4 medium) | 詳細 (gpt-5.3-codex high) |
|---|---|---|
| T072 | 5 round | 3 round |
| T073 | 3 round | 2 round |
| T074 | 3 round | 4 round |
| T075 | 4 round | 3 round |
| **合計** | **15 round** | **12 round** |

合計 **27 Codex review round**、 全 APPROVED。 累積 (T058 から T075 まで) では **63 概念 round + 52 詳細 round = 115 review**。

### 2.3 主要な設計判断 (本セッションで確立)

#### T072 (DST/holiday boundary contract)
1. **broker 配信 schedule と市場 holiday observability の完全分離**: BrokerTradingSchedule が expected の唯一の入力、 MarketHolidayCalendar は観測情報のみ。 holiday を expected に混ぜない (= synthesis § 4.4 「8h × 3 covering partition」 を不変、 holiday は別 layer で audit)
2. **open_minutes を SessionBlock primary field 化**: expected_bar_count / schedule_status は両方 derived computed property、 H4 等粗い granularity でも partial 強度を open_minutes に保持 (= floor 演算で消失しない)
3. **broker date_overrides 追加**: early close (= クリスマス前日 18:00 close 等) を date 単位で表現、 priority = `date_overrides > broker_full_close > weekly/DST > weekday default`
4. **DST season 境界 semantics 確定**: `dst_aware_close_table` の region は inclusive / disjoint / 連続 cover、 春切替日は当日が新 region の region_start
5. **bucket-local eligibility は削除**: FX bucket は物理取引所ではなく流動性時間帯、 holiday 単独で分母除外は collider bias、 caller 委譲
6. **半開区間 `[start, end)` 統一**: bucket UTC range / open_window / overlap 計算 / coverage 判定全て同規約
7. **YAML duplicate key + merge key reject**: `_DuplicateKeyRejectLoader` で構造的防止
8. **production wrapper**: `aggregate_session_blocks_production` で mode="production" 構造的強制
9. **schema version path 形式**: `SESSION_BLOCK_DERIVED_FIELD_PATHS` で `observability_flags.all_g3_market_holiday` のような nested path を明示
10. **collider bias 規範継承**: holiday_markets 単独 drop 禁止、 stratified audit を T072 で明文化

#### T073 (Audit layer)
1. **既存 deflated_sharpe_ratio を v2 cascade port と整合する純ライブラリ wrap**: 数式 (Bailey & López de Prado 2014 Eq.(7) (9)) 不変、 入力経路のみ v2 化
2. **AuditNullModel SSOT**: null_model_kind="standard_normal" + sr_scale="session_block_non_annualized" + trial_source="run_evaluated_genomes_unique_canonical" + n_trials/n_trial_candidates_raw/unique 分離
3. **n_trials = unique canonical genome_id 数**: retry/fold/cache replay は別 trial にしない (= 保守的 multiple testing correction)
4. **PBO/SPA scaffold の数値 field なし** (T073 SSOT、 T074 / T075 でも継承): status="not_implemented" 固定 + audit_calc_version="scaffold-v1"、 status check 漏れで誤読 risk 排除
5. **AuditDSRStatus (5 値) と AuditScaffoldStatus (1 値) 分離**: not_implemented 流入防止
6. **sentinel policy 分離**: DSR_VALUE_SENTINEL=Decimal("-1") (値域外、 fail-closed) + MOMENT_SENTINEL=Decimal("0") (解釈禁止)
7. **stratification API guard**: marginal default + interaction allowlist、 sparse strata 量産防止 + C7 規範 n>=30
8. **既存 statistics.py docstring 同 PR で同期更新** (= 別 PR 不可、 同 PR 内別 commit で分割)
9. **archive `dsr` field の v2 切替は Phase 2 で dsr_v1/dsr_v2 併存**: 履歴比較互換、 sharpe_calc_version 厳格運用
10. **collider bias 規範継承 (T072 から)**: T071 / 後段 analytic 詳細設計改訂申し送りに「holiday_markets 単独 drop/filter 禁止、 stratified audit」 を統一規範

#### T074 (Graduation lane scaffold)
1. **既存 swim_lane / archive / cross_pair に touch しない**: 純ライブラリ + early gate ではない、 GraduationLane.run_generation は Phase 4 まで NotImplementedError 維持
2. **trigger 判定は epoch 基準** (Round 1 [C2] 反映): 「直近 N Run」 ではなく「直近 N epoch」、 GraduationEpochSummary 中心
3. **`recent_epochs_with_mission_pass_required` は caller 引数化** (Round 1 [C1] 反映): 数値操作禁止規範整合、 smoke 後再校正
4. **6 batch pair = frozenset SSOT**: T064 STAGE_C_ANCHOR_PAIR ∪ STAGE_C_SHADOW_PAIR_LIST 集合等価、 順序非依存
5. **GraduationEpochSummary 3 field**: dataset_epoch_id / observed_run_ids / mission_pass_run_ids (`issubset` SSOT、 inclusive)
6. **archive_epoch_id_active str|None で empty archive 業務不足扱い**: distinct 空集合 + recent 空 tuple
7. **GraduationTriggerEvaluation の cross-field invariant**: duplicate 禁止 + n_distinct_epochs >= len(recent_mission_pass_epoch_ids)
8. **partial pass diagnostic 保持** (Round D2 [W1]): no_recent_mission_pass で実測値 (= 0..N-1 個 pass) を保持、 実測 diagnostic field
9. **batch 系 dataclass (GraduationBatchInput / GraduationBatchReport) は Phase 4 で導入**: Phase 1 で死蔵 risk 排除
10. **collider bias 規範継承**: T074 で stratified audit 判定しない、 Phase 2 で T071 経由
11. **AST grep DoD 13 検索語 + case-sensitive substring + exact name 分離**: false positive 排除

#### T075 (Big-bang cleanup + smoke) — 新規 SSOT
1. **synthesis local projection 限定** (Round R1 [C1] 反映): T075 module で親 SSOT を再定義しない、 FM1-FM5 / new_cascade 採用しない / DoD 機械検証形式 等は **synthesis Round 22 改訂 blocked-by**
2. **DoD 二層分離** (Round R1 [C2]): PerRunSmokeDoDResult (= DoD1-DoD7、 1 Run) / CrossRunSmokeDoDResult (= DoD8、 5 Run 集約)
3. **EvidenceClass threshold-free 4 値** (Round R1 [C3]): 数値 threshold (FM1=0.3 等) を T075 で SSOT 化しない、 別 TODO + smoke 後再校正
4. **classify_smoke_outcome (事実認定) と decide_release_action (運用判断 hint) を 2 段階分離** (Round R1 [C4]): 自動 rollback / proceed 判定廃止、 manual review に委ねる
5. **AggregateEvidence 二軸保持** (Round R3 [C1]): severity (3 値: hard_fail / warning / ok) + has_inconclusive 別軸、 inconclusive を warning に隠さず C8 規範保護
6. **decide_release_action 優先順位**: hard_fail → has_inconclusive → FM observed → warning → ok
7. **review_hint 3 値 (= no_blocker_observed / hold_for_delay / hold_for_review)**: hint only、 自動切替指示ではない、 「自動承認」 誤読 risk 低減のため `candidate_proceed` → `no_blocker_observed`
8. **EvidenceClassifierProtocol** (Round R2 [C3]): caller-supplied、 supported_metric_names + __call__ 2 method、 unsupported metric_name は inconclusive 必須 (= fail-closed)
9. **typed projection** (Round R1 [C5]): SmokeObservabilityProjection (= 5 metric class + epoch_consistency) / CrossRunSmokeObservabilityProjection (= cross_run_epoch_pollution_class)、 untyped Mapping 排除
10. **DeletionTarget / MigrationTarget 分離** (Round R2 [W4]): cleanup と migrate を別 manifest、 change_group_id 命名規則 `^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$` + supersedes
11. **dual-path operational definition** (Round R1 [W3]): 並走 = runtime 到達 OR feature flag OR 二経路出力、 同居 (= source tree のみ) は許容
12. **dual-path enforce 4 経路 + path normalization** (Round D2 [W1]): source / scripts / config / docs runbook、 PurePosixPath + repository-root relative + symlink follow なし
13. **collider bias non-goal 3 項目** (Round R1 [W6]): stratified audit / 因果解釈 / 比率差判定を T075 で禁止
14. **select_rollback_relevant_failure_modes API 名予約** (Round R3 [S4]): Phase 1 NotImplementedError raise、 Phase 2 別 TODO で実装
15. **docs/runbook / PR template / CI meta check は Phase 2 申し送り** (Round D2 [C1]): Phase 1 純ライブラリ SSOT 整合
16. **「1 cycle = run cadence」**: 数値定数 (= ROLLBACK_DELAY_CYCLE_DAYS=7) 廃止、 Phase 2 で確定

---

## 3. Phase 2 移行戦略 (= 設計から実装フェーズへ)

### 3.1 Phase 2 が解決する課題

cascade port v2 を runtime に組み込み、 cascade 切替コミットを実施。 全 17 件の Phase 2 配線 PR + T075 切替 PR を big-bang 1-shot で merge:

| 配線対象 | 担当 TODO の Phase 2 |
|---|---|
| T058 schema v2 (= dataset_epoch_id / archive_role / source_stage / schema_version=2 全経路) | T058 Phase 2 |
| T059 epoch / window manager | T059 Phase 2 |
| T060 partition + fold generator | T060 Phase 2 |
| T061 canonical 5 engine | T061 Phase 2 |
| T062 mission_inf_gap engine | T062 Phase 2 |
| T063 Stage A evaluator | T063 Phase 2 |
| T064 Stage B/C evaluator | T064 Phase 2 |
| T065 NSGA-II core | T065 Phase 2 |
| T066 CPPS 2-state FSM + CA/DA archive | T066 Phase 2 |
| T067 Loop closure (warmstart + emergency) | T067 Phase 2 |
| T068 Failure handling | T068 Phase 2 |
| T069 Calibrate-gate scope (3 Run freeze) | T069 Phase 2 |
| T070 Backtest engine 拡張 (SessionBlock) | T070 Phase 2 |
| T071 Observability layer (RunObservabilityReport) | T071 Phase 2 |
| T072 DST/holiday boundary contract | T072 Phase 2 |
| T073 Audit layer (DSR + PBO/SPA scaffold) | T073 Phase 2 |
| T074 Graduation lane scaffold | T074 Phase 2 |
| T075 Big-bang cleanup + smoke | T075 Phase 2 (= 切替コミット 1-shot) |

### 3.2 synthesis Round 22 改訂候補 (= T075 blocked-by 5 件)

T075 PR 先 merge 前に synthesis Round 22 改訂が必要:

1. **§ 12.4「new_cascade 名前空間」 文言**: 「採用しない、 直接 src/alpha_factory/* で実装」 と明文化
2. **§ 12.4 「FM1/FM4」 ロールバック条件**: T075 FailureModeKind enum と紐付けて確定 (= rollback_relevant_fms 集合定義)
3. **§ 18.3 Smoke DoD 8 項目**: per-run / cross-run 分離形式 (= DoD1-DoD7 / DoD8) で明文化
4. **§ 16 Risk Top 5 と FM1-FM5 の数値 threshold**: 別 TODO で確定 (= smoke 後再校正)
5. **stable clause anchor 体系**: synthesis 全文に `synthesis_schema_version: 22` を冒頭 metadata block に追加 + 旧 1-21 round の遡及付与

これら 5 件は別 TODO で実施 (= T076 等)、 T075 PR と同期 or 先 merge。

### 3.3 Phase 2 配線時の主要な統合点

#### T071 RunObservabilityReport.* field 配線 (= 中央 hub)

T071 が cascade port v2 の **observability hub**。 Phase 2 で RunObservabilityReport に以下 field を追加:

- `audit: RunAuditReport` (T073 Phase 2)
- `graduation_trigger: GraduationTriggerEvaluation` (T074 Phase 2)
- `smoke_dod: PerRunSmokeDoDResult` (T075 Phase 2)
- 他 T067 / T068 / T072 関連 field

#### run_ga.py = 唯一の SSOT adapter

archive read-only 集計 → 各 dataclass 構築 → RunObservabilityReport 同梱 → log/report 出力 を **run_ga.py に集約**。 T072 / T073 / T074 / T075 の各 docstring で「Phase 2 で run_ga.py が唯一の SSOT adapter」 を申し送り済。

T074 / T075 では **同一 archive snapshot 単一 transaction** で集計する adapter contract 5 項目 (= 入力 snapshot / 出力 summary 一貫性 / 失敗時 raise / config missing fail-closed / immutable build ロールバック) も明文化。

#### archive `dsr` field の v1 → v2 切替 (T073 Phase 2)

archive Parquet schema で `dsr_v1` / `dsr_v2` 併存 (= 履歴比較互換)、 sharpe_calc_version 厳格運用。 既存 archive.py:81 の `dsr` field は v1 入力で計算済、 Phase 2 で `dsr_v1` rename + 新 `dsr_v2` 追加。

#### dual-path 並走禁止 (T075 Phase 2 切替コミット)

切替コミットで以下を **同日削除** (= big-bang 1-shot):

- 旧 src: `calibrate_gate.py` / `calibrate_state.py`
- 旧 scripts: `scripts/alpha_factory/calibrate_gate.py` / `scripts/alpha_factory/run_alpha_sieve.py`
- 旧 config キー (synthesis § 12.1): default.yaml の `target_pass_rate` / `wf_*` / `spread_stress_*` / `seed_strategy` / `plateau_cycles` 等
- 全面置換対象 (synthesis § 12.2): `stage_gate.stage_a/b/c` / `ga.population_size,generations,fitness_metric,max_workers` / `cross_pair.*` / archive Parquet schema v1

dual-path operational definition (T075 SSOT): 「並走」 = runtime 到達 OR feature flag OR 二経路出力 / 「同居」 (= source tree のみ) は許容。

---

## 4. 次セッションの開始手順 (= Phase 2 配線実装着手)

### 4.1 まず読むもの (30 分)

1. **本ハンドオフ** (`devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md`)
2. **synthesis 全体** (`devnotes/20260428-2300-cascade-port-debate/synthesis.md`、 Round 21 改訂後)
3. **TODO リスト** (`docs/alpha_factory/TODO.md`、 T058-T075 全 18 件 Open に登録済)
4. **直近 4 TODO 設計** (本セッションで完了):
   - `devnotes/20260430-2036-todo-T072-dst-holiday-boundary/`
   - `devnotes/20260430-2301-todo-T073-audit-layer/`
   - `devnotes/20260501-0023-todo-T074-graduation-lane-scaffold/`
   - `devnotes/20260501-0136-todo-T075-bigbang-cleanup-smoke/`
5. **過去 handoff** (履歴参照のみ): `devnotes/cascade-port-handoffs-historical/`

### 4.2 Phase 2 着手の選択肢

設計フェーズが完了したので、 ユーザ判断で以下のいずれかに進む:

**選択肢 A: synthesis Round 22 改訂を先に完了**
- T075 blocked-by 5 件を解消
- 別 TODO (= T076 synthesis-round22 等) を作成して synthesis 改訂実施
- 以後の Phase 2 配線 PR は synthesis 改訂後の SSOT で進める

**選択肢 B: Phase 2 配線を T058 から順次実装** (= 推奨)
- synthesis Round 22 改訂は T075 PR と同期 merge or 先 merge で別途
- Phase 2 配線 PR を T058-T075 の **依存順**で進める:
  - 先行必須: T058 (schema v2) → T059 → T060 (= 基盤層配線)
  - 評価系: T061 → T062 → T063 → T064 (T060 完了後)
  - GA 中核: T065 → T066 (T058 / T064 完了後)
  - 運用制御: T067 → T068 → T069 (T065 / T066 完了後)
  - 基盤拡張: T070 → T071 → T072 (T064 完了後)
  - 監査/展開: T073 → T074 → T075 (= 最終切替、 T071 完了後)

**選択肢 C: Phase 1 + Phase 2 を並行実装**
- 設計 only ではなく Phase 1 純ライブラリ実装 + Phase 2 配線を一気に進める
- リスク: 18 PR 並行で SSOT drift risk、 大きい
- 推奨: 選択肢 B の段階導入

### 4.3 Phase 2 配線の各 TODO に共通する作業

各 TODO の Phase 2 では以下が共通:

1. **概念設計 + 詳細設計 (Phase 1)** から **実装 (Phase 2)** へ移行
2. 既存 src への touch (= Phase 1 では 0 件、 Phase 2 で配線実装)
3. 既存 caller の signature 変更があれば 5 段階 grep DoD
4. T071 RunObservabilityReport field 追加 (= 各 Phase 2 で 1 field 追加)
5. run_ga.py adapter 拡張 (= 各 Phase 2 で archive 集計 logic を追加)
6. 単体テスト + integration test
7. mypy / ruff / pytest pass
8. Codex impl-review (= zenigame-fx-codex-review skill)

### 4.4 設計フローのテンプレート (各 Phase 2 PR で踏襲)

```
1. devnotes/{YYYYMMDD-HHMM}-impl-T{NNN}-{topic}/ ディレクトリ作成
2. 実装計画 (= Phase 1 詳細設計の DoD 全項目を踏襲)
3. 実装 + 単体テスト (= Phase 1 詳細設計の擬似コード実装)
4. Codex impl-review (gpt-5.5-codex / xhigh) → APPROVED まで Round
5. 既存 caller への影響を 5 段階 grep DoD で確認
6. integration test (= 既存挙動への影響を確認)
7. T071 RunObservabilityReport field 配線 (Phase 2 統合)
8. run_ga.py adapter 拡張
9. mypy / ruff / pytest pass
10. PR description にチェックリスト全項目記載
11. commit (実装 + tests + Phase 2 PR description)
```

### 4.5 重要な原則 (本セッションで継続適用、 Phase 2 でも踏襲)

- **Phase 1 / Phase 2 分離**: 各 TODO PR は **設計 only**、 Phase 2 で **実装**。 設計フェーズで触れていない src を Phase 2 で touch
- **Phase 2 申し送りを設計時に明示**: 後段で同時更新が必要な箇所を漏らさず列挙 (= 各 TODO 詳細設計の § Phase 2 申し送り)
- **synthesis 確定値を変えない**: Round 22 改訂候補は別 PR で同期、 T075 では blocked-by として明示
- **§ 11.2 SSOT 規約**: 概念設計の API シグネチャを唯一の正本とし、 詳細設計 / Phase 2 実装は同期
- **status field 方式継承** (T071 / T073 / T074 / T075 で確立): None 経路完全排除、 Optional に逃げない
- **scaffold 数値 field なし** (T073 / T074 / T075 で確立): scaffold は status + calc_version のみ、 数値 field は実装 PR で MINOR bump
- **collider bias 規範継承** (T072 / T073 / T074 / T075): holiday_markets 単独 drop 禁止、 Phase 2 で T071 経由 stratified audit
- **dual-path operational definition** (T075 で確立): 並走と同居の境界を明示、 切替コミットで big-bang 1-shot
- **synthesis local projection** (T075 で確立): 親 SSOT を再定義しない、 改訂は Round 22 で

### 4.6 cascade port v2 全体の依存関係 (Phase 2 配線順序)

```
依存関係 (= synthesis § 18.1 厳密準拠 + T075 で再整理):

先行必須: T058 → T059 → T060
評価系: T061 → T062 → T063 → T064 (T060 完了後)
GA中核: T065 → T066 (T058 / T064 完了後)
運用制御: T067 → T068 → T069 (T065 / T066 完了後)
基盤拡張: T070 → T071 → T072 (T064 完了後)
監査/展開: T073 → T074 → T075 (T071 完了後)

並行可能:
  評価系と GA 中核 (T060 完了後)
  基盤拡張は他全 Phase と並行可
  監査/展開は T071 完了後並行可

T075 切替コミット = 全 17 件 Phase 2 完了 + synthesis Round 22 改訂後の big-bang 1-shot
```

### 4.7 注意事項 (本セッションで発生した重要な設計決定)

- **T058 詳細設計改訂申し送り**: HistoryRecord.applied_from_run_id v2 必須化 (T069 反映済)
- **T064 詳細設計改訂申し送り**: TradeRecord → Trade 命名統一 (T070 反映済)、 session_pass_pattern 3 bit string 固定 (T071 反映済)
- **T063 詳細設計改訂申し送り**: q_force_recommendation の caller 配線 (StageAControllerState 更新、 T071 反映済)
- **T071 詳細設計改訂申し送り**: RunObservabilityReport に audit / graduation_trigger / smoke_dod field 追加 (T073 / T074 / T075 で申し送り)
- **T058 詳細設計改訂申し送り (T073 反映)**: archive `dsr` field を `dsr_v1` rename + `dsr_v2` 追加 (= 履歴比較互換、 Phase 2 で sharpe_calc_version 同期)
- **T064 / T058 詳細設計改訂申し送り (T074 反映)**: STAGE_C_ANCHOR_PAIR / STAGE_C_SHADOW_PAIR_LIST と GRADUATION_BATCH_PAIRS の整合は T074 PR test 側で確認
- **synthesis Round 22 改訂候補 5 件 (T075 反映)**: new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor

---

## 5. リソース / Contact 点

### 5.1 重要 docs / devnotes

| 場所 | 内容 |
|---|---|
| `devnotes/20260428-2300-cascade-port-debate/synthesis.md` | 設計上位文書 21 章 + Round 21 改訂済 (= cascade port v2 baseline) |
| `devnotes/20260429-1912-todo-T058-schema-v2-contract/` 〜 `20260430-0230-todo-T064-stage-bc-evaluator/` | M1 + M2 設計 (T058-T064) |
| `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/` | synthesis Round 21 改訂 PR rationale |
| `devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/` | T065 設計 |
| `devnotes/20260430-1200-todo-T066-cpps-fsm-and-archive/` | T066 設計 |
| `devnotes/20260430-1310-todo-T067-loop-closure-warmstart-emergency/` | T067 設計 |
| `devnotes/20260430-1430-todo-T068-failure-handling/` | T068 設計 |
| `devnotes/20260430-1700-todo-T069-calibrate-gate-scope/` | T069 設計 |
| `devnotes/20260430-1810-todo-T070-backtest-engine-extension/` | T070 設計 |
| `devnotes/20260430-1925-todo-T071-observability/` | T071 設計 |
| `devnotes/20260430-2036-todo-T072-dst-holiday-boundary/` | T072 設計 (本セッション) |
| `devnotes/20260430-2301-todo-T073-audit-layer/` | T073 設計 (本セッション) |
| `devnotes/20260501-0023-todo-T074-graduation-lane-scaffold/` | T074 設計 (本セッション) |
| `devnotes/20260501-0136-todo-T075-bigbang-cleanup-smoke/` | T075 設計 (本セッション) |
| `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md` | **本ハンドオフ (cascade port v2 設計完了時点、 canonical な引き継ぎ)** |
| `devnotes/cascade-port-handoffs-historical/` | 過去 handoff (M1 完了 / M2 中間 / M2 完了 / M4 進行中 / M5 進行中 履歴参照のみ) |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T075 全 18 件 Open に登録済) |
| `AGENTS.md` | プロジェクト全体規約 |

### 5.2 zenigame コード参照 (Phase 2 配線で参考)

| 機構 | zenigame ファイル |
|---|---|
| DSR (T073) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_dsr.py:126` |
| 主選抜 B-pooled (T065) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/optimize.py:2125,2141` |
| CA/DA Two-Archive (T066) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/archives.py` |
| breeding (T065) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/breeding.py:211,255` |
| Sieve filter (T067) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/alpha_sieve/filter.py` |
| Run loop (T067) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_runner.py:673,952` |
| determinism (T065) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/core.py:114,1026,1085` |
| GENOMES_SCHEMA (T058) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/genome_archive.py:540` (= dataset_epoch_id 不在、 fx で新設) |
| 祝日カレンダ (T072) | (zenigame 側に存在せず、 fx で新設、 zenigame 逆輸入候補) |
| DST 切替判定 (T072) | (zenigame 側に存在せず、 fx で先行実装) |

### 5.3 Codex 呼び出し方 (Phase 2 でも踏襲)

- 概念レビュー: `gpt-5.4` / `medium`、 label `conceptual-review`
- 詳細レビュー: `gpt-5.3-codex` / `high`、 label `design-review`
- 実装レビュー: `gpt-5.5-codex` / `xhigh`、 label `impl-review`
- skill: `zenigame-fx-codex-review`
- **重要**: Codex は file read を「コマンド実行禁止」 と誤解釈して拒否することがある。 Round 1 で本文を inline で貼り付けるのが確実 (本セッションでも全 Round で確認)

### 5.4 TODO 登録方法 (theme 制約あり)

```bash
uv run python scripts/alpha_factory/todo_manager.py add \
  --id "T0XX" \
  --title "T0XX-{topic}" \
  --theme "{infrastructure|stage-gate|ga-architecture|statistics|cross-pair|data-ingest|general|primitives|skill-port|swim-lane}" \
  --summary "..." \
  --priority "Critical" \
  --mode "incremental" \
  --design-link "[設計](devnotes/{dir}/)" \
  --added-at "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
```

theme 制約:
- T072: `infrastructure`
- T073: `statistics`
- T074: `swim-lane`
- T075: `infrastructure`
- 'observability' は theme として未登録 (T071 では `infrastructure` を採用)

---

## 6. 進捗状況サマリー

```
synthesis (Round 21 改訂済) ████████████████████ 100%
M1 (基盤)                   ████████████████████ 100% (T058-T060 完了)
M2 (評価)                   ████████████████████ 100% (T061-T064 完了)
M3 (GA)                     ████████████████████ 100% (T065-T066 完了)
M4 (Loop)                   ████████████████████ 100% (T067-T069 完了)
M5 (Engine)                 ████████████████████ 100% (T070-T072 完了)
M6 (Final)                  ████████████████████ 100% (T073-T075 完了) ✨
```

**全体進捗**: 設計 18 件全件完了 (100%)、 実装は 0%

---

## 7. 次セッションの最初の指示テンプレート

### 7.1 Phase 2 配線実装に進む場合 (= 推奨)

ユーザが次セッションで以下のように指示すると即座に再開可能:

> 引き継ぎは `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md` 読んで。 Phase 2 配線実装フェーズに進む。 T058 (schema v2 contract) Phase 2 から開始。 設計は `devnotes/20260429-1912-todo-T058-schema-v2-contract/` 全 Round 参照。 implement skill (zenigame-fx-implement) で worktree + 実装 + Codex impl-review で進める。

### 7.2 synthesis Round 22 改訂を先に進める場合

> 引き継ぎは `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md` 読んで。 T075 blocked-by の synthesis Round 22 改訂を別 TODO で先に進める。 改訂候補 5 件 (= new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor) を synthesis に反映する concept design を起こす。

### 7.3 cascade port 全体の見直しを行う場合

> 引き継ぎは `devnotes/20260501-0253-cascade-port-handoff-design-complete/handoff.md` 読んで。 cascade port v2 設計 18 件 (T058-T075) 全体を俯瞰、 Phase 2 配線着手前に「全体整合性監査」 を実施する。 各 TODO の Phase 2 申し送り集約 + 依存関係グラフ + collider bias 規範整合性 + scaffold SSOT 整合性を Codex 全件 review。

---

## 8. 未解決事項 / 次セッション最初に確認

1. **Phase 2 配線実装の着手戦略**: 選択肢 A / B / C のいずれを採るか (= 推奨は B、 段階導入)
2. **synthesis Round 22 改訂のタイミング**: T075 PR と同期 / 先 merge / 後 merge - 推奨は **先 merge** (= T075 で blocked-by 明示)
3. **T064 follow-up PR (c_pass_depth field)**: T066/T067/T068 詳細実装より先に着地必須 (Phase 2 配線時の前提)、 前セッション持ち越し
4. **T058 詳細設計改訂 (applied_from_run_id v2 必須化)**: T069 完了で必須化が確定、 T069 と T058 の同時 merge 計画
5. **T064 詳細設計改訂 (TradeRecord → Trade、 session_pass_pattern 3 bit)**: T070 / T071 完了で必要性が確定、 T064 PR 改訂のタイミング検討
6. **T063 詳細設計改訂 (q_force_recommendation 配線)**: T071 完了で必要性が確定
7. **T058 詳細設計改訂 (= dsr_v1 / dsr_v2 併存)**: T073 完了で必要性が確定、 Phase 2 で sharpe_calc_version 同期
8. **synthesis Round 22 改訂候補 5 件**: T075 で SSOT 化した new_cascade 採用しない / FM1-FM5 SSOT / DoD 機械検証形式 / 数値 threshold / stable clause anchor を別 PR で synthesis 改訂
9. **T071 詳細設計改訂申し送り**: RunObservabilityReport に audit / graduation_trigger / smoke_dod field 追加 (T073 / T074 / T075 で申し送り、 Phase 2 で同時実装)
10. **collider bias 規範統一**: T072-T075 で確立された non-goal 規範を T071 / T064 / T066 詳細設計改訂で継承 (= holiday_markets 単独 drop 禁止、 stratified audit は Phase 2 で T071 経由)

---

## 9. Codex Review 累積統計 (cascade port v2 全 18 件 + synthesis 改訂)

### 全 18 TODO + synthesis 改訂 の Round 数集計

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
| T069 calibrate-gate-scope | 3 | 3 | 6 |
| T070 backtest-engine-extension | 4 | 2 | 6 |
| T071 observability | 2 | 3 | 5 |
| **T072 DST/holiday boundary contract** | **5** | **3** | **8** |
| **T073 audit-layer-DSR-PBO-SPA-scaffold** | **3** | **2** | **5** |
| **T074 graduation-lane-batch-evaluator-scaffold** | **3** | **4** | **7** |
| **T075 bigbang-cleanup-smoke** | **4** | **3** | **7** |
| **合計** | **63** | **52** | **115** |

### Codex review コスト累計 (全 18 件)

- 概念レビュー: 63 round × ~30K tokens/round ≈ **1,890K tokens** (gpt-5.4 medium)
- 詳細レビュー: 52 round × ~50K tokens/round ≈ **2,600K tokens** (gpt-5.3-codex high)
- **合計: 約 4,490K tokens** (≈ 4.5M tokens)

cascade port v2 設計フェーズで投入された Codex レビューコストの total。 全 APPROVED で完了。

---

## 10. 補足: 本セッションで学んだこと (Phase 2 で適用)

### 10.1 synthesis local projection 規範 (T075 で確立)

T075 設計で「親 SSOT を再定義しない」 規範が確立。 子 TODO は親 SSOT (= synthesis / T071-T074) を **参照のみ** で利用、 SSOT の意味論を拡張する場合は親 SSOT 改訂 (= synthesis Round 22 等) を blocked-by として明示。

**Phase 2 でも採用**: 各 Phase 2 PR は Phase 1 詳細設計を SSOT として参照、 詳細設計の改訂は別 PR で同期。

### 10.2 status field 方式の最終形 (T071 → T073 → T074 → T075 で進化)

Optional 経路 (= None で計算不能を表現) の代わりに `status: Literal[...]` field + sentinel value を使う方式が cascade port v2 全体で標準化:

- T071 で導入: `ABDivergenceMetric` 等で status field
- T073 で `AuditDSRStatus` (5 値) と `AuditScaffoldStatus` (1 値) 分離
- T074 で `GraduationTriggerStatus` (4 値、 業務不足状態のみ、 入力 contract 違反は ValueError)
- T075 で `EvidenceClass` (4 値、 threshold-free) + `Severity` (4 値、 同型) + `AggregateEvidence` 二軸保持 で C8 規範 (= データ不足は正当な結論) を保護

**Phase 2 でも採用**: 全 Phase 2 PR で status field 方式を継承、 None 経路完全排除。

### 10.3 scaffold 数値 field なし規範 (T073 → T074 → T075 で確立)

Phase 4 / Phase 2 で実装する scaffold dataclass は **数値 field を持たない**:
- T073 AuditPBOMetric / AuditSPAMetric: status + audit_calc_version のみ
- T074 MultiPairAggregationSketch: 同上
- T075 SmokeDoDItem: status + detail (文字列) のみ

理由: status check 漏れで誤読 risk 排除 (= 例えば PBO scaffold で pbo_value=Decimal("0") を「最良値」 と誤読)、 fail-closed 強化。 Phase 2 で field 追加時は MINOR bump (= 1.0.0 → 1.1.0、 後方互換)。

**Phase 2 でも採用**: 各 scaffold dataclass を実装値で置換する際は MINOR bump、 旧 reader は status field のみ参照。

### 10.4 collider bias non-goal 規範 (T072 → T073 → T074 → T075 で継承)

T072 で確立した collider bias 規範:

> holiday_markets / dst_transition_markets / schedule_status を T072 / T073 / T074 / T075 module 内では参照しない。 stratified audit / 因果解釈 / 比率差判定は **Phase 2 で T071 RunObservabilityReport 経由** で出力する責務。

AST grep DoD test で T072-T075 全 module で `observability_flags` / `holiday` / `DST` / `stratified` の参照不在を構造的に確認。

**Phase 2 でも採用**: T071 RunObservabilityReport 経由で stratified audit を実装、 各 caller は holiday_markets を condition variable として明示し、 単独 drop しない。

### 10.5 dual-path operational definition (T075 で確立)

「並走」 (= 禁止) と「同居」 (= 許容) の境界を operational definition で明確化:

- 並走: runtime 到達可能 OR feature flag で切替可能 OR 同じ出力契約を二経路で生成可能
- 同居: source tree に残るが runtime から到達不能

**Phase 2 でも採用**: 切替コミット (T075 Phase 2) で旧実装を git rm、 history からは復元可能だが「再有効化禁止」 規範。

### 10.6 hard dependency 昇格規範 (T071 → T072 → T073 → T074 で進化)

上流 PR 未確定の field 表現は **hard dependency** として扱う。 PR description に依存 PR の merge commit hash + field grep DoD を明記、 上流 PR と同期 merge。

**Phase 2 でも採用**: 各 Phase 2 PR で T071 RunObservabilityReport 拡張 + run_ga.py adapter 拡張を hard dependency として申し送り。

### 10.7 Fact / Interpretation 分離規範 (全 Round で採用)

C6「観察された事実 (Facts)」 と「解釈・推論 (Interpretations)」 を明確に区別。 全 Codex review プロンプト + 概念設計 / 詳細設計で本テンプレート採用。

**Phase 2 でも採用**: 全 review プロンプト + design 文書で Fact / Interpretation 分離を継承。

これらの教訓は次セッション (Phase 2 配線) でも継続適用する。

---

これで cascade port v2 設計フェーズ完了時点の handoff は以上。 次セッションで Phase 2 配線実装に移行 → 全 17 件 Phase 2 完了 + synthesis Round 22 改訂 + T075 切替コミット (big-bang 1-shot) で cascade port v2 完了へ。
