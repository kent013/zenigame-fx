# Selection Cascade Port — Session Handoff (M5 進行中、 T071 完了時点)

**作成日時**: 2026-04-30 20:09 JST
**Session**: M5 (Engine+DST+Observability) 進行中、 T070+T071 完了 (2/3)、 T072 残
**前セッション**: M4 完了 (T067-T069) → 本セッションで M5 半分超 (T070+T071) 設計
**次セッション**: M5 残 (T072 DST/holiday boundary contract) → M6 (T073-T075) へ

---

## 0. 現在地 (Where we are)

### 完了済 (M1 + M2 + M3 + M4 + M5 半分超)

**M1 基盤層** (前々セッション完了): T058 / T059 / T060
**M2 評価層** (前々セッション完了): T061 / T062 / T063 / T064
**synthesis Round 21 改訂** (前々セッション完了): mission_signed_margin SSOT 昇格
**M3 GA 中核** (前セッション完了): T065 / T066
**M4 Loop+緊急** (前セッション完了): T067 / T068 / T069 (T069 は本セッション開始時点で残、 完了済)

**M5 Engine+DST+Observability** (本セッションで T070 / T071 完了、 T072 残):

- **T069 Calibrate-gate scope** (M4 完了マーカー): 概念 3 round + 詳細 3 round APPROVED
  - synthesis § 8.6 厳密準拠 (scope key=dataset_epoch_id 1 軸 / 凍結窓 3 Run / |Δ|<=0.03)
  - distinct applied_from_run_id count で Run 数判定 (二重 append 耐性)
  - skip_frozen は load_calibrated_threshold 対象外 SSOT (= config 値 fallback)
  - big-bang atomic cut (library + default.yaml + docs 同時更新)、 caller 配線は Phase 2
  - yaml 書き戻し経路は T069 で作らない (Phase 2 で案 A immutable seed 推奨確定)
  - T058 詳細設計に applied_from_run_id v2 必須化を申し送り
  - commit: `f5e6fc2`

- **T070 Backtest engine 拡張**: 概念 4 round + 詳細 2 round APPROVED
  - SessionBlockBucket (8h covering partition: Tokyo 0-8 / London 8-16 / NY 16-24 UTC、 重複なし)
  - SessionBlock (1 営業日 × 1 bucket、 trade.exit_time 一括帰属)
  - aggregate_session_blocks (date universe = bars touched UTC date set × 3 bucket、 empty block 含む)
  - apply_spread_stress (T064 申し送り解消、 Trade(normal) と Trade(stressed) 契約境界明示)
  - Trade.spread_cost / holding_cost field 追加 (記録のみ、 既存 cash 操作不変)
  - BacktestResult.session_blocks transport SSOT (caller 再計算禁止)
  - DST/holiday は T072 で別 layer 対応
  - commit: `04aa271`

- **T071 Observability layer**: 概念 2 round + 詳細 3 round APPROVED
  - synthesis § 8.7 / § 10.1 / § 18.2 T915 厳密準拠
  - A→B 乖離 (Pearson corr on B-evaluated population、 conditioning 関数名で明示)
  - q_force 自動補正推奨 (synthesis 確定値 0.40/0.02/0.5 + T071 仮説値 0.30/0.15)
  - archive churn / bypass 比率 / session entropy / feasible_ratio_ema / front1 cardinality
  - inflow consistency (warmstart + admission + config 統合)、 FailureSummary 消費
  - status field 方式で None 経路完全排除 (else: raise で runtime 強制)
  - AB_MIN_ACTIONABLE_PAIRS=10 (C7 規範準拠)
  - session_pass_pattern 3 bit 正規表現契約 + T064/T066 hard dependency 昇格
  - T065-T068 hard dependency (PR description merge commit hash + field grep DoD + extract 期待値テスト)
  - 単一 module run_metrics.py (11 dataclass + 9 関数) で機能集約
  - commit: `a8ecd1d`

### 未着手 (M5 残 + M6)

