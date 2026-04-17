# Phase 2 詳細設計 — バックテスト基盤

**作成**: 2026-04-17 23:00 JST
**前提**: [../20260417-1700-initial-design/conceptual-design.md](../20260417-1700-initial-design/conceptual-design.md), [../20260417-1830-phase0-detailed-design/detailed-design.md](../20260417-1830-phase0-detailed-design/detailed-design.md), [../20260417-2200-phase1-detailed-design/detailed-design.md](../20260417-2200-phase1-detailed-design/detailed-design.md)
**状態**: DRAFT

---

## 1. スコープ

**含む**:
- `BrokerGateway` Protocol（Phase 3 Paper Trading と共有）
- `MockBroker`（証拠金維持率チェック・強制ロスカット・スプレッド適用）
- シンプルなテクニカル戦略（Bollinger Bands 逆張り）と Strategy Protocol
- バックテストエンジン（バー単位リプレイ、翌バー始値約定）
- パフォーマンス指標計算（勝率・Profit Factor・MaxDD・総損益）
- Markdown レポート出力

**含まない**:
- Paper Trading（リアルタイムフロー、Phase 3）
- 戦略の自動探索（GA、Phase 4）
- 経済指標連携（Phase 4）
- 可視化（Web UI、Phase 5）
- マージンコール通知（Phase 3 以降）

---

## 2. 確定事項（概念設計・Phase 0 から継承）

- レバレッジは 1〜25 倍可変、ユーザ指定（戦略ごと）
- スプレッド: OANDA の bid/ask をそのまま反映（固定・時間変動なし）
- スリッページ: ゼロ（MVP 割り切り）
- スワップ: MVP は **0 円固定**（設計方針は §10.2 に記載。Phase 2 の中で後半スプリントで追加するかは工数次第）
- 週末ポジション禁止: **UTC 日またぎで全決済**（イントラデー前提）
- home currency: **JPY**（demo 口座が JPY 建て前提）

---

## 3. アーキテクチャ

```
┌──────────────────────────────────────────────────────┐
│                  BacktestEngine                       │
│                                                       │
│    for bar in bars:                                  │
│        1. broker.fill_pending(bar.open)   ← 翌バー始値 │
│        2. broker.mark_to_market(bar.close)           │
│        3. if margin_level < threshold: forced_close  │
│        4. signals = strategy.on_bar(bar, snapshot)   │
│        5. broker.submit(signals)                     │
│        6. if is_eod(bar): broker.close_all("eod")    │
└──────────┬──────────────────────────┬────────────────┘
           │                          │
    ┌──────▼─────────┐      ┌─────────▼────────┐
    │   Strategy     │      │  BrokerGateway   │
    │ (Protocol)     │      │  (Protocol)      │
    │                │      │                  │
    │ on_bar() →     │      │ submit_open()    │
    │   list[Signal] │      │ submit_close()   │
    │                │      │ fill_pending()   │
    │ Impl:          │      │ mark_to_market() │
    │ BollingerMR    │      │ margin_level()   │
    └────────────────┘      │ snapshot()       │
                            │                  │
                            │ Impl: MockBroker │
                            └──────────────────┘
```

---

## 4. データモデル

### 4.1 ドメインオブジェクト（`src/broker/orders.py`）

```python
@dataclass(frozen=True)
class OrderSignal:
    kind: Literal["open_long", "open_short", "close_position", "close_all"]
    units: int | None = None
    position_id: int | None = None

@dataclass
class Position:
    id: int
    instrument: str
    side: Literal["long", "short"]
    units: int                    # 常に正
    entry_price: Decimal          # 約定価格（スプレッド込み）
    entry_time: datetime
    entry_margin: Decimal         # 拘束された証拠金（home currency）
    leverage: int

@dataclass
class Trade:
    position_id: int
    instrument: str
    side: Literal["long", "short"]
    units: int
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_time: datetime
    pnl: Decimal                  # home currency
    exit_reason: Literal["signal", "eod", "margin_call", "end_of_run"]

@dataclass(frozen=True)
class PortfolioSnapshot:
    cash: Decimal                 # 利用可能残高
    equity: Decimal               # cash + Σ unrealized_pnl
    margin_used: Decimal
    margin_level_pct: Decimal     # equity / margin_used * 100。未保有時は Infinity
    positions: tuple[Position, ...]
```

