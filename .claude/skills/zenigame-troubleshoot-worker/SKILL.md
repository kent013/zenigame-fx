---
name: zenigame-troubleshoot-worker
description: Zenigameワーカーのトラブルシューティングを実行（ログ確認、状態確認、Discord監視確認）
argument-hint: "<service>"
---

# Zenigameワーカートラブルシューティング

以下の手順で {{service}} ワーカーのトラブルシューティングを実行してください：

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `service` ($1) | Yes | サービス名（edinet, jpx-ipo, jpx-tpm, kabutan, minute-bar, mynavi, newseval, nikkei, stock, wikipedia） |

## 重要ルール

- **絶対にローカルでワーカーを起動しない**
- **必ずsystemdコンテナ内で操作する**
- **対話型スクリプト（login_nikkei.py等）は実行しない**

## 実行手順

### 1. ログ確認（最優先）

```bash
# 最新100行のログを確認（エラーのみ）
docker exec zenigame-systemd tail -n 100 /var/log/zenigame/{{service}}.log | grep -E "ERROR|Exception|CRITICAL|Traceback"
```

エラーがある場合は、エラーの種類を分析：
- DB接続エラー（`connection`, `database`）
- 認証エラー（`401`, `403`, `login_required`）
- スクレイピングエラー（`timeout`, `selector not found`）
- レート制限（`rate limit`, `429`）
- その他

### 2. ワーカー状態確認

```bash
# サービス状態確認
docker exec zenigame-systemd systemctl status zenigame-worker-{{service}}
```

状態を確認：
- `Active: active (running)` → 正常稼働
- `Active: failed` → 起動失敗
- `Active: inactive (dead)` → 停止中

### 3. Discord監視サービス確認

```bash
# アラートサービスの状態確認
docker exec zenigame-systemd systemctl status zenigame-alert.service
```

起動していない場合：
```bash
docker exec zenigame-systemd systemctl start zenigame-alert.service
```

### 4. 分析結果の報告

以下の形式で結果を報告：

```
## {{service}} ワーカーの状態

### エラーログ
- [エラーの内容を要約]
- [発生頻度・最終発生時刻]

### サービス状態
- [Active/Inactive/Failed]
- [プロセスID]

### Discord監視
- [起動中/停止中]

### 推奨対応
1. [エラー内容に基づく具体的な対応策]
2. [必要であれば再起動・設定変更等]
```

### 5. 認証エラーの場合の特別対応

**nikkeiワーカーで認証エラー（login_required）の場合**：

❌ Claude Codeは絶対に実行しない：
```bash
uv run python scripts/nikkei.py login
```

✅ ユーザーに以下を伝える：
```
日経電子版のログインが必要です。以下のコマンドを実行してください：
  uv run python scripts/nikkei.py login
```

**kabutanワーカーで認証エラー（login_required）の場合**：

❌ Claude Codeは絶対に実行しない：
```bash
uv run python scripts/kabutan.py login
```

✅ ユーザーに以下を伝える：
```
株探のログインが必要です。以下のコマンドを実行してください：
  uv run python scripts/kabutan.py login
```

## 注意事項

- データベース確認は、ログ確認後に必要と判断した場合のみ実行
- ワーカー再起動は、ユーザーの承認を得てから実行（または `/zenigame-restart-worker` skillを使用）
- 問題が解決しない場合は、より詳細なログ（tail -n 500等）を確認