- **T072 DST/holiday boundary contract** (M5 最後): FX 専用 UTC 基準 + 祝日カレンダ + 週末 gap 処理
- T073 Audit layer (DSR 先行 + PBO/SPA scaffold)
- T074 Graduation lane batch evaluator scaffold
- T075 Big-bang cleanup + smoke (1 Run E2E + 5 Run 連続検証)

### 重要: 設計のみ完了、 実装はまだ

T058-T071 全 14 TODO は **devnotes/ の概念 + 詳細設計のみ完了**、 src/ に新規コードは未実装。 既存 stage_gate.py / archive.py / cross_pair.py / swim_lane.py / run_ga.py / broker/orders.py / backtest/engine.py には**一切 touch していない**。

---

## 1. 全体ロードマップ

| Milestone | TODO 範囲 | 進捗 |
|---|---|---|
| **M1: 基盤層** | T058-T060 | ✅ 完了 |
| **M2: 評価層** | T061-T064 | ✅ 完了 |
| **synthesis Round 21 改訂** | mission_signed_margin SSOT | ✅ 完了 |
| **M3: GA 中核** | T065-T066 | ✅ 完了 |
| **M4: Loop+緊急** | T067-T069 | ✅ 完了 |
| **M5: Engine+DST+Observability** | T070-T072 | 🟡 2/3 完了 (T070/T071 完了、 T072 残) |
| **M6: Audit+Graduation+Smoke** | T073-T075 | ⏳ 最終 |

---

## 2. 本セッション完了内容詳細

### 2.1 commit 一覧 (本セッション、 計 3 commit)

| commit | 内容 |
|---|---|
| `f5e6fc2` | docs(T069): Calibrate-gate scope 設計完了 (M4 完了) |
| `04aa271` | docs(T070): Backtest engine 拡張 設計完了 (M5 開始) |
| `a8ecd1d` | docs(T071): Observability layer 設計完了 (M5 残 T072 のみ) |

### 2.2 Codex review 統計 (本セッション)

| TODO | 概念 (gpt-5.4 medium) | 詳細 (gpt-5.3-codex high) |
|---|---|---|
| T069 | 3 round (C1-C5/W1-W3 → C5/W1-W2 → APPROVED) | 3 round (C1-C5/W1-W3 → C1-C2/W1-W3 → APPROVED) |
| T070 | 4 round (C1-C3/W1-W3 → C4-C5/W4-W6 → C6-C7/W7-W9 → APPROVED) | 2 round (C1-C4/W1-W3 → APPROVED) |
| T071 | 2 round (C1-C6/W1-W4 → APPROVED) | 3 round (C1-C5/W1-W4 → C1-C7/W1-W5 → APPROVED) |
| **合計** | **9 round** | **8 round** |

合計 17 Codex review round、 重要 modification は全反映済。

### 2.3 主要な設計判断 (本セッションで確立)

