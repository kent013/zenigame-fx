# 概念設計: docs-alpha-factory-skeleton

## 参照ソース（C1 Design-first 証跡）

本設計の前提となる参照元（いずれも 2026-04-22 時点で読了）:

1. `docs/alpha_factory/concepts/docs-alpha-factory-skeleton.md` — 本施策の stub
2. `docs/alpha_factory/README.md` — 既存リンク 10 ファイル分の参照表 (L33-L48)
3. `devnotes/20260421-1850-fx-skill-port/debate-synthesis.md` — Codex × Claude 3 ラウンド議論の確定仕様
4. `devnotes/20260421-1850-fx-skill-port/master-plan.md` Phase 2A — `docs/alpha_factory/` 構成と Phase 2I の `default.yaml` 再設計案
5. `config/alpha_factory/default.yaml` — 現状の SSOT（live_criteria など、master-plan の改修案はまだ未反映）
6. `AGENTS.md` L42-66 — 思考原則と C1-C9 discipline
7. `docs/alpha_factory/TODO.md` / `TODO-closed.md` — 既存 TODO 表（本タスクで一切編集しない）

## 背景・課題

`docs/alpha_factory/README.md` は既に 10 本の主要ドキュメントへリンクを張っているが、リンク先ファイルは存在しない。autopilot / improve-cycle / codex-review など複数 skill がこれらの doc を参照する前提で動くため、**リンク切れの状態は早期に解消する必要がある**。

一方、各 doc を一度に詳細化しようとすると、以下のリスクがある:

- 確定仕様（debate-synthesis.md）と未確定仕様（n_eff キャリブレーション、PBO/RC 実装詳細など Phase 4 以降）が混在し、誤った値がドキュメントに固定化される
- SSOT 違反: 値を doc にハードコードすると `config/alpha_factory/default.yaml` との二重管理になる
- 用語の重複定義: 各 doc で IS/OOS, DSR, PBO, Clause, Modulator 等を都度定義してしまうと、後で揃わなくなる

## 改善アイデア

`docs/alpha_factory/` 配下に**骨格（skeleton）として 30-80 行**で 10 本のドキュメントを一度に作成する。各ドキュメントは:

1. **目的・スコープ**を 2-3 行で定義
2. **確定仕様の構造のみ**を記載（数値は SSOT 参照に置き換え）
3. **詳細ルールは別 TODO**（後続作業）への参照リンクを明記
4. **用語の初出は `terminology.md` の anchor へリンク**

### 採用/除外判定表（10 本構成の根拠を一元化）

下表が 10 本構成の唯一の根拠表。「README が既にリンクしているか」「後続 TODO の議論ベースとして必須か」「他 doc に統合可能か」の 3 軸で判定:

| # | ファイル | 採用理由 | 出典 | 行数目安 |
|---|---------|---------|------|---------|
| 1 | `clause-architecture.md` | README リンク済み + Phase 2C 実装の議論ベース | debate-synthesis A | 30-80 |
| 2 | `stage-gates.md` | README リンク済み + Phase 2E 実装の議論ベース。情報密度高、上限 100 行を例外許可 | debate-synthesis B | 30-100 |
| 3 | `swim-lane.md` | README リンク済み + Phase 2G 実装の議論ベース | master-plan 2G | 30-80 |
| 4 | `primitives.md` | README リンク済み + Phase 2D 32 個並列実装の索引が必須。32 行表のため上限 100 行を例外許可 | master-plan 2D | 30-100 |
| 5 | `cross-pair.md` | README リンク済み + Phase 2H 実装の議論ベース | debate-synthesis C | 30-80 |
| 6 | `statistics.md` | README リンク済み + Phase 別実装（DSR / PBO / RC）の段階表が必須。情報密度高、上限 100 行を例外許可 | debate-synthesis D | 30-100 |
| 7 | `migration-triggers.md` | README リンク済み + Phase 6 の自動判定実装の議論ベース | debate-synthesis F | 30-80 |
| 8 | `terminology.md` | 横断参照される用語集。10-15 用語想定、上限 120 行を例外許可 | 横断 | 30-120 |
| 9 | `runbook.md` | README リンク済み + autopilot / improve-cycle 運用手順の唯一の入口。フェーズ図 + CLI 表のため上限 100 行を例外許可 | README + skill 名 | 30-100 |
| 10 | `codex-discipline.md` | README リンク済み + AGENTS.md C1-C9 の運用解説。原則 9 個 + 呼び出しシーン表のため上限 100 行を例外許可 | AGENTS.md L42-66 | 30-100 |

