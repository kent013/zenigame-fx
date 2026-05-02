# 詳細設計: T076 — synthesis Round 22 改訂

**作成日時**: 2026-05-02 10:35 JST
**性質**: docs-only PR (= 実装 touch なし、 synthesis Round 21 → Round 22 SSOT 同期改訂)
**前提**: 概念設計 APPROVED (Codex gpt-5.4 / medium、 Round 3、 残存 [Critical] / [Warning] なし、 [Suggestion] 3 件は本詳細設計で取込済)
**改訂対象**: `devnotes/20260428-2300-cascade-port-debate/synthesis.md` (1 file 直接編集) + `devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md` (1 file 新規)

---

## 1. 使命・制約 (絶対遵守)

### 1.1 zenigame-fx Alpha Factory 使命

live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 1.2 禁止事項

1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提
8. archive スキーマ伝搬漏れ

### 1.3 T076 該当性 (= 概念設計 § A-2 の再掲)

T076 は docs-only PR で、 上記禁止事項 1-8 のいずれにも該当しない (= synthesis Round 21 → Round 22 SSOT 同期改訂、 評価期間 / 数値見せかけ / GA / criteria / 取引回数 / オーバーナイト / archive スキーマには触れない)。

### 1.4 コーディングルール (docs-only PR 適用形)

- **テストファースト不要** (= バグ修正ではなく文書改訂、 ただし機械検証手順 grep を test 等価として PR コミット前に実行)
- **テスト命名 / 配置**: 該当なし (= test 不在)
- **uv 必須**: docs 検証では grep のみ、 ただし `uv run pytest tests/alpha_factory/ -x` を smoke として実行し regression 0 確認
- **ruff / mypy 通過**: 実装 touch なしで自動 PASS、 確認のみ
- Python 3.13 + numpy + pandas: 該当なし (= docs)

---

## 2. 概念設計リファレンス

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1001-todo-T076-synthesis-round-22/conceptual-design.md` (Round 3 APPROVED 後の最新版)

主要内容:
- 5 改訂候補 (改訂 1-5) の Before / After
- 期待効果 (= live_criteria 因果列 4 段の rung 2 担当)
- 機械検証手順 (= 2 段化、 synthesis 側 + smoke.py 側 1:1)
- 制約・前提 (= T075 詳細設計 → 実装 → 上位設計 SSOT 復元 cycle、 inconclusive blocking semantics)
- スコープ外 (= 数値 threshold / select_rollback_relevant_failure_modes 本実装 / Phase 2 切替 commit / 残り 17 章 anchor / 自動 lint)

---

## 3. 改訂対象一覧表

| # | 改訂名 | synthesis.md 該当 line | 性質 | 優先度 |
|---|---|---|---|---|
| 1 | § 12.4 「new_cascade 名前空間」 廃止 + dual-path 規範 | L516-521 (= 4 bullet + 空行) | 文言置換 | 高 |
| 2 | § 12.4 ロールバック条件 → FM1-FM5 enum + API 名記載 | L523 (= 1 段落) | 文言置換 + 拡張 | 高 |
| 3 | § 18.3 Smoke DoD → per-run / cross-run 二層分離形式 | L662-674 (= 8 bullet) | 全置換 (= 表形式 2 段) | 高 |
| 4 | § 16 Risk Top 5 + FM ID 紐付け + threshold-free 規範 | L587-597 (= 表 5 行) | 表拡張 + 評価規範追記 | 高 |
| 5a | 冒頭 metadata block (synthesis_schema_version: 22 等) | L1-7 直後 (= 新規 HTML コメント block 挿入) | 新規追加 | 中 |
| 5b | 各章冒頭の stable clause anchor (5 章 = § 12.4 / § 16 / § 18.3 / § 21 / § 22) | 各章ヘッダ直後 (= 5 箇所 HTML コメント挿入) | 新規追加 | 中 |
| 5c | 末尾 § 22 Clause Anchor Index 新章 | L714 直後 (= 新章追加) | 新規追加 | 中 |
| ε | § 21 議論履歴サマリー末尾に Round 22 行追加 | L713 直後 | 1 行追加 | 中 |
| ε | rationale.md 新規追加 | `devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md` | 新規 file | 中 |

合計: synthesis.md 内 5 + 5b 5 箇所 (anchor) + 5c 1 章 + ε 1 行 = **8 箇所編集** + **1 file 新規** (rationale.md) + **1 file 改訂** (synthesis.md)

---

## 4. 改訂 1: § 12.4 切替戦略 (= new_cascade 廃止 + dual-path 規範)

### 4.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L516-521

### 4.2 波及変更

- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし (= synthesis 内部 SSOT のみ)
- `src/alpha_factory/smoke.py`: 該当 docstring (L9 / L100-101) は「synthesis Round 22」 を既に参照しており touch 不要

### 4.3 現行 (Round 21、 L516-521)

```markdown
### 12.4 切替戦略

- 開発中は新実装を `new_cascade` 名前空間で実装
- T918 smoke (1 Run E2E) + 5 Run 連続検証通過で切替
- 切替コミットで旧 stage / 旧 GA / 旧 sieve を**同日削除**
- dual-path 並走なし (分岐バグ温床)
```

### 4.4 改訂後 (Round 22、 L516-521 を以下で置換)

```markdown
### 12.4 切替戦略

<!-- @clause-anchor: switching-strategy -->

- 新実装は `src/alpha_factory/` 配下に直接 module 追加で実装 (= `new_cascade` 名前空間は採用しない、 Phase 2 配線で確定)
- T918 (= 実装上の identifier は T075) smoke (1 Run E2E) + 5 Run 連続検証通過で切替
- 切替コミットで旧 stage / 旧 GA / 旧 sieve を**同日削除** (= T075 `DeletionTarget` / `MigrationTarget` manifest に従う)
- dual-path 並走なし (分岐バグ温床、 T075 `DUAL_PATH_ENFORCE_TARGETS` 4 経路で機械検証)
  - `source_import` (`src/**/*.py`) / `scripts` (`scripts/**/*.py`) / `config_yaml` (`config/**/*.yaml` + `config/**/*.yml`、 2 globs) の 3 経路は `parser_failure_mode="fail_closed"` + `severity="fail"`
  - `docs_runbook` (`docs/runbook/**/*.md`) の 1 経路は `parser_failure_mode="fail_open"` + `severity="warning"` (= markdown 自然言語のため parse 失敗 warn のみ)
  - `DUAL_PATH_ENFORCE_ALLOWLIST` 5 patterns (`docs/historical/**`, `devnotes/**`, `tests/**`, `.git/**`, `**/__pycache__/**`) は対象外
```

---

## 5. 改訂 2: § 12.4 ロールバック条件 → FM enum

### 5.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L523 (= 改訂 1 の続きの段落)

### 5.2 現行 (Round 21、 L523)

```markdown
ロールバック条件: smoke で FM1/FM4 が強く出る場合のみ 1 サイクル延期、 旧実装は「実行不可の参照コード」 として一時凍結のみ (再有効化はしない)。
```

### 5.3 改訂後 (Round 22、 L523 を以下で置換)

```markdown
ロールバック条件: smoke で「rollback 対象 FM 集合」 (= 本 synthesis § 16 で確定する FM1-FM5 のサブセット) のいずれかが `hard_fail` evidence_class で観測された場合のみ 1 サイクル延期 (旧実装は「実行不可の参照コード」 として一時凍結のみ、 再有効化はしない)。

- **観測判定**: `T075 SmokeOutcomeClassification.observed_failure_modes: frozenset[FailureModeKind]`
- **rollback 対象判定**: `T075 select_rollback_relevant_failure_modes(observed, policy) -> frozenset[FailureModeKind]` (= Phase 2 別 TODO で実装、 policy = 本 synthesis § 16 Risk Top 5 の FM 別 hard_fail 判定境界、 数値 threshold は smoke 後再校正の別 TODO で確定)
- **inconclusive blocking** (= fail-closed): `EvidenceClass` 4 値のうち `inconclusive` は smoke pass として扱わず、 Phase 2 切替を **ブロックする**。 切替 commit (= 別 PR) の前提条件は「全 metric および全 DoD item が `ok` または `warning`」 (= `inconclusive` も `hard_fail` も含まない)。 `EvidenceClassifierProtocol` で unsupported metric_name は inconclusive 必須。
```

---

## 6. 改訂 3: § 18.3 Smoke DoD → 二層分離形式

### 6.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L662-674 (= 8 bullet + 区切り)

### 6.2 現行 (Round 21、 L662-674)

```markdown
### 18.3 T918 Smoke DoD (Codex Round 20 確定)

