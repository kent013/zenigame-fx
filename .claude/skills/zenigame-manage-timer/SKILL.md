---
name: zenigame-manage-timer
description: Zenigame Timerサービス管理（status, enable, disable, start）
argument-hint: "<action> [timer]"
---

# Zenigame Timer管理

以下の手順で {{action}} を実行してください：

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `action` ($1) | Yes | 実行アクション（status, enable, disable, start） |
| `timer` ($2) | No | timer名（edinet, jpx-ipo, jpx-tpm, kabutan, minute-bar, mynavi, newseval, nikkei, stock, wikipedia, security-description, all）。action=status以外は必須 |

## 重要ルール

- **必ずsystemdコンテナ内で操作する**
- **本番環境のサービスのため、慎重に操作する**

---

## Timer 管理

### status: Timer状態確認

```bash
# 全timer一覧表示
docker exec zenigame-systemd systemctl list-timers --all

# 個別timer状態確認
docker exec zenigame-systemd systemctl status zenigame-edinet-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-jpx-ipo-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-jpx-tpm-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-kabutan-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-mynavi-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-newseval-daily.timer
docker exec zenigame-systemd systemctl status zenigame-nikkei-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-stock-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-wikipedia-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-security-description-daily.timer
docker exec zenigame-systemd systemctl status zenigame-minute-bar-incremental.timer
```

報告内容（各timer）：
- Enabled状態（enabled/disabled）
- 次回実行予定時刻
- 前回実行時刻
- 実行スケジュール（OnCalendar設定）

**各timerの実行スケジュール**：
- **edinet-incremental**: 毎日 19:00 JST（営業時間後、EDINET書類一覧取得）
- **jpx-ipo-incremental**: 毎日 20:00 JST（JPX Iの部、新規上場チェック）
- **jpx-tpm-incremental**: 毎日 21:00 JST（JPX TPM発行者情報チェック）
- **kabutan-incremental**: 3時間ごと（0/3/6/9/12/15/18/21時、株探ニュースクロール、当日分）
- **mynavi-incremental**: 毎日 18:00 JST（マイナビニュース増分クロール、最大5ページ）
- **newseval-daily**: 毎日 20:00 JST（ニュース評価・予測実行）
- **nikkei-incremental**: 3時間ごと（0/3/6/9/12/15/18/21時、日経速報ページクロール、2ページ）
- **stock-incremental**: 毎日 06:00 JST（市場終了後、株価データ増分同期）
- **wikipedia-incremental**: 毎日 22:00 JST（Wikipedia企業情報、全銘柄対象・投資商品を除く）
- **security-description-daily**: 毎日 23:00 JST（会社概要LLM生成、未処理銘柄のみ）
- **minute-bar-incremental**: 毎日 17:30 JST（分足データ増分同期、未取得営業日を自動投入）

---

### enable: Timer有効化

**{{timer}}が指定されている場合**：

個別timer有効化：
```bash
# edinet, jpx-ipo, jpx-tpm, kabutan, mynavi, nikkei, stock, wikipediaの場合
docker exec zenigame-systemd systemctl enable --now zenigame-{{timer}}-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-{{timer}}-incremental.timer

# newsevalの場合
docker exec zenigame-systemd systemctl enable --now zenigame-newseval-daily.timer
docker exec zenigame-systemd systemctl status zenigame-newseval-daily.timer
```

**{{timer}}が"all"の場合**：

全timer有効化：
```bash
docker exec zenigame-systemd systemctl enable --now zenigame-edinet-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-jpx-ipo-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-jpx-tpm-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-kabutan-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-mynavi-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-newseval-daily.timer
docker exec zenigame-systemd systemctl enable --now zenigame-nikkei-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-stock-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-wikipedia-incremental.timer
docker exec zenigame-systemd systemctl enable --now zenigame-security-description-daily.timer
docker exec zenigame-systemd systemctl enable --now zenigame-minute-bar-incremental.timer

# 状態確認
docker exec zenigame-systemd systemctl list-timers --all
```

有効化後の確認項目：
- `Loaded: enabled` → ✅ 自動起動有効
- NEXT列に次回実行時刻が表示される → ✅ アクティブ

---

### disable: Timer無効化

**{{timer}}が指定されている場合**：

個別timer無効化：
```bash
# edinet, jpx-ipo, jpx-tpm, kabutan, mynavi, nikkei, stock, wikipediaの場合
docker exec zenigame-systemd systemctl disable --now zenigame-{{timer}}-incremental.timer
docker exec zenigame-systemd systemctl status zenigame-{{timer}}-incremental.timer

# newsevalの場合
docker exec zenigame-systemd systemctl disable --now zenigame-newseval-daily.timer
docker exec zenigame-systemd systemctl status zenigame-newseval-daily.timer
```

