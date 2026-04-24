---
name: zenigame-manage-sessions
description: Claudeセッションの管理（status=一覧表示, cleanup=ゾンビ掃除, complete=完了マーク）
argument-hint: "<action> (status, cleanup, complete)"
user-invocable: true
---

# zenigame-manage-sessions

Claudeセッションの管理（ステータス確認・クリーンアップ・完了マーク）。

## 使い方

```
/zenigame-manage-sessions status     # セッション一覧表示
/zenigame-manage-sessions cleanup    # ゾンビセッション掃除
/zenigame-manage-sessions complete   # 現セッションを完了マーク
```

## コマンド

### status

全Claudeセッションの一覧を表示する。

```bash
uv run python scripts/cleanup_claude_sessions.py --status
```

結果をそのままユーザーに表示する。

### cleanup

完了済み・放置されたゾンビセッションを掃除する。

**手順**:

1. まず `--status` で一覧を取得し、STALE/COMPLETEDのセッションをユーザーに表示する
2. **ユーザーの明示的な承認を得てから** `--cleanup` を実行する
3. 承認なしにkillしない

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

現セッションを完了としてマークする。セッションIDは自動検出される。

```bash
uv run python scripts/cleanup_claude_sessions.py --complete
```

完了マーカーが `.cache/alpha_factory/session-completed/{sessionId}.done` に書き込まれる。
次回の `cleanup` 実行時に、このマーカーがあるセッションのプロセスが生存していればkillされる。

## 他スキルからの呼び出し

### post-run-review 終了時
全終了パス（正常完了・エラー・スキップ）の末尾で:
```
uv run python scripts/cleanup_claude_sessions.py --complete
```

### improve-cycle 新セッション起動前
Phase 5 で新しいバックグラウンドセッションを起動する前に:
```
uv run python scripts/cleanup_claude_sessions.py --cleanup
```
※ improve-cycleからの呼び出しはユーザー承認不要（自動運用のため）

## 注意事項

- **セッションをkillする前に必ず一覧を表示してユーザー確認を取ること**（cleanupコマンドで手動実行時）
- プロセスツリー全体をkillする（MCP server等の子プロセスも含む）
- SIGTERM → 2秒待機 → SIGKILL の2段階で確実に停止
