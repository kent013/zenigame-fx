# zenigame-fx ランブック

実装されている CLI とその使い方の全体像。OANDA demo 口座の認証情報（`OANDA_ACCOUNT_ID` / `OANDA_API_TOKEN`）が `.env` に設定されている前提。

---

## 1. セットアップ

### 初回

```bash
bash scripts/init.sh
# 内部で以下を実行:
#   uv sync --dev
#   docker-compose up -d db
#   uv run alembic upgrade head
```

### 環境変数

`.env.example` を `.env` にコピーして OANDA の認証情報を入れる。

```
OANDA_ENV=practice
OANDA_ACCOUNT_ID=xxx-xxx-xxxxxxx-xxx
OANDA_API_TOKEN=<your token>
DATABASE_URL=postgresql+psycopg://zenigame_fx:zenigame_fx_dev@localhost:15433/zenigame_fx
```

### Alembic マイグレーション追加時

```bash
uv run alembic revision -m "description"
uv run alembic upgrade head
```

現在のリビジョン:
- `001` initial schema: currency_pair, price_bar_m1
- `002` economic_event

---

## 2. データ層（Phase 0〜1）

### 2.1 疎通確認

```bash
uv run python scripts/oanda_ping.py
```

OANDA から残高と `USD_JPY` の instrument メタを取得し、`currency_pair` テーブルへ UPSERT する。Phase 0 完了判定の主要項目。

### 2.2 ヒストリカル取得（1 年分デフォルト）

```bash
uv run python scripts/fetch_historical.py \
    --instrument USD_JPY \
    --days 365 \
    [--end 2026-04-18T00:00:00Z] \
    [--chunk-count 5000] \
    [--no-cache]
```

OANDA から M1 candles を取得し `price_bar_m1` へ UPSERT。diskcache（`.cache/http/oanda/candles/`）により過去分は 2 回目以降に API を叩かない。

### 2.3 インクリメンタル取得

```bash
uv run python scripts/fetch_incremental.py --instrument USD_JPY --count 60
```

直近 `count` 本の完成バーのみ UPSERT。cron / systemd timer から毎分呼び出す想定。

### 2.4 経済指標ロード

```bash
uv run python scripts/load_economic_events.py --csv path/to/events.csv
```

CSV フォーマット（`event_time`, `currency`, `name`, `impact[1-3]`, `forecast?`, `actual?`）を `economic_event` テーブルへ UPSERT。

---

## 3. 戦略評価層（Phase 2, 4a〜4e）

### 3.1 単発バックテスト

```bash
uv run python scripts/backtest_run.py \
    --instrument USD_JPY \
    --from 2026-01-01 --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --strategy bollinger --window 20 --k 2.0 --units 10000
```

利用可能な戦略: `bollinger` / `ma_crossover` / `rsi` / `donchian`。結果は `reports/backtests/backtest-<ts>/{result.md,result.json}`。

### 3.2 グリッドサーチ

```bash
uv run python scripts/grid_search.py \
    --instrument USD_JPY \
    --from 2026-01-01 --to 2026-04-01 \
    --leverage 10 \
    --strategy bollinger \
    --param window=10,20,30 \
    --param k=1.5,2.0,2.5 \
    --parallel 4
```

パラメータ全組合せでバックテストを並列実行し `reports/grid-searches/grid-<ts>/` へ Top N を出力。

### 3.3 ウォークフォワード

```bash
uv run python scripts/walk_forward.py \
    --instrument USD_JPY \
    --from 2025-01-01 --to 2026-04-01 \
    --leverage 10 \
    --strategy bollinger \
    --param window=10,20,30 --param k=2.0 \
    --train-days 60 --test-days 14 --step-days 14 \
    --mode rolling
```

train でグリッドサーチ → best params を test で評価、fold を重ねて汎化性能を測定。`overfit_score` でカーブフィッティング度合いを確認できる。

**推奨**:
- `--step-days` は `--test-days` 以下にすること（超えると fold に穴が空く、警告ログは出るが skip されない）
- `overfit_score` は train の total_pnl が正のときのみ定義される（train 損失のケースでは None）

### 3.4 アンサンブル評価

```bash
uv run python scripts/ensemble.py \
    --instrument USD_JPY \
    --from 2026-01-01 --to 2026-04-01 \
    --leverage 10 \
    --strategy boll20:bollinger:window=20,k=2.0,units=5000 \
    --strategy boll30:bollinger:window=30,k=2.0,units=5000 \
    --strategy mac520:ma_crossover:fast_window=5,slow_window=20,units=5000 \
    [--weights 1,1,1]
```

