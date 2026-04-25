---
name: zenigame-fx-autopilot
description: zenigame-fx Alpha Factory の自走ループ（現在地確認→設計→TODO登録→worktree実装→TODOクローズ→マージ→多角監査→繰り返し）
user-invocable: true
argument-hint: "[topic_or_todo_id] [--repeat] [--from phase] [--max-cycles N]  例: /zenigame-fx-autopilot --repeat --max-cycles 100, /zenigame-fx-autopilot T001"
---

# zenigame-fx Alpha Factory 自走ループ（Autopilot）

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| topic_or_todo_id | No | 開始地点の指定。TODO ID（例: T001）なら実装から開始。トピック名なら設計から開始。省略時は TODO.md を見て自動判断 |
| --repeat | No | サイクルをループする。省略時は 1 回のみ実行して終了 |
| --from | No | 開始フェーズの強制指定: survey / design / todo-add / implement / next-cycle（省略時は自動判断） |
| --max-cycles | No | 最大サイクル数（--repeat 時のみ有効。省略時: 5、上限: 200） |
| --skip-consensus | No | Codex 合議スキップモード。実装フェーズでテスト通過をもって完了とみなす |
| --audit-interval | No | 何サイクルごとに多角監査を実施するか（省略時: 2）。1 なら毎サイクル、0 なら監査スキップ |
| --resume | No | 前回の中断から再開する。`devnotes/autopilot-state/current.json` を読み込み、最後に完了した Phase の次から続行 |
| --no-state | No | 状態ファイルへの書き込みを行わない（テスト用途等） |

**設計→TODO 登録→worktree 実装→TODO クローズ→マージ→多角監査→位置確認→次の設計…** を自律的に繰り返す統合オーケストレーションスキル。

---

## 使命（North Star）— 絶対遵守

> **zenigame-fx Alpha Factory の使命は「`config/alpha_factory/default.yaml` → `live_criteria` を全て満たす FX イントラデイ戦略ゲノム個体を 1 つ見つけ出すこと」である。**
>
> Stage C 通過は最低条件。使命達成 = `live_criteria` の全指標（Sharpe, Total PnL, Max Drawdown, Trade Count 範囲）を同時に満たす個体が Cross-pair (ii-lite) 評価も通過した状態での出現。達成後は `live_criteria` の各閾値を引き上げて次の水準を設定する（漸進的目標更新）。

**絶対的な制約**:
- **イントラデイ前提**（オーバーナイト保有を前提にする設計は避ける）
- **ロング・ショート両方向許容**（FX の性質上）
- **スワップ・スプレッドを fitness に反映**（見かけの PnL でなく純利益）

## 思考原則 — 全サイクルに適用

**まず仮説を立てろ。** 何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。仮説なき改善はただの試行錯誤であり、結果から学ぶことができない。

**データに真摯に向き合え。** 成果だけでなく、多様性の変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

**先人の知恵を探せ。** zenigame（日本株 Alpha Factory）の Clause 構造・Stage A/B/C・Codex 合議の設計パターンを参考にする。学術論文（López de Prado, Bailey, Asness, Koza 等）の示唆を活かす。ただし零から移植するのではなく FX 文脈に合わせて適応する。

**機能の名前に立ち返れ。** 名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

**仕組みが機能していない段階で値を弄るな。** 閾値チューニングやフィールド追加（KAIZEN）は、設計の方向性が正しいと確認できてから行え。方向性が間違っているなら、値をいくら調整しても意味はない。設計そのものを見直せ（INNOVATION）。成果が出なければ早期に見切り、次の仮説へ進め。

**因果ループを切断するな。** 「X は Y に影響しない」という主張に出会ったら、間接経路を含む因果ループ全体を追え。観測→判断→介入→GA の結果→観測… のフィードバックループを一部切断する主張は、ほぼ常に間違いである。

## 禁止事項（全フェーズで厳守）