1. **scope key 1 軸厳密準拠 (T069)**: synthesis § 8.6 「scope key=dataset_epoch_id」 を厳密に 1 軸固定。 base_config_hash 等の整合は T058 load_calibrated_threshold (4 軸 verify) で別 layer 担保 → 多層防御
2. **distinct Run count + applied_from_run_id v2 必須化申し送り (T069)**: record 数ではなく `len({r.applied_from_run_id for r in matching})` で count、 二重 append 耐性。 v2 必須化は T058 詳細設計改訂申し送り
3. **skip_frozen state 解決 SSOT 統一 (T069)**: 「load_calibrated_threshold 対象外 → config 値 fallback」 で単一系統。 freeze 中の旧 yaml threshold 流入は Phase 2 案 A (yaml=immutable seed) で確定
4. **big-bang atomic cut (T069)**: library + default.yaml + docs を T069 PR で同時更新、 Phase 1 単独 merge でも fail-closed 起こさない
5. **8h × 3 covering partition (T070)**: synthesis § 4.4 厳密準拠、 既存 9h overlap (primitives) と別責務並列管理
6. **trade exit_time 一括帰属 (T070)**: 全 cost (pnl / spread_cost / holding_cost) を exit bucket に集計、 entry/exit 跨ぎ trade の混在配賦回避
7. **Trade.spread_cost / holding_cost は記録のみ、 既存 cash 操作不変 (T070)**: 既存 broker (apply_bar_holding_cost / _close_one) 挙動を破壊しない、 二重計上防御
8. **apply_spread_stress: Trade(normal) vs Trade(stressed) 契約境界 (T070)**: F13 invariant は normal のみ、 stressed は別 invariant `pnl + holding_cost == raw_pnl - delta_spread`
9. **BacktestResult.session_blocks transport SSOT (T070)**: caller 再計算禁止、 engine 内で 1 回計算 + 同梱
10. **status field 方式で None 経路完全排除 (T071)**: 全 metric 常時存在、 ABDivergenceMetric / ArchiveChurnMetric / SessionEntropyMetric の __post_init__ で `else: raise ValueError` で runtime 強制
11. **A→B 乖離 conditioning 関数名で明示 (T071)**: `compute_ab_divergence_on_b_evaluated`、 C3 collider bias 配慮
12. **synthesis 確定値 vs T071 仮説値の Final 定数分離 (T071)**: DELTA_PER_RUN/Q_FORCE_MAX/RESTORE_THRESHOLD vs Q_FORCE_MIN/DIVERGENCE_THRESHOLD
13. **AB_MIN_ACTIONABLE_PAIRS=10 (T071)**: C7 規範準拠 (n<10 で q_force 補正抑止)
14. **session_pass_pattern 3 bit 正規表現契約 + T064/T066 hard dependency 昇格 (T071)**: 上流 contract を T071 PR の hard dependency に
15. **T065-T068 hard dependency (T071)**: PR description merge commit hash + field grep DoD + extract function 期待値テスト

---

## 3. 次セッションの開始手順

### 3.1 まず読むもの (15 分)

1. **本ハンドオフ** (`devnotes/20260430-2009-cascade-port-handoff-m5-progress/handoff.md`)
2. **synthesis 全体** (`devnotes/20260428-2300-cascade-port-debate/synthesis.md`、 Round 21 改訂後)
3. **TODO リスト** (`docs/alpha_factory/TODO.md`、 T058-T071 が Open に登録済)
4. **直近 3 TODO 設計** (T069-T071):
   - `devnotes/20260430-1700-todo-T069-calibrate-gate-scope/`
   - `devnotes/20260430-1810-todo-T070-backtest-engine-extension/`
   - `devnotes/20260430-1925-todo-T071-observability/`
5. **過去 handoff** (履歴参照のみ): `devnotes/cascade-port-handoffs-historical/`

### 3.2 T072 開始時のチェックリスト

T072 (DST/holiday boundary contract) は M5 最後の TODO:

synthesis 関連箇所:
- synthesis § 18.2 T914: 「Timezone / DST / holiday session boundary contract: FX 専用 UTC 基準 + 祝日カレンダ + 週末 gap 処理」
- synthesis § 15 (INCONCLUSIVE 一覧): 「DST/holiday 詳細境界は T914 で contract 化」 と明示

T072 の責務:
- BLOCK_BUCKET_RANGES_UTC (T070 SSOT) への DST 例外
- 祝日カレンダ (= 主要市場 holiday: 日本 / 英国 / 米国)
- 週末 gap 処理 (= 金曜 NY close 後 ～ 月曜 Tokyo open までの bar 不在区間)
- holiday 時 SessionBlock の特別扱い (= bar_count=0 / trade_count=0 の neutral block 扱い、 または partial day block の境界)

T070 (concept §3.2 / §6.4) で「T072 で DST 例外を別 layer で扱う」 旨が申し送り済。 T070 SSOT (UTC 単純基準 8h×3) は変えず、 別 layer で例外を加える設計が想定。

参考:
- synthesis § 4.4 「8h × 3 = 24h」 partition (T070 SSOT)
- synthesis § 6.2 / § 6.3 session block PnL series (T070 SSOT)
- T070 detailed-design § 3.1 BLOCK_BUCKET_RANGES_UTC + §3.4.1 trade exit_time 一括帰属
- T071 conceptual-design § 3.6 session_pass_pattern 3 bit (T064/T066/T072 共通契約)
- 既存 zenigame-fx の祝日カレンダ参照: 不在 (= T072 PR で新設)、 zenigame 側にもなさそう