複数戦略に資金を配分して並行運用、戦略間の PnL 相関と合成 PnL を出力。

---

## 4. 進化探索（Phase 4f〜4g）

### 4.1 GA 実行

```bash
uv run python scripts/ga_run.py \
    --instrument USD_JPY \
    --from 2025-11-01 --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --population 30 \
    --generations 10 \
    --fitness-metric total_pnl \
    --seed 42
```

DSL ゲノム（式木）を GA で進化させる。ベスト個体は `reports/ga-runs/ga-<ts>/best_genome.json` に保存。

進化結果のゲノムを手動でコードに取り込みたい場合は、JSON を `src/dsl/serialize.py:genome_from_dict` でロードして `DslStrategy(genome)` で動かす。

---

## 5. Paper Trading（Phase 3）

### 5.1 Replay モード（OANDA なしでも検証可能）

```bash
uv run python scripts/paper_trade.py \
    --mode replay \
    --instrument USD_JPY \
    --from 2026-04-01 --to 2026-04-07 \
    --speedup 60 \
    --leverage 10 \
    --strategy bollinger
```

DB から bars を読み出して 60 倍速（1 分足 → 1 秒）でシミュレート。構造バリデーション用。

### 5.2 Live モード

```bash
uv run python scripts/paper_trade.py \
    --mode live \
    --instrument USD_JPY \
    --poll-interval 10 \
    --leverage 10 \
    --strategy bollinger
```

OANDA を定期ポーリングして実時間で Paper Trading。SIGINT / SIGTERM でグレースフル停止。ログは `paper-logs/paper-<ts>/events.jsonl` + `daily-pnl.md`。

---

## 6. 典型的な改善フロー

1. `fetch_historical.py` で十分な期間のバーを取得
2. `grid_search.py` でパラメータ候補を広く調査
3. `walk_forward.py` で train/test 分割により過剰適合を検証
4. `ensemble.py` で複数設定の相関を見て組合せを検討
5. `ga_run.py` で DSL レベルの新規戦略を探索
6. 有望な戦略を `paper_trade.py --mode replay` でシナリオ確認
7. OANDA demo 口座で `paper_trade.py --mode live` 稼働（1 週間以上の安定稼働を目指す）
8. 信頼性が確認できたら Phase 5（Live Trading）へ

---

## 7. ログと成果物の配置

| 種別 | パス | .gitignore |
|------|------|-----------|
| バックテスト結果 | `reports/backtests/backtest-<ts>/` | ✓ |
| グリッドサーチ | `reports/grid-searches/grid-<ts>/` | ✓ |
| ウォークフォワード | `reports/walk-forwards/wf-<ts>/` | ✓ |
| アンサンブル | `reports/ensembles/ensemble-<ts>/` | ✓ |
| GA | `reports/ga-runs/ga-<ts>/` | ✓ |
| Paper Trading | `paper-logs/paper-<ts>/` | ✓ |
| HTTP キャッシュ | `.cache/http/oanda/` | ✓ |

---

## 8. 開発コマンド

```bash
# テスト
uv run pytest
uv run pytest -x tests/backtest/test_grid_search.py -v

# Lint / Format
uv run ruff check src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/

# 型チェック（warning のみ）
uv run mypy src/

# DB に直接接続
psql -h localhost -p 15433 -U zenigame_fx -d zenigame_fx
# パスワードは .env の DATABASE_URL から
```

---

## 9. トラブルシューティング

### `currency_pair not found`

`scripts/oanda_ping.py` を先に実行して `USD_JPY` を DB へ投入する。

### `no bars in [start, end)`

対象期間のバーが未取得。`scripts/fetch_historical.py --days N --end <ts>` で取得してから再実行。

### OANDA 401 (認証エラー)

`.env` の `OANDA_API_TOKEN` / `OANDA_ACCOUNT_ID` を確認。practice 口座のトークンか `OANDA_ENV=practice` であるか確認。

### Paper Trading (Live) が進まない

- OANDA が完成バーを返すまで polling が続くだけ。`poll-interval` を短くすれば反応は早くなるが API 負荷に注意
- `--mode replay` で動作確認してから `--mode live` に戻すのが確実

### GA の fitness が `-1000000000000` のまま

DslStrategy が評価中に例外を起こしている可能性。`structlog` のログに `ga.fitness.failure` として出るはず。式木の型不整合（bool と numeric の混同等）が疑わしい。