以下を全て満たすと smoke 完了:

- 1 Run 完走 (クラッシュ無し、 NaN/Inf fail-soft 動作)
- A-pass only B-eval をログで検証 (A-fail が B/親選択へ入らない)
- 主選抜が **B-pooled 指標のみ**で計算されている
- archive 書込の全レコードで `dataset_epoch_id` 必須 (欠落=fail)
- inflow / per_run_max / warmstart_share が設定通り
- CA/DA 配分が state ごとに一致 (pop=192 push 84/108、 pull 120/72)
- invariant fail-fast (session_close_drop, negative_equity_drop_open) が有効
- 連続 5 Run で epoch 汚染なし (prev_epoch 20% 制約順守)
```

### 6.3 改訂後 (Round 22、 L662-674 を以下で置換)

```markdown
### 18.3 T918 (T075) Smoke DoD (Round 22 二層分離形式、 T075 `PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult` SSOT 同期)

<!-- @clause-anchor: smoke-dod -->

T075 `src/alpha_factory/smoke.py` で機械検証する DoD は **per-run** (1 Run ごと、 7 項目) と **cross-run** (5 Run 集約、 1 項目) の二層に分離する。 Round 21 までの 8 bullet 混在表記は本 Round 22 で形式置換 (内容同等、 SSOT 同期目的)。

#### Per-run DoD (= `PerRunSmokeDoDResult.items: tuple[SmokeDoDItem, ...]` 7 項目、 `DoDIdPerRun = Literal["DoD1"-"DoD7"]`)

DoD 判定の主 SSOT は **`SmokeDoDItem.status: EvidenceClass`** (全 DoD 共通)。 caller (= smoke runner) が `SmokeObservabilityProjection` の各 field と `EvidenceClassifierProtocol` を組み合わせて `SmokeDoDItem.status` を導出する。 表中の「関連 projection field」 列は補助情報 (= `SmokeObservabilityProjection` の実 field 名、 caller が DoD 判定時に参照する元値、 Round 2 [Critical] 1 反映で実 field 名を明記)。

| dod_id | 内容 | 主 SSOT | 関連 projection field (= caller 経由で参照) |
|---|---|---|---|
| DoD1 | 1 Run 完走 (クラッシュ無し、 NaN/Inf fail-soft 動作) | `SmokeDoDItem.status` | `SmokeOutcomeClassification.crashed` (`False` 期待) + caller 判定 |
| DoD2 | A-pass only B-eval (A-fail が B/親選択へ入らない) | `SmokeDoDItem.status` | `SmokeObservabilityProjection.ab_divergence_class` 等を caller が参照 (= FM1 系) |
| DoD3 | 主選抜が B-pooled 指標のみで計算 | `SmokeDoDItem.status` | `SmokeObservabilityProjection.ab_divergence_class` 関連 (= FM1 系、 caller が parent selection の metric class を確認) |
| DoD4 | archive 書込全レコードで `dataset_epoch_id` 必須 (欠落 = fail) | `SmokeDoDItem.status` | `SmokeObservabilityProjection.dataset_epoch_id_present` + `epoch_consistency_class` (= FM2 系) |
| DoD5 | inflow / per_run_max / warmstart_share が設定通り | `SmokeDoDItem.status` | `SmokeObservabilityProjection.warmstart_shortfall_class` (= FM3 系) |
| DoD6 | CA/DA 配分が state ごとに一致 (pop=192 push 84/108、 pull 120/72) | `SmokeDoDItem.status` | `SmokeObservabilityProjection.bypass_ratio_class` (= FM4 系、 caller が CA/DA 配分一致を確認) |
| DoD7 | invariant fail-fast (session_close_drop, negative_equity_drop_open) 有効 | `SmokeDoDItem.status` | `SmokeObservabilityProjection.session_entropy_class` 等 (= FM5 系) + caller の invariant 確認 |

`PerRunSmokeDoDResult` invariant: `len(items) == PER_RUN_DOD_ITEMS_COUNT(=7)`、 全 item が `scope == "per_run"`、 dod_id は DoD1-DoD7 完全網羅、 `overall_evidence_class` は items.status の max 集約 (順序: hard_fail > warning > inconclusive > ok)。

#### Cross-run DoD (= `CrossRunSmokeDoDResult.item: SmokeDoDItem` 1 項目、 `DoDIdCrossRun = Literal["DoD8"]`)

| dod_id | 内容 | 主 SSOT | 関連 projection field |
|---|---|---|---|
| DoD8 | 連続 5 Run で epoch 汚染なし (prev_epoch 20% 制約順守) | `CrossRunSmokeDoDResult.item.status` | `CrossRunSmokeObservabilityProjection.cross_run_epoch_pollution_class` (5 Run 集約後の EvidenceClass) |

`CrossRunSmokeDoDResult` invariant: `item.scope == "cross_run"` + `item.dod_id == "DoD8"`。 5 Run 集約は `SMOKE_RUNS_REQUIRED(=5)` 固定。

#### 完走判定 (= smoke 完了条件、 item-level 評価、 Round 2 [Warning] G 反映)

- **item-level fail-closed**: 全 8 DoD item (= per-run 7 + cross-run 1) の各 `SmokeDoDItem.status` が **`ok` または `warning`** であること (= `inconclusive` も `hard_fail` も含まない、 個別 item レベルで fail-closed)。 `overall_evidence_class` の集約値ではなく **item-level** で判定する (= 集約順序 `hard_fail > warning > inconclusive > ok` で warning と inconclusive 混在時に overall=warning となり inconclusive を見落とす false PASS を防ぐ)
- **per-run補助条件**: `PerRunSmokeDoDResult.overall_evidence_class` は再集約 invariant (= `__post_init__` で items.status max と一致) のため、 全 item が ok or warning なら overall も ok or warning となる (= 補助条件として整合性確認に使用、 主判定ではない)
- **cross-run単一item**: `CrossRunSmokeDoDResult.item.status` (= DoD8 単独) が ok or warning であること
- すなわち: 切替 commit (= Phase 2 別 PR) の前提条件は「全 8 DoD item の status が ok または warning」 (= item-level 必須条件)
- `inconclusive` 観測時は別 TODO で classifier / threshold を確定するまで切替不可 (= EvidenceClassifierProtocol の unsupported metric_name は inconclusive 必須、 fail-closed)

#### SSOT 同期規範

`dod_id` / `scope` / SSOT field 名は T075 module の `DoDIdPerRun` / `DoDIdCrossRun` Literal 型および `PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult` invariant と完全一致。 synthesis 側の表記変更時は T075 module も同期改訂 (別 PR) すること。
```

---

## 7. 改訂 4: § 16 Risk Top 5 + FM 紐付け + threshold-free 規範

### 7.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L587-597 (= 表 5 行 + ヘッダ + 区切り)

### 7.2 現行 (Round 21、 L587-597)

```markdown
## 16. Risk Top 5 と緩和策

| 順位 | リスク | 緩和 |
|---|---|---|
| 1 | A-pass / B-pooled 乖離で探索誤誘導 | A→B 乖離メトリクス毎 Run 記録、 q_force 自動引き上げ (上限 0.40)、 戻し条件あり |
| 2 | epoch_id 伝搬漏れで cross-epoch 汚染 | schema lint で必須フィールド欠落 fail (fail-closed) |
| 3 | 緊急時 warmstart 供給不足 | 35% 廃止、 25% 固定、 ramp 整合、 prev_epoch 20% 維持 |
| 4 | archive bypass 偏重で品質低下 | bypass = B 評価済 + 品質床 (invariant_feasible AND margin_inf p<=70) |
| 5 | DA 多様性形骸化 | DA eviction で novelty/coverage 主キー化、 entropy 週次監視 |

---
```

### 7.3 改訂後 (Round 22、 L587-597 を以下で置換)

```markdown
## 16. Risk Top 5 と緩和策

<!-- @clause-anchor: risk-top-5 -->

| 順位 | FM ID | リスク | 緩和方針 | 数値 threshold (= hard_fail 判定境界) |
|---|---|---|---|---|
| 1 | FM1 | A-pass / B-pooled 乖離で探索誤誘導 | A→B 乖離メトリクス毎 Run 記録、 q_force 自動引き上げ (仮値 0.40)、 戻し条件あり | smoke 後再校正 (別 TODO) |
| 2 | FM2 | epoch_id 伝搬漏れで cross-epoch 汚染 | schema lint で必須フィールド欠落 fail (fail-closed) | threshold-free (= 必須=0 件、 lint で機械検証) |
| 3 | FM3 | 緊急時 warmstart 供給不足 | 35% 廃止、 25% 固定、 ramp 整合、 prev_epoch 20% 維持 | smoke 後再校正 (別 TODO) |
| 4 | FM4 | archive bypass 偏重で品質低下 | bypass = B 評価済 + 品質床 (invariant_feasible AND margin_inf p<=70) | smoke 後再校正 (別 TODO) |
| 5 | FM5 | DA 多様性形骸化 | DA eviction で novelty/coverage 主キー化、 entropy 週次監視 | smoke 後再校正 (別 TODO) |

