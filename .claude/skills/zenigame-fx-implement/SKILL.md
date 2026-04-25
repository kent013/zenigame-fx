---
name: zenigame-fx-implement
description: zenigame-fx Alpha Factory TODO 実装（worktree で実装・テスト・Codex レビュー・コミット・TODO クローズ→main マージ）。RUN は行わない
argument-hint: "<todo_id> [--tmp_dir path] [--skip-consensus] [--skip-todo]"
---

# zenigame-fx Alpha Factory 実装（worktree 分離）

詳細設計に基づき、**git worktree で分離した環境**でコード実装→テスト→Codex レビュー→ドキュメント更新→コミット→TODO クローズ→main マージを行う。**RUN は行わない。**

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `todo` ($1) | Yes | TODO ID（例: T099）。TODO.md から設計リンクを取得 |
| `--tmp_dir` | No | 中間成果物の保存先。--todo 時は自動生成 |
| `--skip-consensus` | No | Codex 合議スキップ。**ユーザー明示指定時のみ**。自動判断付与禁止 |
| `--skip-todo` | No | TODO 遷移スキップ（Phase C） |

---

## 思考原則 / 使命 / 禁止事項

`zenigame-fx-codex-review` で定義される内容を自分・Codex 双方に適用。

---

## Phase W: Worktree 準備

### W-1. TODO 情報の取得

```bash
row=$(uv run python scripts/alpha_factory/todo_manager.py get "{todo}")
```

見つからない場合はエラー終了。
`row` から「設計」列のリンク先を取得 → `detailed-design.md` を Read。概念設計もリンクがあれば Read。

### W-2. tmp_dir の準備

```bash
TZ=Asia/Tokyo date '+%Y%m%d-%H%M'
```
で `devnotes/{YYYYMMDD-HHMM}-todo-{todo_id}/` を作成。

### W-3. Worktree 作成

```bash
git worktree add ./worktrees/todo-{todo_id} -b todo/{todo_id}
```

以降の全作業は **worktree 内** で行う:
```bash
cd ./worktrees/todo-{todo_id}
```

### W-4. 依存関係セットアップ

```bash
cd ./worktrees/todo-{todo_id} && uv sync
```

---

## Phase A: 実装 & Codex レビュー合議

### A-1. 実装

詳細設計書に従い実装。

**実装ルール**:
1. 施策ごとに順番に実装（依存関係がある場合は先行施策から）
2. **primitive（`src/alpha_factory/primitives/`）を変更・追加する施策はルックアヘッドバイアスチェック 6 項目 + パフォーマンスチェック 4 項目を全パス確認**
3. **各施策に必ずテスト**（テストのないものは実装完了としない）
   - ロジック変更 → 単体テストで Before/After
   - パラメータ範囲変更 → 境界値テスト
   - 新機能追加 → 正常系・異常系
   - テスト命名・配置: 振る舞いを説明する汎用的な名前、対象モジュールに対応するテストファイル
4. 各施策実装後に `cd ./worktrees/todo-{todo_id} && uv run pytest tests/ -x` 実行
5. **テスト失敗時はテスト駆動で修正**: 再現最小テスト → FAIL 確認 → 修正 → PASS
6. 全施策実装後に `uv run pytest tests/ -x` 全実行
7. `uv run ruff check src/ tests/` と `uv run mypy src/` も通過確認

### A-2. Codex 実装レビュー

**`--skip-consensus` 時は A-2/A-3 をスキップ**。

差分取得（worktree 内）:
```bash
cd ./worktrees/todo-{todo_id}
git add -N src/ tests/ config/ docs/
git diff HEAD --no-color
```

`zenigame-fx-codex-review` のセッションモード。

**model**: `gpt-5.3-codex`
**reasoning**: `high`
**label**: `impl-review`

**system**:
```
あなたは経験豊富な Python コードレビュアーです。zenigame-fx Alpha Factory の改善実装をレビューしてください。

（C1-C9 は自動挿入済み）

【レビュー観点】
1. 設計との一致性
2. 正確性（ロジック / エッジケース / NaN）
3. パフォーマンス
4. 一貫性（命名規約、パターン）
5. テスト網羅性（各施策にテストあるか）
6. ruff / mypy 準拠
7. 禁止事項違反なし

【転記漏れ・伝搬漏れの重点チェック】
- config → GaConfig → genome.meta → consumer の 4 段伝搬
- GENOMES_SCHEMA 定義 → _create_row_template 初期値 → collect_stage_* 書き込み → flush 出力
- 新規カラム追加時の 4 点セット確認
- 値を書き込む全箇所に logger.debug/info 追加

【出力形式】
- ファイルごとに判定
- [Critical] [Warning] [Suggestion]
- 全体判定: APPROVED / CHANGES_REQUESTED / INCONCLUSIVE
- 日本語
```

