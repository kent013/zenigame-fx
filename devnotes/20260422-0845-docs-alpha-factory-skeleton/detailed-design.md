# 詳細設計: docs-alpha-factory-skeleton

参照: [conceptual-design.md](conceptual-design.md)

Codex 概念レビュー Round 2 の Critical 3 件（SSOT 整合 / 編集禁止対象明示 / 採用判定一元化）は概念設計に反映済み。本詳細設計は Claude 単独で確定する。

---

## 1. 全体構成

10 本のドキュメント skeleton を `docs/alpha_factory/` 配下に作成する。

```
docs/alpha_factory/
├── README.md                  # 既存（編集禁止）
├── TODO.md                    # 既存（編集禁止）
├── TODO-closed.md             # 既存（編集禁止）
├── concepts/                  # 既存 18 stub（編集禁止）
├── clause-architecture.md     # NEW
├── stage-gates.md             # NEW
├── swim-lane.md               # NEW
├── primitives.md              # NEW
├── cross-pair.md              # NEW
├── statistics.md              # NEW
├── migration-triggers.md      # NEW
├── terminology.md             # NEW
├── runbook.md                 # NEW
└── codex-discipline.md        # NEW
```

## 2. 共通テンプレ（必須節）

各 doc は以下の節構成を順守:

```
# {タイトル}

## 目的
{2-3 行で何のためのドキュメントかを記述}

## スコープ
{扱う範囲・扱わない範囲}

## 用語リンク
本ドキュメントで使用する用語: [Term1](terminology.md#term1), [Term2](terminology.md#term2), ...

## 主要定義
{構造的・恒久的な定数・式・構成のみ。チューニング値は SSOT 参照}

## SSOT 参照
| 項目 | 参照キーパス（config/alpha_factory/default.yaml） |
|------|--------------------------------------------------|
| ... | ... |

## 関連ドキュメント
- 内部リンク（他 doc）
- 外部リンク（concepts / devnotes）

## 関連 TODO
- 後続 TODO 名と概要（未着手なら "未着手" と明記）
```

## 3. 各 doc の skeleton 内容

### 3.1 `clause-architecture.md`（30-80 行）

- 目的: Clause 内部構造（directional × local_gate × weight、composite score 計算式、ヒステリシス）を一箇所に集約
- 主要定義:
  - Clause = `directional × local_gate × weight`
  - `dir_score = Σ(w_i × signal_i) / Σ|w_i|`
  - `gate ∈ [0, 1]`（sigmoid 有界）
  - `clause_score = dir_score × gate`
  - `composite = Σ(clause_weight × clause_score) / Σ|clause_weight|`
  - composite ヒステリシス: `θ_on > θ_off`
  - max_clause: 初期 1 / 標準 2 / 上限 3（昇格段階）
  - long/short 対称制御（パラメータ分離可）
  - session close / time_stop / spread・slippage フィルタ必須
- SSOT 参照: 現状 `default.yaml` には `ga.max_depth` のみ存在（max_clause 系は Phase 2I で追加予定と明示）
- 関連: `swim-lane.md` / `stage-gates.md` / `concepts/clause-genome-structure.md`

### 3.2 `stage-gates.md`（30-100 行）

- 目的: Stage A/B/C 仕様（期間、WF パラメータ、通過基準、α ペナルティ）を一箇所に集約
- 主要定義:
  - Stage A: Fast Screen（短期窓、α_A ペナルティ）
  - Stage B: Full IS + WF-OOS（train / test / step / embargo の 4 パラメータ、median OOS Sharpe / 正 fold 比率 / DSR の 3 条件 AND）
  - Stage C: Live Criteria + Stress（live_criteria + (ii-lite) + spread×N stress + trade range）
  - 期間延長禁止（禁止事項 #1）の構造的明示
- SSOT 参照: 現行 `default.yaml` の `live_criteria` キー群、`improve_cycle.*` を参照
- 関連: `clause-architecture.md` / `cross-pair.md` / `statistics.md` / `concepts/stage-gate-implementation.md`