### 16.1 評価規範 (Round 22 確定、 T075 SSOT 同期)

- **threshold-free 4 値 EvidenceClass 採用**: T075 `EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]` で評価する。 数値 threshold は T075 module の SSOT に **含めず**、 smoke 後再校正で別 TODO により確定する (= 概念設計 Round 3 [Suggestion] 1 反映、 calibration data 必要)。
- **classifier 注入規範**: `EvidenceClassifierProtocol` で caller-supplied (= classifier は smoke caller が提供)、 `supported_metric_names` 不在 metric_name は **`inconclusive` 必須** (= fail-closed、 unsupported を黙って ok にしない)。
- **FM 紐付け**: 上記表の FM ID 5 値は T075 `FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]` enum と完全一致。 `select_rollback_relevant_failure_modes(observed, policy)` の policy 入力は本 § 16 表で確定 (= Phase 2 別 TODO で本実装)。
- **別 TODO 着手条件**: smoke 5 Run 完走 + DoD8 全 PASS + 観測値分布が確認可能 (= calibration data 取得済)、 かつ T076 (本 PR) 完了で synthesis Round 22 SSOT が確定済であること。

---
```

---

## 8. 改訂 5a: 冒頭 metadata block (synthesis_schema_version: 22)

### 8.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L1 (`# Selection Cascade Port — fx 適用ロードマップ (最終確定版)`) の **直後** に HTML コメント block 挿入。

### 8.2 現行 (Round 21、 L1-8)

```markdown
# Selection Cascade Port — fx 適用ロードマップ (最終確定版)

**最終更新**: 2026-04-29
**議論**: Codex gpt-5.4 / xhigh × 20 ラウンド (`round-1.md` 〜 `round-20.md`、 1-10 は前提誤りで `historical/` 隔離、 11-20 が確定議論)
**位置付け**: zenigame の selection cascade 思想 (T508/T509/T511/T513) を zenigame-fx に big-bang 導入する**設計上位文書**。 Codex Round 20 で全構成合意確定済み (異論なし)。
**ベースライン**: 本設計をベースラインとする。 既存 zenigame-fx 実装 (絶対閾値 AND 直列フィルタ + post-RUN MD-only sieve + pop=40 / gen=15 / max_workers=2) はベースラインにせず、 全削除・big-bang 置換。

---
```

### 8.3 改訂後 (Round 22、 L2 直後に metadata block 挿入 + 既存 metadata 行を Round 22 反映に更新)

```markdown
# Selection Cascade Port — fx 適用ロードマップ (最終確定版)

<!-- ============================================================
  synthesis_schema_version: 22
  last_revised: 2026-05-02
  revision_lineage:
    - round-21 (2026-04-30): mission_signed_margin SSOT 昇格 / mission_margin BACKWARD COMPAT 化
      rationale: devnotes/20260430-1045-synthesis-revise-mission-signed-margin/rationale.md
    - round-22 (2026-05-02): new_cascade 廃止 / FM enum 化 / DoD 二層分離 / threshold-free 規範 / stable clause anchor 体系
      rationale: devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md
  retroactive_anchor_grant: round-1 〜 round-21 (= clause anchor は Round 22 から導入、 旧 round md 自体は不変保持、 anchor index は本 file § 22 で SSOT 提供)
  scope: 5 改訂対象章 (= § 12.4 / § 16 / § 18.3 / § 21 / § 22) のみ anchor 付与、 残り 17 章 anchor / 自動 lint は後続別 TODO
============================================================ -->

**最終更新**: 2026-05-02
**議論**: Codex gpt-5.4 / xhigh × 20 ラウンド (`round-1.md` 〜 `round-20.md`、 1-10 は前提誤りで `historical/` 隔離、 11-20 が確定議論) + Round 21 改訂 PR (mission_signed_margin) + Round 22 改訂 PR (Phase 2 配線完了後 SSOT 同期)
**位置付け**: zenigame の selection cascade 思想 (T508/T509/T511/T513) を zenigame-fx に big-bang 導入する**設計上位文書**。 cascade port v2 Phase 2 配線 18/18 TODO 全完了 (`commit 09bd56d`) に伴う Round 22 同期改訂で実装 (= T058-T075 module 群 in `src/alpha_factory/`) と SSOT 整合済。
**ベースライン**: 本設計をベースラインとする。 既存 zenigame-fx 実装 (絶対閾値 AND 直列フィルタ + post-RUN MD-only sieve + pop=40 / gen=15 / max_workers=2) はベースラインにせず、 全削除・big-bang 置換。

---
```

---

## 9. 改訂 5b: 各章冒頭の stable clause anchor (5 章)

### 9.1 変更箇所と挿入内容

| anchor 名 | 章 | 挿入箇所 (synthesis.md line) | 挿入内容 |
|---|---|---|---|
| `switching-strategy` | § 12.4 切替戦略 | L516 (`### 12.4 切替戦略`) の **直後** | `<!-- @clause-anchor: switching-strategy -->` (= 改訂 1 内に内包済、 § 4.4 参照) |
| `risk-top-5` | § 16 Risk Top 5 | L587 (`## 16. Risk Top 5 と緩和策`) の **直後** | `<!-- @clause-anchor: risk-top-5 -->` (= 改訂 4 内に内包済、 § 7.3 参照) |
| `smoke-dod` | § 18.3 Smoke DoD | L662 (`### 18.3 ...`) の **直後** | `<!-- @clause-anchor: smoke-dod -->` (= 改訂 3 内に内包済、 § 6.3 参照) |
| `discussion-history` | § 21 議論履歴サマリー | L698 (`## 21. 議論履歴サマリー`) の **直後** | `<!-- @clause-anchor: discussion-history -->` |
| `clause-anchor-index` | § 22 Clause Anchor Index | 新章冒頭 | `<!-- @clause-anchor: clause-anchor-index -->` |

### 9.2 期待される anchor 件数 (= 概念設計 Round 3 [Suggestion] 2 反映)

`grep -nE "@clause-anchor" devnotes/20260428-2300-cascade-port-debate/synthesis.md | wc -l` の出力は **5** であること (= switching-strategy / risk-top-5 / smoke-dod / discussion-history / clause-anchor-index)。

### 9.3 anchor 未付与対象の明示 (= Round 2 [Warning] J 反映 + Round 3 [Warning] 算定整理)

#### 「anchorable clause unit」 の定義 (= Round 3 [Warning] 反映で曖昧性解消)

synthesis.md は top-level 章 (= § 0, § 1, § 2, ..., § 21, § 22) と subsection (= § 1.1, § 1.2, ..., § 12.4, ..., § 18.3 等) の 2 階層構造。 anchor 付与単位は **clause unit** = 1 つの意味的に独立した節 (= top-level 章本体、 または subsection)。

Round 22 で anchor 付与する 5 clause units:
- `switching-strategy` → § 12.4 (subsection)
- `risk-top-5` → § 16 (top-level、 subsection なし)
- `smoke-dod` → § 18.3 (subsection)
- `discussion-history` → § 21 (top-level、 subsection なし)
- `clause-anchor-index` → § 22 (top-level 新設、 subsection なし)

つまり Round 22 anchor 付与は「§ 12.4 / § 16 / § 18.3 / § 21 / § 22」 の **5 clause units** で、 § 12 / § 18 全体に anchor が付くわけではない (= subsection のみ付与)。

#### anchor 未付与対象 (= 残り clause units、 後続別 TODO)

top-level 章 = 23 個 (§ 0-22):
- anchor 付与: § 16 / § 21 / § 22 = 3 個 (top-level として anchor 付与)
- anchor 未付与: § 0 / § 1 / ... / § 15 / § 17 / § 18 / § 19 / § 20 = 20 個 (top-level として未付与、 ただし subsection 単位で一部付与あり)

subsection anchor 付与: § 12.4 / § 18.3 = 2 個