| # | 禁止事項 |
|---|---------|
| 1 | mypy / ruff のエラーを `# type: ignore` や noqa で無根拠に抑制する |
| 2 | テストなしの実装完了（各施策に pytest 必須） |
| 3 | 既存テストの削除・上書き（意図的な書き換えは設計ドキュメントで justify） |
| 4 | `RefreshDatabase` 相当の DB 全削除テスト（トランザクション rollback を使う） |
| 5 | 不必要な複雑化（大規模リファクタリング、独自フレームワーク導入等） |
| 6 | 外部 API・ライブラリを MCP / 公式ドキュメント未確認で使う |
| 7 | **live_criteria の閾値を根拠なしに緩和**（見かけの使命達成を作らない） |
| 8 | **GA をハックして Stage を進める**（fitness 関数の歪曲、評価期間の意味なき延長等） |
| 9 | **取引回数を削減して見かけの成績を上げる**（entry_threshold 過剰引き上げ、max_pos 過度縮小等） |
| 10 | **オーバーナイト保有前提の設計**（スイングトレード化） |
| 11 | **ゲノム archive スキーマ変更時の値伝搬漏れ**（定義→GaConfig→meta→consumer の 4 段接続漏れ） |
| 12 | .env / secrets の git への混入 |

---

## 動作モード

### Single Shot（デフォルト）

`--repeat` なし。1 サイクル（Phase 0→1→2→3→4）を実行して終了。

```
/zenigame-fx-autopilot              ← 自動判断で 1 サイクル
/zenigame-fx-autopilot T001         ← T001 を実装して終了
/zenigame-fx-autopilot clause-migration ← clause-migration を設計→実装して終了
```

### Repeat（自走モード）

`--repeat` あり。サイクルを繰り返し、`max-cycles` に達するか、やることがなくなるまで自走。

```
/zenigame-fx-autopilot --repeat                     ← 最大 5 サイクル自走
/zenigame-fx-autopilot --repeat --max-cycles 100    ← 最大 100 サイクル自走
```

---

## 全体フロー概要

```
┌──────────────────────────────────────────────────────────┐
│                     Autopilot Loop                       │
│                                                          │
│  Phase 0 Survey                                          │
│    docs/alpha_factory/TODO.md / 概念設計 / 詳細設計を確認 │
│         │                                                │
│         ▼                                                │
│  Phase 1 Design ─ /zenigame-fx-alpha-design              │
│    概念設計→Codex レビュー→詳細設計                       │
│         │                                                │
│         ▼                                                │
│  Phase 2 TODO Add ─ /zenigame-fx-todo-add                │
│         │                                                │
│         ▼                                                │
│  Phase 3 Implement ─ /zenigame-fx-implement              │
│    worktree で実装→pytest→Codex レビュー→マージ          │
│         │                                                │
│         ▼                                                │
│  Phase 4 Checkpoint                                      │
│         │                                                │
│         ├── --repeat なし → 最終報告して終了              │
│         │                                                │
│         ▼ --repeat あり                                  │
│  Phase 4A Multi-Perspective Evaluation                   │
│    audit-interval サイクルごとに実行                      │
│         │                                                │
│         └──────── Phase 0 に戻る（次サイクル）───────────┘
└──────────────────────────────────────────────────────────┘
```

---

## 状態保存（State Persistence）

**目的**: サイクル横断で進捗・結果を永続化し、中断・再開・事後追跡を可能にする。

### 保存場所

```
devnotes/autopilot-state/
├── current.json           ← 実行中の状態（常に最新）
└── {started_at}.json      ← 完了・中断後にアーカイブ（履歴）
```

### ファイル構造（`current.json`）

```json
{
  "started_at": "20260421-2100",
  "last_updated_at": "20260421-2130",
  "mode": "repeat",
  "max_cycles": 100,
  "audit_interval": 2,
  "skip_consensus": false,
  "args": { "topic_or_todo_id": null, "from": null },
  "notes": [
    {
      "added_at": "20260421-2100",
      "content": "Phase 2 の FX Alpha Factory 基盤構築完了まで止まらずに進めること"
    }
  ],
  "current_cycle": 2,
  "current_phase": "phase-3",
  "status": "running",
  "cycles": [
    {
      "cycle": 1,
      "phase_completed": "phase-4a",
      "designed_topic": "clause-architecture-foundation",
      "design_tmp_dir": "devnotes/20260421-2100-clause-architecture",
      "added_todo_ids": ["T006"],
      "implemented_todo_ids": ["T005"],
      "merge_commit": "c44b17a",
      "audit_report_path": "devnotes/20260421-2130-audit-cycle-1/audit-report.md",
      "error": null,
      "started_at": "20260421-2100",
      "ended_at": "20260421-2131"
    }
  ]
}
```