### 3.3 `swim-lane.md`（30-80 行）

- 目的: Tier 1 + Graduation lane 設計と graduation 条件
- 主要定義:
  - Tier 1: per-instrument GA（target ペアごとに独立）
  - Graduation lane: Stage C 通過個体を集合させた universal 探索
  - Graduate 条件: Stage C 通過 AND (ii-lite) shadow 基準超え
- SSOT 参照: `default.yaml` には未定義（Phase 2I で追加予定キー: `ga.population_size_tier1` / `ga.population_size_graduation`）
- 関連: `stage-gates.md` / `cross-pair.md` / `concepts/swim-lane-manager.md`

### 3.4 `primitives.md`（30-80 行）

- 目的: プリミティブ 32 個カタログの索引（実体は別 TODO で実装）
- 主要定義: 32 個の名称・カテゴリ表（汎用 Directional 14 / 汎用 Modulator 6 / ペア特化 12）
  - 実装時の必須メタ: `category`, `domain`, `required_data`
- SSOT 参照: なし（プリミティブは config 駆動でなく registry 駆動）
- 関連: `clause-architecture.md` / `concepts/primitives-registry.md` / `concepts/primitives-directional-generic.md` / `concepts/primitives-modulator-generic.md` / `concepts/primitives-pair-specific.md`

### 3.5 `cross-pair.md`（30-80 行）

- 目的: (ii-lite) 評価、アンカーペア、集約関数、通過基準
- 主要定義:
  - 評価: target + アンカー 2 ペア
  - 主目的関数 F の構造: `mean(Sharpe_i) - λ × std(Sharpe_i)`（λ は SSOT）
  - 通過基準は **3 条件 AND**（target_cross 比率 / mean / min）
  - shadow / hard モードの切替（Phase 2 shadow → Phase 6 hard）
  - アンカー定義表（target → 2 アンカー）は debate-synthesis 表をそのまま転載
- SSOT 参照: Phase 2I で `ii_lite.anchors` / `ii_lite.pass_criteria` キーが追加予定
- 関連: `swim-lane.md` / `migration-triggers.md` / `concepts/cross-pair-evaluation-shadow.md`

### 3.6 `statistics.md`（30-100 行）

- 目的: DSR / PBO / Reality Check 仕様（Phase 別実装スケジュール含む）
- 主要定義:
  - DSR: Bailey & López de Prado (2014) — Phase 2 必須
  - PBO-lite: Bailey et al. (2014) — Phase 3
  - RC / SPA: White (2000) / Hansen (2005) — Phase 4
  - block bootstrap CI: Phase 2 必須
  - 各関数の signature は別 TODO（concepts/statistics-dsr-bootstrap.md）に記載
- SSOT 参照: Phase 2I で `statistics.*` キー追加予定
- 関連: `stage-gates.md` / `migration-triggers.md` / `concepts/statistics-dsr-bootstrap.md`

### 3.7 `migration-triggers.md`（30-80 行）

- 目的: (b)×(i) → (ii) 移行条件、shadow→hard、rollback
- 主要定義:
  - (b)×(i) → (ii) hard 移行: PBO / DSR / fold 負比率 / RC p-value の複合 AND/OR
  - (ii-lite) shadow → hard: ウォームアップ / 安定性 / 予測力の 3 条件
  - rollback: hard 化後の急落・極端通過率での自動 shadow 戻し
  - 判定不能時: 永久 shadow 運用
- SSOT 参照: Phase 2I / Phase 6 で `migration_triggers.*` キー追加予定
- 関連: `cross-pair.md` / `statistics.md`

### 3.8 `terminology.md`（30-120 行）