**{{timer}}が"all"の場合**：

全timer無効化：
```bash
docker exec zenigame-systemd systemctl disable --now zenigame-edinet-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-jpx-ipo-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-jpx-tpm-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-kabutan-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-mynavi-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-newseval-daily.timer
docker exec zenigame-systemd systemctl disable --now zenigame-nikkei-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-stock-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-wikipedia-incremental.timer
docker exec zenigame-systemd systemctl disable --now zenigame-security-description-daily.timer
docker exec zenigame-systemd systemctl disable --now zenigame-minute-bar-incremental.timer

# 状態確認
docker exec zenigame-systemd systemctl list-timers --all
```

無効化後の確認項目：
- `Loaded: disabled` → ✅ 自動起動無効
- NEXT列が `-` になる → ✅ 非アクティブ

---

### start: Timer即座に実行（テスト用）

**注意**: timerを待たずに即座にサービスを実行します。テスト目的での使用を推奨。

**{{timer}}が指定されている場合**：

```bash
# edinet, jpx-ipo, jpx-tpm, kabutan, mynavi, nikkei, stock, wikipediaの場合
docker exec zenigame-systemd systemctl start zenigame-{{timer}}-incremental.service
docker exec zenigame-systemd systemctl status zenigame-{{timer}}-incremental.service
docker exec zenigame-systemd journalctl -u zenigame-{{timer}}-incremental.service -n 30 --no-pager

# newsevalの場合
docker exec zenigame-systemd systemctl start zenigame-newseval-daily.service
docker exec zenigame-systemd systemctl status zenigame-newseval-daily.service
docker exec zenigame-systemd journalctl -u zenigame-newseval-daily.service -n 30 --no-pager
```

**実行内容**：
- **edinet**: EDINET書類一覧取得（`scripts/queue/start_edinet_incremental.py -y`）
- **jpx-ipo**: JPX Iの部収集（`scripts/queue/start_jpx_ipo_crawler.py -y`）
- **jpx-tpm**: JPX TPM発行者情報収集（`scripts/queue/start_jpx_tpm_crawler.py -y`）
- **kabutan**: 株探ニュースクロール（`scripts/queue/start_kabutan_crawler.py -y`）
- **mynavi**: マイナビニュース増分クロール（`scripts/queue/start_mynavi_historical.py --max-pages 5`）
- **newseval**: ニュース評価・予測実行（`scripts/queue/start_newseval_daily.py -y`）
- **nikkei**: 日経速報ページクロール（`scripts/queue/start_nikkei_breaking.py --pages 2`）
- **stock**: 株価データの増分同期（`scripts/sync_stock_data.py --mode incremental -y`）
- **wikipedia**: Wikipedia企業情報収集（`scripts/queue/start_wikipedia_crawler.py -y`）
- **minute-bar**: 分足データ増分同期（`scripts/queue/start_minute_bar_incremental.py -y`）

**{{timer}}が"all"の場合**：

全serviceを即座に実行：
```bash
# 全service実行
docker exec zenigame-systemd systemctl start zenigame-edinet-incremental.service
docker exec zenigame-systemd systemctl start zenigame-jpx-ipo-incremental.service
docker exec zenigame-systemd systemctl start zenigame-jpx-tpm-incremental.service
docker exec zenigame-systemd systemctl start zenigame-kabutan-incremental.service
docker exec zenigame-systemd systemctl start zenigame-mynavi-incremental.service
docker exec zenigame-systemd systemctl start zenigame-newseval-daily.service
docker exec zenigame-systemd systemctl start zenigame-nikkei-incremental.service
docker exec zenigame-systemd systemctl start zenigame-stock-incremental.service
docker exec zenigame-systemd systemctl start zenigame-wikipedia-incremental.service
docker exec zenigame-systemd systemctl start zenigame-minute-bar-incremental.service

# 各service状態確認
docker exec zenigame-systemd systemctl status zenigame-edinet-incremental.service
docker exec zenigame-systemd systemctl status zenigame-jpx-ipo-incremental.service
docker exec zenigame-systemd systemctl status zenigame-jpx-tpm-incremental.service
docker exec zenigame-systemd systemctl status zenigame-kabutan-incremental.service
docker exec zenigame-systemd systemctl status zenigame-mynavi-incremental.service
docker exec zenigame-systemd systemctl status zenigame-newseval-daily.service
docker exec zenigame-systemd systemctl status zenigame-nikkei-incremental.service
docker exec zenigame-systemd systemctl status zenigame-stock-incremental.service
docker exec zenigame-systemd systemctl status zenigame-wikipedia-incremental.service
docker exec zenigame-systemd systemctl status zenigame-minute-bar-incremental.service
```

