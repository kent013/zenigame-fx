# Phase 3 詳細設計 — Paper Trading 一気通貫

**作成**: 2026-04-17 23:30 JST
**前提**: [../20260417-2300-phase2-detailed-design/detailed-design.md](../20260417-2300-phase2-detailed-design/detailed-design.md)（バックテスト基盤）
**状態**: DRAFT

---

## 1. スコープ

**含む**:
- `BarFeed` Protocol（新規）と 2 実装: `LiveBarFeed`（OANDA polling）/ `ReplayBarFeed`（DB リプレイ）
- `PaperTradingOrchestrator`: BarFeed → Strategy → Broker の接続
- JSONL 形式の監査ログ（signal / fill / close の記録）
- 日次 Markdown PnL レポート自動生成
- SIGTERM / SIGINT でのグレースフルシャットダウン
- CLI: `scripts/paper_trade.py --mode replay|live`

**含まない**:
- 実ブローカー発注（Phase 5）
- WebSocket 配信（Phase 4 以降）
- Discord / メール通知（Phase 4 以降）
- DB 永続化（MVP は JSONL ログのみ。Phase 3 後半で検討）

---

## 2. 背景と方針

Paper Trading は **バックテストエンジンを時間軸で動かす** もの。Phase 2 で作った `MockBroker` はそのまま使い、「バーの供給源」だけ Replay（過去データ）と Live（OANDA polling）で切り替える。

開発期間中は OANDA 口座未発行なので **ReplayBarFeed** で機能検証し、口座発行後に LiveBarFeed に差し替えるだけで本番運用に入れる状態を作る。

---

## 3. BarFeed Protocol

```python
class BarFeed(Protocol):
    def __iter__(self) -> Iterator[PriceBar]: ...
    def stop(self) -> None: ...
```

### 3.1 ReplayBarFeed

- DB の `price_bar_m1` を `bar_time ASC` で順次 yield
- `speedup` パラメータで実時間との倍率を指定（`0` = as fast as possible）
- 既存のバックテスト用途と違い、各バーの間に `60 / speedup` 秒スリープ（speedup=60 なら 1 秒ごと）
- `stop()` で中断可能

### 3.2 LiveBarFeed

- OANDA `/v3/instruments/{instrument}/candles?count=1&price=BA` を定期 polling
- 新しい `complete=true` バーが返ったら yield
- ポーリング周期: デフォルト 10 秒（M1 バーは毎分確定するが、polling 同期遅延を抑える）
- 既出バー（`bar_time` 一致）はスキップ
- `stop()` でポーリング停止
- **OANDA 仕様**: `complete=false` が混入する可能性 → 必ず skip

---

## 4. PaperTradingOrchestrator

```python
class PaperTradingOrchestrator:
    def __init__(
        self,
        feed: BarFeed,
        strategy: Strategy,
        broker: MockBroker,
        leverage: int,
        initial_cash: Decimal,
        logger: EventLogger,
    ): ...

    def run(self) -> None: ...
    def request_stop(self) -> None: ...
```

### ループ

```
broker.deposit(initial_cash)
for bar in feed:
    if stop_requested: break
    broker.fill_pending(bar)      # 前 bar の発注を約定
    broker.mark_to_market(bar)
    trades_mc = broker.force_close_if_margin_call(bar)
    logger.log_margin_call(trades_mc)

    snapshot = broker.snapshot()
    signals = strategy.on_bar(bar, snapshot)
    for signal in signals:
        broker.submit(signal, leverage)
        logger.log_signal(signal, bar, snapshot)

    if is_eod(bar, peek_next=None):
        trades_eod = broker.close_all(bar, reason="eod")
        logger.log_eod_close(trades_eod)

    logger.log_bar(bar, broker.snapshot())

# 終了処理
broker.close_all(last_bar, reason="end_of_run")
logger.flush()
```