- 目的: 横断用語集
- 主要用語（HTML anchor 付き、各 1-2 行定義）:
  - `#clause` Clause
  - `#composite-score` Composite Score
  - `#directional` Directional Signal
  - `#local-gate` Local Gate
  - `#modulator` Modulator
  - `#tier` Tier
  - `#lane` Lane
  - `#graduation` Graduation
  - `#stage-a`, `#stage-b`, `#stage-c` Stage A/B/C
  - `#walk-forward`, `#is-oos` Walk-Forward / IS / OOS
  - `#dsr` Deflated Sharpe Ratio
  - `#pbo` Probability of Backtest Overfitting
  - `#reality-check` Reality Check
  - `#spa` Superior Predictive Ability
  - `#crn` Common Random Numbers
  - `#tc` Transaction Cost
  - `#ic` Information Coefficient
  - `#ii-lite` (ii-lite) Cross-pair Evaluation
  - `#anchor-pair` Anchor Pair
- 各定義は短く、必要なら学術引用（著者・年・タイトル）

### 3.9 `runbook.md`（30-80 行）

- 目的: autopilot / improve-cycle 運用手順
- 主要定義:
  - autopilot: `/zenigame-fx-autopilot --repeat`
  - improve-cycle: `/zenigame-fx-improve-cycle`
  - Phase 0-4 サイクルの呼び出し順
  - audit-interval / Phase 4A Evaluation
  - 失敗時の復旧手順（簡略）
- SSOT 参照: 現行 `default.yaml` の `improve_cycle.*` を参照
- 関連: `concepts/` 配下の各 stub

### 3.10 `codex-discipline.md`（30-80 行）

- 目的: Codex 合議の C1-C9 解説
- 主要定義:
  - C1-C9 を `AGENTS.md` L56-66 から転載 + 各原則 1-2 行の運用解説
  - SSOT は AGENTS.md。本 doc は運用ガイド
  - レビュアー / 実装者向けの「いつ呼び出すか」の指針
- 関連: `AGENTS.md` / `.claude/skills/zenigame-fx-codex-review/SKILL.md`

## 4. 完了条件

1. 上記 10 ファイルが `docs/alpha_factory/` 直下に存在する
2. 全 doc に `## 用語リンク` 節が存在する（grep `^## 用語リンク` で 10 ヒット）
3. 全 doc に `## SSOT 参照` 節が存在する（grep `^## SSOT 参照` で 10 ヒット）
4. README.md / TODO.md / TODO-closed.md / concepts/* / default.yaml / AGENTS.md は変更されていない
5. 数値直書きが無い（`grep -E '\b(0\.\d+|\d+%|=\s*\d)' docs/alpha_factory/*.md` の出力で「構造的・恒久的な定数」以外がヒットしないこと — composite 式やバージョン番号など構造定数のみ許容）
6. 各 doc の行数: terminology.md ≤ 120 / stage-gates.md ≤ 100 / statistics.md ≤ 100 / primitives.md ≤ 100 / runbook.md ≤ 100 / codex-discipline.md ≤ 100 / その他 ≤ 80

## 5. 実装手順

1. Write ツールで 10 ファイルを順次作成
2. 完了条件 1-6 を bash で順次検証
3. 検証 OK なら git add / commit
4. TODO 登録 → close

## 6. リスクと緩和

| リスク | 緩和策 |
|-------|-------|
| skeleton 化したつもりが詳細仕様に踏み込みすぎ、後続 TODO 議論を縛る | 各 doc の主要定義は「構造・式・分類」に限定し、実装手順や閾値選定理由は書かない |
| terminology.md の anchor 不整合（リンク先未定義） | 全 doc 作成後に anchor 整合を grep で検証 |
| Phase 2I 後に default.yaml キー名が変わると参照キーパスが古くなる | SSOT 参照表に「Phase 2I で追加予定」と注記し、再設計後に追従することを明記 |
| 「構造的・恒久的定数」と「チューニング値」の線引きで判断ぶれ | 概念設計の許可例 / 禁止例リストを SSOT として参照 |
