---
name: zenigame-restart-worker
description: Zenigameワーカーを安全に再起動（Discord監視確認、再起動後のログ確認を含む）
argument-hint: "<service>"
---

# Zenigameワーカー再起動

以下の手順で {{service}} ワーカーを安全に再起動してください：

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `service` ($1) | Yes | サービス名（edinet, jpx-ipo, jpx-tpm, kabutan, minute-bar, mynavi, newseval, nikkei, stock, wikipedia, all） |

## 重要ルール

- **絶対にローカルでワーカーを起動しない**
- **必ずsystemdコンテナ内で操作する**
- **再起動前にユーザーの承認を得る**（このskillが呼ばれた時点で承認済みと見なす）

## 実行手順

### 1. 再起動前の状態確認

```bash
# 現在の状態を記録
docker exec zenigame-systemd systemctl status zenigame-worker-{{service}}
```

### 2. ワーカー再起動

**個別ワーカーの場合（{{service}} != "all"）**：

```bash
docker exec zenigame-systemd systemctl restart zenigame-worker-{{service}}
```

**全ワーカーの場合（{{service}} == "all"）**：

```bash
# 全ワーカーを再起動（アルファベット順）
docker exec zenigame-systemd systemctl restart zenigame-worker-edinet
docker exec zenigame-systemd systemctl restart zenigame-worker-jpx-ipo
docker exec zenigame-systemd systemctl restart zenigame-worker-jpx-tpm
docker exec zenigame-systemd systemctl restart zenigame-worker-kabutan
docker exec zenigame-systemd systemctl restart zenigame-worker-mynavi
docker exec zenigame-systemd systemctl restart zenigame-worker-newseval
docker exec zenigame-systemd systemctl restart zenigame-worker-nikkei
docker exec zenigame-systemd systemctl restart zenigame-worker-stock
docker exec zenigame-systemd systemctl restart zenigame-worker-wikipedia
docker exec zenigame-systemd systemctl restart zenigame-worker-minute-bar
```

### 3. Discordアラートサービス確認・起動

```bash
# アラートサービスの状態確認
docker exec zenigame-systemd systemctl status zenigame-alert.service
```

起動していない場合は起動：
```bash
docker exec zenigame-systemd systemctl start zenigame-alert.service
```

### 4. 再起動後の状態確認

待機（5秒）してから状態を確認：

```bash
# 状態確認
docker exec zenigame-systemd systemctl status zenigame-worker-{{service}}
```

確認項目：
- `Active: active (running)` → ✅ 正常起動
- `Active: failed` → ❌ 起動失敗
- プロセスIDが変わっていることを確認

### 5. 再起動後のログ確認（エラーチェック）

```bash
# 最新30行のログを確認（エラーチェック）
docker exec zenigame-systemd tail -n 30 /var/log/zenigame/{{service}}.log
```

エラーがある場合：
- 設定ミス → 修正して再度再起動
- 認証エラー → ユーザーに対処を依頼
- その他 → トラブルシューティングskillを使用

### 6. 結果報告

以下の形式で結果を報告：

```
## {{service}} ワーカー再起動完了

### 再起動結果
- 状態: [Active/Failed]
- プロセスID: [新しいPID]
- Discord監視: [起動中/停止中→起動済み]

### 再起動後のログ
- [エラーがあれば記載、なければ「エラーなし」]

### 次のステップ
- [必要であれば追加対応を記載]
```

## 特殊ケース：nikkeiワーカー

nikkeiワーカー再起動後に認証エラーが出た場合：

❌ Claude Codeは絶対に実行しない：
```bash
uv run python scripts/nikkei.py login
```

✅ ユーザーに以下を伝える：
```
日経電子版のログインが必要です。以下のコマンドを実行してください：
  uv run python scripts/nikkei.py login
```

## 特殊ケース：kabutanワーカー

kabutanワーカー再起動後に認証エラーが出た場合：

❌ Claude Codeは絶対に実行しない：
```bash
uv run python scripts/kabutan.py login
```

✅ ユーザーに以下を伝える：
```
株探のログインが必要です。以下のコマンドを実行してください：
  uv run python scripts/kabutan.py login
```

## 再起動が必要なケース

以下の変更を行った場合は、必ずワーカー再起動が必要です：

- Pythonコード修正（`src/queue/tasks/` 配下）
- 環境変数変更（`.env.devcontainer`）
- 設定ファイル変更（`alert_config.yaml` 等）
- 依存パッケージ追加・更新（`pyproject.toml`）

## 注意事項

- 再起動中は該当キューのタスクが処理されない（数秒程度）
- RabbitMQキューに残っているタスクは再起動後に自動的に処理される
- 再起動失敗時は、詳細なログ（tail -n 100等）を確認して原因を特定
