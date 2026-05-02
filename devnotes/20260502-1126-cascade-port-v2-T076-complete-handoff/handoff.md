# Selection Cascade Port — Session Handoff (T076 完了 ✨🎉 + cascade port v2 follow-up 4 件 TODO 化)

**作成日時**: 2026-05-02 11:26 JST、 **更新**: 2026-05-02 13:35 JST (= follow-up 4 件 TODO 登録追記)
**Session**: T076 (synthesis Round 22 改訂) 完了 + cascade port v2 follow-up 4 件 (T077-T080) を skeleton design + TODO 登録
**前セッション**: cascade port v2 Phase 2 配線 18/18 完了 (`devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md`)
**次セッション**: **follow-up 4 件 (T077-T080) を順次実装 → Phase 2 切替コミット → smoke 5 Run / 実 GA 動作確認**

---

## 0. 現在地 ✨🎉 cascade port v2 設計 + 配線 + Round 22 SSOT 同期 全完了

```
Phase 1 設計 18 件 (T058-T075)            ████████████████████ 100%
T064 Follow-up                            ████████████████████ 100%
Phase 2 配線 18 件 (T058-T075)            ████████████████████ 100%
T076 synthesis Round 22 改訂              ████████████████████ 100% ✨🎉 (本セッション完了)
Phase 2 切替コミット (旧実装削除等)       ░░░░░░░░░░░░░░░░░░░░   0% (次セッション、 cascade port v2 完全完了の最終段)
```

**達成内容**:
- cascade port v2 設計 18 件 全件 Codex APPROVED (= 前々セッション)
- cascade port v2 Phase 2 配線 18 件 全 PR main merge + Closed 移動完了 (= 前セッション系列)
- T076 synthesis Round 22 改訂 完了 (= synthesis SSOT が T075 module 詳細設計と完全 1:1 整合、 本セッション)
- 全 TODO で regression 0 件
- Codex review 累計 N+ round 全 APPROVED

**残作業**:
- **Phase 2 切替コミット** (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消 big-bang 1-shot、 別 PR、 別 TODO 不要)
- 数値 threshold 確定 (= FM1-FM5 hard_fail 判定境界、 smoke 後再校正、 別 TODO)
- `select_rollback_relevant_failure_modes` 本実装 (= synthesis § 16 確定後の Phase 2 別 TODO)
- 残り 18 top-level 章 anchor 付与 + 自動 lint (= 別 TODO、 Round 23 以降)

---

## 1. T076 PR 1 (commit `77844a9` + `00d8867`、 docs-only PR、 Codex 実装 Round 1 APPROVED)

### 1.1 主要追加・変更

- `devnotes/20260428-2300-cascade-port-debate/synthesis.md` 改訂 (= 8 箇所、 +150 lines / -27 lines、 Round 21 → Round 22)
- `devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md` 新規 (= 153 lines、 Round 21 同型 7 章)
- `docs/alpha_factory/TODO.md` (= T076 Open → Closed 移動)

DoD: pytest 2050 + 1 xfailed (regression 0)、 mypy clean (no issues found in 120 source files)、 ruff 8 errors (= 既存 issue、 main HEAD でも同じ、 T076 は src/ tests/ touch なし、 別 TODO 申し送り)。

### 1.2 T076 で確定した中核要素 (5 改訂 + ε)