---

## 結果報告テンプレート

### status実行時

```
## Timer状態

- **edinet-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 19:00 JST
  - 実行内容: EDINET書類一覧取得

- **jpx-ipo-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 20:00 JST
  - 実行内容: JPX Iの部（新規上場チェック）

- **jpx-tpm-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 21:00 JST
  - 実行内容: JPX TPM発行者情報チェック

- **kabutan-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 3時間ごと（0/3/6/9/12/15/18/21時）
  - 実行内容: 株探ニュースクロール（当日分）

- **mynavi-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 18:00 JST
  - 実行内容: マイナビニュース増分クロール（最大5ページ）

- **newseval-daily**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 20:00 JST
  - 実行内容: ニュース評価・予測実行

- **nikkei-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 3時間ごと（0/3/6/9/12/15/18/21時）
  - 実行内容: 日経速報ページクロール（2ページ）

- **stock-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 06:00 JST
  - 実行内容: 株価データ増分同期

- **wikipedia-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 22:00 JST
  - 実行内容: Wikipedia企業情報収集（全銘柄対象・投資商品を除く）

- **security-description-daily**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 23:00 JST
  - 実行内容: 会社概要LLM生成（未処理銘柄のみ）

- **minute-bar-incremental**: [enabled/disabled], 次回: [日時 or -]
  - スケジュール: 毎日 17:30 JST
  - 実行内容: 分足データ増分同期（未取得営業日を自動投入）
```

### enable/disable実行時

```
## Timer {{action}}実行結果

- 操作: {{action}}
- Timer: {{timer}}
- 結果: [成功/失敗]
- 有効化状態: [enabled/disabled]
- 次回実行: [日時 or -]
```

### start実行時

```
## Timer即座実行結果

- 操作: start
- Timer: {{timer}}
- 結果: [成功/失敗]
- Service状態: [active/inactive/failed]

### 実行ログ（抜粋）
[ログの重要部分を記載]

[エラーがあれば詳細を記載]
```

---

## 関連コマンド

queue_manager.pyでの確認：
```bash
# timer状態がTimers行に表示される
uv run scripts/queue_manager.py monitor
```

Timer対応serviceのログ確認：
```bash
# 各incrementalサービスのログ確認
docker exec zenigame-systemd journalctl -u zenigame-edinet-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-jpx-ipo-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-jpx-tpm-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-kabutan-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-mynavi-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-nikkei-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-stock-incremental.service -n 50
docker exec zenigame-systemd journalctl -u zenigame-wikipedia-incremental.service -n 50
```

Timer設定ファイル確認：
```bash
# Timer設定ファイル（OnCalendar設定）
cat scripts/systemd/zenigame-edinet-incremental.timer
cat scripts/systemd/zenigame-jpx-ipo-incremental.timer
cat scripts/systemd/zenigame-jpx-tpm-incremental.timer
cat scripts/systemd/zenigame-kabutan-incremental.timer
cat scripts/systemd/zenigame-mynavi-incremental.timer
cat scripts/systemd/zenigame-nikkei-incremental.timer
cat scripts/systemd/zenigame-stock-incremental.timer
cat scripts/systemd/zenigame-wikipedia-incremental.timer
```

手動でキュー投入（timer不使用）：
```bash
# timerを使わず直接キューにタスク投入する場合
/zenigame-enqueue-task edinet incremental
/zenigame-enqueue-task jpx_ipo incremental
/zenigame-enqueue-task jpx_tpm incremental
/zenigame-enqueue-task kabutan incremental
/zenigame-enqueue-task mynavi incremental
/zenigame-enqueue-task nikkei incremental
/zenigame-enqueue-task stock incremental
/zenigame-enqueue-task wikipedia incremental
```

---

## トラブルシューティング

### Timerが実行されない

```bash
# timer詳細ログ確認
docker exec zenigame-systemd journalctl -u zenigame-{{timer}}-incremental.timer -n 30 --no-pager

# 対応するservice確認
docker exec zenigame-systemd systemctl status zenigame-{{timer}}-incremental.service
```

よくある原因：
- timerが無効化されている（`systemctl enable`が必要）
- serviceファイルのコマンドが間違っている
- 実行スクリプトが存在しない
- 依存パッケージが不足している（`uv sync`実行）

### Timer実行後にタスクが処理されない