「残り」 の算定 (= 後続 TODO で anchor 付与する候補):
- top-level 章単独で anchor 付与可能: § 0 / § 1 / § 2 / § 3 / § 4 / § 5 / § 6 / § 7 / § 8 / § 9 / § 10 / § 11 / § 13 / § 14 / § 15 / § 17 / § 19 / § 20 = **18 個** (= top-level 23 から付与済 § 16 / § 21 / § 22 を除外、 さらに § 12 / § 18 は subsection 付与で部分的に anchor を持つが top-level としては未付与)

= 「残り 18 top-level 章」 (= 概念設計 Round 1 の「残り 17 章」 は § 0 を除外した数え方、 詳細設計では § 0 を含めて 18 と算定)

#### subsection anchor は別カウント

§ 1.1 / § 1.2 / § 4.1 / ..., § 8.5 / ..., § 11.2 / ..., § 22.1 / § 22.2 等の subsection anchor は **別カウント** で、 後続別 TODO の scope で必要に応じて付与する (= 全 subsection 一括ではなく、 cross-ref 需要のあるもののみ段階的付与)。

これら 18 top-level 章 + N subsection への anchor 付与 / 自動 lint / CI 検証は本 T076 スコープ外、 後続別 TODO で実施。

### 9.4 anchor 命名規則 (= Round 3 [Warning] § 9.3 重複解消で 9.4 に変更)

- 形式: kebab-case ASCII slug (= 章タイトルの英訳、 slug 化、 全小文字)
- 一意性: synthesis.md 内で重複なし
- 安定性: Round 23 以降で章番号 shift しても anchor 名は不変

---

## 10. 改訂 5c: 末尾 § 22 Clause Anchor Index 新章

### 10.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L714 (= § 21 末尾) の **直後**、 EOF 直前に新章追加。

### 10.2 挿入内容

```markdown
---

## 22. Clause Anchor Index (Round 22 新設)

<!-- @clause-anchor: clause-anchor-index -->

stable clause anchor を提供する index 表。 章番号 shift に対する SSOT として、 cross-ref 参照は `@clause-anchor: <name>` 形式で記述すること。 Round 22 では 5 改訂対象章のみ anchor 付与、 残り 17 章は後続別 TODO。

| anchor | 章 | scope | 用途 |
|---|---|---|---|
| `switching-strategy` | § 12.4 切替戦略 | 1 章 | Phase 2 切替 commit / 旧実装削除 / dual-path 規範参照 |
| `risk-top-5` | § 16 Risk Top 5 | 1 章 | FM1-FM5 紐付け / threshold-free 評価規範 / `select_rollback_relevant_failure_modes` policy 参照 |
| `smoke-dod` | § 18.3 T918 (T075) Smoke DoD | 1 章 | per-run / cross-run 二層分離 DoD / 切替 commit 前提条件参照 |
| `discussion-history` | § 21 議論履歴サマリー | 1 章 | Round 1-22 系譜参照 |
| `clause-anchor-index` | § 22 Clause Anchor Index | 1 章 | 本 index 自身の self-reference |

### 22.1 retroactive_anchor_grant 取扱

旧 round md (round-1.md 〜 round-20.md + Round 21 rationale) は **不変保持** (= history 改変禁止)。 retroactive な anchor 付与は **不可**、 旧 round md からの synthesis 章参照は本 anchor index 経由で参照すること。 既存「§ 12.4」 等の section 番号参照は不変保持で問題なし (= R-FM-3 失敗モード解析、 概念設計 § A-6 参照)。

### 22.2 残り 18 top-level 章 + subsection anchor の後続 TODO 切出 (= Round 22 [Warning] J + Round 3 [Warning] 算定整理 反映)

Round 22 anchor 付与 (= 5 clause units):
- top-level 章付与: § 16 (`risk-top-5`) / § 21 (`discussion-history`) / § 22 (`clause-anchor-index`)
- subsection 付与: § 12.4 (`switching-strategy`) / § 18.3 (`smoke-dod`)

未付与 top-level 章 (= 計 18 個): § 0 / § 1 / § 2 / § 3 / § 4 / § 5 / § 6 / § 7 / § 8 / § 9 / § 10 / § 11 / § 13 / § 14 / § 15 / § 17 / § 19 / § 20

未付与 subsection (= cross-ref 需要に応じて段階的付与): § 1.1-1.4 / § 4.1-4.4 / § 5.1-5.5 / § 6.1-6.7 / § 7.1-7.7 / § 8.1-8.7 / § 9.1-9.3 / § 10.1-10.2 / § 11.1-11.2 / § 12.1-12.3 (§ 12.4 は付与済) / § 18.1-18.2 (§ 18.3 は付与済) / § 22.1-22.2 (subsection 単独 anchor は不要、 § 22 anchor で代替可)

これら 18 top-level + 未付与 subsection への anchor 付与 / 自動 lint / CI 検証は本 T076 スコープ外、 後続別 TODO で実施 (= Round 23 以降の段階的付与を予定)。

#### 詳細設計 § 9.3 との同期 (= Round 3 [Warning] § 22.2 提示不足 反映)

本節の clause unit 定義および 18 top-level 章列挙は、 詳細設計 [`devnotes/20260502-1001-todo-T076-synthesis-round-22/detailed-design.md`](../../20260502-1001-todo-T076-synthesis-round-22/detailed-design.md) § 9.3 「anchor 未付与対象の明示」 と完全同期。 後続別 TODO 着手時は両 file (= synthesis § 22.2 + 詳細設計 § 9.3) を SSOT として参照する。

---
```

---

## 11. ε 改訂: § 21 末尾 Round 22 行追加

### 11.1 変更箇所

`devnotes/20260428-2300-cascade-port-debate/synthesis.md` L713 (= Round 21 行) の **直後** に Round 22 行を追加。

### 11.2 挿入内容

```markdown
| 22 | (cascade port v2 Phase 2 配線完了後 / 2026-05-02) synthesis 改訂 | T075 Big-bang cleanup + smoke モジュール (commit `09bd56d`) で確定した詳細設計 SSOT (= `FailureModeKind` enum 5 値 / `EvidenceClass` 4 値 / `PerRunSmokeDoDResult` (DoD1-DoD7) / `CrossRunSmokeDoDResult` (DoD8) / `DUAL_PATH_ENFORCE_TARGETS` 4 経路 (3 fail_closed + 1 fail_open) / `select_rollback_relevant_failure_modes` API 予約) を上位設計 (synthesis) に反映する cycle 最終段。 § 12.4 / § 16 / § 18.3 / § 21 改訂 + § 22 anchor index 新設 + 冒頭 metadata block 追加。 改訂 PR: `devnotes/20260502-1001-todo-T076-synthesis-round-22/` |
```

---

## 12. ε 改訂: rationale.md 新規追加 (Round 21 同型)

### 12.1 file 配置

`/Users/ishitoya/repository/zenigame-fx/devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md` (新規)

### 12.2 構造 (Round 21 前例 `devnotes/20260430-1045-synthesis-revise-mission-signed-margin/rationale.md` と完全同型: 1 改訂理由 / 2 改訂方針 / 3 改訂内容詳細 / 4 改訂しないことの確認 / 5 整合性検証 / 6 PR 構成 / 7 完了判定)