### 3.3 T073 以降の準備 (M6)

- **T073 Audit layer**: DSR (Bailey & López de Prado 2014) 先行実装 (zenigame `_dsr.py:126` 同等) + PBO (Bailey CSCV 2015) / SPA (Hansen 2005) は schema scaffold + 「未実装」 タグ。 archive / report 層に置く (early gate ではない)
- **T074 Graduation lane batch evaluator scaffold**: 起動条件 (graduates>=24 + 3 epoch + mission 連続) + multi-pair 集約 sketch (詳細実装は Phase 4 別 TODO)
- **T075 Big-bang cleanup + smoke**: 旧 path 削除 + 1 run E2E smoke + 5 run 連続検証

### 3.4 設計フローのテンプレート (T069-T071 と同じ)

```
1. devnotes/{YYYYMMDD-HHMM}-todo-T{NNN}-{topic}/ ディレクトリ作成
2. 概念設計 → Codex 概念レビュー (gpt-5.4 / medium) → APPROVED まで Round
3. 詳細設計 → Codex 詳細レビュー (gpt-5.3-codex / high) → APPROVED まで Round
4. /zenigame-fx-todo-add で TODO 登録 (theme は 'infrastructure' / 'stage-gate' / 'ga-architecture' / 'statistics' / 'cross-pair' / 'data-ingest' / 'general' / 'primitives' / 'skill-port' / 'swim-lane' のいずれか)
5. commit (devnotes + TODO.md)
```

### 3.5 重要な原則 (本セッションで継続適用、 T072 でも踏襲)

- **Phase 1 / Phase 2 分離**: 各 TODO PR は単体テストのみで runtime 未組込
- **Phase 2 申し送りを設計時に明示**: 後段で同時更新が必要な箇所を漏らさず列挙
- **C2 parallel-path 5 段階 grep**: 直 import / alias / relative / 再エクスポート / runtime シンボル
- **C4 前提検証**: 設計書冒頭で `main@<commit>` 基準を明示
- **synthesis 確定値を変えない**: 安易な変更禁止、 矛盾発見時は synthesis 改訂 PR を別途 (Round 21 改訂と同じ手順)
- **概念設計の Round で確定**: SSOT 不整合は概念設計で必ず潰す (詳細設計送りにしない)、 Codex レビューでよくある指摘
- **§ 11.2 SSOT 規約**: 概念設計の API シグネチャを唯一の正本とし、 他節は同期。 詳細設計内も SSOT 注記で固定
- **status field 方式 (T071 確立)**: Optional 経路を排除する場合は全 case の invariant + `else: raise` で runtime 強制
- **hard dependency 昇格 (T071 確立)**: 上流 PR 未確定の field 表現は hard dependency として扱い、 PR description に merge commit hash + field grep DoD を明記
- **C7 規範準拠 (T071 確立)**: n<10 で actionable 抑止、 sample size guard を構造で担保

### 3.6 T072-T075 が消費する依存先 module

- **T058 schema v2**: dataset_epoch_id / archive_role / source_stage / schema_version=2 全経路必須 (T072 でも継承)
- **T060 Partition+Fold**: Period / Fold dataclass (T072 で holiday 例外を加味)
- **T061 canonical_metrics**: SessionBlock を入力 (T072 で boundary 例外があれば skip)
- **T064 stage_bc_evaluator**: BCEvaluationResult / shadow_robustness_score (T070 申し送りで spread stress 経路結合)
- **T065 nsga2_selection**: GenerationSelectionResult (T071 で消費済)
- **T066 cpps_archive**: ArchiveState / ArchiveCandidate / ArchiveMember / AdmissionReport (T071 で消費済)
- **T067 loop_closure**: WarmstartState / EmergencyState / EvaluationOutcome (T071 で消費済)
- **T068 failure_handling**: FailureRecord / FailureSummary / RunFailureSummary (T071 で消費済)
- **T069 calibrate_freeze**: FreezeStatus / 関連関数 (T072 では touch せず)
- **T070 session_block**: SessionBlock / SessionBlockBucket / BLOCK_BUCKET_RANGES_UTC (T072 で DST 例外を加える)
- **T071 observability**: RunObservabilityReport (T073 audit が一部消費)