1. **§ 12.4 切替戦略** 全置換: `new_cascade` 名前空間廃止 → `src/alpha_factory/` 直接実装宣言 + `DUAL_PATH_ENFORCE_TARGETS` 4 経路規範 (= 3 fail_closed (`source_import` / `scripts` / `config_yaml` [yaml + yml 2 globs]) + 1 fail_open (`docs_runbook` warning)) + `DUAL_PATH_ENFORCE_ALLOWLIST` 5 patterns
2. **§ 12.4 ロールバック条件** → `FailureModeKind = Literal["FM1"-"FM5"]` enum + `select_rollback_relevant_failure_modes` API 名 + **inconclusive blocking semantics** (= `inconclusive` も `hard_fail` も含まない fail-closed、 全 metric/DoD item が ok or warning が切替 commit 前提条件)
3. **§ 18.3 Smoke DoD** 二層分離: `PerRunSmokeDoDResult` (DoD1-DoD7) / `CrossRunSmokeDoDResult` (DoD8) + 主 SSOT `SmokeDoDItem.status: EvidenceClass` (全 DoD 共通) + 関連参照 field/class (= caller 経由 `SmokeObservabilityProjection` 実 field: ab_divergence_class / epoch_consistency_class / warmstart_shortfall_class / bypass_ratio_class / session_entropy_class / dataset_epoch_id_present + cross_run_epoch_pollution_class) + **item-level fail-closed 完走判定** (= overall_evidence_class は補助条件、 集約順序 hard_fail > warning > inconclusive > ok で warning と inconclusive 混在時の false PASS を item-level で防止)
4. **§ 16 Risk Top 5** + FM ID 紐付け + threshold-free 4 値 EvidenceClass 評価規範 + `EvidenceClassifierProtocol` caller-supplied (= unsupported metric_name は inconclusive 必須、 fail-closed) + 数値 threshold smoke 後再校正の別 TODO 明示
5. **冒頭 metadata block** (`synthesis_schema_version: 22` / `last_revised` / `revision_lineage` Round 21 + Round 22 / `retroactive_anchor_grant` / `scope`) + **stable clause anchor 5 件** (= `switching-strategy` / `risk-top-5` / `smoke-dod` / `discussion-history` / `clause-anchor-index`、 kebab-case ASCII、 一意性) + **§ 22 Clause Anchor Index** 新章 (= anchor → 章マッピング + § 22.1 retroactive 取扱 + § 22.2 残り 18 top-level 章 + subsection 後続 TODO 切出)
6. **ε**: § 21 末尾に Round 22 行追加 + rationale.md 新規 (= 1 改訂理由 / 2 改訂方針 / 3 改訂内容詳細 / 4 改訂しないこと / 5 整合性検証 / 6 PR 構成 / 7 完了判定、 Round 21 同型)

### 1.3 Codex Review 経緯 (= 概念 3 round + 詳細 4 round + 実装 1 round = 計 8 round)

- **概念設計 (gpt-5.4 / medium)**: Round 1 INCONCLUSIVE (= file read 不可) → Round 2 CHANGES_REQUESTED (3 [Critical] + 4 [Warning]) → Round 3 **APPROVED** (= 残存 [Suggestion] 3 件は詳細設計で取込)
- **詳細設計 (gpt-5.3-codex / xhigh)**: Round 1 INCONCLUSIVE → Round 2 CHANGES_REQUESTED (4 [Critical] + 4 [Warning] + 1 [Suggestion] + 1 [INCONCLUSIVE]) → Round 3 CHANGES_REQUESTED (1 [Critical] + 4 [Warning] + 1 [Suggestion]) → Round 4 **APPROVED** (= 残存 [Suggestion] 4 件は実装時調整として § 18.3 に取込)
- **実装 (gpt-5.3-codex / high)**: Round 1 **APPROVED** ([Critical] なし、 [Warning] 1 + [Suggestion] 1 = 即日取込)

### 1.4 修正された主要論点 (= 設計品質向上の記録)

