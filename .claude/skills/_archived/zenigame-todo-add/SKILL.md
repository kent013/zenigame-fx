---
name: zenigame-todo-add
description: Alpha Factory TODOリストにタスクを追加（概念設計・詳細設計の存在確認あり、なければ Reject）
argument-hint: "[title] [theme] [summary] [devnotes_dir] [--priority P] [--mode M] [--target T] [--trigger_condition C]"
---

# Alpha Factory TODO 追加

TODOリスト `docs/alpha-factory/TODO.md` に改善タスクを追加する。
**概念設計・詳細設計の両ファイルが存在することを確認してから追加する。存在しない場合は Reject する。**

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `title` ($1) | Yes | TODOのタイトル（簡潔な改善名） |
| `theme` ($2) | Yes | テーマ分類: `speed` / `live-trading` / `performance` / `japan-market` / `signal-predictive-power` / `general` |
| `summary` ($3) | Yes | 30文字以内の実装概要（何をするか一言で） |
| `devnotes_dir` ($4) | Yes | devnotesディレクトリ名（例: `20260221-0100-topic`）。`conceptual-design.md` と `detailed-design.md` が配置されていることを確認 |
| `--priority` | No | 優先度: `Critical` / `High` / `Medium` / `Low`（省略時: `Medium`） |
| `--mode` | No | 実装モード: `incremental`（改善ループに自動組み込み）/ `standalone`（単独実装セッションが必要）（省略時: `incremental`） |
| `--target` | No | 追加先: `open`（デフォルト、即実装可能）/ `conditional`（条件付き待機。`--trigger_condition` 必須） |
| `--trigger_condition` | No | トリガー条件（`--target conditional` 時のみ必須）。例: `'Stage C突破率 > 5%'` `'GA実行時間 < 30min'` |

---

## 実装モードの説明

| モード | 説明 | 向いているケース |
|--------|------|----------------|
| **incremental** | `zenigame-improve-cycle` が自動選定・実装 | 単一コンポーネントの変更、他施策との競合リスクが低い、1 Runで並走できる |
| **standalone** | 改善ループからは除外。ユーザーが個別に実装セッションを開始 | 複数コンポーネントの協調変更、大規模変更、慎重な事前確認が必要 |

**判断に迷ったら**: 「1 Runで他の施策と並走できるか？」→ YES なら `incremental`、NO なら `standalone`

## テーマ分類の説明

| テーマ | 向いているケース |
|--------|----------------|
| `speed` | GA実行速度・並列化・キャッシュ・ホットパス最適化 |
| `live-trading` | 執行品質・スリッページ・市場インパクト・コスト現実性・ライブ運用 |
| `performance` | シグナル予測力・GA探索・フィットネス・Stage C突破・プリミティブ品質 |
| `japan-market` | 東証固有の市場構造・値動き特性・制度対応・時間帯特性・流動性条件 |
| `general` | 上記に分類されない汎用改善 |

---

## 手順

### Step 1: 設計ファイルの存在確認

`devnotes_dir` からファイルパスを構成し、それぞれ `Read` ツールで読み込みを試みる:

```
conceptual_design_path = devnotes/{devnotes_dir}/conceptual-design.md
detailed_design_path   = devnotes/{devnotes_dir}/detailed-design.md

Read: {conceptual_design_path}
Read: {detailed_design_path}
```

- **どちらかでもファイルが存在しない場合**（読み込みエラーが発生した場合）:

  ```
  ❌ REJECT

  以下のファイルが存在しません:
  - {存在しないファイルのパス}

  TODO への追加には概念設計・詳細設計の両ファイルが必要です。
  先に /zenigame-alpha-design スキルで設計を完成させてから再度 /zenigame-todo-add を実行してください。
  ```

  **ここで処理を終了する（TODO.md は変更しない）**。

- 両方のファイルが正常に読み込めた場合、Step 2 に進む。

### Step 2: 引数のバリデーション

- `theme` が `speed` / `live-trading` / `performance` / `japan-market` / `signal-predictive-power` / `general` のいずれかでない場合はエラー
- `summary` が30文字を超える場合は警告を表示し、30文字以内に短縮するよう案内する
- `priority` が省略された場合は `Medium`
- `mode` が省略された場合は `incremental`
- `mode` が `incremental` / `standalone` 以外の場合はエラーを表示して終了
- `target` が省略された場合は `open`
- `target` が `conditional` の場合、`trigger_condition` が指定されていなければエラー:
  ```
  ❌ ERROR
  target=conditional には trigger_condition が必須です。
  例: /zenigame-todo-add "title" speed "summary" devnotes/... --target conditional --trigger_condition "Stage C突破率 > 5%"
  ```
- `target` が `open` / `conditional` 以外の場合はエラーを表示して終了

### Step 3: ID 採番と日時取得

`scripts/todo_manager.sh` を使って次の ID を採番する（`Read` でファイルを読み込む必要なし）:

```bash
next_id=$(bash scripts/todo_manager.sh next-id)
today=$(date '+%Y-%m-%d %H:%M')
```

### Step 4: テーブルへの行追記

`scripts/todo_manager.sh` で TODO.md に直接行を追加する（`Edit` ツール不要）。

#### target = open（デフォルト）の場合:

```bash
bash scripts/todo_manager.sh add "{next_id}" "{title}" "{theme}" "{summary}" "{priority}" "{mode}" "[設計](devnotes/{devnotes_dir}/)" "{today}"
```

#### target = conditional の場合:

```bash
bash scripts/todo_manager.sh add-conditional "{next_id}" "{title}" "{theme}" "{summary}" "{trigger_condition}" "{priority}" "{mode}" "[設計](devnotes/{devnotes_dir}/)" "{today}"
```

### Step 5: 完了報告

#### target = open の場合:
```
✅ TODO 追加完了

ID: {ID}
タイトル: {title}
テーマ: {theme}
概要: {summary}
優先度: {priority}
実装モード: {mode}
設計: devnotes/{devnotes_dir}/
追加日時: {today}

{mode が incremental の場合}
→ 次回の /zenigame-improve-cycle 実行時に自動で選定候補になります。

{mode が standalone の場合}
→ 改善ループからは除外されます。実装する際はユーザーが個別にセッションを開始してください。
```

#### target = conditional の場合:
```
✅ TODO 追加完了（Conditional）

ID: {ID}
タイトル: {title}
テーマ: {theme}
概要: {summary}
トリガー条件: {trigger_condition}
昇格時優先度: {priority}
実装モード: {mode}
設計: devnotes/{devnotes_dir}/
追加日時: {today}

→ Conditionalテーブルに追加しました。トリガー条件が成立すると plan-and-design Phase A-1 で自動的にOpenへ昇格します。
```

---

## 注意事項

- TODO.md の操作は `scripts/todo_manager.sh` 経由で行う（`Read` / `Edit` ツールでのファイル直接操作は不要）
- 設計列は `[設計](devnotes/{devnotes_dir}/)` 形式でディレクトリリンクとして記録する（conceptual-design.md / detailed-design.md は固定ファイル名）
- `summary` はテーブルが読みやすいよう30文字以内に収めること