```markdown
# Synthesis 改訂 PR (Round 22): cascade port v2 Phase 2 配線完了後 SSOT 同期

**作成日時**: 2026-05-02 10:35 JST
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

§ 1-11 / § 13-15 / § 17 / § 19-20、 数値 threshold、 `select_rollback_relevant_failure_modes` 本実装、 残り 17 章 anchor、 旧 round md retroactive 書換は本 PR では touch しない。

---

## 3. 改訂内容詳細 (5 章 + ε)

### 3.1 § 12.4 切替戦略 (改訂 1 + 2)

(本詳細設計 § 4 + § 5 の Before / After に同じ)

### 3.2 § 18.3 Smoke DoD (改訂 3)

(本詳細設計 § 6 の Before / After に同じ)

### 3.3 § 16 Risk Top 5 (改訂 4)

(本詳細設計 § 7 の Before / After に同じ)

### 3.4 冒頭 metadata + anchor (改訂 5a + 5b + 5c)

(本詳細設計 § 8 + § 9 + § 10 の Before / After に同じ)

### 3.5 § 21 議論履歴 + rationale.md (ε)

(本詳細設計 § 11 + § 12 に同じ)

---

## 4. 改訂しないことの確認 (No-touch リスト)

- **synthesis 改訂対象外章**: § 1-11 / § 13-15 / § 17 / § 19-20 (= T075 SSOT 同期に影響なし)
- **Round 21 改訂部分** (= § 6.4 / § 6.5 / § 8.3 / § 15 / § 17 の `mission_signed_margin` SSOT 昇格関連): touch せず保持 (Round 22 の改訂対象外)
- **数値 threshold** (= FM1-FM5 hard_fail 判定境界 / q_force 0.40 上限再校正等): 別 TODO で smoke 後再校正
- **`select_rollback_relevant_failure_modes` 本実装**: 別 TODO で synthesis Round 22 § 16 確定後の Phase 2
- **残り 17 章 anchor 付与 / 自動 lint**: 別 TODO で Round 23 以降
- **旧 round md (1-21) への retroactive 書換**: **禁止** (history 不変保持、 anchor index 経由参照のみ)
- **smoke.py 本体 / docstring**: touch なし (= forward reference 文言は Round 22 完了で「未来参照」 から「現在参照」 へ自動的に valid 化)
- **AGENTS.md / SKILL.md / config / docs/alpha_factory/* / scripts / tests**: touch なし

---

## 5. 改訂後の整合性検証

### 5.1 T075 詳細設計との整合

T075 `devnotes/20260501-0136-todo-T075-bigbang-cleanup-smoke/detailed-design.md` で確定した SSOT (= `FailureModeKind` / `EvidenceClass` / `DoDIdPerRun` / `DoDIdCrossRun` / `PerRunSmokeDoDResult` / `CrossRunSmokeDoDResult` / `DUAL_PATH_ENFORCE_TARGETS` / `select_rollback_relevant_failure_modes`) の文言と Round 22 改訂後の synthesis 文言が完全 1:1 整合 (= 本詳細設計 § 13 機械検証手順 で grep 確認)。

### 5.2 smoke.py 実装との整合

`src/alpha_factory/smoke.py` (commit `09bd56d`) の Literal / dataclass / Final 定数定義と Round 22 改訂後の synthesis 文言が完全 1:1 整合 (= 本詳細設計 § 13.1-13.5 の smoke.py 側 grep で確認)。

### 5.3 Phase 2 切替 commit 前提条件としての整合

Phase 2 切替 commit (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消) の前提条件 (= 概念設計 § F-1 / F-2 / F-3 の dual-path 解消条件 / FAIL_CLOSED 条件 / 旧実装削除条件) が Round 22 改訂後の synthesis で全て参照可能 (= rollback 判定 / DoD 完走 / dual-path 検証の設計側 SSOT 確定)。

### 5.4 コードベースとの整合 (現状 0 件 touch)

T076 は docs-only PR で `src/` / `scripts/` / `config/` / `tests/` は 0 件 touch。 ruff / mypy / pytest の regression は 0 件で自動 PASS (= § 13.8 横断確認で実機検証)。

---

## 6. PR 構成

| PR | 内容 | コミット数 | 検証 |
|---|---|---|---|
| **T076 PR1 (本 PR)** | synthesis.md 8 箇所改訂 + rationale.md 新規 | 1 commit (= docs-only、 atomic consistency boundary) | § 13 機械検証 7 ブロック + § 13.8 横断確認 |
| (T076 後の別 PR) Phase 2 切替 commit | 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消 | 別 PR、 別 commit、 別 TODO ではなく単発 cleanup commit | T075 `DUAL_PATH_ENFORCE_TARGETS` test fail_closed 通過 + smoke 5 Run 連続 PASS |

---

## 7. 完了判定

T076 PR1 完了 = 以下を全て満たす:

- [ ] synthesis.md 改訂 1-5 + ε の 8 箇所編集が完了
- [ ] rationale.md 新規追加 (本 file、 § 1-7 全章存在)
- [ ] § 13.1-13.7 の機械検証 grep / sed / awk が全 PASS
- [ ] § 13.8 横断確認 (pytest / ruff / mypy) が全 PASS (regression 0)
- [ ] commit message に「T076 (synthesis Round 22 確定) 完了 → Phase 2 切替 commit 前提成立」 旨を明記
- [ ] PR タイトル `docs(T076): synthesis Round 22 改訂 — cascade port v2 Phase 2 配線完了後 SSOT 同期`
- [ ] main fast-forward merge (worktree → main)
```

---

## 13. 機械検証手順 (= 概念設計 § 機械検証手順を完全コマンド形式に展開、 Round 3 [Suggestion] 取込 + Round 2 [Critical] 4 件 + [Warning] 4 件反映で全面書き直し)

### 13.0 共通規約 (= Round 2 [Critical] 4 反映)

全 § 13.x ブロック共通の shell 規約:
- スクリプト先頭に `set -euo pipefail` を必ず置く (= pipe exit code 消失防止、 unset variable detection)
- line range 固定の sed は **使わない** (= metadata block 追加で drift する)、 代わりに `awk '/^### 12\.4/,/^---$/' file` で **章 heading 範囲抽出**
- 複数語句 grep は OR (`A|B|C`) ではなく、 個別 `grep -q` を **AND で全件 PASS 必須** (= 1 要素 PASS の false positive 防止、 Round 2 [Critical] 3)
- 全コマンドは `&&` で chain、 失敗時に明示的な FAIL message + exit 1

### 13.1 改訂 1: § 12.4 new_cascade 廃止 + dual-path 規範 (= Round 2 [Critical] 2-3 + [Warning] H 反映)

```bash
#!/usr/bin/env bash
set -euo pipefail
SYN=devnotes/20260428-2300-cascade-port-debate/synthesis.md
SEC=$(awk '/^### 12\.4 切替戦略/,/^### 12\.5|^## 13\./' "$SYN")

# synthesis 側 § 12.4 範囲抽出後の旧文言不在 (= awk heading 抽出で line drift 耐性)
echo "$SEC" | grep -qE "new_cascade 名前空間で実装" \
  && { echo "FAIL: 旧 new_cascade 文言が § 12.4 に残存"; exit 1; } || true

# synthesis 側 § 12.4 内の新文言: AND 検証 (= OR の false positive 防止)
echo "$SEC" | grep -qE "src/alpha_factory/.*直接" \
  || { echo "FAIL: § 12.4 に 'src/alpha_factory/...直接' 不在"; exit 1; }
echo "$SEC" | grep -qE "DUAL_PATH_ENFORCE_TARGETS" \
  || { echo "FAIL: § 12.4 に DUAL_PATH_ENFORCE_TARGETS 不在"; exit 1; }
echo "$SEC" | grep -qE "DUAL_PATH_ENFORCE_ALLOWLIST" \
  || { echo "FAIL: § 12.4 に DUAL_PATH_ENFORCE_ALLOWLIST 不在"; exit 1; }

# synthesis 側 § 12.4 内の dual-path 3+1 経路書き分け (= AND 検証)
echo "$SEC" | grep -qE "source_import" \
  || { echo "FAIL: § 12.4 に source_import 不在"; exit 1; }
echo "$SEC" | grep -qE "config_yaml" \
  || { echo "FAIL: § 12.4 に config_yaml 不在"; exit 1; }
echo "$SEC" | grep -qE "config/\*\*/\*\.yaml" \
  || { echo "FAIL: § 12.4 に config/**/*.yaml glob 不在"; exit 1; }
echo "$SEC" | grep -qE "config/\*\*/\*\.yml" \
  || { echo "FAIL: § 12.4 に config/**/*.yml glob 不在 (= [Warning] H 反映)"; exit 1; }
echo "$SEC" | grep -qE "fail_closed" \
  || { echo "FAIL: § 12.4 に fail_closed 不在"; exit 1; }
echo "$SEC" | grep -qE "fail_open" \
  || { echo "FAIL: § 12.4 に fail_open 不在"; exit 1; }
echo "$SEC" | grep -qE "docs_runbook" \
  || { echo "FAIL: § 12.4 に docs_runbook 不在"; exit 1; }

# smoke.py 側 SSOT 現状維持 (= AND 検証)
SMK=src/alpha_factory/smoke.py
grep -qE "DUAL_PATH_ENFORCE_TARGETS" "$SMK" \
  || { echo "FAIL: smoke.py に DUAL_PATH_ENFORCE_TARGETS 不在"; exit 1; }
grep -qE "DUAL_PATH_ENFORCE_ALLOWLIST" "$SMK" \
  || { echo "FAIL: smoke.py に DUAL_PATH_ENFORCE_ALLOWLIST 不在"; exit 1; }
grep -qE "config/\*\*/\*\.yml" "$SMK" \
  || { echo "FAIL: smoke.py に config/**/*.yml glob 不在 (= SSOT 整合性検証)"; exit 1; }

echo "PASS: 改訂 1 § 12.4 切替戦略"
```

### 13.2 改訂 2: § 12.4 ロールバック条件 → FM enum + inconclusive blocking