### 4.2 戦略インターフェース（`src/strategy/base.py`）

```python
class Strategy(Protocol):
    def warmup_bars(self) -> int: ...            # 指標計算に必要な過去本数
    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]: ...
```

---

## 5. MockBroker 実装方針

### 5.1 約定価格（spread 反映）

- 新規 long（買い）: `bar.open.ask`
- 新規 short（売り）: `bar.open.bid`
- 決済 long（売り戻し）: `bar.*.bid` （mark-to-market は bar.close.bid）
- 決済 short（買い戻し）: `bar.*.ask`

スリッページなし、手数料ゼロ。

### 5.2 証拠金計算（home currency = JPY 前提）

- USD_JPY のように **quote = JPY** の場合、`notional_jpy = units × price`
- EUR_USD のように **quote ≠ JPY** の場合は Phase 4 以降で home 換算レートを導入する。MVP は USD_JPY 1 本に限定
- `margin_required = notional_jpy / leverage`
- ユーザ指定 leverage が `1 / instrument.margin_rate` を超える場合はエラー（例: instrument margin_rate=0.04 → 最大 25 倍、50 倍指定は reject）

### 5.3 マージンコール閾値

- `maintenance_margin_level_pct` パラメータ（デフォルト **100%**）
- `equity / margin_used × 100 < threshold` で**全ポジション強制クローズ**
- 国内業者の典型値に合わせたシンプル実装。業者別の 2 段階（margin call → liquidation）は Phase 5 で導入

### 5.4 約定タイミング

- 戦略は `bar_t` の終値までの情報（OHLC + close 時点スナップショット）を見て判断
- 発注は**内部キューに入り、`bar_{t+1}` の始値で約定**する（look-ahead 回避）
- 最終バーで発注された残注文は `end_of_run` として `bar_N.close` で約定

### 5.5 EOD 強制クローズ

- 連続するバーで UTC 日付が変わる時点で、**一つ前のバーの終値**を使い全ポジションを決済（exit_reason=eod）
- 実装上は「次バーを先読みして現バーが当日最後なら close_all」とする

---

## 6. バックテストエンジン（`src/backtest/engine.py`）

```python
@dataclass
class BacktestConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    maintenance_margin_level_pct: Decimal = Decimal("100")

@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: list[tuple[datetime, Decimal]]
    final_cash: Decimal
    config: BacktestConfig

def run_backtest(
    bars: Iterable[PriceBar],
    strategy: Strategy,
    broker: BrokerGateway,
    config: BacktestConfig,
) -> BacktestResult: ...
```

バーの取得元は DB（`price_bar_m1`）。CLI 側で bar iterator を構築して渡す。

---

## 7. Bollinger Bands 逆張り戦略（`src/strategy/bollinger.py`）

### 7.1 パラメータ

| 名前 | 既定値 | 説明 |
|------|-------|------|
| `window` | 20 | SMA / stddev の期間（バー単位） |
| `k` | 2.0 | バンド幅係数 |
| `units` | 10000 | 1 回あたりのロット（OANDA units） |
| `exit_on_sma_touch` | True | SMA タッチで決済するか |

### 7.2 ルール

- `close < lower_band` かつ無ポジションなら **open_long**
- `close > upper_band` かつ無ポジションなら **open_short**
- long 保有中、`close >= sma` → **close_position**
- short 保有中、`close <= sma` → **close_position**
- `warmup_bars = window`

---

## 8. パフォーマンス指標（`src/backtest/metrics.py`）

