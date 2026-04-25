---
name: zenigame-fx-todo-close
description: Alpha Factory TODO リストのタスクを完了マークまたは廃止マーク（Open→Closed/Obsoleted 移動）
argument-hint: "<todo_id> [run_id] [--obsolete --reason <reason>]"
---

# Alpha Factory FX TODO クローズ / 廃止

指定した TODO を `docs/alpha_factory/TODO.md` の Open / Conditional テーブルから削除し、`docs/alpha_factory/TODO-closed.md` の **Closed** または **Obsoleted** テーブルへ移動する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `todo_id` ($1) | Yes | 対象 TODO の ID（例: T001） |
| `run_id` ($2) | No | 実装完了 Run ID（close 時のみ、省略可） |
| `--obsolete` | No | 廃止モード。省略時は close |
| `--reason` | No | 廃止理由（--obsolete 時は必須） |

- `action` 省略 or `close`: Open → **Closed**（実装完了）
- `action` = `obsolete`: Open or Conditional → **Obsoleted**

---

## 手順

### Step 1: 引数バリデーション

`action` = `obsolete` の場合、`reason` が指定されていなければエラー:
```
❌ ERROR

action=obsolete には reason が必須です。
例: /zenigame-fx-todo-close T035 --obsolete --reason "設計陳腐化"
```
**ここで処理を終了**。

### Step 2: 今日の日時を取得

```bash
today=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')
```

### Step 3: todo_manager.py で一括実行

#### action = close（デフォルト）:

```bash
result=$(uv run python scripts/alpha_factory/todo_manager.py close "{todo_id}" --closed-at "{today}" --run-id "{run_id}")
```

`run_id` が省略された場合は `--run-id -` を指定する。

#### action = obsolete:

```bash
result=$(uv run python scripts/alpha_factory/todo_manager.py obsolete "{todo_id}" --obsoleted-at "{today}" --reason "{reason}")
```

**行が見つからない場合**（exit code 1）:
```
❌ ERROR

{todo_id} は Open / Conditional リストに存在しません。
```
**ここで処理を終了**（TODO.md は変更しない）。

### Step 4: 完了報告

#### close の場合:
```
✅ TODO クローズ完了

ID: {todo_id}
タイトル: {title}
テーマ: {theme}
優先度: {priority}
完了日時: {today}
Run ID: {run_id または "-"}

docs/alpha_factory/TODO.md（Open 削除）と TODO-closed.md（Closed 追加）を更新しました。
```

#### obsolete の場合:
```
✅ TODO 廃止完了

ID: {todo_id}
タイトル: {title}
テーマ: {theme}
優先度: {priority}
廃止日時: {today}
理由: {reason}

docs/alpha_factory/TODO.md（Open/Conditional 削除）と TODO-closed.md（Obsoleted 追加）を更新しました。
```

---

## 注意事項

- TODO.md / TODO-closed.md の操作は `scripts/alpha_factory/todo_manager.py` 経由で行う（Read / Edit でのファイル直接操作は不要）
- `obsolete` は Open と Conditional の両テーブルを検索（todo_manager.py が自動判定）
- `close` は Open のみ対象（Conditional は直接 close 不可、先に昇格が必要）