`status` は `running` / `completed` / `interrupted` / `failed`。

### メモ（`notes[]`）

ユーザーからの指示・注意事項・終了条件などを自由に蓄積する領域。Autopilot は各サイクル開始時にこれを読み、意思決定に反映する。

**用途**:
- 終了条件の指定（例: 「Phase 2 完了まで止まらない」「T050 まで完了したら止まる」）
- 優先順位の指示（例: 「セキュリティ監査で出た項目を最優先」）
- 避けるべき変更（例: 「`src/db/models.py` を今週は触らない」）
- 進行中の文脈共有

**読み書き**:
- ユーザーが「メモに〜と書いておいて」「autopilot に〜を伝えて」等と指示した場合、`notes[]` に追記する
- 各サイクル Phase 0 の冒頭で `notes[]` を読み、現在地レポートに「### 反映中のメモ」として明示する
- 終了条件系のメモは Phase 4 の継続判断に組み込む
- 達成済みメモは `resolved_at` フィールドを追加して無効化する

**フォーマット**:
```json
{
  "added_at": "YYYYMMDD-HHMM",
  "content": "指示内容をそのまま記録",
  "resolved_at": "YYYYMMDD-HHMM"
}
```

### 書き込みタイミング

| タイミング | 操作 |
|-----------|------|
| Autopilot 起動時 | `current.json` を新規作成（--resume 時は既存読み込み） |
| 各サイクル Phase 0 開始時 | `cycles[]` に新規エントリ追加、`current_cycle` 更新 |
| 各 Phase 完了時 | 当該サイクルの結果フィールド更新、`phase_completed` / `current_phase` 進行 |
| Phase 4A 完了時 | `audit_report_path` を記録 |
| サイクル内エラー発生時 | `error` に内容、`status: "failed"` で中断 |
| 最終報告時 | `status: "completed"` → `{started_at}.json` にアーカイブ、`current.json` 削除 |
| ユーザー中断時 | 次回起動までそのまま残す（--resume で続行可能） |

**`--no-state` 指定時は全書き込みスキップ**。

### 再開（`--resume`）の流れ

1. `devnotes/autopilot-state/current.json` を確認。無ければエラー停止
2. 既存フィールド（mode, max_cycles, audit_interval 等）を復元。CLI 引数で上書きされたらそちら優先
3. 最後の `cycles[]` エントリ:
   - `phase_completed` が `phase-4` 以降 → 次サイクルの Phase 0 から
   - それ以外 → 同サイクルの次 Phase から
4. 再開報告:
```
───────────────────────────────────
Autopilot 再開
前回: サイクル {N}、最終完了 Phase: {phase_completed}
次の開始 Phase: {next_phase}
累計成果: 設計 {X}件 / TODO 登録 {Y}件 / 実装 {Z}件
───────────────────────────────────
```

### 実装ヒント

- 状態ファイル更新は Read → 編集 → Write で行う。原子性が必要なら一時ファイル書き込み後 `mv` でアトミックに置換
- `started_at` は `TZ=Asia/Tokyo date '+%Y%m%d-%H%M'` の形式
- アーカイブ: `mv devnotes/autopilot-state/current.json devnotes/autopilot-state/{started_at}.json`

---

## Phase 0: 現在地確認（Survey）

**目的**: プロジェクトの現状を把握し、次に取るべきアクションを決定する。

### 0-0. 状態ファイルの初期化／復元

- `--resume` 指定時: `current.json` を読み込み、最後の `cycles[]` エントリから開始 Phase を決定
- `--resume` なし & `current.json` が既存: ユーザーに警告（前回未完了）。上書き開始か --resume か確認
- 新規: `devnotes/autopilot-state/current.json` を作成、`status: "running"` で初期メタ情報書き込み

サイクル開始時は `cycles[]` に空エントリを追加し、`current_cycle` と `current_phase: "phase-0"` を更新。

### 0-1. TODO.md の読み込み

```
Read: docs/alpha_factory/TODO.md
```

- **Open**: 未着手の TODO があるか
- **Closed**: 直近で完了したもの
- **Obsoleted**: 廃止

### 0-2. Alpha Factory 概念ドキュメントの確認

```
Read: docs/alpha_factory/README.md
Glob: docs/alpha_factory/*.md
```

