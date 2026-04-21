---
name: zenigame-manage-alert
description: Zenigameアラートサービス(zenigame-alert)管理（status, start, stop, restart, enable, disable, install）
argument-hint: "<action>"
---

# Zenigame Alert管理

以下の手順で {{action}} を実行してください：

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `action` ($1) | Yes | 実行アクション（status, start, stop, restart, enable, disable, install） |

## 重要ルール

- **必ずsystemdコンテナ内で操作する**
- **本番環境のサービスのため、慎重に操作する**

---

## Alert サービス管理

### status: Alert状態確認

```bash
# 監視サービスの詳細状態確認
docker exec zenigame-systemd systemctl status zenigame-alert.service

# 有効/無効状態確認
docker exec zenigame-systemd systemctl is-enabled zenigame-alert.service

# 監視中のログファイル確認
docker exec zenigame-systemd ps aux | grep alert_logs.py
```

報告内容：
- Active状態（active/inactive）
- Enabled状態（enabled/disabled）
- 稼働時間
- 監視対象ログファイル（stock, newseval, mynavi, nikkei, edinet）

---

### start: Alert起動

```bash
docker exec zenigame-systemd systemctl start zenigame-alert.service
docker exec zenigame-systemd systemctl status zenigame-alert.service
```

起動後の確認項目：
- `Active: active (running)` → ✅ 正常起動
- プロセスが`tail -f`で5つのログファイルを監視中

---

### stop: Alert停止

**注意**: 停止するとDiscord通知が送信されなくなります。

```bash
docker exec zenigame-systemd systemctl stop zenigame-alert.service
docker exec zenigame-systemd systemctl status zenigame-alert.service
```

---

### restart: Alert再起動

設定ファイル（alert_config.yaml）を変更した場合に実行：

```bash
docker exec zenigame-systemd systemctl restart zenigame-alert.service

# 5秒待機
sleep 5

# 状態確認
docker exec zenigame-systemd systemctl status zenigame-alert.service

# 最新ログ確認（エラーチェック）
docker exec zenigame-systemd journalctl -u zenigame-alert.service -n 20 --no-pager
```

---

### enable: Alert自動起動有効化

```bash
docker exec zenigame-systemd systemctl enable zenigame-alert.service
docker exec zenigame-systemd systemctl is-enabled zenigame-alert.service
```

有効化後、systemd再起動時に自動的にalertが起動します。

---

### disable: Alert自動起動無効化

```bash
docker exec zenigame-systemd systemctl disable zenigame-alert.service
docker exec zenigame-systemd systemctl is-enabled zenigame-alert.service
```

---

### install: Alert初回インストール

**注意**: 通常は`scripts/systemd/install.sh`で自動実行されるため、手動実行は不要。

インストール内容確認：
```bash
# サービスファイル存在確認
docker exec zenigame-systemd ls -l /etc/systemd/system/zenigame-alert.service

# 設定ファイル存在確認
ls -l scripts/systemd/alert_config.yaml
```

手動インストールが必要な場合：
```bash
# systemdコンテナ再起動（install.shが自動実行される）
docker-compose restart app-systemd

# または手動でinstall.sh実行
docker exec zenigame-systemd bash /workspace/scripts/systemd/install.sh
```

---

## 結果報告テンプレート

### status実行時

```
## Alert Service状態

- 状態: [active/inactive]
- 有効化: [enabled/disabled]
- 稼働時間: [時間]
- 監視対象: stock, newseval, mynavi, nikkei, edinet
```

### start/stop/restart実行時

```
## {{action}}実行結果

- 操作: {{action}}
- サービス: zenigame-alert
- 結果: [成功/失敗]
- 現在の状態: [active/inactive]

[エラーがあれば記載]
```

---

## 関連コマンド

alertログのリアルタイム確認：
```bash
docker logs zenigame-systemd -f | grep alert
```

監視設定ファイル編集：
```bash
# [scripts/systemd/alert_config.yaml](scripts/systemd/alert_config.yaml)を編集
# 編集後はalert再起動が必要
```

queue_manager.pyでの確認：
```bash
# alert状態がWorkers行に表示される
uv run scripts/queue_manager.py alert
```

監視対象ログファイル：
```bash
# 各workerのログを直接確認
docker exec zenigame-systemd tail -f /var/log/zenigame/mynavi.log
docker exec zenigame-systemd tail -f /var/log/zenigame/nikkei.log
docker exec zenigame-systemd tail -f /var/log/zenigame/edinet.log
docker exec zenigame-systemd tail -f /var/log/zenigame/stock.log
docker exec zenigame-systemd tail -f /var/log/zenigame/newseval.log
```

---

## トラブルシューティング

### Alertが起動しない

```bash
# 詳細ログ確認
docker exec zenigame-systemd journalctl -u zenigame-alert.service -n 50 --no-pager

# Discord Webhook URL確認（環境変数）
docker exec zenigame-systemd printenv | grep DISCORD_WEBHOOK
```

よくある原因：
- Discord Webhook URLが未設定（`.env.devcontainer`）
- Python依存パッケージ不足（`uv sync`実行）
- 監視対象ログファイルが存在しない

### Discord通知が届かない

確認項目：
- Alert serviceが起動中か（`systemctl status`）
- Webhook URLが正しく設定されているか（環境変数）
- エラーパターンが`alert_config.yaml`に定義されているか
- 閾値（errors_per_minute）を超えているか
- クールダウン期間内でないか（デフォルト300秒）

---

## 監視設定について

[scripts/systemd/alert_config.yaml](scripts/systemd/alert_config.yaml)で以下を設定：

### サービスごとの監視設定
- `enabled`: 監視有効/無効
- `channel`: 通知先Discordチャンネル（alerts, critical, stock, news, evaluation）
- `threshold.errors_per_minute`: エラー閾値
- `error_patterns`: 検知パターン（ERROR, CRITICAL, Exception等）
- `cooldown_seconds`: 通知クールダウン期間

### グローバル設定
- `max_sample_logs`: 通知に含める最大ログ行数
- `mask_patterns`: 機密情報マスキングパターン
- `timezone`: タイムゾーン（Asia/Tokyo）

設定変更後は必ずalert再起動：
```bash
docker exec zenigame-systemd systemctl restart zenigame-alert.service
```

---

## 注意事項

- **Alert停止中はDiscord通知が送信されない**
- 設定変更後は必ずalert再起動が必要
- エラー通知はクールダウン期間内は再送されない
- 各workerは独立して動作（alert停止中もworkerは稼働）