**Live の「EOD 判定」**: live では将来バーを先読みできない。JST or UTC の固定時刻（例: 22:00 UTC = 日本の早朝）で全決済する簡易ルールを採用。ReplayBarFeed では「次バーの日付が変わる」方式。

MVP は「24 UTC 切り替えで force close」の単純実装にする（実運用の週末 friday-close は Phase 4 以降）。

---

## 5. EventLogger

```
paper-logs/{session_id}/
├── events.jsonl        # 逐次イベント（signal / fill / close / bar-summary）
└── daily-pnl.md        # 日次レポート（EOD で生成・追記）
```

- `session_id = paper-{YYYYMMDD-HHMMSS}`
- 各イベントは 1 行 JSON: `{"ts": "2026-...", "kind": "signal", "payload": {...}}`
- EOD 時点で当日分の trades を集計し Markdown を追記（累計損益・勝率）
- Phase 3 では **DB への書き出しはしない**（JSONL で十分）

---

## 6. グレースフルシャットダウン

- `signal.SIGINT` / `signal.SIGTERM` を捕捉し `orchestrator.request_stop()`
- 次のバー処理前にループを抜け、`broker.close_all("end_of_run")` → `logger.flush()` → exit 0
- 強制終了（SIGKILL）は考慮外（OS レベルなので対応不可）

---

## 7. CLI

```
uv run python scripts/paper_trade.py \
    --mode replay \
    --instrument USD_JPY \
    --from 2026-04-01 --to 2026-04-07 \
    --speedup 60 \
    --leverage 10 \
    --initial-cash 1000000 \
    --strategy bollinger --window 20 --k 2.0 --units 10000
```

```
uv run python scripts/paper_trade.py \
    --mode live \
    --instrument USD_JPY \
    --leverage 10 \
    --initial-cash 1000000 \
    --strategy bollinger
```

ログ出力先は `paper-logs/paper-YYYYMMDD-HHMMSS/`（`--log-dir` で上書き可）。

---

## 8. ディレクトリ構成の追加

```
src/
└── paper_trading/         # ← 新規
    ├── __init__.py
    ├── feed.py            # BarFeed Protocol, ReplayBarFeed, LiveBarFeed
    ├── events.py          # イベント型と EventLogger
    └── orchestrator.py    # PaperTradingOrchestrator
scripts/
└── paper_trade.py         # ← 新規
tests/
└── paper_trading/
    ├── __init__.py
    ├── test_feed.py       # ReplayBarFeed（DB 不要、memory で検証）
    └── test_orchestrator.py
paper-logs/                # 生成物（.gitignore）
```

---

## 9. テスト戦略

- `test_feed.py`: ReplayBarFeed が与えられた bar list を順次 yield する（speedup=0）、`stop()` で中断できる
- `test_orchestrator.py`: InMemory BarFeed + ScriptedStrategy + MockBroker で 1 本のトレードが signal → fill → close まで完結し events.jsonl に 3 種のイベントが書かれる
- LiveBarFeed は respx で OANDA モック（polling loop のテストは time.sleep の monkeypatch で高速化）

---

## 10. 完了判定

1. `uv run python scripts/paper_trade.py --mode replay --instrument USD_JPY --from ... --to ... --speedup 0` で `paper-logs/paper-*/events.jsonl` と `daily-pnl.md` が生成される（DB に price_bar_m1 が入っている前提）
2. `uv run pytest` が green（全テスト）
3. SIGINT でループが安全に終了し、端数ポジションが end_of_run として決済される
4. OANDA 口座発行後、`--mode live` に切り替えるだけで稼働開始できる

---

## 11. 先送り事項

- Discord / メール通知
- DB への orders / trades / events 永続化（Phase 3 後半 or Phase 5）
- WebSocket pricing / ストリーミング
- 週末 friday-close の実装（MVP は UTC 日切り替えのみ）
- 複数戦略・複数 instrument 同時稼働