プロジェクトの使命・アーキテクチャ・改善サイクルの全体像を把握。

### 0-3. 未設計トピック stub の確認

```
Glob: docs/alpha_factory/concepts/*.md
```

`docs/alpha_factory/concepts/{topic}.md` は「これから設計・実装すべきトピックの stub」を格納する。
各 stub に対応する `devnotes/*-{topic}/` が既に存在する場合は設計済みと判定し、存在しないものが**未設計トピック**となる。

### 0-4. 設計ファイルの確認

```
Glob: devnotes/*/conceptual-design.md
Glob: devnotes/*/detailed-design.md
```

設計済みだが TODO 未登録のもの、設計途中のものを確認。

### 0-5. 現在地の判定と次アクション

以下の優先順位で次のフェーズを決定:

| 優先度 | 状態 | 次のアクション |
|--------|------|---------------|
| 1 | Open TODO（未実装） | → Phase 3（Implement）。優先度の高い TODO から |
| 2 | 詳細設計あり、TODO 未登録 | → Phase 2（TODO Add） |
| 3 | 概念設計あり、詳細設計未完 | → Phase 1（Design）。既存概念設計を引き継ぐ |
| 4 | concepts/ に未設計トピック stub あり | → Phase 1（Design）。stub を概念設計として引き継ぐ |
| 5 | 全て完了 | → 完了報告して終了 |

### 0-6. 現在地レポート

```
## Autopilot サイクル {N}/{max-cycles}: 現在地確認

### プロジェクト状況
- Open TODO: {N}件（{ID 一覧}）
- Closed TODO: {N}件
- 未登録の設計: {N}件（{ディレクトリ一覧}）
- 未設計のトピック: {N}件（{ファイル一覧}）

### 反映中のメモ（notes[] より）
- {content 1}
- {content 2}

### 次のアクション
→ Phase {X}（{フェーズ名}）: {具体的に何をするか}
  対象: {TODO ID or トピック名}
  理由: {なぜこれを次にやるか}
```

---

## Phase 1: 設計（Design）

### 1-1. トピックの決定

Phase 0 の判定結果に基づき、設計対象トピックを決定:

1. `topic_or_todo_id` 引数で指定されたトピック
2. 概念設計途中のもの
3. `docs/alpha_factory/` の未設計トピック（Open TODO から逆引きできるもの、または master-plan.md 参照）

### 1-2. /zenigame-fx-alpha-design のバックグラウンド呼び出し

**Agent ツール（`run_in_background: true`）で設計スキルを起動する。**

Agent プロンプト:
```
/zenigame-fx-alpha-design {topic} [{conceptual_design_path}]

設計が完了したら、以下を報告せよ:
- 概念設計ファイルパス
- 詳細設計ファイルパス
- 設計の APPROVED ステータス（Round 数含む）
- 施策一覧（タイトル・テーマ・優先度・モード）
```

**バックグラウンド完了通知を受けたら**、結果を確認して次フェーズへ。
待機中のユーザー報告:
```
設計をバックグラウンドで実行中です（/zenigame-fx-alpha-design {topic}）
完了通知を受け次第、Phase 2（TODO 登録）に進みます。
```

### 1-3. フェーズ完了確認

- 設計が APPROVED になったことを確認
- `tmp_dir` と施策情報を次フェーズに引き継ぐ
- 失敗時はエラー内容を報告してサイクルを中断

### 1-4. 状態ファイル更新

`current.json` の当該サイクルに `designed_topic` / `design_tmp_dir` を記録、`phase_completed: "phase-1"`, `current_phase: "phase-2"`。

---

## Phase 2: TODO 登録（TODO Add）

### 2-1. 設計情報の抽出

詳細設計書から以下を抽出:
- **title**: 施策タイトル
- **theme**: テーマ分類（ga-architecture / primitives / stage-gate / cross-pair / statistics / data-ingest / swim-lane / skill-port / infrastructure / general）
- **summary**: 30 文字以内の概要
- **priority**: Critical / High / Medium / Low
- **mode**: 実装モード（詳細設計の推奨モード）

### 2-2. /zenigame-fx-todo-add のバックグラウンド呼び出し

```
/zenigame-fx-todo-add "{title}" {theme} "{summary}" {tmp_dir_name} {priority} {mode}

完了したら登録された TODO ID を報告せよ。
```

