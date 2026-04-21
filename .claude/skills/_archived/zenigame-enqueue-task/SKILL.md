---
name: zenigame-enqueue-task
description: Zenigameのキューにタスクを投入（増分更新・履歴取得）
argument-hint: "<source> <mode>"
---

# Zenigameタスク投入

以下の手順で {{source}} の {{mode}} タスクをキューに投入してください：

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `source` ($1) | Yes | ソース名（edinet, jpx_ipo, jpx_tpm, kabutan, minute_bar, mynavi, nikkei, stock, wikipedia） |
| `mode` ($2) | Yes | モード（incremental=増分更新, historical=履歴全件取得） |

## 重要ルール

- **タスク投入はローカルで実行**（systemdコンテナ内ではない）
- **投入前にキュー状態を確認**
- **日経の場合はセッション確認必須**
- **投入後にキュー状態を確認**

## 実行手順

### 1. 投入前のキュー状態確認

```bash
# 現在のキュー状態を確認
uv run python scripts/queue_manager.py status
```

確認項目：
- 該当キューが空いているか（大量のPendingタスクがないか）
- ワーカーが正常稼働しているか

### 2. セッション確認（nikkei/kabutanのみ）

**{{source}} == "nikkei" の場合**：

```bash
# セッションファイルの確認
ls -lh .cache/nikkei/session.json

# login_requiredフラグの確認（存在しないことを確認）
ls .cache/nikkei/login_required 2>/dev/null && echo "ログインが必要です" || echo "セッション有効"
```

`login_required` フラグが存在する場合：

❌ Claude Codeは絶対に実行しない：
```bash
uv run python scripts/nikkei.py login
```

✅ ユーザーに以下を伝える：
```
日経電子版のログインが必要です。以下のコマンドを実行してください：
  uv run python scripts/nikkei.py login
タスク投入はログイン完了後に再実行してください。
```

**{{source}} == "kabutan" の場合**：

```bash
# セッションファイルの確認
ls -lh .cache/kabutan/session.json

# login_requiredフラグの確認（存在しないことを確認）
ls .cache/kabutan/login_required 2>/dev/null && echo "ログインが必要です" || echo "セッション有効"
```

`login_required` フラグが存在する場合：

✅ 自動ログイン可能（OTPなし）：
```bash
uv run python scripts/kabutan.py login
```

### 3. タスク投入

以下のコマンドを {{source}} と {{mode}} に応じて実行してください：

**マイナビニュース（{{source}} == "mynavi"）**：

```bash
# 増分更新（過去24時間）
uv run python scripts/queue/start_mynavi_historical.py --mode incremental

# 履歴全件取得
uv run python scripts/queue/start_mynavi_historical.py --mode historical --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

**日経電子版（{{source}} == "nikkei"）**：

```bash
# 増分更新（推奨）- 速報ページから最新記事を収集
uv run python scripts/queue/start_nikkei_breaking.py --pages 5

# ⚠️ 非推奨: カテゴリ別クロール（サイト構造変更により不安定）
# uv run python scripts/queue/start_nikkei_historical.py --category economy --pages 10
```

⚠️ **注意**: カテゴリ別クロール（`start_nikkei_historical.py`）は非推奨です。日経電子版のサイト構造変更により不安定なため、速報ページクロール（`start_nikkei_breaking.py`）を使用してください。

**EDINET（{{source}} == "edinet"）**：

```bash
# 増分更新（過去1営業日）
uv run python scripts/queue/start_edinet_historical.py --mode incremental

# 履歴全件取得
uv run python scripts/queue/start_edinet_historical.py --mode historical --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

**JPX Iの部（{{source}} == "jpx_ipo"）**：

```bash
# 増分更新（2026年の新規上場銘柄チェック）
uv run python scripts/queue/start_jpx_ipo_crawler.py -y

# 特定年度指定
uv run python scripts/queue/start_jpx_ipo_crawler.py --year 2025 -y
```

**JPX TPM発行者情報（{{source}} == "jpx_tpm"）**：

```bash
# 増分更新（TPM銘柄の発行者情報チェック）
uv run python scripts/queue/start_jpx_tpm_crawler.py -y
```

**Wikipedia企業情報（{{source}} == "wikipedia"）**：

```bash
# 増分更新（全銘柄対象・投資商品を除く）
uv run python scripts/queue/start_wikipedia_crawler.py -y
```

**株探（{{source}} == "kabutan"）**：

```bash
# 増分更新（当日の記事を収集）
uv run python scripts/queue/start_kabutan_crawler.py -y

# 履歴取得（日付範囲指定）
uv run python scripts/queue/start_kabutan_historical.py --start 20260101 --end 20260130 -y
```

**株価データ（{{source}} == "stock"）**：

