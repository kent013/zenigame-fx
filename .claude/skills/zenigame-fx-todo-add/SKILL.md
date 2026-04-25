---
name: zenigame-fx-todo-add
description: Alpha Factory TODO リストにタスクを追加（概念設計・詳細設計の存在確認あり、なければ Reject）
argument-hint: "[title] [theme] [summary] [devnotes_dir] [--priority P] [--mode M] [--target T] [--trigger_condition C]"
---

# Alpha Factory FX TODO 追加

TODO リスト `docs/alpha_factory/TODO.md` に改善タスクを追加する。
**概念設計・詳細設計の両ファイルが存在することを確認してから追加する。存在しない場合は Reject する。**

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `title` ($1) | Yes | TODO のタイトル |
| `theme` ($2) | Yes | テーマ分類: `ga-architecture` / `primitives` / `stage-gate` / `cross-pair` / `statistics` / `data-ingest` / `swim-lane` / `skill-port` / `infrastructure` / `general` |
| `summary` ($3) | Yes | 30 文字以内の実装概要 |
| `devnotes_dir` ($4) | Yes | devnotes ディレクトリ名（例: `20260421-2100-topic`） |
| `--priority` | No | `Critical` / `High` / `Medium` / `Low`（省略時: `Medium`） |
| `--mode` | No | `incremental` / `standalone`（省略時: `incremental`） |
| `--target` | No | `open` / `conditional`（省略時: `open`） |
| `--trigger_condition` | No | `--target conditional` 時のみ必須 |

---

## 実装モード

| モード | 説明 | 向いているケース |
|--------|------|----------------|
| **incremental** | autopilot / improve-cycle が自動選定・実装 | 単一コンポーネントの変更、他施策との競合リスクが低い |
| **standalone** | 改善ループから除外。ユーザーが個別に実装 | 複数コンポーネント協調変更、大規模変更 |

## テーマ分類

| テーマ | 向いているケース |
|--------|----------------|
| `ga-architecture` | GA 構造・Genome 表現・Clause 構造変更 |
| `primitives` | プリミティブ追加・変更・ペア特化の実装 |
| `stage-gate` | Stage A/B/C ゲート、通過率制御 |
| `cross-pair` | (ii-lite) 評価、アンカーペア戦略 |
| `statistics` | DSR / PBO / Reality Check 等の統計検定 |
| `data-ingest` | OANDA / FRED / 外部データ取り込み |
| `swim-lane` | スイムレーン・マネージャ、Graduation lane |
| `skill-port` | zenigame-fx-* skill の移植・改修 |
| `infrastructure` | DB / cache / migration / 運用基盤 |
| `general` | 上記に分類されない汎用改善 |

---

## 手順

### Step 1: 設計ファイルの存在確認

```
conceptual_design_path = devnotes/{devnotes_dir}/conceptual-design.md
detailed_design_path   = devnotes/{devnotes_dir}/detailed-design.md

Read: {conceptual_design_path}
Read: {detailed_design_path}
```

- **どちらかでもファイルが存在しない場合**:
  ```
  ❌ REJECT

  以下のファイルが存在しません:
  - {存在しないファイルのパス}

  TODO への追加には概念設計・詳細設計の両ファイルが必要です。
  先に /zenigame-fx-alpha-design で設計を完成させてから再度実行してください。
  ```
  **ここで処理を終了**（TODO.md は変更しない）。

### Step 2: 引数バリデーション

- `theme` が許容リスト外 → エラー
- `summary` が 30 文字超 → 警告、短縮案内
- `priority` 省略 → `Medium`
- `mode` 省略 → `incremental`
- `target` = `conditional` で `trigger_condition` なし → エラー

### Step 3: ID 採番と日時取得

```bash
next_id=$(uv run python scripts/alpha_factory/todo_manager.py next-id)
today=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')
```

### Step 4: テーブルへの行追記

#### target = open:

```bash
uv run python scripts/alpha_factory/todo_manager.py add \
  --id "{next_id}" \
  --title "{title}" \
  --theme "{theme}" \
  --summary "{summary}" \
  --priority "{priority}" \
  --mode "{mode}" \
  --design-link "[設計](devnotes/{devnotes_dir}/)" \
  --added-at "{today}"
```

#### target = conditional:

```bash
uv run python scripts/alpha_factory/todo_manager.py add-conditional \
  --id "{next_id}" \
  --title "{title}" \
  --theme "{theme}" \
  --summary "{summary}" \
  --trigger-condition "{trigger_condition}" \
  --priority "{priority}" \
  --mode "{mode}" \
  --design-link "[設計](devnotes/{devnotes_dir}/)" \
  --added-at "{today}"
```

### Step 5: 完了報告

#### target = open:
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

{mode = incremental なら:}
→ 次回の /zenigame-fx-autopilot or /zenigame-fx-improve-cycle で自動選定候補になります。
{mode = standalone なら:}
→ 改善ループからは除外。実装する際はユーザーが個別にセッションを開始してください。
```

#### target = conditional:
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

→ Conditional テーブルに追加しました。条件成立時に plan-and-design で Open へ昇格します。
```

---

## 注意事項

- TODO.md の操作は `scripts/alpha_factory/todo_manager.py` 経由（Read / Edit での直接操作不要）
- 設計列は `[設計](devnotes/{devnotes_dir}/)` 形式
- `summary` はテーブルが読みやすいよう 30 文字以内
