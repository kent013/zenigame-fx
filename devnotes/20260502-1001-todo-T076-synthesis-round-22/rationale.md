# Synthesis 改訂 PR (Round 22): cascade port v2 Phase 2 配線完了後 SSOT 同期

**作成日時**: 2026-05-02 11:07 JST
**対象**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md`
**改訂範囲**: 冒頭 metadata + § 12.4 + § 16 + § 18.3 + § 21 + § 22 (新設) (計 5 章 + index、 docs-only)
**起源**: cascade port v2 Phase 2 配線 18/18 TODO 全完了 (`commit 09bd56d`)、 T075 module SSOT 確定後の上位設計同期
**位置付け**: T076 完了 → Phase 2 切替 commit (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消) の前提条件

---

## 1. 改訂理由 (Why)

### 1.1 SSOT 倒立の発見 (= Phase 2 配線完了時の派生実装)

cascade port v2 Phase 2 配線 18 TODO は全て synthesis Round 21 を SSOT として実装したが、 Round 21 から派生実装 (= T075 smoke.py の `EvidenceClass` 4 値 / `FailureModeKind` enum 5 値 / DoD 二層分離 / `DUAL_PATH_ENFORCE_TARGETS` 4 経路) が確定したことで Round 21 自体が「実装の sub-set」 となり、 上位設計と詳細設計の SSOT 倒立が発生した。

### 1.2 Phase 2 切替 commit の前提条件

Phase 2 切替 commit (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消) の rollback 判定 / DoD 完走 / dual-path 検証の **設計側 SSOT が現実装と整合** していることが必須。 T076 でこの同期を確定し、 切替 commit (= 別 PR) の前提条件を満たす。

### 1.3 T075 module 内の Round 22 forward reference

T075 `src/alpha_factory/smoke.py` 自身が以下のように Round 22 を forward reference している:
- L9: `# FM1-FM5 / new_cascade 採用しない / DoD 機械検証形式 等は synthesis Round 22`
- L100-101: `FailureModeKind = Literal[...]; """synthesis § 16 enum 5 値 (= 数値 threshold は T075 範囲外、 別 TODO で確定)."""`
- L1170-1175: `select_rollback_relevant_failure_modes` docstring 内 「synthesis Round 22 改訂後に別 TODO で実装」

これらの forward reference を **有効化する** のが Round 22 改訂。

---

## 2. 改訂方針 (What)

### 2.1 5 改訂候補の atomic consistency boundary

5 改訂候補は同一 synthesis SSOT に対する atomic な同時改訂 (= 部分採用すると未完整状態が main に滞留):
1. § 12.4 「new_cascade 名前空間」 廃止 + dual-path 4 経路規範
2. § 12.4 ロールバック条件 → FM1-FM5 enum + `select_rollback_relevant_failure_modes` API 名 + inconclusive blocking semantics
3. § 18.3 Smoke DoD → per-run (DoD1-DoD7) / cross-run (DoD8) 二層分離形式
4. § 16 Risk Top 5 + FM ID 紐付け + threshold-free 4 値 EvidenceClass 評価規範
5. 冒頭 metadata block (`synthesis_schema_version: 22`) + 各章 stable clause anchor + § 22 Clause Anchor Index 新設

改訂 #1-4 は T075 smoke.py SSOT 同期、 改訂 #5 は synthesis 内部 anchor SSOT で性質は異なるが、 同一 file への atomic な PR で扱うのが consistency boundary として最適 (= Codex 概念設計 Round 2 [Warning] A 反映)。

### 2.2 cycle 位置付け (= Round 21 と同型)

T076 は「実装が設計を上書きした」 のではなく、 **「T075 詳細設計 → 実装 → 上位設計 SSOT 復元」 の健全な 3 段 cycle 最終段** (= Round 21 (mission_signed_margin) の前例と同型)。

### 2.3 改訂しない箇所 (詳細は § 4)

§ 1-11 / § 13-15 / § 17 / § 19-20、 数値 threshold、 `select_rollback_relevant_failure_modes` 本実装、 残り 18 top-level 章 anchor、 旧 round md retroactive 書換は本 PR では touch しない。

---

## 3. 改訂内容詳細 (5 章 + ε)

### 3.1 § 12.4 切替戦略 (改訂 1 + 2)

**Before** (Round 21):
- 4 bullet で「new_cascade 名前空間で実装」 + dual-path 並走なし (詳細不在)
- ロールバック条件: 「smoke で FM1/FM4 が強く出る場合のみ」