```bash
#!/usr/bin/env bash
set -euo pipefail
SYN=devnotes/20260428-2300-cascade-port-debate/synthesis.md
SEC=$(awk '/^### 12\.4 切替戦略/,/^### 12\.5|^## 13\./' "$SYN")

# synthesis 側 § 12.4 範囲抽出後の旧文言不在
echo "$SEC" | grep -qE "FM1/FM4 が強く出る場合のみ" \
  && { echo "FAIL: 旧 'FM1/FM4 が強く出る場合のみ' 文言が § 12.4 に残存"; exit 1; } || true

# synthesis 側 § 12.4 内の新文言: AND 検証
echo "$SEC" | grep -qE "FM1-FM5" \
  || { echo "FAIL: § 12.4 に FM1-FM5 不在"; exit 1; }
echo "$SEC" | grep -qE "FailureModeKind" \
  || { echo "FAIL: § 12.4 に FailureModeKind 不在"; exit 1; }
echo "$SEC" | grep -qE "select_rollback_relevant_failure_modes" \
  || { echo "FAIL: § 12.4 に select_rollback_relevant_failure_modes 不在"; exit 1; }
echo "$SEC" | grep -qE "hard_fail" \
  || { echo "FAIL: § 12.4 に hard_fail 不在"; exit 1; }
echo "$SEC" | grep -qE "inconclusive" \
  || { echo "FAIL: § 12.4 に inconclusive 不在"; exit 1; }
echo "$SEC" | grep -qE "ブロック" \
  || { echo "FAIL: § 12.4 に inconclusive blocking 文言 (ブロック) 不在"; exit 1; }

# smoke.py 側 SSOT 現状維持
SMK=src/alpha_factory/smoke.py
grep -qE "FailureModeKind = Literal" "$SMK" \
  || { echo "FAIL: smoke.py に FailureModeKind Literal 不在"; exit 1; }
grep -qE "def select_rollback_relevant_failure_modes" "$SMK" \
  || { echo "FAIL: smoke.py に select_rollback_relevant_failure_modes def 不在"; exit 1; }

echo "PASS: 改訂 2 § 12.4 ロールバック条件"
```

### 13.3 改訂 3: § 18.3 Smoke DoD 二層分離 (= item-level inconclusive 不在検証、 Round 2 [Warning] G 反映)

```bash
#!/usr/bin/env bash
set -euo pipefail
SYN=devnotes/20260428-2300-cascade-port-debate/synthesis.md
SEC_18_3=$(awk '/^### 18\.3/,/^## 19\./' "$SYN")

# synthesis 側 § 18.3 内の二層分離文言: AND 検証
echo "$SEC_18_3" | grep -qE "PerRunSmokeDoDResult" \
  || { echo "FAIL: § 18.3 に PerRunSmokeDoDResult 不在"; exit 1; }
echo "$SEC_18_3" | grep -qE "CrossRunSmokeDoDResult" \
  || { echo "FAIL: § 18.3 に CrossRunSmokeDoDResult 不在"; exit 1; }
echo "$SEC_18_3" | grep -qE "per-run" \
  || { echo "FAIL: § 18.3 に per-run 不在"; exit 1; }
echo "$SEC_18_3" | grep -qE "cross-run" \
  || { echo "FAIL: § 18.3 に cross-run 不在"; exit 1; }
echo "$SEC_18_3" | grep -qE "DoDIdPerRun" \
  || { echo "FAIL: § 18.3 に DoDIdPerRun 不在"; exit 1; }
echo "$SEC_18_3" | grep -qE "DoDIdCrossRun" \
  || { echo "FAIL: § 18.3 に DoDIdCrossRun 不在"; exit 1; }

# § 18.3 内 DoD1-DoD8 全 8 件記載 (Round 3 [Suggestion] 3 反映)
for i in 1 2 3 4 5 6 7 8; do
  echo "$SEC_18_3" | grep -qE "DoD${i}\b" \
    || { echo "FAIL: § 18.3 に DoD${i} 不在"; exit 1; }
done

# § 18.3 完走判定: item-level inconclusive 不在 文言 (= Round 2 [Warning] G 反映)
echo "$SEC_18_3" | grep -qE "item-level" \
  || { echo "FAIL: § 18.3 に item-level fail-closed 文言不在"; exit 1; }
echo "$SEC_18_3" | grep -qE "全.*DoD.*ok.*warning" \
  || { echo "FAIL: § 18.3 に 'item の status が ok または warning' 文言不在"; exit 1; }

# smoke.py 側 SSOT 現状維持
SMK=src/alpha_factory/smoke.py
grep -qE 'DoDIdPerRun = Literal' "$SMK" \
  || { echo "FAIL: smoke.py に DoDIdPerRun Literal 不在"; exit 1; }
grep -qE 'DoDIdCrossRun = Literal' "$SMK" \
  || { echo "FAIL: smoke.py に DoDIdCrossRun Literal 不在"; exit 1; }
grep -qE "class PerRunSmokeDoDResult" "$SMK" \
  || { echo "FAIL: smoke.py に PerRunSmokeDoDResult 不在"; exit 1; }
grep -qE "class CrossRunSmokeDoDResult" "$SMK" \
  || { echo "FAIL: smoke.py に CrossRunSmokeDoDResult 不在"; exit 1; }

# smoke.py 側 SmokeObservabilityProjection 実 field 存在確認 (= Round 3 [Critical] 1 反映)
# § 6.3 DoD 表で参照する SmokeObservabilityProjection field が smoke.py 実装に存在することを保証
for field in ab_divergence_class epoch_consistency_class warmstart_shortfall_class bypass_ratio_class session_entropy_class dataset_epoch_id_present; do
  grep -qE "^[[:space:]]+${field}:" "$SMK" \
    || { echo "FAIL: smoke.py SmokeObservabilityProjection に '${field}' field 不在 (= Round 3 [Critical] 1 反映)"; exit 1; }
done
grep -qE "cross_run_epoch_pollution_class" "$SMK" \
  || { echo "FAIL: smoke.py CrossRunSmokeObservabilityProjection に 'cross_run_epoch_pollution_class' field 不在"; exit 1; }

echo "PASS: 改訂 3 § 18.3 Smoke DoD"
```

### 13.4 改訂 4: § 16 Risk Top 5 + FM 紐付け + threshold-free 規範

```bash
#!/usr/bin/env bash
set -euo pipefail
SYN=devnotes/20260428-2300-cascade-port-debate/synthesis.md
SEC_16=$(awk '/^## 16\./,/^## 17\./' "$SYN")

# § 16 内の新文言: AND 検証
echo "$SEC_16" | grep -qE "FM ID" \
  || { echo "FAIL: § 16 に 'FM ID' 列不在"; exit 1; }
echo "$SEC_16" | grep -qE "threshold-free" \
  || { echo "FAIL: § 16 に threshold-free 不在"; exit 1; }
echo "$SEC_16" | grep -qE "EvidenceClass" \
  || { echo "FAIL: § 16 に EvidenceClass 不在"; exit 1; }
echo "$SEC_16" | grep -qE "smoke 後再校正" \
  || { echo "FAIL: § 16 に 'smoke 後再校正' 不在"; exit 1; }
echo "$SEC_16" | grep -qE "EvidenceClassifierProtocol" \
  || { echo "FAIL: § 16 に EvidenceClassifierProtocol 不在"; exit 1; }

# § 16 内 FM1-FM5 全件記載
for i in 1 2 3 4 5; do
  echo "$SEC_16" | grep -qE "FM${i}\b" \
    || { echo "FAIL: § 16 に FM${i} 不在"; exit 1; }
done

# smoke.py 側 SSOT 現状維持
SMK=src/alpha_factory/smoke.py
grep -qE 'EvidenceClass = Literal' "$SMK" \
  || { echo "FAIL: smoke.py に EvidenceClass Literal 不在"; exit 1; }
grep -qE "class EvidenceClassifierProtocol" "$SMK" \
  || { echo "FAIL: smoke.py に EvidenceClassifierProtocol 不在"; exit 1; }

echo "PASS: 改訂 4 § 16 Risk Top 5"
```

### 13.5 改訂 5: 冒頭 metadata + anchor index (Round 3 [Suggestion] 2 反映で件数チェック)