### 3.7 注意事項 (本セッションで発生した重要な設計決定)

- **synthesis Round 22 改訂候補 (T067 PR と同時)**: synthesis § 8.2 を「3 層流入 = CA admission、 DA admission = warmstart 経路」 と明文化 (前セッション持ち越し、 まだ未着手)
- **T064 follow-up Phase 0**: BCEvaluationResult.c_pass_depth field 追加が必須 (T066/T067/T068 共通依存、 まだ未着手)
- **T058 詳細設計改訂申し送り (T069 反映)**: HistoryRecord.applied_from_run_id を v2 必須化
- **T064 詳細設計改訂申し送り (T070 / T071 反映)**: TradeRecord → Trade 命名統一、 session_pass_pattern を 3 bit string で固定
- **T063 詳細設計改訂申し送り (T071 反映)**: q_force_recommendation の caller 配線 (StageAControllerState 更新)
- **session_pass_pattern T064/T066 hard dependency (T071 反映)**: T072 で holiday 時の pattern 値 (= 営業日数不足の block で session_pass_pattern が定義可能か) を確認
- **Codex 詳細レビューの Critical 多発傾向**: T071 詳細 Round 1 で C5、 Round 2 で C7 発生。 status invariant・field 同期・test_id 1:1 の指摘が頻出、 概念設計で潰せるものは概念で

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
| `devnotes/20260430-1700-todo-T069-calibrate-gate-scope/` | T069 設計 (本セッション) |
| `devnotes/20260430-1810-todo-T070-backtest-engine-extension/` | T070 設計 (本セッション) |
| `devnotes/20260430-1925-todo-T071-observability/` | T071 設計 (本セッション) |
| `devnotes/20260430-2009-cascade-port-handoff-m5-progress/handoff.md` | **本ハンドオフ (T071 完了時点、 canonical な引き継ぎ)** |
| `devnotes/cascade-port-handoffs-historical/` | 過去 handoff (M1 完了 / M2 中間 / M2 完了 / M4 進行中 履歴参照のみ) |
| `docs/alpha_factory/TODO.md` | TODO 一覧 (T058-T071 が Open に登録済) |
| `AGENTS.md` | プロジェクト全体規約 |

### 4.2 zenigame コード参照 (T072-T075 で参考)

| 機構 | zenigame ファイル |
|---|---|
| 祝日カレンダ | (zenigame 側にも不在の見込み、 T072 で新設) |
| DST 切替判定 | (zenigame 側に存在しないため fx で先行実装、 zenigame 逆輸入候補の追加) |
| DSR (T073) | `/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/runner/_dsr.py:126` (T073 で参考) |
| PBO (T073 schema scaffold) | (zenigame 側にも未実装) |
| SPA (T073 schema scaffold) | (zenigame 側にも未実装) |

### 4.3 Codex 呼び出し方 (T069-T071 と同じ)

- 概念レビュー: `gpt-5.4` / `medium`、 label `conceptual-review`
- 詳細レビュー: `gpt-5.3-codex` / `high`、 label `design-review`
- skill: `zenigame-fx-codex-review`
- **重要**: Codex は file read を「コマンド実行禁止」 と誤解釈して拒否することがある。 Round 1 で本文を inline で貼り付けるのが確実 (本セッションで全 Round で確認)

### 4.4 TODO 登録方法 (theme 制約あり)

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

注: 'observability' は theme として未登録。 T071 では 'infrastructure' を採用。 T073 audit layer も同様 (= 'statistics' or 'infrastructure' で登録予定)。

---

## 5. 進捗状況サマリー

```
synthesis (Round 21 改訂済) ████████████████████ 100%
M1 (基盤)                   ████████████████████ 100% (T058-T060 完了)
M2 (評価)                   ████████████████████ 100% (T061-T064 完了)
M3 (GA)                     ████████████████████ 100% (T065-T066 完了)
M4 (Loop)                   ████████████████████ 100% (T067-T069 完了)
M5 (Eng)                    █████████████░░░░░░░  67% (T070-T071 完了、 T072 残)
M6 (Fin)                    ░░░░░░░░░░░░░░░░░░░░   0% (T073-T075 未着手)
```