Timer実行時はキューにタスクが投入されます。ワーカーが処理します。

```bash
# キュー状態確認
uv run scripts/queue_manager.py status

# ワーカー状態確認
docker exec zenigame-systemd systemctl status zenigame-worker-stock
docker exec zenigame-systemd systemctl status zenigame-worker-mynavi
docker exec zenigame-systemd systemctl status zenigame-worker-kabutan
docker exec zenigame-systemd systemctl status zenigame-worker-nikkei

# ワーカーログ確認
docker exec zenigame-systemd tail -f /var/log/zenigame/stock.log
docker exec zenigame-systemd tail -f /var/log/zenigame/mynavi.log
docker exec zenigame-systemd tail -f /var/log/zenigame/kabutan.log
docker exec zenigame-systemd tail -f /var/log/zenigame/nikkei.log
```

確認項目：
- 対応するworkerが起動中か
- キューにタスクが残っているか（詰まっている可能性）
- workerログにエラーが出ていないか

### Nikkei timer実行時に認証エラー

日経電子版のセッション切れの可能性：

```bash
# ログイン必要フラグ確認
ls -la .cache/nikkei/login_required

# セッション確認
cat .cache/nikkei/session.json
```

対処方法：
```
日経電子版のログインが必要です。以下のコマンドを実行してください：
  uv run python scripts/login_nikkei.py
```

---

## Timer設定詳細

各timerの設定は以下のファイルで定義：
- [scripts/systemd/zenigame-edinet-incremental.timer](scripts/systemd/zenigame-edinet-incremental.timer)
- [scripts/systemd/zenigame-jpx-ipo-incremental.timer](scripts/systemd/zenigame-jpx-ipo-incremental.timer)
- [scripts/systemd/zenigame-jpx-tpm-incremental.timer](scripts/systemd/zenigame-jpx-tpm-incremental.timer)
- [scripts/systemd/zenigame-kabutan-incremental.timer](scripts/systemd/zenigame-kabutan-incremental.timer)
- [scripts/systemd/zenigame-mynavi-incremental.timer](scripts/systemd/zenigame-mynavi-incremental.timer)
- [scripts/systemd/zenigame-newseval-daily.timer](scripts/systemd/zenigame-newseval-daily.timer)
- [scripts/systemd/zenigame-nikkei-incremental.timer](scripts/systemd/zenigame-nikkei-incremental.timer)
- [scripts/systemd/zenigame-stock-incremental.timer](scripts/systemd/zenigame-stock-incremental.timer)
- [scripts/systemd/zenigame-wikipedia-incremental.timer](scripts/systemd/zenigame-wikipedia-incremental.timer)
- [scripts/systemd/zenigame-minute-bar-incremental.timer](scripts/systemd/zenigame-minute-bar-incremental.timer)

主要設定：
- `OnCalendar`: 実行スケジュール（systemd timer形式）
- `Persistent=false`: システム起動時に過去の実行をスキップ
- `AccuracySec=1min`: タイマーの精度

Timer対応serviceファイル：
- [scripts/systemd/zenigame-edinet-incremental.service](scripts/systemd/zenigame-edinet-incremental.service)
- [scripts/systemd/zenigame-jpx-ipo-incremental.service](scripts/systemd/zenigame-jpx-ipo-incremental.service)
- [scripts/systemd/zenigame-jpx-tpm-incremental.service](scripts/systemd/zenigame-jpx-tpm-incremental.service)
- [scripts/systemd/zenigame-kabutan-incremental.service](scripts/systemd/zenigame-kabutan-incremental.service)
- [scripts/systemd/zenigame-mynavi-incremental.service](scripts/systemd/zenigame-mynavi-incremental.service)
- [scripts/systemd/zenigame-newseval-daily.service](scripts/systemd/zenigame-newseval-daily.service)
- [scripts/systemd/zenigame-nikkei-incremental.service](scripts/systemd/zenigame-nikkei-incremental.service)
- [scripts/systemd/zenigame-stock-incremental.service](scripts/systemd/zenigame-stock-incremental.service)
- [scripts/systemd/zenigame-wikipedia-incremental.service](scripts/systemd/zenigame-wikipedia-incremental.service)

---

## 注意事項

- **Timer無効化中は自動クロールが実行されない**
- Timer実行中はキューにタスクが投入される（ワーカーが処理）
- Timer実行時刻はUTC基準で設定されているため、JSTとのズレに注意
- `systemctl start`でのテスト実行は即座に実行されるため、本番環境では慎重に使用
- Timer有効化後、次回実行まで待つ必要がある（即座実行ではない）