```bash
#!/usr/bin/env bash
set -euo pipefail
SYN=devnotes/20260428-2300-cascade-port-debate/synthesis.md

# 冒頭 metadata block: 個別 AND 検証
HEAD_50=$(head -n 50 "$SYN")
echo "$HEAD_50" | grep -qE "synthesis_schema_version: 22" \
  || { echo "FAIL: 冒頭に synthesis_schema_version: 22 不在"; exit 1; }
echo "$HEAD_50" | grep -qE "revision_lineage:" \
  || { echo "FAIL: 冒頭に revision_lineage: 不在"; exit 1; }
echo "$HEAD_50" | grep -qE "retroactive_anchor_grant:" \
  || { echo "FAIL: 冒頭に retroactive_anchor_grant: 不在"; exit 1; }
echo "$HEAD_50" | grep -qE "round-21" \
  || { echo "FAIL: 冒頭 metadata に round-21 lineage 不在"; exit 1; }
echo "$HEAD_50" | grep -qE "round-22" \
  || { echo "FAIL: 冒頭 metadata に round-22 lineage 不在"; exit 1; }

# § 22 Clause Anchor Index 新章存在
grep -qE "^## 22\. Clause Anchor Index" "$SYN" \
  || { echo "FAIL: § 22 Clause Anchor Index 章不在"; exit 1; }

# anchor 件数 = 5 (Round 3 [Suggestion] 2 反映)
ANCHOR_COUNT=$(grep -cE "^<!-- @clause-anchor:" "$SYN")
test "$ANCHOR_COUNT" -eq 5 \
  || { echo "FAIL: anchor 件数 $ANCHOR_COUNT (期待 5)"; exit 1; }

# 期待 anchor 名 5 件すべて存在 (= AND 検証、 OR ではない)
for anchor in switching-strategy risk-top-5 smoke-dod discussion-history clause-anchor-index; do
  grep -qE "@clause-anchor: ${anchor}" "$SYN" \
    || { echo "FAIL: anchor '${anchor}' 不在"; exit 1; }
done

echo "PASS: 改訂 5 metadata + anchor index"
```

### 13.6 ε 改訂: § 21 末尾 Round 22 行追加

```bash
#!/usr/bin/env bash
set -euo pipefail
SYN=devnotes/20260428-2300-cascade-port-debate/synthesis.md
SEC_21=$(awk '/^## 21\./,/^## 22\.|^---$/' "$SYN")

# § 21 表内に "| 22 |" 行存在 (= AND 検証)
echo "$SEC_21" | grep -qE "^\| 22 \|" \
  || { echo "FAIL: § 21 に Round 22 行 (| 22 |) 不在"; exit 1; }
echo "$SEC_21" | grep -qE "T075 Big-bang cleanup" \
  || { echo "FAIL: § 21 Round 22 行に T075 言及不在"; exit 1; }
echo "$SEC_21" | grep -qE "synthesis Round 22" \
  || { echo "FAIL: § 21 Round 22 行で 'synthesis Round 22' 言及不在"; exit 1; }

echo "PASS: ε § 21 末尾 Round 22 行"
```

### 13.7 ε 改訂: rationale.md 新規追加 (= Round 2 [Critical] 1 反映、 Round 21 同型 7 章 loop 検証)

```bash
#!/usr/bin/env bash
set -euo pipefail
RAT=devnotes/20260502-1001-todo-T076-synthesis-round-22/rationale.md

# rationale.md 存在
test -f "$RAT" \
  || { echo "FAIL: rationale.md 不在"; exit 1; }

# Round 21 同型 7 章すべて loop で個別 AND 検証 (= Round 2 [Critical] 1 反映、 OR ではない)
declare -a REQ_SECTIONS=(
  "## 1\. 改訂理由"
  "## 2\. 改訂方針"
  "## 3\. 改訂内容詳細"
  "## 4\. 改訂しないことの確認"
  "## 5\. 改訂後の整合性検証"
  "## 6\. PR 構成"
  "## 7\. 完了判定"
)
for section in "${REQ_SECTIONS[@]}"; do
  grep -qE "^${section}" "$RAT" \
    || { echo "FAIL: rationale.md に '${section}' 不在"; exit 1; }
done

# 1.1 / 1.2 / 1.3 sub-section 存在
grep -qE "^### 1\.1" "$RAT" \
  || { echo "FAIL: rationale.md に 1.1 不在"; exit 1; }
grep -qE "^### 1\.2" "$RAT" \
  || { echo "FAIL: rationale.md に 1.2 不在"; exit 1; }
grep -qE "^### 1\.3" "$RAT" \
  || { echo "FAIL: rationale.md に 1.3 不在"; exit 1; }

# 5.1 / 5.2 / 5.3 / 5.4 sub-section 存在 (= 整合性検証 4 軸)
grep -qE "^### 5\.1" "$RAT" \
  || { echo "FAIL: rationale.md に 5.1 不在"; exit 1; }
grep -qE "^### 5\.2" "$RAT" \
  || { echo "FAIL: rationale.md に 5.2 不在"; exit 1; }

echo "PASS: ε rationale.md 構造"
```

### 13.7.5 並行経路の取扱 (= Round 2 [Critical] 13 / C2 反映)