### 除外検討（採用しない doc とその理由）

- `data-ingest.md`（FRED / OANDA 取込手順） — README に未リンク、別 TODO（fred-ingest-implementation 等）の concepts に閉じる
- `archive-schema.md`（Parquet スキーマ詳細） — README に未リンク、`statistics.md` または別 TODO（genome-archive-schema concept）に統合
- `walk-forward.md`（WF 詳細手順） — `stage-gates.md` 内に折り込む（独立 doc 化は行数過剰）
- `evaluation.md`（評価指標一覧） — `stage-gates.md` + `statistics.md` で機能分担

### skeleton テンプレ（全 doc 共通）

各 doc は以下の節を持つ:

```
# {タイトル}

## 目的
（2-3 行）

## スコープ
（2-3 行）

## 用語リンク
（用語の初出を terminology.md anchor へリンク）

## 主要定義
（構造的・恒久的な定数・式・構成のみ。チューニング値は SSOT 参照）

## SSOT 参照
（default.yaml の参照キーパス一覧）

## 関連ドキュメント
（他 doc / concepts / devnotes へのリンク）

## 関連 TODO
（後続 TODO 名と概要、未着手なら "未着手" と明記）
```

## SSOT 原則

チューニング可能なデフォルト値（α、population_size、generations、threshold 等）は `config/alpha_factory/default.yaml` を参照する記法で記述する。**本文に数値そのものを残してはならない**（執筆時点の値を丸括弧で添えるのも禁止 — 将来ドリフトの温床になる）。

参照記法の例:

> Stage A の通過率目標は `config/alpha_factory/default.yaml` の対応キー（命名は再設計後の Phase 2I 時点で確定）を参照。

**重要**: 本タスクの skeleton 作成時点で `default.yaml` に**未定義のキーパス**は本文に記載してはならない（grep で参照先がヒットしない記述は禁止）。`default.yaml` 再設計（master-plan Phase 2I）が未完なため、現状は live_criteria / improve_cycle / ga など**現行 yaml に存在するキーのみ**を参照可能とする。未定義領域については「Phase 2I で `default.yaml` に追加されるキーを参照する（本 skeleton 時点では未定義）」と明示する。

### 例外（doc 直書き許可）

**構造的・恒久的な定数**に限り doc 直書きを許可する。判定基準は「**チューニング対象になりえないか**」の一点。

許可例（直書き OK）:
- composite score の式 `Σ(cw_k × cs_k) / Σ|cw_k|`（数学的構造、変更しない）
- (ii-lite) 通過基準が「3 条件 AND」であるという**構造**（しきい値そのものは SSOT 参照）
- max_clause の理論上限 3（昇格段階の最大値、設計上の不変量）

禁止例（必ず SSOT 参照）:
- Stage A の通過率目標 15%（チューニング対象）
- ペナルティ α=0.03（実測 `n_eff` で連動調整される）
- pass_criteria の数値（median_oos_sharpe_min, mean_sharpe_cross_min など）

## 用語管理

- `terminology.md` で全用語を初出定義（短い 1-2 行 + 必要なら根拠引用）
- 他 doc から用語の初出箇所は `[Clause](terminology.md#clause)` 形式で必ずリンク
- 同じ doc 内 2 回目以降はリンク不要

### 執行メカニズム（テンプレ強制）

規約だけでは執行困難なため、**全 skeleton に「用語リンク」必須節をテンプレ化**する。各 doc の冒頭近くに以下の節を持つ:

```
## 用語リンク

本ドキュメントで使用する用語: [Clause](terminology.md#clause), [Modulator](terminology.md#modulator), ...
```

この節が無い doc は本タスク完了条件を満たさない（grep で全 doc に `## 用語リンク` セクションが存在することを確認）。