**user**: `## 詳細設計書\n{detailed-design.md}\n\n## 実装差分\n{diff}\n\n## テスト結果\n{pytest 出力サマリー}`

### A-3. 実装レビュー合議ループ

1. [Critical] は必ず修正
2. [Warning] は検討
3. 修正後にテスト再実行
4. 修正差分を Codex に再送信

APPROVED まで最大 3 ラウンド。

保存: `{tmp_dir}/impl-review-round-{N}.md`

### A-4. ユーザー報告

```
## Phase A 完了: 実装 & レビュー

### 実装完了
- ブランチ: todo/{todo_id}
- 変更ファイル: N files
- テスト: XXX passed, 0 failed

### Codex 実装レビュー: APPROVED (Round {N})

→ Phase B（ドキュメント更新 & コミット）に進みます
```

---

## Phase B: ドキュメント更新 & コミット

### B-1. ドキュメント更新

以下を worktree 内で更新:

- `docs/alpha_factory/` 配下の関連ドキュメント
- `docs/alpha_factory/primitives.md` — primitive 変更時
- `config/alpha_factory/default.yaml` — パラメータ変更時は `@why` コメント含めて
- `AGENTS.md` — 運用手順・コマンド例の変更時
- `.claude/skills/zenigame-fx-*/SKILL.md` — skill インターフェース変更時

### B-2. コミット

```bash
cd ./worktrees/todo-{todo_id}
git add src/ tests/ docs/ config/ AGENTS.md .claude/
git commit -m "$(cat <<'EOF'
feat: {todo_id} {施策タイトル}

施策:
- S1: {施策名}
- S2: {施策名}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C: TODO クローズ & main マージ

### C-1. TODO クローズ

**`--skip-todo` 時はスキップ**。

main ブランチに戻って TODO クローズ:
```bash
cd /Users/ishitoya/repository/zenigame-fx
```

`/zenigame-fx-todo-close` を呼び出す:
```
/zenigame-fx-todo-close {todo_id}
```

### C-2. main へマージ

```bash
cd /Users/ishitoya/repository/zenigame-fx
git merge todo/{todo_id} --no-ff -m "$(cat <<'EOF'
Merge branch 'todo/{todo_id}'

{todo_id}: {施策タイトル}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### C-3. コンフリクト解消

1. `git diff --name-only --diff-filter=U` でコンフリクトファイル特定
2. 解消方針:
   - 同一関数内の変更: 両方を論理的に統合
   - import / テスト追加: 両方保持（重複除去）
   - 設定値: main 側優先、worktree の新規追加分を追加
   - TODO.md 等のドキュメント: main 側優先
3. コンフリクト解消後にテスト:
   ```bash
   uv run pytest tests/ -x
   ```
4. PASS 確認後コミット:
   ```bash
   git add -A && git commit --no-edit
   ```
5. 3 回修正しても通らない場合はユーザー報告

### C-4. Worktree クリーンアップ

```bash
git worktree remove ./worktrees/todo-{todo_id}
git branch -d todo/{todo_id}
```

### C-5. 最終報告

```
## 実装完了: {todo_id} {施策タイトル}

### サマリー
- ブランチ: todo/{todo_id} → main にマージ済み
- 変更ファイル: N files
- テスト: XXX passed, 0 failed
- Codex レビュー: APPROVED / SKIPPED
- TODO クローズ: 完了 / スキップ
- コンフリクト: なし / 解消済み（N files）

### コミット
- 実装: {commit_hash}
- マージ: {merge_commit_hash}
```

---

## エラーハンドリング

### Codex CLI エラー
- 30 秒待って 1 回リトライ
- 2 回連続失敗でユーザー報告

### テスト失敗
- **テスト駆動で修正**
- 3 回失敗でユーザー報告

### Worktree エラー
- ブランチ名既存: `git worktree remove` + `git branch -D` して再作成
- 作成失敗: エラー報告

### マージコンフリクト
- Phase C-3 の手順
- 解消不能なら `git merge --abort` してユーザー報告

---

## 使用例

### 例 1: standalone TODO 実装
```
/zenigame-fx-implement T001
```

### 例 2: Codex レビュースキップ
```
/zenigame-fx-implement T001 --skip-consensus
```

### 例 3: autopilot からの呼び出し（内部用）
```
/zenigame-fx-implement T001 --tmp_dir devnotes/20260421-2100-autopilot-cycle-1
```