T076 検証は **現行 SSOT のみ対象**:
- **検証対象 (= 現行 SSOT)**: synthesis.md (Round 22 改訂後) + smoke.py (commit `09bd56d` 以降) + rationale.md (本 PR で新規)
- **検証対象外 (= 歴史文書)**: round-1.md 〜 round-20.md + Round 21 rationale + handoff* + historical/ 配下 + docs/historical/ + devnotes/ 内の旧 TODO 設計 = 不変保持、 anchor index 経由参照のみ
- **検証対象外 (= 派生文書)**: docs/alpha_factory/* の各 specification document (= terminology / stage-gates / clause-architecture 等) は別 SSOT で管理、 T076 では touch なし

T076 機械検証で「synthesis に X が無い」 と主張する箇所 (= § 13.x の grep -qE 不在検証) は、 **synthesis.md 内 § 12.4 / § 16 / § 18.3 / § 21 / § 22 の章範囲** に限定された主張であり、 旧 round md / handoff / docs/alpha_factory/* 等の並行経路には遡求しない (= history 不変保持原則)。 並行経路への影響は § 17 リスク表「synthesis 章番号 shift で他 docs cross-ref 破損」 で別途緩和済。

### 13.8 横断確認 (= Round 2 [Critical] 4 反映、 set -o pipefail で exit code 保持)

```bash
#!/usr/bin/env bash
set -euo pipefail

# T075 docstring 内 "synthesis Round 22" 参照 (= 既存 forward reference 確認のみ、 touch 不要)
grep -qE "synthesis Round 22" src/alpha_factory/smoke.py \
  || { echo "FAIL: smoke.py に Round 22 forward reference 不在 (= 既存 docstring の前提崩壊)"; exit 1; }

# pytest regression check (= docs-only PR、 0 件 fail 期待、 pipefail で exit code 保持)
LOG_PYTEST=$(mktemp)
if ! uv run pytest tests/alpha_factory/ -x --no-header -q > "$LOG_PYTEST" 2>&1; then
  tail -20 "$LOG_PYTEST"
  echo "FAIL: pytest regression"; exit 1
fi
tail -3 "$LOG_PYTEST"

# ruff
LOG_RUFF=$(mktemp)
if ! uv run ruff check src/ tests/ > "$LOG_RUFF" 2>&1; then
  tail -10 "$LOG_RUFF"
  echo "FAIL: ruff check"; exit 1
fi

# mypy
LOG_MYPY=$(mktemp)
if ! uv run mypy src/ > "$LOG_MYPY" 2>&1; then
  tail -10 "$LOG_MYPY"
  echo "FAIL: mypy"; exit 1
fi

echo "PASS: 横断確認 (pytest / ruff / mypy)"
```

---

## 14. テスト計画 (= docs-only PR の特殊形)

| # | 検証項目 | 検証方法 | 期待結果 |
|---|---|---|---|
| T1 | synthesis.md 旧文言不在 | § 13.1-13.4 の sed/grep | 各 grep 0 件 (exit 1 で fail-closed) |
| T2 | synthesis.md 新文言存在 | § 13.1-13.5 の grep | 各 grep 1 件以上 |
| T3 | anchor 件数 == 5 | § 13.5 の wc -l | 5 |
| T4 | anchor 名 5 件 (switching-strategy / risk-top-5 / smoke-dod / discussion-history / clause-anchor-index) | § 13.5 ループ grep | 全件存在 |
| T5 | DoD1-DoD8 全件 § 18.3 内記載 | § 13.3 ループ grep | 全 8 件存在 |
| T6 | FM1-FM5 全件 § 16 内記載 | § 13.4 ループ grep | 全 5 件存在 |
| T7 | rationale.md 必須セクション | § 13.7 grep | 6 必須セクション存在 |
| T8 | pytest regression 0 | § 13.8 `uv run pytest` | exit 0 |
| T9 | ruff / mypy clean | § 13.8 | exit 0 |

T1-T9 全 PASS で T076 PR コミット可能。

---

## 15. ルックアヘッドバイアスチェック

該当なし (= primitive 変更ではない、 docs-only PR で fitness / metric 計算 / window 集計に touch なし)。

---

## 16. パフォーマンスチェック

該当なし (= primitive 変更ではない、 `compute_all_bars` / SoA / キャッシュは無関係)。

---

## 17. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| synthesis 章番号 shift で他 docs (docs/alpha_factory/* / handoff* / detailed-design.md 等) の cross-ref 破損 | 中 | T076 では §-番号自体は変更せず内容差替のみ + § 22 anchor index で stable 化、 既存参照は不変 |
| anchor 名 typo / 重複 | 中 | § 13.5 で 5 件名前を機械検証、 lint で fail-closed |
| metadata block YAML 形式 typo (= HTML コメント内の YAML 風記述で markdown render 崩れ) | 低 | HTML コメント全体は markdown render 時に non-rendered、 内部 YAML 記述は機械検証用のみ。 PR レビューで render 確認 |
| Round 22 改訂 PR と Phase 2 切替 commit PR の順序逆転 | 中 | T076 完了 = synthesis Round 22 確定 → 切替 commit PR の前提成立、 PR タイトル / commit message で順序明示 |
| 5 改訂候補のうち 1 つでも Codex から CHANGES_REQUESTED が出ると 5 件全部が再合議 | 低 | 同一 synthesis SSOT の atomic consistency boundary、 同時改訂が正、 Round 21 同型で実績あり |
| inconclusive blocking semantics の運用不明確 | 低 | § 5.3 (改訂 2) と § 6.3 (改訂 3) で「全 metric および全 DoD item が ok または warning」 を fail-closed と明文化、 operational 判断は Phase 2 別 TODO の policy で確定 |
| Round 2 [Critical] 2 (= line range drift) を反映、 § 13.x の awk heading 抽出が章タイトル変更で外れる | 低 | § 13.x は `awk '/^### 12\.4 切替戦略/,/^### 12\.5\|^## 13\./'` 等の章 heading regex で抽出、 章番号 shift には耐性。 章タイトル変更時は本詳細設計の検証スクリプトも同期改訂 (= 別 PR で対応) |
| Round 2 [Critical] 3 (= OR grep 抜け道) を反映、 個別 grep の AND 検証で 1 要素不足を確実に検出 | 低 | § 13.x で各語句を個別 `grep -q` し、 1 件でも不在なら exit 1。 OR 判定は使わない |
| Round 2 [Critical] 4 (= pipefail なし pytest exit code 消失) を反映、 set -euo pipefail + tmpfile 経由で exit code 保持 | 低 | § 13.8 で pytest / ruff / mypy 出力を mktemp に保存し、 exit code を if 判定。 tail は失敗時の log 表示用のみ |

---

## 18. 実装モード

| 項目 | 内容 |
|---|---|
| 推奨モード | **standalone** (docs-only、 1 file 直接編集 + 1 file 新規、 既存 PR 並走なし、 Round 21 と同型) |
| 判断根拠 | (a) 実装 touch なし → ruff/mypy/pytest 影響なし、 (b) Round 21 で同型 PR 実績あり、 (c) Phase 2 切替 commit の前提条件 = 単独で完結する単位、 (d) 5 改訂候補は同一 synthesis SSOT の atomic consistency boundary で同時改訂が妥当 (改訂 #1-4 は T075 smoke SSOT 同期、 改訂 #5 は synthesis 内部 anchor SSOT、 同一 file への atomic PR が consistency boundary として最適) |
| 競合リスク | なし (synthesis.md は Round 21 完了以降 touch なし、 main HEAD と乖離 0) |
| 想定実装時間 | 短 (= 文書 diff のみ、 検証は § 13 grep 7 ブロック + pytest/ruff/mypy 確認、 テスト不要) |

### 18.1 実装手順 (= zenigame-fx-implement skill 起動時の guideline)

1. worktree 作成 (= main から fork)
2. synthesis.md を § 4-11 の Before / After に従って編集 (= 8 箇所)
3. rationale.md を § 12 の構造に従って新規作成
4. § 13 機械検証 7 ブロックを順次実行、 全 PASS 確認
5. § 13.8 横断確認 (pytest / ruff / mypy) 実行、 全 PASS 確認
6. § 18.3 実装時調整 4 件 (= Codex Round 4 [Suggestion] 反映) を取込
7. commit message: `docs(T076 PR1): synthesis Round 22 改訂 (cascade port v2 Phase 2 配線完了後 SSOT 同期)`
8. main fast-forward merge

### 18.3 実装時の調整事項 (= Codex 詳細設計 Round 4 [Suggestion] 4 件、 APPROVED 後の品質向上)

PR 実装時に以下の軽微調整を取り込む (= 詳細設計時点では現状で APPROVED、 ただし実装品質向上のため):

1. **§ 13.3 synthesis 側 SSOT field 参照検証追加**: `SEC_18_3` 抽出後に projection field 名 (= ab_divergence_class / epoch_consistency_class / warmstart_shortfall_class / bypass_ratio_class / session_entropy_class / dataset_epoch_id_present / cross_run_epoch_pollution_class) を loop で grep -qE 確認 (= 表中の field 名が改訂後 synthesis に実際に書かれているか検証、 smoke.py 側の存在確認だけでは不足)
2. **§ 13.3 smoke.py field grep を class 範囲限定**: `grep -qE "^[[:space:]]+${field}:" "$SMK"` のままでは class 外に同名 field があると false positive になる。 `awk '/^class SmokeObservabilityProjection/,/^class |^@dataclass/' "$SMK"` で class 範囲を切ってから field 検証するとより堅い (= optional、 SmokeObservabilityProjection class が単一定義 = 重複なしなら現状のままで OK)
3. **§ 22.2 相対リンク修正**: synthesis.md (= `devnotes/20260428-2300-cascade-port-debate/synthesis.md`) から sibling devnotes (= `devnotes/20260502-1001-todo-T076-synthesis-round-22/detailed-design.md`) への relative path は `../../20260502-1001-todo-T076-synthesis-round-22/detailed-design.md` ではなく `../20260502-1001-todo-T076-synthesis-round-22/detailed-design.md` が正 (= synthesis.md → 親 dir `20260428-2300-cascade-port-debate/` → `..` で `devnotes/`、 そこから sibling dir 1 段下る)。 PR 実装時に修正
4. **「残り 18 top-level 章」 表現補強**: 「§ 0 / § 1-11 / § 13-15 / § 17 / § 19-20」 だけでは subsection 部分付与済の § 12 / § 18 が誤解されかねないので、 「§ 12 / § 18 を除く残り 18 top-level 章 (= top-level としては anchor 未付与、 subsection で部分付与あり)」 と明示するとさらに誤読が減る (= 主に § 22.2 + § 9.3 で適用)

これら 4 件は PR 実装時に取り込み、 詳細設計 → 実装間で品質向上を図る。 Round 5 は不要 (= APPROVED)。

### 18.2 PR タイトル / commit message guideline (= Round 2 [Suggestion] 9 反映、 PR title に Phase 2 切替前提を明示)

- PR タイトル: `docs(T076): synthesis Round 22 改訂 (Phase 2 切替前提) — cascade port v2 Phase 2 配線完了後 SSOT 同期`
- commit message body (= Phase 2 切替 commit との順序明示):
  ```
  T076 (本 PR) で synthesis Round 22 が確定 → Phase 2 切替 commit (= 旧実装削除 + LOG_ONLY → FAIL_CLOSED + dual-path 並走解消、 別 PR 別 commit) の前提条件成立。

  改訂内容:
  - § 12.4: new_cascade 廃止 + dual-path 4 経路規範 (3 fail_closed + 1 fail_open)
  - § 12.4: ロールバック条件 FM1-FM5 enum + select_rollback_relevant_failure_modes API 名 + inconclusive blocking semantics
  - § 18.3: Smoke DoD per-run (DoD1-DoD7) / cross-run (DoD8) 二層分離
  - § 16: Risk Top 5 + FM ID 紐付け + threshold-free EvidenceClass 4 値評価規範 + 数値 threshold smoke 後再校正
  - 冒頭 metadata block (synthesis_schema_version: 22) + 各章 stable clause anchor (5 章) + § 22 Clause Anchor Index 新設
  - § 21 末尾に Round 22 行追加 + rationale.md 新規

  Codex review: gpt-5.4 概念 Round 3 APPROVED + gpt-5.3-codex 詳細 (本 PR 着手後)
  ```