- 概念 Round 2 [Critical] 機械検証 grep が smoke.py 側偏在 → **2 段化** (synthesis 側 + smoke.py 側 1:1) で docs-only PR 本体検証可能に
- 概念 Round 2 [Critical] dual-path「4 経路 fail_closed」 が SSOT と矛盾 → **3+1 経路書き分け** (3 fail_closed + 1 fail_open/warning) に修正
- 概念 Round 2 [Critical] inconclusive blocking 意味曖昧 → **「inconclusive は smoke pass として扱わず Phase 2 切替をブロック、 全 metric/DoD item が ok or warning が前提条件」** で fail-closed 明確化
- 詳細 Round 2 [Critical] sed line range drift → **awk heading 範囲抽出** に統一 (= 章番号 shift 耐性)
- 詳細 Round 2 [Critical] OR grep 抜け道 → **個別 grep -q AND 検証** (= 1 要素 PASS の false positive 防止)
- 詳細 Round 2 [Critical] pipefail なし pytest exit code 消失 → **set -euo pipefail + mktemp + if 判定** で exit code 保持
- 詳細 Round 2 [Warning] overall vs item-level inconclusive 安全側崩壊 → **item-level fail-closed 完走判定** に書換
- 詳細 Round 2 [Warning] config_yaml *.yml 漏れ → **2 globs (yaml + yml)** 明記
- 詳細 Round 3 [Critical] DoD 表 SmokeObservabilityProjection 実 field 不一致 → **主 SSOT (SmokeDoDItem.status) + 関連参照 field/class (実 field: ab_divergence_class 等)** に再構成
- 詳細 Round 3 [Warning] 「残り 17/18 章」 算定曖昧 → **「anchorable clause unit」 概念導入 + § 12 / § 18 を除く残り 18 top-level 章** で正確化

---

## 2. cascade port v2 全体サマリー (Phase 1 設計 + Phase 2 配線 + Round 22 SSOT 同期 = 完了)

| Phase | 件数 | 状態 |
|---|---|---|
| Phase 1 設計 (T058-T075) | 18 件 | 全件 Codex APPROVED |
| T064 Follow-up | 1 件 | 完了 |
| Phase 2 配線 (T058-T075) | 18 件、 25 PR | 全件 main fast-forward merge、 regression 0 |
| **T076 synthesis Round 22 改訂** | **1 件、 1 PR (本 PR)** | **完了、 SSOT 同期確定** |
| Phase 2 切替コミット | 1 commit (= 単発 cleanup) | **次セッション着手** |

cascade port v2 設計 + Phase 2 配線 + synthesis Round 22 SSOT 同期が **完全完了**。 残るは Phase 2 切替コミット (= 別 PR 単発 cleanup) のみ。

---

## 3. T076 で確立した規範 (累積追加)

cascade port v2 で既に確立済の 15 設計規範 + 13 実装フロー規範に加え、 T076 で新たに確立:

### 3.1 設計規範 (T076 追加)

16. **synthesis 改訂 atomic consistency boundary**: 同一 SSOT への複数同時改訂 (= 5 改訂 + ε) を 1 PR で扱う boundary 定義、 部分採用は未完整状態を main に滞留させるため不可
17. **詳細設計 → 実装 → 上位設計 SSOT 復元 cycle**: 「実装が設計を上書きした」 のではなく、 詳細設計 SSOT を上位設計 (synthesis) に反映する 3 段健全 cycle (Round 21 と同型)
18. **inconclusive blocking semantics**: EvidenceClass 4 値で `inconclusive` は smoke pass として扱わず、 切替 commit 前提条件は「全 metric/DoD item が ok or warning」 (= item-level fail-closed)
19. **dual-path 3+1 経路の正確記述**: source_import / scripts / config_yaml の 3 経路 fail_closed + docs_runbook の 1 経路 fail_open / warning、 「4 経路 fail_closed」 という単純化記述は誤り
20. **stable clause anchor 体系**: kebab-case ASCII slug、 一意性、 章番号 shift 不変、 anchorable clause unit 単位 (= top-level 章 OR subsection)
21. **synthesis_schema_version metadata**: revision_lineage / retroactive_anchor_grant / scope を冒頭 HTML コメント block で機械可読に提供、 Round 23 以降の同型改訂継続可能
22. **rationale.md Round 21 同型 7 章構造**: 改訂理由 / 改訂方針 / 改訂内容詳細 / 改訂しないこと / 整合性検証 / PR 構成 / 完了判定

### 3.2 実装フロー規範 (T076 追加)