**全体進捗**: 設計 18 件中 14 件完了 (77.8%)、 実装は 0%

---

## 6. 次セッションの最初の指示テンプレート

ユーザが次セッションで以下のように指示すると即座に再開可能:

> 引き継ぎは `devnotes/20260430-2009-cascade-port-handoff-m5-progress/handoff.md` 読んで。 T072 (DST/holiday boundary contract) から続行してください。 同じ flow (概念設計 → Codex レビュー APPROVED → 詳細設計 → Codex レビュー APPROVED → TODO 登録 → commit) で。

---

## 7. 未解決事項 / 次セッション最初に確認

1. **synthesis Round 22 改訂 PR のタイミング**: T067 PR と同時 / T067 後 - 推奨は T067 PR (Phase 2) と同時 (現状 Phase 1 設計のみなので Round 22 改訂もまだ着手不要)、 前セッション持ち越し
2. **T064 follow-up PR (c_pass_depth field) のタイミング**: T066/T067/T068 詳細実装より先に着地必須 (Phase 2 配線時の前提)、 前セッション持ち越し
3. **T058 詳細設計改訂 (applied_from_run_id v2 必須化)**: T069 完了で必須化が確定、 T069 と T058 の同時 merge 計画
4. **T064 詳細設計改訂 (TradeRecord → Trade、 session_pass_pattern 3 bit)**: T070 / T071 完了で必要性が確定、 T064 PR 改訂のタイミング検討
5. **T063 詳細設計改訂 (q_force_recommendation 配線)**: T071 完了で必要性が確定
6. **実装フェーズ移行戦略**: 全 18 設計完了後 (M6 まで) / M5 完了後 / 現時点 (T071 完了) - ユーザ判断保留
7. **T072 → T075 の優先順位**: T072 (M5 最後) が直近、 T073-T075 は M6 全体で並行可能 (T073 audit が cascade port 切替 commit に必要)

---

## 8. Codex Review 累積統計 (M1+M2+synthesis 改訂+M3+M4+M5 部分)

### 全 14 TODO + synthesis 改訂 の Round 数集計

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
| **合計** | **48** | **40** | **88** |

### Codex review コスト (gpt-5.4 medium = 概念、 gpt-5.3-codex high = 詳細)

- 概念レビュー: 48 round × ~30K tokens/round ≈ 1,440K tokens
- 詳細レビュー: 40 round × ~50K tokens/round ≈ 2,000K tokens
- 合計: **~3.44M tokens** (gpt-5.4 / gpt-5.3-codex 混在)

---

## 9. 補足: 本セッションで学んだこと (T072 以降で適用)

### 9.1 status field 方式のパターン (T071 で確立)

Optional 経路 (= None で計算不能を表現) の代わりに `status: Literal[...]` field + sentinel value を使う方式:

```python
@dataclass(frozen=True)
class XxxMetric:
    status: XxxStatus            # Literal["ok", "insufficient_data", ...]
    value: Decimal               # status="ok" 以外では sentinel
    n_pairs: int                 # 補助情報

    def __post_init__(self) -> None:
        if self.status == "ok":
            # 値域 invariant
        elif self.status == "insufficient_data":
            # sentinel 強制
        # ...
        else:
            raise ValueError(f"unknown status: {self.status!r}")  # runtime 拒否
```

**メリット**:
- caller は `status == "ok"` で計算可否を判定、 None check より型 safe
- runtime で Literal 違反 / None / 未知 status を `else: raise` で拒否
- sentinel invariant で「計算不能なのに値が入っている」 状態を構造的に排除

**T072 でも採用候補**: holiday 時の SessionBlock に `block_status: Literal["regular", "holiday", "weekend_gap", "dst_transition"]` を追加する形

### 9.2 hard dependency 昇格 (T071 で確立)