### 2-3. TODO ID の記録

バックグラウンド結果から TODO ID（例: `T002`）を取得し、次フェーズに引き継ぐ。

### 2-4. 状態ファイル更新

`current.json` の当該サイクルの `added_todo_ids` に追加、`phase_completed: "phase-2"`, `current_phase: "phase-3"`。

---

## Phase 3: 実装（Implement）

### 3-1. 実装対象の決定

**TODO ID が引き継がれている場合**: そのまま使用。

**Phase 0 から直接来た場合**: Open TODO から優先度の高いものを選択。
- Critical > High > Medium > Low
- 同一優先度なら追加日が古いものを優先

### 3-2. /zenigame-fx-implement のバックグラウンド呼び出し

**Agent ツール（`run_in_background: true`, `isolation: "worktree"`）で起動。**

Agent プロンプト:
```
/zenigame-fx-implement {todo_id} [--skip-consensus]

実装完了後、以下を報告せよ:
- マージコミットハッシュ
- 変更ファイル数
- テスト結果（pytest passed / failed）
- Codex レビュー結果（APPROVED / SKIPPED）
- TODO クローズ結果
- コンフリクトの有無と解消結果
```

このスキルが以下を全て実行する:
- worktree 作成
- 実装 & pytest
- Codex レビュー合議
- コミット
- TODO クローズ（/zenigame-fx-todo-close）
- main マージ
- worktree クリーンアップ

### 3-3. 実装結果の記録

マージコミットハッシュ、テスト結果、レビュー結果を取得・記録。失敗時はエラー報告しサイクル中断。

### 3-4. 状態ファイル更新

`current.json` に `implemented_todo_ids`、`merge_commit` 追加、`phase_completed: "phase-3"`, `current_phase: "phase-4"`。失敗時 `error` に内容、`status: "failed"`。

---

## Phase 4: チェックポイント（Checkpoint）

### 4-1. サイクル完了報告

```
## Autopilot サイクル {N}/{max-cycles} 完了

### 今サイクルの成果
- 設計: {トピック名}（APPROVED）
- TODO: {ID} 登録済み
- 実装: {ID} → main マージ済み
  - 変更ファイル: {N} files
  - テスト: {結果}
  - コミット: {hash}

### 残タスク
- Open TODO: {N}件（{ID 一覧}）
- 未登録の設計: {N}件
- 未設計のトピック: {N}件
```

### 4-2. 継続判断

`current.json` の当該サイクルエントリの `phase_completed: "phase-4"` と `ended_at` を書き込む。

**--repeat なし**: 状態ファイルを `status: "completed"` にしてアーカイブ、最終報告を出力して**即座に終了**。

**--repeat あり**: 以下を**全て**満たせば次サイクルへ:
1. `max-cycles` に達していない
2. 次にやるべきことがある（Open TODO / 未登録設計 / 未設計トピックのいずれか）
3. 前サイクルでエラーが発生していない
4. `notes[]` の終了条件系メモが該当しない

**いずれかを満たさない**: 最終報告を出力して終了。

### 4-3. 次サイクルへの遷移（--repeat 時のみ）

```
サイクル番号 % audit-interval == 0 → Phase 4A（多角監査）
それ以外 → Phase 0（現在地確認）に直行
```

---

## Phase 4A: 多角監査（Multi-Perspective Evaluation）

**目的**: 個々の TODO を片付ける「木を見る」作業の合間に、「森を見る」視点で全体の健全性を点検する。

**実行タイミング**: `audit-interval`（デフォルト 2）サイクルごと。`audit-interval=0` でスキップ。

### 4A-1. 監査の準備

```bash
TZ=Asia/Tokyo date '+%Y%m%d-%H%M'
```

保存先: `devnotes/{YYYYMMDD-HHMM}-audit-cycle-{N}/`

### 4A-2. 五つの監査観点（バックグラウンド並列実行）

**5 つのバックグラウンド Agent を同時起動**。各 Agent は独立して点検、全完了後に統合レポート作成。

#### 観点 1: 使命整合性監査（Mission Alignment）

直近のサイクルで実装した変更が使命から逸脱していないか。