14. **docs-only PR の機械検証 2 段化**: synthesis 側 (新文言存在 + 旧文言不在) + 実装 SSOT 側 (= smoke.py field 存在) を改訂候補ごとに 1:1 写像、 OR grep ではなく個別 grep -q AND 検証
15. **shell 検証規範**: `set -euo pipefail` 必須 / 固定 line range sed 禁止 → awk heading 範囲抽出 / pipe exit code 保持 (mktemp + if ! command) / 配列 loop で必須項目全件 grep
16. **Codex review prompt の inline 提示パターン**: ファイル read 不可な制約環境では本文 inline + 関連 SSOT 抜粋 + 対応マトリクス + 検証要件で再提示
17. **既存 issue (= main HEAD でも発生する ruff/mypy/test 問題) は当該 PR scope 外**: regression 0 件 = 「当該 PR が新たな issue を導入していない」 ことを意味、 既存 issue 修正は別 TODO

---

## 3.5 cascade port v2 follow-up 4 件 (= 2026-05-02 13:35 追記、 TODO 登録済)

T076 完了後、 「実際に GA を fail-closed で動かすため」 の follow-up を再精査した結果、 handoff § 6 残作業のうち以下 4 件は **TODO 登録 + 個別実装** が必要 (= 当初「軽量」 と判断したが、 schema 変更や caller 影響範囲が広いため):

| TODO | タイトル | 設計 | 優先度 | 規模 |
|---|---|---|---|---|
| **T077** | T058 docstring 改訂 + applied_from_run_id v2 必須化 | `devnotes/20260502-1130-todo-t077-t058-history-record-required/` | Medium | 中 (= type 変更 + caller 整合確認) |
| **T078** | T064 apply_spread_stress 重複解消 + TradeRecord schema 拡張 | `devnotes/20260502-1130-todo-t078-t064-spread-stress-import/` | **High** | 重 (= TradeRecord に spread_cost field 追加 + adapter) |
| **T079** | T070 DST/holiday → BLOCK_BUCKET_RANGES_UTC 連携完成 | `devnotes/20260502-1130-todo-t079-t070-dst-holiday-connect/` | Medium | 中 (= option A/B/C 議論先行) |
| **T080** | T071 caller 注入式 Phase 2 配線 (= run_ga.py から build_run_observability_report 呼出追加) | `devnotes/20260502-1130-todo-t080-t071-caller-injection/` | **High** | 中 (= run_ga.py 改造 + caller-supplied 値収集) |

設計 doc は **skeleton 状態** (= 後続セッションで `zenigame-fx-alpha-design` skill で Codex review し本格化 → `zenigame-fx-implement` で実装)。

**SessionBlock mode 必須化** (= handoff § 6 残作業 7) は実は既に実装済 (= `aggregate_session_blocks_production` wrapper 新設済)。 残るは `engine.py:205` で `mode="test"` を production wrapper 置換、 これは **Phase 2 切替コミット (B) 内で実施**。

### 推奨実装順 (= 高優先 → smoke 通過に必要 → Phase 2 切替に必要)

1. **T080** (= run_ga.py 配線、 smoke の DoD 観測 SSOT 取得経路確立)
2. **T078** (= TradeRecord schema 拡張、 Stage C spread stress 評価可能化)
3. **T077** (= HistoryRecord v2 必須化、 fail-closed 強化)
4. **T079** (= DST/holiday 連携、 Phase 2 切替前は option A 現状維持で OK)
5. **B Phase 2 切替コミット** (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消、 SessionBlock production wrapper 置換含む)
6. **smoke 5 Run / 実 GA 動作確認**

T077-T080 の各 TODO は **独立した 1 worktree / 1 PR** で実装するのが推奨 (= cascade port v2 同型運用)。 ただし軽い T077 + 中規模 T080 を 1 セッションで併用可能性あり。

---

## 4. 次セッション着手フロー (= follow-up 実装 → Phase 2 切替コミット)

### 4.1 Phase 2 切替コミットの内容 (= 単発 cleanup commit、 別 TODO 不要)

T076 完了で synthesis Round 22 SSOT 確定 → 切替条件が設計側で参照可能になったため、 以下を 1 commit で実施:

#### F-1. dual-path 解消条件
- T075 `DUAL_PATH_ENFORCE_TARGETS` 4 経路 (= source_import / scripts / config_yaml / docs_runbook) test を **fail_closed で実行 + 並走経路 0 件確認**
- `DUAL_PATH_ENFORCE_ALLOWLIST` 5 patterns (= historical / devnotes / tests / .git / __pycache__) が現状と整合
- T075 smoke 5 Run 連続実行で `CrossRunSmokeObservabilityProjection.cross_run_epoch_pollution_class` == `ok`