## 期待効果

### 使命達成への直接寄与

- **直接寄与: なし**。本施策は doc 整備のみで GA / primitive / gate には触れない

### 開発オペレーション健全化への寄与（間接）

- README の壊れリンク 10 件解消 → autopilot / codex-review が「ファイル無し」で stall しない
- 後続 Phase 2 系 TODO（clause-genome-structure, stage-gate-implementation, swim-lane-manager 等）の議論ベースが揃う
- Codex レビューで「設計 doc を先に読む」(C1) を強制できる土台になる

### Fact / Interpretation 分離

- **Fact**: 本施策は doc skeleton 作成のみで、設定値・実装コードへの変更を含まない
- **Interpretation**: 優先度 High の論拠は「使命達成への直接寄与」ではなく「後続 TODO の議論ベース整備」である

## 実装方針（概要）

1. **テンプレ統一**: 各 doc は以下の節構成を共通化
   - `目的` / `スコープ` / `関連ドキュメント` / `主要定義` / `SSOT 参照` / `関連 TODO`
2. **長さ制約**: 30-80 行（terminology.md は用語数で 100 行程度を許容）
3. **値ハードコード禁止**: 数値はすべて `default.yaml` のキーパスで参照
4. **用語リンク**: 初出は `terminology.md` の anchor へ
5. **既存 TODO 表（`TODO.md` / `TODO-closed.md`）には触れない**
6. **README.md は触らない**（既にリンク表は完成しており、本施策はリンク先実体の作成）

## 制約・前提

### verified（確認済み）

- README.md は既に 10 本のリンクを定義済み（L33-L48）→ 本施策はリンク先 10 ファイルを 1 対 1 で作成
- `config/alpha_factory/default.yaml` は live_criteria とサイクル設定を含む既存 SSOT として動作中
- `debate-synthesis.md` の最終仕様は 3 ラウンド議論で確定済み
- `docs/alpha_factory/concepts/` 配下に各 TODO の stub（clause-ga-operators, stage-gate-implementation 等）が既存 → 詳細化作業はその stub に紐付けて別 TODO で進行する建付け

### unverified（task exit 時点で確証が完全でない可能性）

- `default.yaml` は master-plan Phase 2I で大幅再設計予定（instruments 6 本化、clause 設定、stage_gate 詳細など）→ skeleton 作成時点では現行 yaml を参照し、再設計後の差分は別 TODO で追従

### exit-blocker（本タスクで必ず潰す）

- **リンク切れ解消**: README から張られた 10 リンクすべてが、本タスク完了時点で実体ファイルへ到達できる
- **SSOT 違反ゼロ**: 数値ハードコードを doc に残さない（grep で検出）
- **terminology.md の anchor 整合**: 他 doc から参照される用語が terminology.md に必ず定義されている

## スコープ外（編集禁止対象を含む）

### 編集禁止対象（本タスクで一切触らない）

- `docs/alpha_factory/README.md`（既にリンク表が完成）
- `docs/alpha_factory/TODO.md` / `docs/alpha_factory/TODO-closed.md`（TODO 表は別 skill 経由でのみ更新）
- `docs/alpha_factory/concepts/*.md`（既存 18 stub。各 stub は対応 TODO の議論ベースとして既に存在し、本タスクとは別系統）
- `config/alpha_factory/default.yaml`（再設計は master-plan Phase 2I の対象）
- `AGENTS.md`（C1-C9 の SSOT、本 doc 群は転載・参照のみ）

### 別 TODO で扱う

- 各 doc の詳細仕様（実装手順、関数 signature、データスキーマ等）は別 TODO（`docs/alpha_factory/concepts/` 配下の stub に対応）で実施
- `default.yaml` の再設計（master-plan Phase 2I の対象）
- Codex 合議 C1-C9 の本文書き換え（AGENTS.md がが SSOT。本 doc 群は転載・参照のみ）

## 優先度・テーマ

- **Priority**: High（後続 Phase 2 系 TODO の議論ベース整備）
- **Mode**: incremental（10 ファイルを 1 コミットで投入、競合リスク低）
- **Theme**: infrastructure