**After** (Round 22):
- 4 bullet で `src/alpha_factory/` 直接実装宣言 + `DUAL_PATH_ENFORCE_TARGETS` 4 経路 (= 3 fail_closed (`source_import` / `scripts` / `config_yaml`、 `config_yaml` は yaml + yml 2 globs) + 1 fail_open (`docs_runbook` warning)) + `DUAL_PATH_ENFORCE_ALLOWLIST` 5 patterns
- ロールバック条件: 「rollback 対象 FM 集合 (= § 16 で確定する FM1-FM5 サブセット) のいずれかが `hard_fail` evidence_class」 + 観測判定 (`SmokeOutcomeClassification.observed_failure_modes`) + rollback 対象判定 (`select_rollback_relevant_failure_modes`、 Phase 2 別 TODO) + **inconclusive blocking semantics** (= `inconclusive` は smoke pass として扱わず Phase 2 切替を **ブロック**、 全 metric/DoD item が ok or warning が前提条件、 fail-closed)

### 3.2 § 18.3 Smoke DoD (改訂 3)

**Before** (Round 21、 8 bullet 混在):
- per-run と cross-run が区別されず、 8 bullet 列挙のみ

**After** (Round 22、 二層分離形式):
- **Per-run DoD** (= `PerRunSmokeDoDResult.items: tuple[SmokeDoDItem, ...]` 7 項目、 `DoDIdPerRun = Literal["DoD1"-"DoD7"]`): DoD1-DoD7 の 4 列表 (dod_id / 内容 / 主 SSOT / 関連 projection field)、 主 SSOT は全 DoD 共通 `SmokeDoDItem.status: EvidenceClass`、 関連 field は `SmokeObservabilityProjection` 実 field (`ab_divergence_class` / `epoch_consistency_class` / `warmstart_shortfall_class` / `bypass_ratio_class` / `session_entropy_class` / `dataset_epoch_id_present`) を caller 経由参照
- **Cross-run DoD** (= `CrossRunSmokeDoDResult.item: SmokeDoDItem` 1 項目、 `DoDIdCrossRun = Literal["DoD8"]`): DoD8 単独、 関連 field `cross_run_epoch_pollution_class`
- **完走判定**: item-level fail-closed (= 全 8 DoD item の `SmokeDoDItem.status` が ok or warning、 overall_evidence_class は補助条件)

### 3.3 § 16 Risk Top 5 (改訂 4)

**Before** (Round 21、 表 3 列): 順位 / リスク / 緩和

**After** (Round 22、 表 5 列): 順位 / FM ID / リスク / 緩和方針 / 数値 threshold (= hard_fail 判定境界)
- FM1-FM5 を T075 `FailureModeKind` enum と紐付け
- 数値 threshold は smoke 後再校正の別 TODO で確定 (= FM2 の lint は threshold-free)
- § 16.1 評価規範新設: threshold-free 4 値 EvidenceClass + classifier 注入規範 (`EvidenceClassifierProtocol`) + FM 紐付け + 別 TODO 着手条件

### 3.4 冒頭 metadata + anchor (改訂 5a + 5b + 5c)

- **5a**: 冒頭タイトル直後に HTML コメント metadata block (`synthesis_schema_version: 22` / `last_revised` / `revision_lineage` (Round 21 + Round 22) / `retroactive_anchor_grant` / `scope`)
- **5b**: 5 clause units に stable clause anchor 付与 (= `switching-strategy` (§ 12.4) / `risk-top-5` (§ 16) / `smoke-dod` (§ 18.3) / `discussion-history` (§ 21) / `clause-anchor-index` (§ 22))
- **5c**: 末尾に新章 § 22 Clause Anchor Index (= anchor → 章マッピング表 + § 22.1 retroactive_anchor_grant 取扱 + § 22.2 残り 18 top-level 章 + subsection の後続 TODO 切出)

### 3.5 § 21 議論履歴 + rationale.md (ε)

- § 21 末尾に Round 22 行追加 (= Round 22 改訂 PR / 設計 SSOT 同期 / `commit 09bd56d` / 改訂対象 5 章 + 冒頭 + § 22 / 改訂 PR ref)
- 末尾「詳細は ...」 行に Round 22 rationale 参照を追加
- rationale.md 新規 (= 本 file)

---

## 4. 改訂しないことの確認 (No-touch リスト)

