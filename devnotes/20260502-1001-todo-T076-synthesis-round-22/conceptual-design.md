# 概念設計: T076 — synthesis Round 22 改訂

**作成日時**: 2026-05-02 10:01 JST
**対象**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md` (Round 21 確定版)
**改訂範囲**: 冒頭 metadata + § 12.4 + § 16 + § 18.3 + § 21 + 末尾 anchor index (計 5 章 + index)
**性質**: docs-only (= 実装 touch なし、 synthesis SSOT を Phase 2 配線完了後の現実に同期)
**前提**: cascade port v2 Phase 2 配線 18/18 TODO 全完了 (handoff: `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md`)
**位置付け**: T076 完了 → Phase 2 切替コミット (旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消) の前提条件

---

## 背景・課題

### 現状

cascade port v2 Phase 1 設計 (18 件) → Phase 2 配線 (18 TODO + T064 follow-up = 25 PR) が全件 main fast-forward merge 済 (regression 0 件)。 現実装 (`src/alpha_factory/*` 直接実装) と synthesis Round 21 の文言の間に **5 箇所の乖離** が発生している。

### 5 箇所の乖離

| # | 章 | 現状の文言 | Phase 2 配線完了後の現実 |
|---|---|---|---|
| 1 | § 12.4 切替戦略 | 「開発中は新実装を `new_cascade` 名前空間で実装」 | `new_cascade` 名前空間は採用せず、 `src/alpha_factory/` 直接 18 module 追加で完了 |
| 2 | § 12.4 ロールバック条件 | 「smoke で FM1/FM4 が強く出る場合のみ」 | T075 で `FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]` enum 化済、 rollback 対象 FM 集合の決定責務は `select_rollback_relevant_failure_modes` (Phase 1 NotImplementedError、 Phase 2 別 TODO) |
| 3 | § 18.3 Smoke DoD | 8 bullet 混在 (1-7 が per-run、 8 が cross-run、 区別なし) | T075 で `PerRunSmokeDoDResult` (DoD1-DoD7) / `CrossRunSmokeDoDResult` (DoD8) に **二層分離** + `DoDIdPerRun` / `DoDIdCrossRun` Literal 型確定済 |
| 4 | § 16 Risk Top 5 | 各行に「緩和策」 を文章記述 (FM 紐付けなし、 数値 threshold 散在) | T075 で **threshold-free EvidenceClass 4 値** (`hard_fail` / `warning` / `inconclusive` / `ok`) を採用、 数値 threshold は別 TODO で smoke 後再校正と確定済 |
| 5 | 全文 anchor 体系 | section 番号 (= § 12.4) のみで参照、 章番号変更で hrefs 全壊リスク | Round 1-21 累積で章追加 / 番号 shift が複数発生済、 stable clause anchor + `synthesis_schema_version` metadata で SSOT 化が望ましい |

### なぜ今 (T076 タイミング) 改訂が必要か

Phase 2 配線 18 TODO は全て synthesis Round 21 を SSOT として実装したが、 Round 21 から派生実装 (= smoke.py 4 値、 二層分離、 enum 5 値) が確定したことで Round 21 自体が「実装の sub-set」 となり SSOT 倒立 (= 実装 > 設計) が発生している。

**Phase 2 切替コミット** (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消) を実施するには、 切替条件 (rollback 判定 / DoD 完走 / dual-path 検証) の **設計側の SSOT が現実装と整合していること** が必須。 T076 でその同期を確定し、 Phase 2 切替コミット (= 別 PR) の前提条件を満たす。

T075 module 自身が「FM1-FM5 / new_cascade 採用しない / DoD 機械検証形式 等は synthesis Round 22」 とコード内 docstring で明記しており (smoke.py L9, L100-101)、 設計同期が技術的負債として明示されている。

---

## 改善アイデア

5 改訂候補を 1 PR で確定 (Round 21 と同型の docs-only 改訂):

### 改訂 1: § 12.4 「new_cascade 名前空間」 廃止

**Before** (Round 21 現状):
```
- 開発中は新実装を `new_cascade` 名前空間で実装
- T918 smoke (1 Run E2E) + 5 Run 連続検証通過で切替
- 切替コミットで旧 stage / 旧 GA / 旧 sieve を**同日削除**
- dual-path 並走なし (分岐バグ温床)
```

**After** (Round 22):
```
- 新実装は `src/alpha_factory/` 配下に直接 module 追加で実装 (= `new_cascade` 名前空間は採用しない、 Phase 2 配線で確定)
- T918 (= T075) smoke (1 Run E2E) + 5 Run 連続検証通過で切替
- 切替コミットで旧 stage / 旧 GA / 旧 sieve を**同日削除** (= T075 `DeletionTarget` / `MigrationTarget` manifest に従う)
- dual-path 並走なし (分岐バグ温床、 T075 `DUAL_PATH_ENFORCE_TARGETS` で 4 経路強制)
```

理由: Phase 2 配線 18 TODO で `src/alpha_factory/` 直接実装が確定済 (= 実態と同期)。 T075 module の `DUAL_PATH_ENFORCE_TARGETS` (source / scripts / config / docs runbook 4 経路) と `DUAL_PATH_ENFORCE_ALLOWLIST` で並走防止が機械検証可能な形で実装されている。

### 改訂 2: § 12.4 ロールバック条件 → FM enum 化

**Before** (Round 21):
```
ロールバック条件: smoke で FM1/FM4 が強く出る場合のみ 1 サイクル延期、 旧実装は「実行不可の参照コード」 として一時凍結のみ (再有効化はしない)。
```

**After** (Round 22):
```
ロールバック条件: smoke で「rollback 対象 FM 集合」 (= synthesis Round 22 § 16 で確定する FM1-FM5 のサブセット) のいずれかが `hard_fail` evidence_class で観測された場合のみ 1 サイクル延期。
- 観測判定: T075 `SmokeOutcomeClassification.observed_failure_modes: frozenset[FailureModeKind]`
- rollback 対象判定: T075 `select_rollback_relevant_failure_modes(observed, policy)` (= Phase 2 別 TODO で実装、 policy = synthesis Round 22 § 16 で確定)
- 旧実装は「実行不可の参照コード」 として一時凍結のみ (再有効化はしない)。
```

理由: T075 で `FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]` enum 化済 + `select_rollback_relevant_failure_modes` API 予約済 (Phase 1 NotImplementedError raise)。 synthesis Round 22 で FM1-FM5 を § 16 と紐付けることで Phase 2 別 TODO の policy 設計が確定可能になる。

### 改訂 3: § 18.3 Smoke DoD → 二層分離形式

**Before** (Round 21、 8 bullet 混在):
```
- 1 Run 完走 (クラッシュ無し、 NaN/Inf fail-soft 動作)
- A-pass only B-eval をログで検証 (A-fail が B/親選択へ入らない)
- 主選抜が **B-pooled 指標のみ**で計算されている
- archive 書込の全レコードで `dataset_epoch_id` 必須 (欠落=fail)
- inflow / per_run_max / warmstart_share が設定通り
- CA/DA 配分が state ごとに一致 (pop=192 push 84/108、 pull 120/72)
- invariant fail-fast (session_close_drop, negative_equity_drop_open) が有効
- 連続 5 Run で epoch 汚染なし (prev_epoch 20% 制約順守)
```

**After** (Round 22、 二層分離):
```
T075 (Big-bang cleanup + smoke) module で機械検証する DoD は per-run / cross-run の二層に分離する:

#### Per-run DoD (= 1 Run ごとに評価、 `PerRunSmokeDoDResult.dod_results: tuple[SmokeDoDItem, ...]` 7 項目)

| dod_id | 内容 | T075 SSOT |
|---|---|---|
| DoD1 | 1 Run 完走 (クラッシュ無し、 NaN/Inf fail-soft 動作) | `SmokeOutcomeClassification.crashed=False` |
| DoD2 | A-pass only B-eval (A-fail が B/親選択へ入らない) | `SmokeObservabilityProjection.a_pass_only_b_eval` |
| DoD3 | 主選抜が B-pooled 指標のみで計算 | `SmokeObservabilityProjection.parent_selection_metric_class` |
| DoD4 | archive 書込全レコードで `dataset_epoch_id` 必須 | `SmokeObservabilityProjection.archive_epoch_id_completeness` |
| DoD5 | inflow / per_run_max / warmstart_share が設定通り | `SmokeObservabilityProjection.inflow_config_match` |
| DoD6 | CA/DA 配分が state ごとに一致 (push 84/108、 pull 120/72) | `SmokeObservabilityProjection.ca_da_split_match` |
| DoD7 | invariant fail-fast (session_close_drop, negative_equity_drop_open) 有効 | `SmokeObservabilityProjection.invariant_fail_fast_active` |

#### Cross-run DoD (= 5 Run 集約評価、 `CrossRunSmokeDoDResult.dod_results: tuple[SmokeDoDItem, ...]` 1 項目)

| dod_id | 内容 | T075 SSOT |
|---|---|---|
| DoD8 | 連続 5 Run で epoch 汚染なし (prev_epoch 20% 制約順守) | `CrossRunSmokeObservabilityProjection.cross_run_epoch_pollution_class` |

**SSOT 同期規範**: dod_id / scope / SSOT field は T075 module の `DoDIdPerRun` / `DoDIdCrossRun` Literal 型と完全一致。 synthesis 側の表記変更時は T075 module も同期改訂 (別 PR)。
```

理由: T075 module で **二層分離** (`PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult`) + scope/dod_id 整合 invariant が確定済。 synthesis 側を後追い同期する。

### 改訂 4: § 16 Risk Top 5 と FM1-FM5 紐付け

**Before** (Round 21、 5 行 × [順位 / リスク / 緩和]):
- 数値 threshold (q_force 上限 0.40 / prev_epoch 20% / archive=120 等) は文中混在
- FM1-FM5 への enum マッピングなし

**After** (Round 22、 5 行 × [順位 / FM ID / リスク / 緩和方針 / 数値確定 TODO]):
```
| 順位 | FM ID | リスク | 緩和方針 | 数値 threshold |
|---|---|---|---|---|
| 1 | FM1 | A-pass / B-pooled 乖離で探索誤誘導 | A→B 乖離メトリクス毎 Run 記録、 q_force 自動引き上げ、 戻し条件あり | smoke 後再校正 (別 TODO) |
| 2 | FM2 | epoch_id 伝搬漏れで cross-epoch 汚染 | schema lint で必須フィールド欠落 fail (fail-closed) | 本項は threshold-free (= 必須=0 件) |
| 3 | FM3 | 緊急時 warmstart 供給不足 | 35% 廃止、 25% 固定、 ramp 整合、 prev_epoch 20% 維持 | smoke 後再校正 (別 TODO) |
| 4 | FM4 | archive bypass 偏重で品質低下 | bypass = B 評価済 + 品質床 (invariant_feasible AND margin_inf p<=70) | smoke 後再校正 (別 TODO) |
| 5 | FM5 | DA 多様性形骸化 | DA eviction で novelty/coverage 主キー化、 entropy 週次監視 | smoke 後再校正 (別 TODO) |

**評価規範** (Round 22 確定):
- T075 は **threshold-free EvidenceClass 4 値** (`hard_fail` / `warning` / `inconclusive` / `ok`) で評価する。 数値 threshold は T075 module の SSOT に含めず、 smoke 後再校正で別 TODO により確定する。
- `EvidenceClassifierProtocol` で caller-supplied (= classifier 注入)、 unsupported metric_name は `inconclusive` 必須 (fail-closed)。
- 別 TODO 着手条件: smoke 5 Run 完走 + DoD8 全 PASS + 観測値分布が確認可能 (= calibration data 取得済)。
```

理由: T075 で threshold-free + fail-closed 規範が確定。 synthesis 側を後追い同期 + FM1-FM5 を § 16 と紐付け (= rollback policy の入力 enum 確定)。

### 改訂 5: stable clause anchor + synthesis_schema_version

**Before** (Round 21、 metadata 不在):
```
# Selection Cascade Port — fx 適用ロードマップ (最終確定版)

**最終更新**: 2026-04-29
**議論**: Codex gpt-5.4 / xhigh × 20 ラウンド (`round-1.md` 〜 `round-20.md`、 1-10 は前提誤りで `historical/` 隔離、 11-20 が確定議論)
**位置付け**: zenigame の selection cascade 思想 (T508/T509/T511/T513) を zenigame-fx に big-bang 導入する**設計上位文書**。 Codex Round 20 で全構成合意確定済み (異論なし)。
**ベースライン**: 本設計をベースラインとする。 ...
```

**After** (Round 22、 metadata block 追加):
```
# Selection Cascade Port — fx 適用ロードマップ (最終確定版)

<!-- ============================================================
  synthesis_schema_version: 22
  last_revised: 2026-05-02
  revision_lineage:
    - round-21 (2026-04-30): mission_signed_margin SSOT 昇格 / mission_margin BACKWARD COMPAT 化
    - round-22 (2026-05-02): new_cascade 廃止 / FM enum 化 / DoD 二層分離 / threshold-free 規範 / stable clause anchor 体系
  retroactive_anchor_grant: round-1 〜 round-21 (= clause anchor は Round 22 から導入、 旧 round md 自体は不変保持、 anchor index は本ファイル末尾 § 22 で SSOT 提供)
  ============================================================ -->

**最終更新**: 2026-05-02
**議論**: Codex gpt-5.4 / xhigh × 21 ラウンド (`round-1.md` 〜 `round-20.md` + Round 21 改訂 PR + Round 22 改訂 PR、 1-10 は前提誤りで `historical/` 隔離、 11-20 が確定議論、 21-22 は派生実装後の SSOT 同期改訂)
**位置付け**: zenigame の selection cascade 思想 (T508/T509/T511/T513) を zenigame-fx に big-bang 導入する**設計上位文書**。 cascade port v2 Phase 2 配線 18/18 TODO 全完了 (`commit 09bd56d`) に伴う Round 22 同期改訂で実装と SSOT 整合済み。
...
```

加えて、 各章冒頭に **stable clause anchor** (HTML コメント形式) を埋め込む:
- 例: § 12.4 → `<!-- @clause-anchor: switching-strategy -->`
- 例: § 16 → `<!-- @clause-anchor: risk-top-5 -->`
- 例: § 18.3 → `<!-- @clause-anchor: smoke-dod -->`

末尾に新章 **§ 22 Clause Anchor Index** を追加し、 anchor → 章番号のマッピング表を提供。 旧 round md (round-1.md 〜 round-20.md + historical/) は **不変保持** とし、 retroactive 付与は anchor index を SSOT として参照する形で実現。

理由: 章番号 shift で hrefs / cross-ref が壊れる問題を anchor で SSOT 化。 旧 round md を改変しないため history 不変性も保持。

---

## 期待効果

### 直接効果

1. **synthesis SSOT と実装の整合復元**: T075 module 内の「synthesis Round 22 で確定」 docstring 参照が有効化される
2. **Phase 2 切替コミットの前提条件成立**: rollback 判定 (FM enum) / DoD 完走 (二層分離) / dual-path 検証 (anchor) の設計側 SSOT が現実装と完全整合
3. **Phase 2 別 TODO `select_rollback_relevant_failure_modes` 実装の前提成立**: § 16 で確定した FM1-FM5 が policy 入力 enum として使用可能になる
4. **threshold-free 規範の SSOT 移行**: 数値 threshold は T076 完了後の Phase 3 別 TODO (smoke 後再校正) で確定する旨が synthesis 自体に明記される

### 副次効果

5. **stable clause anchor 体系**: 今後 Round 23 以降で章追加 / 番号 shift が起きても、 cross-ref が壊れない持続可能な構造を確立
6. **revision_lineage metadata**: 各改訂の rationale / scope を冒頭で機械可読に提供 (= Round 23 以降で同型改訂を継続可能)

### live_criteria への寄与経路

T076 自体は docs-only で live_criteria 達成に直接寄与しない。 ただし **Phase 2 切替コミット** (= LOG_ONLY → FAIL_CLOSED 切替) の前提条件であり、 切替後は selection cascade v2 が fail-closed で運用され、 cross-epoch 汚染 / dual-path 並走 / archive bypass 偏重等の bug class が **構造的に排除** される。 これは long-tail bug 根絶 → Stage A/B/C 評価の信頼性向上 → live_criteria 達成個体探索の SN 比改善に間接寄与する。

---

## 実装方針 (概要)

### 変更ファイル (1 file 直接編集 + 1 file 新規)

1. **直接編集**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md`
   - 冒頭 metadata block 追加 (改訂 5)
   - § 12.4 改訂 (改訂 1 + 2)
   - § 16 改訂 (改訂 4)
   - § 18.3 改訂 (改訂 3)
   - § 21 末尾に Round 22 行追加
   - 末尾 § 22 Clause Anchor Index 新設 (改訂 5)
   - 各章冒頭に stable clause anchor HTML コメント埋め込み (改訂 5)

2. **新規追加**: `devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md`
   - Round 21 同型の rationale.md 形式 (改訂理由 / 改訂方針 / 改訂内容詳細 / 影響範囲 / 検証手順)

### 機械検証手順 (= 改訂 PR 完了の必要条件、 Codex Round 2 [Critical] 反映で 2 段化)

各改訂候補について **synthesis 側 (= 文書改訂が機械検証可能な形で完了)** と **smoke.py 側 (= 詳細設計 SSOT が現実装と整合)** の 2 系統で検証。 PR コミット前の同期検証:

#### 改訂 1: § 12.4 new_cascade 廃止 + dual-path 規範

- **synthesis 側**: `! grep -nE "new_cascade" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= 旧文言不在) + `grep -nE "src/alpha_factory/.*直接|DUAL_PATH_ENFORCE_TARGETS" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= 新文言存在)
- **smoke.py 側**: `grep -nE "DUAL_PATH_ENFORCE_TARGETS|DUAL_PATH_ENFORCE_ALLOWLIST" src/alpha_factory/smoke.py` の 4 経路 dict + 5 patterns allowlist が現状維持

#### 改訂 2: § 12.4 ロールバック条件 → FM enum

- **synthesis 側**: `grep -nE "FM1-FM5|FailureModeKind|select_rollback_relevant_failure_modes" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= FM enum 5 値 + API 名記載) + `! grep -nE "FM1/FM4 が強く出る" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= 旧文言不在)
- **smoke.py 側**: `grep -nE "FailureModeKind|select_rollback_relevant_failure_modes" src/alpha_factory/smoke.py` の Literal 5 値 + API NotImplementedError 予約が現状維持

#### 改訂 3: § 18.3 Smoke DoD 二層分離

- **synthesis 側**: `grep -nE "DoD1-DoD7|DoD8|PerRunSmokeDoDResult|CrossRunSmokeDoDResult|per-run|cross-run" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= 二層分離 + dod_id 完全網羅 + per/cross-run 区分が文書化)
- **smoke.py 側**: `grep -nE "DoDIdPerRun|DoDIdCrossRun|PerRunSmokeDoDResult|CrossRunSmokeDoDResult" src/alpha_factory/smoke.py` の Literal + dataclass invariant が現状維持

#### 改訂 4: § 16 Risk Top 5 + FM 紐付け + threshold-free 規範

- **synthesis 側**: `grep -nE "FM ID|threshold-free|EvidenceClass|smoke 後再校正" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= FM 紐付け + threshold-free 規範 + 数値確定別 TODO の文言が記載)
- **smoke.py 側**: `grep -nE "EvidenceClass|EvidenceClassifierProtocol" src/alpha_factory/smoke.py` の 4 値 Literal + protocol が現状維持

#### 改訂 5: 冒頭 metadata + anchor index

- **synthesis 側**: `grep -nE "synthesis_schema_version: 22|@clause-anchor|revision_lineage|§ 22" devnotes/20260428-2300-cascade-port-debate/synthesis.md` (= metadata block + 5 anchor + § 22 index が追加)
- **smoke.py 側**: 該当なし (= anchor 体系は synthesis.md 内部 SSOT、 smoke.py に対応物を持たない)

#### 横断確認

- T075 docstring 内「synthesis Round 22」 参照箇所 (smoke.py L9 / L100-101) が Round 22 改訂後の synthesis を実際に参照可能 (= 章番号 / 内容整合)
- **dual-path enforce mode の正確な書き分け** (= Codex Round 2 [Critical] 反映): `source_import` / `scripts` / `config_yaml` の 3 経路は `parser_failure_mode="fail_closed"` + `severity="fail"`、 `docs_runbook` の 1 経路は `parser_failure_mode="fail_open"` + `severity="warning"`。 「4 経路すべて fail_closed」 という記述は誤り、 synthesis § 12.4 改訂時にこの違いを保持して記述する

### 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **standalone** (docs-only、 1 file + 1 file 新規、 既存 PR 並走なし、 Round 21 と同型) |
| 判断根拠 | (a) 実装 touch なし → ruff/mypy/pytest 影響なし、 (b) Round 21 で同型 PR 実績あり、 (c) Phase 2 切替コミットの前提条件 = 単独で完結する単位、 (d) 5 改訂候補は **同一 synthesis SSOT の atomic consistency boundary** として同時改訂が妥当 (= 改訂 #1-4 は T075 smoke SSOT 同期、 改訂 #5 は synthesis 内部 anchor SSOT で性質は異なるが、 同一 file への atomic な PR で扱うのが consistency boundary として最適、 Codex Round 2 [Warning] A 反映) |
| 競合リスク | なし (synthesis.md は Round 21 完了以降 touch なし、 main HEAD と乖離 0) |
| 想定実装時間 | 短〜中 (= 文書 diff のみ、 検証は grep 5 件、 テスト不要) |

---

## 制約・前提

### 既存アーキテクチャとの整合

- 位置付け (= Codex Round 2 [Warning] D 反映): T075 で確定した **詳細設計 SSOT** (= `FailureModeKind` / `EvidenceClass` / `DoDIdPerRun` / `DoDIdCrossRun` Literal 型 + `PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult` 二層分離 invariant + `DUAL_PATH_ENFORCE_TARGETS` 4 経路 + `DUAL_PATH_ENFORCE_ALLOWLIST`) を **上位設計 (synthesis)** に反映する cycle 最終段。 「実装が設計を上書きした」 のではなく、 **「T075 詳細設計 → 実装 → 上位設計 SSOT 復元」 の健全な 3 段 cycle** (= Round 21 と同型)
- `select_rollback_relevant_failure_modes` API は Phase 1 NotImplementedError 維持、 Phase 2 別 TODO で実装。 T076 は **API 仕様の前提条件** を確定するのみ
- 数値 threshold は T076 では確定しない (= smoke 後再校正の別 TODO で確定)
- **inconclusive blocking semantics** (= Codex Round 2 [Critical] 反映): `EvidenceClass` 4 値のうち `inconclusive` は smoke pass として扱わず、 Phase 2 切替を **ブロックする** (= fail-closed)。 EvidenceClassifierProtocol で unsupported metric_name は inconclusive 必須、 切替 commit (= 別 PR) の前提条件として「全 metric が `ok` または `warning`」 (= `inconclusive` も `hard_fail` も含まない) であること

### Round 21 との関係

- Round 21 改訂 (= mission_signed_margin SSOT 昇格) は Round 22 で touch せず保持
- Round 22 metadata block の `revision_lineage` に Round 21 を記載 (= 改訂系譜の機械可読化)

### 旧 round md (1-21) の取扱

- round-1.md 〜 round-20.md + Round 21 rationale は **不変保持** (history 改変禁止)
- retroactive clause anchor 付与は **不可** (= 旧 md を後付け書換しない)
- 代わりに synthesis 末尾 § 22 Clause Anchor Index を SSOT として提供し、 旧 round md からの参照は anchor index を経由

### コーディングルール (docs-only PR でも適用)

- 文書のテスト = `grep` 5 件の機械検証手順 (上記)
- ruff / mypy / pytest は通過すること (= 実装 touch なしで自動 PASS、 ただし PR 確認として実行する)

---

## スコープ外 (T076 で扱わないこと、 後続別 TODO)

1. **数値 threshold 確定** (= FM1-FM5 の各 hard_fail 判定境界、 q_force 0.40 上限再校正、 archive=120 再校正等): smoke 後再校正の別 TODO
2. **`select_rollback_relevant_failure_modes` 本実装**: synthesis Round 22 § 16 確定後の Phase 2 別 TODO
3. **Phase 2 切替コミット** (旧実装削除 + LOG_ONLY → FAIL_CLOSED 切替 + dual-path 並走解消 big-bang 1-shot): T076 完了後の別 PR、 別 TODO ではなく単独 commit (= 設計記述変更なし、 実装削除のみ)
4. **旧 round md (1-21) への遡及書換**: history 不変保持、 anchor index 経由参照のみ
5. **stable clause anchor 全章付与の自動化**: T076 では手動付与、 自動付与 lint は別 TODO
6. **synthesis_schema_version の自動 bump 機構**: T076 では手動記述、 自動 bump は別 TODO
7. **T070 follow-up / T071 caller 注入式 Phase 2 配線 / T058 detailed-design 改訂依頼 / T064 follow-up 申し送り** 等の handoff § 6 残作業 (3-10): T076 と独立した別 TODO

---

## リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| synthesis 章番号 shift で他 docs (docs/alpha_factory/* / handoff* / detailed-design.md 等) の cross-ref が破損 | 中 (= 文書整合性) | T076 では §-番号自体は変更せず内容差替のみ + § 22 anchor index で stable 化、 既存参照は不変 |
| T075 module docstring の「synthesis Round 22」 参照が Round 22 完了前後で文言ズレ発生 | 低 | smoke.py 側の docstring は Round 22 完了時に touch 不要 (= 「synthesis Round 22」 の記述自体は両方で valid) |
| Round 22 改訂 PR と Phase 2 切替コミット PR の順序逆転 | 中 (= 切替条件不整合) | T076 完了 = synthesis Round 22 確定 → 切替コミット PR の前提成立、 PR タイトル / commit message で順序明示 |
| 5 改訂候補のうち 1 つでも Codex から CHANGES_REQUESTED が出ると 5 件全部が再合議 | 低 | 5 候補は同一 synthesis SSOT の atomic consistency boundary として同時改訂が妥当、 Round 21 同型で Codex 実績あり |
| anchor index 体系を導入しても旧 round md の section 番号参照は残存 | 低 | 旧 round md は historical 性質、 anchor index は新規参照用、 旧参照は不変保持で問題なし |

---

## 参考資料

- handoff: `devnotes/20260502-0710-cascade-port-v2-phase2-complete-handoff/handoff.md` § 4.1 / § 6
- Round 21 改訂 rationale (前例): `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/rationale.md`
- T075 詳細設計 (smoke.py): `devnotes/20260501-0136-todo-T075-bigbang-cleanup-smoke/detailed-design.md`
- T075 実装: `src/alpha_factory/smoke.py` (= 1176 LOC、 commit `09bd56d`)
- 現 synthesis: `devnotes/20260428-2300-cascade-port-debate/synthesis.md` (Round 21 確定)