| 指標 | 式 |
|------|----|
| `total_pnl` | Σ trade.pnl |
| `trade_count` | len(trades) |
| `win_count` / `loss_count` | pnl > 0 / pnl < 0 の件数 |
| `win_rate` | win_count / trade_count |
| `profit_factor` | Σ(wins) / Σ|losses|。losses 0 のとき Infinity |
| `avg_win` / `avg_loss` | 平均勝ち幅・平均負け幅 |
| `max_drawdown` | equity_curve のピークトゥトラフ最大 |
| `max_drawdown_pct` | max_drawdown / peak × 100 |
| `final_equity` | equity_curve[-1] |

**Sharpe は MVP では計算しない**（適切なリスク無リターンレート・サンプリング粒度の議論が必要なため Phase 4 に先送り）。

---

## 9. レポート出力（`src/backtest/report.py`）

```
reports/backtests/backtest-YYYYMMDD-HHMMSS/{result}.md
```

内容:
- Config サマリ（instrument, period, leverage, initial_cash）
- パフォーマンス指標テーブル
- 最初・最後の 10 トレード一覧
- 終了時の equity

JSON 版も同ディレクトリに出力して機械可読にする（`result.json`）。

---

## 10. CLI（`scripts/backtest_run.py`）

```
uv run python scripts/backtest_run.py \
    --instrument USD_JPY \
    --from 2025-11-01 \
    --to 2026-04-01 \
    --initial-cash 1000000 \
    --leverage 10 \
    --strategy bollinger \
    --window 20 --k 2.0 --units 10000
```

DB から期間内の m1 バーを取得し backtest を実行、レポートを `reports/backtests/` に書き出す。

---

## 11. ディレクトリ構成の追加

```
src/
├── broker/                    # ← 新規
│   ├── __init__.py
│   ├── gateway.py             # BrokerGateway Protocol + エラー型
│   ├── mock.py                # MockBroker 実装
│   ├── orders.py              # Order / Position / Trade / PortfolioSnapshot
│   └── margin.py              # 証拠金計算ユーティリティ
├── strategy/                  # ← 新規
│   ├── __init__.py
│   ├── base.py                # Strategy Protocol + OrderSignal
│   └── bollinger.py
└── backtest/                  # ← 新規
    ├── __init__.py
    ├── engine.py              # run_backtest
    ├── metrics.py
    └── report.py
tests/
├── broker/
│   └── test_mock_broker.py
├── strategy/
│   └── test_bollinger.py
└── backtest/
    ├── test_engine.py
    └── test_metrics.py
scripts/
└── backtest_run.py
```

---

## 12. テスト戦略

- `test_mock_broker.py`:
  - 新規 long/short で margin が正しく拘束される
  - close で PnL が bid/ask スプレッド反映済みで算出される
  - maintenance_margin_level_pct 割れで全 close
  - leverage 超過は reject
- `test_bollinger.py`:
  - バンド下抜けで long シグナル、SMA タッチで close シグナル
  - warmup 期間中はシグナルなし
- `test_engine.py`:
  - 翌バー始値で約定
  - EOD で強制クローズ
  - end_of_run でも残ポジション決済
- `test_metrics.py`:
  - 単純な既知 trade リストから指標値を逆算チェック
  - drawdown 計算の境界（常に上昇・常に下降）

コスト計算整合性確認: BackTest で 1 trade を実行し、手動計算と PnL が完全一致することを 1 本の integration test で保証。

---

## 13. 完了判定

1. `uv run pytest` が green（新規テストすべて）
2. `uv run ruff check src/ tests/ scripts/` が green
3. 以下の手動コマンドでレポートが生成される:
   ```
   uv run python scripts/backtest_run.py --instrument USD_JPY --from ... --to ... --leverage 10
   ```
   （実行には Phase 1 で取得した price_bar_m1 データが必要）
4. レポート md に PnL・勝率・MaxDD が出ている

---

## 14. 先送り事項

- スワップ金利計算: Phase 2 終盤で再検討、必要なら Phase 3 に繰越
- 複数通貨ペア同時バックテスト: Phase 4
- Sharpe / Sortino / Calmar: Phase 4
- 戦略パラメータのグリッドサーチ: Phase 4
- ウォークフォワード分析: Phase 4
- home currency が USD / EUR 等の場合の換算: Phase 4（USD_JPY 以外取り扱い時）