```bash
# 増分更新（過去1営業日）
uv run python scripts/queue/start_stock_historical.py --mode incremental

# 履歴全件取得
uv run python scripts/queue/start_stock_historical.py --mode historical --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

⚠️ **注意**: 履歴全件取得（historical）は大量のタスクを投入します。確認してから実行してください。

**分足データ（{{source}} == "minute_bar"）**：

```bash
# 増分更新（最終同期日以降の未取得営業日を自動投入）
uv run python scripts/queue/start_minute_bar_incremental.py -y

# 履歴取得（日付範囲指定、1日=1タスク）
uv run python scripts/queue/start_minute_bar_historical.py --from YYYYMMDD --to YYYYMMDD -y
```

⚠️ **注意**: 履歴取得は1営業日あたり約63分かかります（~3,800銘柄 × 1.0秒/req）。2年分（~490営業日）は約21日。

### 4. 投入後のキュー状態確認

待機（5秒）してからキュー状態を確認：

```bash
# キュー状態確認
uv run python scripts/queue_manager.py status
```

確認項目：
- 該当キューにタスクが投入されたか（Pendingカウントが増加）
- ワーカーが処理を開始したか（一部がProcessingになる）

### 5. リアルタイム監視（オプション）

タスク処理状況をリアルタイムで確認：

```bash
# リアルタイム監視
uv run python scripts/queue_manager.py monitor
```

Ctrl+Cで終了。

### 6. 結果報告

以下の形式で結果を報告：

```
## {{source}} タスク投入完了（{{mode}}）

### 投入前の状態
- キュー: [Pendingタスク数]
- ワーカー: [状態]

### 投入結果
- 投入タスク数: [推定数]
- 投入後のPending: [タスク数]
- ワーカー処理状況: [Processing数]

### 次のステップ
- [必要に応じて追加対応を記載]
```

## タスク投入の判断基準

### 増分更新（incremental）

**実行タイミング**：
- 定期的な更新（日次・時間単位）
- 最新データの取得

**対象期間**：
- マイナビ・日経: 過去24時間
- EDINET: 過去1営業日
- JPX IPO/TPM: 最新情報の確認
- Wikipedia: 全銘柄対象（投資商品を除く）
- 株価: 過去1営業日

### 履歴全件取得（historical）

**実行タイミング**：
- 初回セットアップ
- データ欠落の補填
- 過去データの再取得

**注意事項**：
- 大量のタスクが投入される（数千〜数万件）
- 完了まで数時間〜数日かかる場合がある
- レート制限により処理速度が制限される

## 特殊ケース

### マイナビニュース
- カテゴリ別にタスクが投入される
- レート制限: 1秒あたり1リクエスト

### 日経電子版
- セッション管理が必須
- セッション切れ時は自動的に処理停止
- レート制限: 1秒あたり0.5リクエスト（2秒に1回）
- **推奨**: 速報ページクロール（`start_nikkei_breaking.py`）
- **非推奨**: カテゴリ別クロール（`start_nikkei_historical.py`）- サイト構造変更により不安定

### 株探（kabutan）
- セッション管理が必須（OTPなし・自動ログイン可能）
- セッション切れ時は自動的に処理停止
- レート制限: 5秒間隔
- 1プロセス1スレッド

### EDINET
- 公式API使用（レート制限緩い）
- 様式コード別にタスクが投入される
- 書類取得とパースが分離

### JPX IPO（Iの部）
- JPX新規上場銘柄一覧ページから収集
- レート制限: 5秒間隔（保守的設定）
- グロース市場の新規上場銘柄が主対象
- HTTPキャッシュで重複防止

### JPX TPM発行者情報
- JPX TPM銘柄の発行者情報を収集
- レート制限: 5秒間隔（JPX同一）
- 約163件のTPM銘柄が対象
- HTTPキャッシュで重複防止

### Wikipedia企業情報
- 全銘柄対象（投資商品を除く）
- Wikipedia API使用（1秒間隔）
- マッチング精度が低い場合は自動スキップ

### 株価データ
- J-Quants API使用
- 銘柄数×日数のタスクが投入される
- APIクォータに注意

### 分足データ（minute_bar）
- J-Quants API使用（Add-on必須）
- レート制限: 60 req/min（1.0秒間隔）
- 1タスク = 1営業日（全上場銘柄 ~3,800銘柄）
- 1営業日あたり約63分で完了
- Parquetファイルに保存（DBには格納しない）
- 冪等性保証（完了済みの日はスキップ）
- 中断再開可能（last_processed_codeから再開）

## トラブルシューティング

### タスクが投入されない
1. スクリプトのエラーを確認
2. RabbitMQ接続を確認（Management UI: `http://localhost:15672`）
3. 環境変数を確認（`.env`）

### タスクが処理されない
1. ワーカーの状態を確認（`/zenigame-troubleshoot-worker` skillを使用）
2. ログを確認
3. 必要に応じてワーカー再起動

### 日経のセッションエラー
1. ログインスクリプトを実行（ユーザーに依頼）
2. セッションファイルを確認
3. ワーカー再起動

### 株探のセッションエラー
1. 自動ログイン可能: `uv run python scripts/kabutan.py login`
2. セッションファイルを確認
3. ワーカー再起動
