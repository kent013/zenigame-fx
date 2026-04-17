---
name: zenigame-todo-close
description: Alpha Factory TODOリストのタスクを完了マークまたは廃止マーク（Open→Closed/Obsoleted移動）
argument-hint: "<todo_id> [run_id] [--obsolete --reason <reason>]"
---

# Alpha Factory TODO クローズ / 廃止

指定した TODO を `docs/alpha-factory/TODO.md` の Open / Conditional テーブルから削除し、`docs/alpha-factory/TODO-closed.md` の **Closed** または **Obsoleted** テーブルへ移動する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `todo_id` ($1) | Yes | 対象TODOのID（例: T001） |
| `run_id` ($2) | No | 実装が完了したRun ID（例: run_20260221_123456）。close時のみ使用。省略時は空欄 |
| `--obsolete` | No | 廃止モード。省略時はclose（Open→Closed）。指定時はOpen/Conditional→Obsoleted |
| `--reason` | No | 廃止理由（--obsolete時は必須。例: 設計陳腐化。nsga2.pyが+31%膨張し適用不可） |

- `action` 省略 or `close`: Open → **Closed**（実装完了）※ Open のみ対象
- `action` = `obsolete`: Open or Conditional → **Obsoleted**（設計陳腐化・条件不要化等）

---

## 手順

### Step 1: 引数バリデーション

`action` = `obsolete` の場合、`reason` が指定されていなければエラー:
```
❌ ERROR

action=obsolete には reason が必須です。
例: /zenigame-todo-close T035 --obsolete --reason "設計陳腐化。nsga2.pyが+31%膨張"
```
**ここで処理を終了する。**

### Step 2: 今日の日時を取得

```bash
today=$(date '+%Y-%m-%d %H:%M')
```

### Step 3: scripts/todo_manager.sh で一括実行

`scripts/todo_manager.sh` が対象行の検索・抽出・削除・移動を全て行う（`Read` / `Edit` ツール不要）。

#### action = close（デフォルト）の場合:

```bash
result=$(bash scripts/todo_manager.sh close "{todo_id}" "{today}" "{run_id}")
```

`run_id` が省略された場合は引数を省略する（スクリプトが `-` をデフォルト使用）。

#### action = obsolete の場合:

```bash
result=$(bash scripts/todo_manager.sh obsolete "{todo_id}" "{today}" "{reason}")
```

**行が見つからない場合**（exit code 1）:
```
❌ ERROR

{todo_id} は Open / Conditional リストに存在しません。

- すでに Closed/Obsoleted になっている可能性があります
- ID の指定が間違っている可能性があります（現在の Open / Conditional リストを確認してください）
```
**ここで処理を終了する（TODO.md は変更しない）**。

**成功時**: `result` に移動された行がパイプ区切りで返される。ここからタイトル・テーマ等を抽出して Step 7 の報告に使用する。

### Step 7: 完了報告

#### close の場合:
```
✅ TODO クローズ完了

ID: {todo_id}
タイトル: {タイトル}
テーマ: {テーマ}
概要: {概要}
優先度: {優先度}
完了日時: {today}
Run ID: {run_id（指定なしの場合は"-"）}

docs/alpha-factory/TODO.md（Open削除）と TODO-closed.md（Closed追加）を更新しました。
```

#### obsolete の場合:
```
✅ TODO 廃止完了

ID: {todo_id}
タイトル: {タイトル}
テーマ: {テーマ}
優先度: {優先度}
廃止日時: {today}
理由: {reason}

docs/alpha-factory/TODO.md（Open削除）と TODO-closed.md（Obsoleted追加）を更新しました。
```

---

## 注意事項

- TODO.md / TODO-closed.md の操作は `scripts/todo_manager.sh` 経由で行う（`Read` / `Edit` ツールでのファイル直接操作は不要）
- Open / Conditional テーブルが空になった場合、テーブルのヘッダー行は残す（スクリプトが自動維持）
- Closed/Obsoleted テーブルは `docs/alpha-factory/TODO-closed.md` に格納されている
- `obsolete` は Open と Conditional の両テーブルを検索する（`todo_manager.sh` が自動判定）
- `close` は Open テーブルのみが対象（Conditional 項目は直接クローズ不可。先に昇格が必要）