**手順**:
1. `git log --oneline -10` で直近コミット確認
2. `git diff {hash}~1 {hash} --stat` で変更把握
3. 判定:
   - この変更は「live_criteria を満たすゲノム探索」または「改善サイクル実行能力」に寄与しているか?
   - 使命と無関係な機能追加・過剰な技術的こだわりはないか?
   - Stage 評価の意味なき延長、閾値緩和、取引回数削減によるごまかしはないか?

**出力**:
```
### 使命整合性: {OK / DRIFT_DETECTED}
- {各コミットの判定}
- 逸脱があれば: 修正提案 or 次サイクルでの設計課題として記録
```

#### 観点 2: 技術的負債監査（Tech Debt）

**手順**:
1. `uv run mypy src/ 2>&1 | tail -20` — 型エラー確認
2. `uv run ruff check src/ tests/ 2>&1 | tail -20` — lint 確認
3. `uv run pytest tests/ -q 2>&1 | tail -10` — テスト健全性
4. TODO コメント・FIXME・HACK の増減:
   ```
   Grep: TODO|FIXME|HACK|XXX（src/ と tests/ を対象）
   ```
5. 依存パッケージ:
   ```bash
   uv tree --outdated 2>&1 | head -20
   ```

**出力**:
```
### 技術的負債: {CLEAN / DEBT_FOUND}
- mypy: {OK / N errors}
- ruff: {OK / N warnings}
- pytest: {N passed, M failed}
- TODO/FIXME: {N 箇所}（増減: +X / -X）
- 依存: {outdated があれば}
```

#### 観点 3: コード構造一貫性監査（Architecture Consistency）

**手順**:
1. `src/alpha_factory/` 配下のモジュール境界が設計通りか
2. プリミティブが `_registry.py` に正しく登録されているか
3. GENOMES_SCHEMA の定義 → consumer 参照の 4 段接続が健全か
4. archive の書き込み（`_create_row_template`, `collect_stage_*`, `flush`）に値伝搬漏れがないか
5. `scripts/alpha_factory/` 配下のスクリプトが `src/alpha_factory/` に依存している方向であるか（逆依存なし）

**出力**:
```
### コード構造一貫性: {CONSISTENT / INCONSISTENCY_FOUND}
- {発見事項}
- 改善が必要な場合: 次サイクルの TODO 候補として記録
```

#### 観点 4: セキュリティ監査（Security）

**手順**:
1. 直近コミットの変更ファイルで:
   - `.env` / secrets の混入確認（特に OANDA_API_TOKEN, FRED_API_KEY）
   - ハードコードされた API キー・パスワードの検索
   - SQL インジェクションのリスク（sqlalchemy text() の生 SQL など）
   - 外部 API 呼び出しのエラーハンドリング漏れ
2. `.env.example` と `.env` のキー対応整合
3. `.gitignore` に `.env` が含まれていること確認

**出力**:
```
### セキュリティ: {SECURE / RISK_FOUND}
- {発見事項}
- Critical な場合: 即座に TODO 登録を推奨
```

#### 観点 5: ドキュメント鮮度監査（Documentation Freshness）

**手順**:
1. 直近コミットで変更されたファイルに対応するドキュメント（`docs/alpha_factory/`）が更新されているか
2. `AGENTS.md` / `CLAUDE.md` が最新状態か
3. 新規追加されたプリミティブが `docs/alpha_factory/primitives.md` に記載されているか
4. `config/alpha_factory/default.yaml` の変更が `docs/alpha_factory/stage-gates.md` 等に反映されているか

**出力**:
```
### ドキュメント鮮度: {FRESH / STALE_FOUND}
- {乖離があれば列挙}
- 更新が必要な場合:
  - 軽微: 次サイクルで `/zenigame-fx-update-docs` を実行
  - 重要: 即座に修正
```

### 4A-3. 監査結果の統合レポート

```
## 多角監査レポート（サイクル {N} 完了時点）

| 観点 | 判定 | 要対応 |
|------|------|--------|
| 使命整合性 | {OK/DRIFT} | {なし / 内容} |
| 技術的負債 | {CLEAN/DEBT} | {なし / 内容} |
| コード構造一貫性 | {OK/INCONSISTENCY} | {なし / 内容} |
| セキュリティ | {SECURE/RISK} | {なし / 内容} |
| ドキュメント鮮度 | {FRESH/STALE} | {なし / 内容} |

### 監査起因の新規 TODO 候補
{監査で発見された問題を、次サイクルで設計・実装すべき TODO 候補として列挙}
- [{priority}] {タイトル}: {概要}
```

