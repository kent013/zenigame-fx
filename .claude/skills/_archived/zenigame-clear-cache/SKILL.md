---
name: zenigame-clear-cache
description: Zenigameのキャッシュを削除（namespace + 期間指定）
argument-hint: "<namespace> <cache_type> <mode> [date_params]"
user-invocable: true
---

# Zenigameキャッシュ削除

以下の手順で {{namespace}} の {{cache_type}} キャッシュを削除してください：

## 重要ルール

- **削除前に必ずキャッシュ状態を確認**
- **範囲指定・相対指定を正しく使い分ける**
- **誤削除を防ぐため、--force なしで実行して確認プロンプトを表示**

## 実行手順

### 1. キャッシュ状態確認

```bash
# 全キャッシュ統計表示
uv run python scripts/cache_manager.py status
```

確認項目：
- 対象namespace（{{namespace}}）が存在するか
- キャッシュ件数とサイズ
- 削除対象のキャッシュタイプ（{{cache_type}}）

### 2. キャッシュ削除実行

{{mode}} に応じて以下のコマンドを実行してください：

**全削除（{{mode}} == "all"）**：

⚠️ **警告**: namespace全体を削除します。本当に必要か確認してください。

```bash
# 確認プロンプト付き
uv run python scripts/cache_manager.py clear --namespace {{namespace}} --cache-type {{cache_type}}

# 確認なしで強制削除（注意して使用）
uv run python scripts/cache_manager.py clear --namespace {{namespace}} --cache-type {{cache_type}} --force
```

**範囲指定（{{mode}} == "range"）**：

期間を指定してキャッシュを削除します（例: 2026-01-01～2026-01-31）。

```bash
# date_paramsから開始日と終了日を抽出
# 例: date_params = "2026-01-01 2026-01-31"
START_DATE=$(echo "{{date_params}}" | awk '{print $1}')
END_DATE=$(echo "{{date_params}}" | awk '{print $2}')

# 範囲指定で削除
uv run python scripts/cache_manager.py clear-by-date \
  --namespace {{namespace}} \
  --cache-type {{cache_type}} \
  --start-date "$START_DATE" \
  --end-date "$END_DATE"
```

**指定日時以前（{{mode}} == "before"）**：

指定した日時以前に保存されたキャッシュを削除します（例: 2026-01-20以前）。

```bash
# 指定日時以前を削除
uv run python scripts/cache_manager.py clear-by-date \
  --namespace {{namespace}} \
  --cache-type {{cache_type}} \
  --before "{{date_params}}"
```

**指定日時以降（{{mode}} == "after"）**：

指定した日時以降に保存されたキャッシュを削除します（例: 2026-01-20以降）。

```bash
# 指定日時以降を削除
uv run python scripts/cache_manager.py clear-by-date \
  --namespace {{namespace}} \
  --cache-type {{cache_type}} \
  --after "{{date_params}}"
```

### 3. 削除後の確認

```bash
# キャッシュ統計を再確認
uv run python scripts/cache_manager.py status
```

確認項目：
- {{namespace}} のキャッシュ件数が減少しているか
- サイズが削減されているか

## 使用例

### 例1: マイナビニュースのHTTPキャッシュを2026年1月分削除

```bash
uv run python scripts/cache_manager.py clear-by-date \
  --namespace mynavi \
  --cache-type http \
  --start-date 2026-01-01 \
  --end-date 2026-01-31
```

### 例2: WikipediaのPlaywrightキャッシュを2026-01-20以前削除

```bash
uv run python scripts/cache_manager.py clear-by-date \
  --namespace wikipedia \
  --cache-type playwright \
  --before 2026-01-20
```

### 例3: 日経電子版のPlaywrightキャッシュを2026-01-20以降削除

```bash
uv run python scripts/cache_manager.py clear-by-date \
  --namespace nikkei \
  --cache-type playwright \
  --after 2026-01-20
```

### 例4: J-QuantsのHTTPキャッシュを全削除

```bash
# 確認プロンプト付き
uv run python scripts/cache_manager.py clear --namespace jquants --cache-type http

# 強制削除（確認なし）
uv run python scripts/cache_manager.py clear --namespace jquants --cache-type http --force
```

## 注意事項

- **日時形式**: `YYYY-MM-DD` または `YYYY-MM-DDTHH:MM:SS`（ISO8601形式）
- **タイムゾーン**: すべてローカル時間（JST）として扱われます
- **削除基準**: キャッシュ保存日時（cached_at）を基準に削除します
- **確認プロンプト**: `--force` オプションなしでは削除前に確認プロンプトが表示されます

## トラブルシューティング

### エラー: namespace が見つからない

```
[yellow]namespace 'xxx' のHTTPキャッシュが見つかりません[/yellow]
```

→ namespace名が間違っているか、キャッシュタイプが間違っています。`uv run python scripts/cache_manager.py status` で確認してください。

### エラー: 日時形式が不正

```
[red]エラー: 日時形式が不正です[/red]
```

→ 日時形式を `YYYY-MM-DD` または `YYYY-MM-DDTHH:MM:SS` に修正してください。

### 削除件数が0件

```
[yellow]指定条件に一致するキャッシュがありません[/yellow]
```

→ 指定した期間にキャッシュが存在しないか、日付範囲が間違っています。`--before` や `--after` で範囲を広げて再試行してください。