- **synthesis 改訂対象外章**: § 1-11 / § 13-15 / § 17 / § 19-20 (= T075 SSOT 同期に影響なし)
- **Round 21 改訂部分** (= § 6.4 / § 6.5 / § 8.3 / § 15 / § 17 の `mission_signed_margin` SSOT 昇格関連): touch せず保持 (Round 22 の改訂対象外)
- **数値 threshold** (= FM1-FM5 hard_fail 判定境界 / q_force 0.40 上限再校正等): 別 TODO で smoke 後再校正
- **`select_rollback_relevant_failure_modes` 本実装**: 別 TODO で synthesis Round 22 § 16 確定後の Phase 2
- **残り 18 top-level 章 anchor 付与 / 自動 lint**: 別 TODO で Round 23 以降 (= § 12 / § 18 を除く)
- **未付与 subsection への anchor 段階付与**: 後続別 TODO で cross-ref 需要に応じて
- **旧 round md (1-21) への retroactive 書換**: **禁止** (history 不変保持、 anchor index 経由参照のみ)
- **smoke.py 本体 / docstring**: touch なし (= forward reference 文言は Round 22 完了で「未来参照」 から「現在参照」 へ自動的に valid 化)
- **AGENTS.md / SKILL.md / config / docs/alpha_factory/* / scripts / tests**: touch なし

---

## 5. 改訂後の整合性検証

### 5.1 T075 詳細設計との整合

T075 `devnotes/20260501-0136-todo-T075-bigbang-cleanup-smoke/detailed-design.md` で確定した SSOT (= `FailureModeKind` / `EvidenceClass` / `DoDIdPerRun` / `DoDIdCrossRun` / `PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult` / `DUAL_PATH_ENFORCE_TARGETS` / `select_rollback_relevant_failure_modes`) の文言と Round 22 改訂後の synthesis 文言が完全 1:1 整合 (= 詳細設計 § 13 機械検証手順 で grep 確認)。

### 5.2 smoke.py 実装との整合

`src/alpha_factory/smoke.py` (commit `09bd56d`、 1176 LOC) の Literal / dataclass / Final 定数定義と Round 22 改訂後の synthesis 文言が完全 1:1 整合 (= 詳細設計 § 13.1-13.5 の smoke.py 側 grep で確認)。

### 5.3 Phase 2 切替 commit 前提条件としての整合

Phase 2 切替 commit (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消) の前提条件 (= 概念設計 § F-1 / F-2 / F-3 の dual-path 解消条件 / FAIL_CLOSED 条件 / 旧実装削除条件) が Round 22 改訂後の synthesis で全て参照可能 (= rollback 判定 / DoD 完走 / dual-path 検証の設計側 SSOT 確定)。

### 5.4 コードベースとの整合 (現状 0 件 touch)

T076 は docs-only PR で `src/` / `scripts/` / `config/` / `tests/` は 0 件 touch。 ruff / mypy / pytest の regression は 0 件で自動 PASS (= 詳細設計 § 13.8 横断確認で実機検証)。

---

## 6. PR 構成

| PR | 内容 | コミット数 | 検証 |
|---|---|---|---|
| **T076 PR1 (本 PR)** | synthesis.md 8 箇所改訂 + rationale.md 新規 | 1 commit (= docs-only、 atomic consistency boundary) | 詳細設計 § 13 機械検証 7 ブロック + § 13.8 横断確認 |
| (T076 後の別 PR) Phase 2 切替 commit | 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消 | 別 PR、 別 commit、 別 TODO ではなく単発 cleanup commit | T075 `DUAL_PATH_ENFORCE_TARGETS` test fail_closed 通過 + smoke 5 Run 連続 PASS |

---

## 7. 完了判定

T076 PR1 完了 = 以下を全て満たす:

- [x] synthesis.md 改訂 1-5 + ε の 8 箇所編集が完了
- [x] rationale.md 新規追加 (本 file、 § 1-7 全章存在)
- [x] 詳細設計 § 13.1-13.7 の機械検証 grep / sed / awk が全 PASS (= worktree todo/T076 実装時 2026-05-02 11:1X JST 実機確認、 全 7 ブロック PASS)
- [x] 詳細設計 § 13.8 横断確認 — pytest tests/alpha_factory/ = 2050 passed / 1 xfailed (regression 0); mypy src/ = Success no issues; ruff = 8 errors (all 既存 issue、 main HEAD でも同じ、 T076 は src/ tests/ touch なし、 別 TODO 申し送り)
- [x] commit message に「T076 (synthesis Round 22 確定) 完了 → Phase 2 切替 commit 前提成立」 旨を明記
- [x] PR タイトル `docs(T076): synthesis Round 22 改訂 (Phase 2 切替前提) — cascade port v2 Phase 2 配線完了後 SSOT 同期`
- [x] main fast-forward / no-ff merge (worktree → main、 = Phase C で実施)