保存: `devnotes/{YYYYMMDD-HHMM}-audit-cycle-{N}/audit-report.md`

`current.json` の当該サイクルに `audit_report_path` を記録、`phase_completed: "phase-4a"`。

### 4A-4. 監査結果の反映

1. **Critical な発見**（セキュリティリスク等）: 次サイクルの Phase 0 で最優先 TODO 候補
2. **ドキュメント陳腐化**: 次サイクルの Phase 0 で `/zenigame-fx-update-docs` 実行判断
3. **使命ドリフト**: 次サイクルの設計時に方向修正
4. **技術的負債**: 深刻であれば専用のリファクタリング TODO を起票

→ Phase 0 に戻って次サイクル。

---

## 最終報告

全サイクル完了後（または中断時・Single Shot 完了時）に出力する。

**先に状態ファイルを確定**:
- 正常完了: `status: "completed"` → `devnotes/autopilot-state/{started_at}.json` にアーカイブ
- 中断: `status: "interrupted"`、`current.json` はそのまま残す
- エラー停止: `status: "failed"`、`current.json` そのまま

```
## Autopilot 完了

### 実行サマリー
- モード: {Single Shot / Repeat}
- 実行サイクル数: {N}/{max-cycles}
- 完了 TODO: {ID 一覧}
- 新規設計: {トピック一覧}
- 新規 TODO: {ID 一覧}
- 多角監査: {実施回数}回

### 成果物
| サイクル | フェーズ | 対象 | 結果 |
|---------|---------|------|------|
| 1 | Design | {topic} | APPROVED |
| 1 | TODO Add | {ID} | 登録済み |
| 1 | Implement | {ID} | main マージ済み |
| 2 | Evaluation | - | {判定サマリー} |

### 残タスク
- Open TODO: {N}件（{ID 一覧}）
- 未登録の設計: {N}件
- 未設計のトピック: {N}件

### 監査サマリー（--repeat 時のみ）
- 使命整合性: {全サイクル通しての傾向}
- 技術的負債: {増減トレンド}
- 注意事項: {次回起動時に意識すべきこと}

### 次のアクション提案
- {何をすべきか}
```

---

## 引数による開始地点の制御

### topic_or_todo_id の解釈

| 値の形式 | 解釈 | 開始フェーズ |
|---------|------|------------|
| `T{NNN}` | TODO ID → 実装から開始 | Phase 3 |
| その他の文字列 | トピック名 → 設計から開始 | Phase 1 |
| 省略 | 自動判断 | Phase 0 |

### --from による強制指定

| 値 | 開始フェーズ |
|-----|------------|
| `survey` | Phase 0（デフォルト） |
| `design` | Phase 1 |
| `todo-add` | Phase 2 |
| `implement` | Phase 3 |
| `next-cycle` | Phase 4 → Phase 0 |

---

## エラーハンドリング

### スキル呼び出し失敗

1. エラー内容をユーザーに報告
2. **自動リカバリーを試みない**（サブスキル内でリトライ済み）
3. 現在のサイクルを中断し、最終報告を出力

### 設計ファイル不整合

- 概念設計あり／詳細設計なし → Phase 1 で概念設計を引き継いで続行
- TODO.md の設計リンク破損 → ユーザーに報告して手動修正依頼

### max-cycles の安全弁

- Single Shot: 常に 1 サイクル
- Repeat: デフォルト 5、上限 200（200 を超える指定は 200 に切り詰め）
- 各サイクル開始時に残サイクル数を表示

---

## 使用例

### 例 1: 1 回だけ実行
```
/zenigame-fx-autopilot
→ 現在地確認→最優先タスクを 1 つ設計→実装→マージして終了
```

### 例 2: 特定 TODO を実装
```
/zenigame-fx-autopilot T001
→ T001 を worktree で実装→マージして終了
```

### 例 3: 自走モード
```
/zenigame-fx-autopilot --repeat
→ 最大 5 サイクル、2 サイクルごとに多角監査を挟みながら自走
```