#### F-2. LOG_ONLY → FAIL_CLOSED 切替
- T067 `loop_closure.py` の LOG_ONLY feature flag を削除 (= FAIL_CLOSED 一本化)
- schema lint で `dataset_epoch_id` 欠落 fail-closed (= synthesis § 18.3 DoD4 + smoke.py `dataset_epoch_id_present` 検証)
- `EvidenceClassifierProtocol` 経由の unsupported metric_name は inconclusive 必須 (= fail-closed)

#### F-3. 旧実装削除
- T075 `DeletionTarget` manifest (synthesis § 12.1 / § 12.2 該当 31 件) の削除完了確認
- T075 `MigrationTarget` manifest (yaml 値更新等) の migrate 完了確認
- 旧 `scripts/alpha_factory/run_alpha_sieve.py` / 旧 `calibrate_gate.py` 等 (synthesis § 12.1 旧 script 列挙) の削除確認
- 旧 `swim_lane.tier1.population_size` / `ga.feasibility.*` / `improve_cycle.plateau_*` / `stage_gate.stage_a.calibrate.*` 等 (synthesis § 12.1 旧 config キー列挙) の削除確認

#### F-4. PR タイトル / commit message
- PR タイトル: `chore: cascade port v2 Phase 2 切替コミット (旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消)`
- commit message body: 「T076 で synthesis Round 22 が確定済 → 本 commit で cascade port v2 完全完了」 旨を明示 + F-1 / F-2 / F-3 の checklist 結果

### 4.2 次セッションの最初の指示テンプレート

#### follow-up T080 着手 (= 推奨次着手、 smoke の DoD 観測 SSOT 取得経路確立)

> 引き継ぎは `devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md` 読んで。 cascade port v2 follow-up T080 (T071 caller 注入式 Phase 2 配線) を skeleton 設計 (`devnotes/20260502-1130-todo-t080-t071-caller-injection/`) から本格化して実装。 zenigame-fx-alpha-design skill で Codex review → APPROVED → zenigame-fx-implement で worktree todo/T080 → main merge。 完了後、 T078 / T077 / T079 を順次同様に実装。 全 follow-up 完了後、 Phase 2 切替コミットへ。

#### follow-up T078 着手 (= Stage C spread stress 評価可能化)

> 引き継ぎは `devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md` 読んで。 follow-up T078 (T064 apply_spread_stress 重複解消 + TradeRecord schema 拡張) を skeleton 設計 (`devnotes/20260502-1130-todo-t078-t064-spread-stress-import/`) から本格化して実装。 TradeRecord に spread_cost / holding_cost field 追加 + stage_bc_evaluator.py の skeleton 削除 + trade 生成経路で伝搬配線 + 既存 caller 整合確認。

#### Phase 2 切替コミット 着手 (= follow-up 全完了後)

> 引き継ぎは `devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md` 読んで。 follow-up T077-T080 全完了後、 cascade port v2 完全完了の最終段、 Phase 2 切替コミットを着手。 § 4.1 の F-1 dual-path 解消 / F-2 LOG_ONLY → FAIL_CLOSED 切替 / F-3 旧実装削除 を 1 commit で実施。 PR タイトル `chore: cascade port v2 Phase 2 切替コミット (旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消)`。

#### 数値 threshold 確定 別 TODO 着手 (= 切替コミット後)

> 引き継ぎは `devnotes/20260502-1126-cascade-port-v2-T076-complete-handoff/handoff.md` 読んで。 Phase 2 切替コミット完了後、 数値 threshold 確定を別 TODO で着手。 FM1 (q_force 0.40 上限再校正) / FM3 (warmstart shortfall 閾値) / FM4 (bypass ratio 閾値) / FM5 (entropy 閾値) を smoke 5 Run 観測値分布から calibration data 取得後に確定。

---

## 5. 累積 commit 一覧 (T076 セッション、 直近 5 件)

