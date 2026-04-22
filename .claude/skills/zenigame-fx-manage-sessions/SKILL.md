---
name: zenigame-fx-manage-sessions
description: zenigame-fx Alpha Factory 用 Claude セッション管理（status=一覧表示, cleanup=ゾンビ掃除, complete=完了マーク）
argument-hint: "<action> (status, cleanup, complete)"
user-invocable: true
---

# zenigame-fx-manage-sessions

zenigame-fx Alpha Factory 用の Claude セッション管理（ステータス確認・クリーンアップ・完了マーク）。

> 使命・禁止事項は呼び出し元スキルが必要に応じて `zenigame-fx-codex-review` を参照すること。本スキル自体は運用補助のため North Star を直接背負わない。

## 実行前提チェック

### script (必須)
- `scripts/cleanup_claude_sessions.py`

### artifact (参照依存・skill では直接チェックしない)
- `.cache/alpha_factory/session-completed/` （`--complete` 実行時に自動生成。事前作成不要）

### related skill
- なし

### 未充足時挙動
script 不在を検出した時点でアボート、不足依存を列挙する。zenigame 側スクリプトをフォールバック参照しない。zenigame-fx は独立コードベースとして扱う。

## 使い方

```
/zenigame-fx-manage-sessions status     # セッション一覧表示
/zenigame-fx-manage-sessions cleanup    # ゾンビセッション掃除
/zenigame-fx-manage-sessions complete   # 現セッションを完了マーク
```

## コマンド

### status

全 Claude セッションの一覧を表示する。

```bash
uv run python scripts/cleanup_claude_sessions.py --status
```

結果をそのままユーザーに表示する。

### cleanup

完了済み・放置されたゾンビセッションを掃除する。

**手順**:

1. まず `--status` で一覧を取得し、STALE/COMPLETED のセッションをユーザーに表示する
2. **ユーザーの明示的な承認を得てから** `--cleanup` を実行する
3. 承認なしに kill しない

```bash
# Step 1: 確認
uv run python scripts/cleanup_claude_sessions.py --status

# Step 2: ユーザー承認後
uv run python scripts/cleanup_claude_sessions.py --cleanup
```

**判定ロジック**（スクリプト内蔵）:

| 状態 | アクション |
|------|----------|
| 完了マーク済み + プロセス生存 | kill |
| jsonlが60分以上未更新 | kill |
| 現セッション（自分自身） | **killしない** |
| 活動中（60分以内に更新あり） | 何もしない |

### complete

現セッションを完了としてマークする。セッション ID は自動検出される。

```bash
uv run python scripts/cleanup_claude_sessions.py --complete
```

完了マーカーが `.cache/alpha_factory/session-completed/{sessionId}.done` に書き込まれる。
次回の `cleanup` 実行時に、このマーカーがあるセッションのプロセスが生存していれば kill される。

## 他スキルからの呼び出し

### zenigame-fx-post-run-review 終了時
全終了パス（正常完了・エラー・スキップ）の末尾で:
```
uv run python scripts/cleanup_claude_sessions.py --complete
```

### zenigame-fx-improve-cycle 新セッション起動前
新しいバックグラウンドセッションを起動する前に:
```
uv run python scripts/cleanup_claude_sessions.py --cleanup
```
※ zenigame-fx-improve-cycle からの呼び出しはユーザー承認不要（自動運用のため）

## 注意事項

- **セッションを kill する前に必ず一覧を表示してユーザー確認を取ること**（cleanup コマンドで手動実行時）
- プロセスツリー全体を kill する（MCP server 等の子プロセスも含む）
- SIGTERM → 2 秒待機 → SIGKILL の 2 段階で確実に停止