### 例 4: フル自走
```
/zenigame-fx-autopilot --repeat --max-cycles 100 --audit-interval 2
→ 最大 100 サイクル、2 サイクルごとに監査付きで自走
```

### 例 5: 設計から開始して自走
```
/zenigame-fx-autopilot clause-architecture-foundation --repeat --max-cycles 50
→ 当該トピックの設計から始めて、完了後は次のタスクへ自走
```

---

## バックグラウンド実行方針

### 原則

**重い処理はバックグラウンド Agent に委譲し、Autopilot 本体は判断・進行管理に専念する。**

| フェーズ | 実行方式 | 理由 |
|---------|---------|------|
| Phase 0（Survey） | **フォアグラウンド** | 軽量な読み取りのみ |
| Phase 1（Design） | **バックグラウンド Agent** | Codex 合議を含む重い処理 |
| Phase 2（TODO Add） | **バックグラウンド Agent** | 設計ファイル確認・TODO.md 編集 |
| Phase 3（Implement） | **バックグラウンド Agent + worktree 分離** | 最も重い処理 |
| Phase 4（Checkpoint） | **フォアグラウンド** | 軽量な集計・判断 |
| Phase 4A（Evaluation） | **バックグラウンド Agent 並列 × 5** | 5 観点は独立 |

### バックグラウンド起動時の共通ルール

1. **Agent ツールの `run_in_background: true` を使用**
2. Phase 3 では追加で **`isolation: "worktree"`** を指定
3. 起動後、**ユーザーに状況を報告**
4. **完了通知を受けたら結果を確認**し次フェーズへ。ポーリング・スリープはしない
5. 失敗時は**エラー報告**してサイクル中断

---

## 注意事項

- **このスキルは他のスキルのオーケストレーターである。** 設計・実装・TODO 管理のロジックは各サブスキルに委譲し、自身は判断・呼び出し・進捗管理・監査に徹する
- **Phase 0（Survey）は毎サイクル実行。** 外部変更（ユーザーによる TODO 追加・設計変更等）も拾うため
- **多角監査は「森を見る」ための仕組み。** 個々の TODO の品質はサブスキル（Codex レビュー等）が保証する
- **サブスキルの出力を信頼する。** APPROVED / 完了を報告したら再検証しない
- **ユーザーへの報告は各 Phase 完了時に行う。** サイレントに進行しない
- **バックグラウンド Agent の完了を待つ間、ポーリングやスリープをしない**

---

## ⚠ CRITICAL: ループ継続の絶対ルール（コンテキスト圧縮後も必ず従うこと）

**このセクションはスキルファイルの末尾に配置されている。コンテキストが圧縮・要約されても、このルールは失われてはならない。**

### `--repeat` が指定されている場合、1 サイクルで終了してはならない

`--repeat` モードでは、以下の**停止条件のいずれかを満たすまで**、必ず Phase 0 に戻って次のサイクルを開始すること:

1. `max-cycles` に達した
2. やることが何もない（Open TODO = 0、未登録設計 = 0、未設計トピック = 0）
3. エラーが発生してリカバリー不能
4. `notes[]` の終了条件系メモに合致した

**上記 4 つ以外の理由で停止してはならない。**

### サイクル終了時の自己チェック

各サイクルの Phase 4（Checkpoint）完了時に、必ず確認:

```
□ --repeat が指定されているか？
  → YES: 停止条件を満たしているか？
    → 停止条件を満たしていない → Phase 0 に戻る（次サイクル開始）
    → 停止条件を満たしている → 最終報告を出力して終了
  → NO (Single Shot): 最終報告を出力して終了
```

### コンテキストが長くなった場合の対処

会話が長くなりコンテキストが圧縮された場合でも:

1. **このスキルファイルを `Read` ツールで再読み込み**して、ループ継続判断を行う
2. 「前のサイクルで何をしたか覚えていない」は停止理由にならない。Phase 0 で現在地を再確認すれば十分
3. 迷ったら **Phase 0（Survey）に戻る**。現在地確認は常に安全な選択肢

### ループ状態の明示

各サイクル開始時に以下を必ず出力:

```
───────────────────────────────────
Autopilot サイクル {N}/{max-cycles} 開始
モード: Repeat
残サイクル: {max-cycles - N + 1}
───────────────────────────────────
```

これにより、コンテキスト圧縮後も自身がループ中であることを認識できる。