```
aead587 Merge branch 'todo/T076' (no-ff merge、 cascade port v2 全体 Round 22 SSOT 同期 完了)
00d8867 docs(TODO): T076 (synthesis Round 22 改訂) Open → Closed
77844a9 docs(T076 PR1): synthesis Round 22 改訂 (Phase 2 切替前提) — cascade port v2 Phase 2 配線完了後 SSOT 同期
fe53cc7 docs(TODO): T076 (synthesis Round 22 改訂) を Open に追加
644bbf0 docs(T076): synthesis Round 22 改訂 設計フロー完了 (概念 + 詳細 全 APPROVED)
```

T076 セッション commit 計 5 個 (= 設計 1 + TODO 追加 1 + 実装 1 + TODO クローズ 1 + merge 1)。

cascade port v2 全体 commit 累計 32 個 (= Phase 2 配線 27 + T076 5)。

---

## 6. 残作業 / 未解決事項

### 6.1 cascade port v2 残作業 (= 完全完了までの最終段)

1. **Phase 2 切替コミット** (= § 4.1 F-1 + F-2 + F-3、 別 PR 単発 commit、 別 TODO 不要)

### 6.2 cascade port v2 完全完了後の別 TODO (= 後続)

2. **数値 threshold 確定** (= FM1-FM5 hard_fail 判定境界、 smoke 後再校正、 別 TODO)
3. **`select_rollback_relevant_failure_modes` 本実装** (= T075 NotImplementedError 解除 + policy 入力対応、 synthesis § 16 確定後の Phase 2 別 TODO)
4. **残り 18 top-level 章 anchor 付与 + 自動 lint** (= § 0 / § 1-11 / § 13-15 / § 17 / § 19-20、 別 TODO、 Round 23 以降)
5. **未付与 subsection への anchor 段階付与** (= cross-ref 需要に応じて、 別 TODO)
6. **stable clause anchor 全章付与の自動化 lint + CI 検証** (= 別 TODO)
7. **synthesis_schema_version の自動 bump 機構** (= 別 TODO)

### 6.3 Phase 2 配線 残作業 (= handoff § 6 から継承)

8. T070 follow-up (BLOCK_BUCKET_RANGES_UTC への DST 例外連携)
9. T071 caller 注入式 Phase 2 配線 (= run_ga.py で必要な値を計算して T071 関数に注入)
10. T058 detailed-design 改訂依頼 (HistoryRecord.applied_from_run_id v2 必須化)
11. T064 follow-up 申し送り (apply_spread_stress を T070 import 経由に置換)
12. SessionBlock mode 必須化に伴う既存 caller 更新 (= test_session_block.py 7 caller / engine.py 1 caller)

### 6.4 既存 issue (= main HEAD で発生、 T076 とは無関係、 別 TODO)

13. ruff 8 errors: tests/alpha_factory/primitives/test_indicators_causality.py B905 1 件 + tests/scripts/test_batch_metrics.py E501 7 件 (= 別 TODO で修正)

### 6.5 その他

14. Run-26 崩壊原因: 未調査 (= yaml threshold revert のみで未追跡)
15. untracked reports: 別 TODO で .gitignore 候補 (= reports/run-reports/run-1/diagnostics/ 等)

---

## 7. cascade port v2 完了に至るまでの全体経緯

1. **Phase 1 設計** (前々セッション): 18 件全件 Codex APPROVED (= T058-T075 + T064 follow-up = c_pass_depth)
2. **Phase 2 配線** (前セッション系列): 18 TODO 全完了 + 25 PR 全 main fast-forward merge + regression 0 件
3. **T076 synthesis Round 22 改訂** (本セッション): 5 改訂 + ε で synthesis SSOT が T075 module 詳細設計と完全 1:1 整合確定
4. **Phase 2 切替コミット** (次セッション): 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消 big-bang 1-shot

cascade port v2 設計 + Phase 2 配線 + synthesis Round 22 SSOT 同期が **100% 完了**。 残るは Phase 2 切替コミット (= 別 PR 単発 commit) のみ。 cascade port v2 完了は **目前**。
