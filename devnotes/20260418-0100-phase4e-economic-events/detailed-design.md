# Phase 4e 詳細設計 — 経済指標カレンダー基盤

**作成**: 2026-04-18 01:00 JST
**状態**: DRAFT

---

## 1. 目的

FX は中銀発表・経済指標（FOMC、CPI、雇用統計、BoJ、ECB など）で短期的に大きく動く。イベント前後数分〜数十分はスプレッド拡大・スリッページ増大・ギャップ発生のリスクが高いため、**MVP ではこの期間にトレードを避ける** 仕組みを提供する。

---

## 2. スコープ

**含む**:
- `economic_event` テーブル + Alembic マイグレーション
- CSV ローダー（手動メンテナンス前提、`scripts/load_economic_events.py`）
- `EconomicCalendar` ドメイン型（blackout 判定）
- `EventAwareStrategy` ラッパー（任意 Strategy を blackout で覆う）
- CLI オプション `--event-blackout-minutes` 経由でバックテスト / Paper Trading に統合できる拡張点

**含まない**:
- 自動スクレイピング（Forex Factory / investing.com は robots.txt / 利用規約に注意が必要）
- Trading Economics / Alpha Vantage 等の有料 API 統合
- 予想値・実績値・サプライズ計算（MVP は「高 impact イベントの時刻」だけ扱う）
- 通貨連動フィルタ（US イベントで EUR/USD もブラックアウト、等）→ Phase 4f 以降
- **ライブ Paper Trading への適用は Phase 4f 以降**（スケジューラ連携が必要）

---

## 3. データモデル

### 3.1 `economic_event` テーブル

| カラム | 型 | 備考 |
|-------|----|------|
| `id` | BIGSERIAL PK | |
| `event_time` | TIMESTAMPTZ NOT NULL | UTC |
| `currency` | CHAR(3) NOT NULL | 例: USD, JPY, EUR |
| `name` | VARCHAR(120) NOT NULL | 例: "FOMC Statement" |
| `impact` | SMALLINT NOT NULL | 1=Low, 2=Medium, 3=High |
| `forecast` | NUMERIC(18,6) NULL | 事前予想値（任意） |
| `actual` | NUMERIC(18,6) NULL | 実績値（任意） |
| `source` | VARCHAR(40) NOT NULL | `manual_csv` or 将来の API 名 |
| `created_at` | TIMESTAMPTZ | |

**インデックス**:
- `INDEX(event_time)` — 時系列検索
- `INDEX(currency, event_time)` — 通貨ごと検索
- `UNIQUE(event_time, currency, name)` — 重複防止

### 3.2 ドメイン

```python
@dataclass(frozen=True)
class EconomicEvent:
    event_time: datetime          # UTC
    currency: str
    name: str
    impact: int                   # 1..3
    forecast: Decimal | None = None
    actual: Decimal | None = None

class EconomicCalendar:
    def __init__(self, events: list[EconomicEvent]) -> None: ...
    def is_blackout(self, ts: datetime, instrument: str, minutes_before: int, minutes_after: int, min_impact: int = 3) -> bool: ...
    def events_for_instrument(self, instrument: str) -> list[EconomicEvent]: ...
```

**通貨 → instrument 対応**: `USD_JPY` なら USD と JPY のイベント両方を監視。`EUR_USD` なら EUR と USD。instrument の `base_currency` / `quote_currency` を split して参照。

---

## 4. CSV フォーマット

```
event_time,currency,name,impact,forecast,actual
2026-05-01T12:30:00Z,USD,Non-Farm Payrolls,3,175000,
2026-05-01T18:00:00Z,USD,FOMC Statement,3,,
2026-05-02T01:30:00Z,JPY,Tokyo CPI,2,2.5,2.6
```

- UTC タイムスタンプ（末尾 Z）
- impact は 1/2/3
- forecast / actual 空欄可
- 同一 `(event_time, currency, name)` は upsert（idempotent）

---

## 5. EventAwareStrategy ラッパー

```python
class EventAwareStrategy:
    def __init__(
        self,
        inner: Strategy,
        calendar: EconomicCalendar,
        instrument: str,
        minutes_before: int = 15,
        minutes_after: int = 30,
        min_impact: int = 3,
    ) -> None: ...

    def warmup_bars(self) -> int:
        return self.inner.warmup_bars()

    def on_bar(self, bar, snapshot) -> list[OrderSignal]:
        if calendar.is_blackout(bar.bar_time, instrument, before, after, impact):
            # ブラックアウト中は close のみ許可、open はブロック
            return [s for s in inner.on_bar(bar, snapshot) if s.kind not in ("open_long", "open_short")]
        return inner.on_bar(bar, snapshot)
```

open はブロックするが、既存ポジションの close は許容する（リスク減少方向は通す）。

---

## 6. CLI 統合

### 6.1 ロード: `scripts/load_economic_events.py`

```
uv run python scripts/load_economic_events.py --csv path/to/events.csv
```

CSV 読み込み → UPSERT（event_time, currency, name 一致なら更新）。

### 6.2 バックテスト連携

`scripts/backtest_run.py` に以下オプションを追加（Phase 4e の範囲外にしてもよいが、統合テストしやすさのため追加）:

```
--event-blackout-before 15 --event-blackout-after 30 --event-min-impact 3
```

省略時は event-aware なし（既存挙動）。指定時は DB から該当期間のイベントを取得して `EventAwareStrategy` でラップ。

---

## 7. ディレクトリ構成追加

```
src/
├── events/                    # ← 新規
│   ├── __init__.py
│   ├── calendar.py            # EconomicEvent, EconomicCalendar
│   ├── repository.py          # DB UPSERT / 期間取得
│   └── csv_loader.py          # CSV パース
├── strategy/
│   └── event_aware.py         # ← 新規
└── db/migrations/versions/
    └── 002_economic_event.py  # ← 新規
scripts/
└── load_economic_events.py    # ← 新規
tests/
├── events/
│   └── test_calendar.py
└── strategy/
    └── test_event_aware.py
```

---

## 8. 完了判定

1. Alembic で `002` マイグレーションが通り、`economic_event` テーブルが作成される
2. `load_economic_events.py` で CSV を投入できる
3. `EventAwareStrategy` がブラックアウト中の open を抑制するテストが通る
4. `uv run pytest` / `uv run ruff check` が green

---

## 9. 先送り

- 自動取得（API / スクレイピング）
- 予想 vs 実績のサプライズスコア計算
- 通貨連動フィルタ（`USD` イベントで `EUR_USD` もブラックアウト等は実装済みだが、影響係数は未チューニング）
- Paper Trading ライブへの適用（Phase 3 の polling 遅延とイベント判定の整合性検討が必要）