上流 PR 未確定の field 表現は **hard dependency** として扱う:
- T071 PR description に T065-T068 merge commit hash を必須記載
- field grep DoD を §2 に明示し、 PR review で実行
- extract function の期待値テストで cross-PR field rename を検出
- session_pass_pattern 3 bit 表現は T064/T066 PR と T071 PR を **同期 merge**

**T072 でも適用候補**: 祝日カレンダ source (= JPX/LSE/NYSE 公式 calendar) と DST 切替日付 (= IANA tz database) の hard dependency 化

### 9.3 synthesis 確定値 vs 設計判断値の Final 定数分離 (T071 で確立)

```python
# synthesis § 8.7 確定値 (= 厳密準拠)
DELTA_PER_RUN: Final[Decimal] = Decimal("0.02")
Q_FORCE_MAX: Final[Decimal] = Decimal("0.40")
RESTORE_THRESHOLD: Final[Decimal] = Decimal("0.50")

# T071 仮説値 (= synthesis 未明示、 T071 設計判断、 Phase 2 で再校正)
Q_FORCE_MIN: Final[Decimal] = Decimal("0.15")
DIVERGENCE_THRESHOLD: Final[Decimal] = Decimal("0.30")
```

「synthesis 厳密準拠」 と「設計判断」 を明確分離することで、 後続レビューでの混同を防ぎ、 再校正ターゲットを明示できる。

**T072 でも採用**: synthesis § 18.2 T914 の文言は「FX 専用 UTC 基準 + 祝日カレンダ + 週末 gap 処理」 と概略のみ、 詳細値 (= どの市場の祝日を採用するか、 DST 切替の bar 帰属、 週末 gap の bar 補完有無) は T072 設計判断値として分離

### 9.4 C7 規範準拠 (T071 で確立)

n<10 で actionable 抑止 (= q_force 補正アクションを起こさない):
- AB_MIN_ACTIONABLE_PAIRS=10 を Final 定数化
- compute_ab_divergence_on_b_evaluated で n<10 → status="insufficient_data"
- recommend_q_force_adjust で status≠"ok" → reason="insufficient_data"、 delta=0

**T072 でも採用候補**: holiday 期間中の bar count が極端に少ない場合 (= n<10 等) は SessionBlock を「neutral block」 として扱い、 後段 evaluator (T061 canonical 5) で SR 計算から除外

これらの教訓は次セッション (T072 以降) でも継続適用する。

---

## 10. 設計上のオープンなアイデア (T072-T075 で検討)

### 10.1 T072 設計のキーポイント (推測)

- **DST 切替日**: 年 2 回 (春/秋)、 主要市場 (London/NY) で別日。 切替時刻も bar tz 換算で異なる
- **祝日カレンダ**: 主要 3 市場 (Tokyo/London/NY) の交易日カレンダ。 国定祝日 + 取引所固有 holiday
- **週末 gap**: 金曜 NY close (= 22:00 UTC 前後) ～ 月曜 Tokyo open (= 23:00 UTC 日曜) の bar 不在
- **T070 SSOT (UTC 単純基準) は変えない**: T072 は別 layer で例外を加える、 BLOCK_BUCKET_RANGES_UTC は不変
- **SessionBlock 拡張**: status field (regular / holiday / dst_transition / weekend_gap) を追加検討
- **新設 module**: `src/alpha_factory/calendar.py` または `src/alpha_factory/observability/holiday_calendar.py` (T071 と統合 or 別 module)

### 10.2 T073 (Audit) 設計のキーポイント (推測)

- DSR は zenigame `_dsr.py:126` を参考に先行実装
- PBO / SPA は schema scaffold + 「未実装」 タグ (smoke 後段階追加)
- archive / report 層に置く (early gate ではない、 = selection 経路に影響しない)
- T071 RunObservabilityReport.ab_divergence を audit input として消費

### 10.3 T075 (Smoke) 設計のキーポイント (推測)

- synthesis § 18.3 で smoke DoD 確定済
- 1 Run E2E + 5 Run 連続検証
- 旧 path 削除 (= synthesis § 12.1) と同日切替

---

これで T071 完了時点の handoff は以上。 次セッションで T072 から再開し、 M5 完了 → M6 (T073-T075) → 全 18 設計完了 → 実装フェーズ移行へ。
