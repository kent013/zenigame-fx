# 詳細設計: broker-snapshot-caching

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **バグ修正はテストファースト**（本 TODO はバグ修正ではなく最適化だが、selection invariance test を先に書く）
- **全施策にテスト必須**
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run 名・日付・セッション固有の識別子 NG）
- **テスト配置**: `tests/broker/test_mock_snapshot_cache.py` / `tests/broker/test_mock_snapshot_invariance.py`
- **uv 必須**: `uv run pytest tests/broker/ tests/backtest/ tests/alpha_factory/ tests/dsl/ -x`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.11（`pyproject.toml` 参照）

## 概念設計リファレンス

[devnotes/20260425-0158-broker-snapshot-caching/conceptual-design.md](./conceptual-design.md) — APPROVED (Round 4)

## 前提 verify 完了（実装開始条件チェックリスト）

| # | 前提 | 状態 | verify 結果 |
|---|---|---|---|
| P1 | BrokerGateway Protocol / MockBroker 唯一 | **Verified** | `src/broker/gateway.py:22` + `__init__.py` で MockBroker のみ concrete |
| P2 | PortfolioSnapshot frozen | **Verified** | `src/broker/orders.py:46` `@dataclass(frozen=True)` |
| P3 | Position mutable (frozen でない) | **Verified** | `src/broker/orders.py:20` `@dataclass`（frozen なし） |
| P4 | Position フィールド書き換え無し | **Verified** | `grep "\._positions\[" src/` で mock.py:313 の 1 箇所のみ。他モジュールからは書き込みなし。mutation 経路は `_open_position` での初期代入のみ |
| P5 | `_snapshot_at` call site は 2 箇所 | **Verified** | `mock.py:264` (`force_close_if_margin_call`) / `mock.py:281` (`snapshot()`) |
| P6 | docs に snapshot caching 設計なし | **Verified** | `docs/alpha_factory/` は MockBroker を consumer 視点で参照するのみ（cross-pair.md / terminology.md）。内部 snapshot 実装は記述なし |
| P7 | snapshot.positions 参照は read-only | **Verified** | `src/dsl/strategy.py:173` `if snapshot.positions:`, line 174 `pos = snapshot.positions[0]` — read のみ |
| P8 | broker tests 分割配置 | **Verified** | `tests/broker/test_mock_broker.py` + `test_mock_multi_currency.py` |
| P9 | cache key 安全性（object reference） | **Verified** | `src/domain/price.py:16-17` PriceBar `@dataclass(frozen=True)` |
| P10 | engine bar loop で同一 reference | **Verified** | `src/backtest/engine.py:115-167` の local `bar` 変数を全呼び出しに共有 |

### invalidate 網羅性 verify 完了

**`self._cash` 変更経路（全 4 箇所）**:
| # | ファイル行 | 操作 | invalidate 要否 |
|---|---|---|---|
| 1 | `mock.py:116` `self._cash = Decimal(0)` | `__init__` 初期化 | 不要（cache も未初期化） |
| 2 | `mock.py:133` `self._cash += amount` | `deposit` | **必要** |
| 3 | `mock.py:260` `self._cash -= total_cost` | `apply_bar_holding_cost` | **必要** |
| 4 | `mock.py:329` `self._cash += raw_pnl` | `_close_one` | **必要** |

**`self._positions` 変更経路（全 2 箇所）**:
| # | ファイル行 | 操作 | invalidate 要否 |
|---|---|---|---|
| 1 | `mock.py:117` `self._positions: dict[...] = {}` | `__init__` 初期化 | 不要 |
| 2 | `mock.py:313` `self._positions[pos.id] = pos` | `_open_position` 追加 | **必要** |
| 3 | `mock.py:319` `pos = self._positions.pop(position_id, None)` | `_close_one` 削除 | **必要** |

→ `deposit` / `apply_bar_holding_cost` / `_close_one` / `_open_position` の 4 箇所で `_invalidate()` を呼ぶ。`_close_one` が `_cash` 変更 + `_positions` 削除の両方を同 body で行うため、末尾 1 箇所の `_invalidate()` で両方カバー。

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 0 | **Position を frozen 化**（stale risk 根絶、Round 1 Critical 対応） | `src/broker/orders.py` | High |
| 1 | MockBroker に per-bar snapshot cache を追加（単一 tuple slot、カプセル化済み） | `src/broker/mock.py` | High |
| 2 | cache invariance / invalidation test（long/short 両方向 parametrize） | `tests/broker/test_mock_snapshot_cache.py` (新規) | High |
| 3 | frozen Position の immutability test | `tests/broker/test_mock_snapshot_invariance.py` (新規) | High |
| 4 | selection outcome invariance test | `tests/alpha_factory/test_stage_gate_selection_invariance.py` (新規) | High |

## 施策 0: Position を frozen 化（Round 1 Critical 対応）

### 背景
詳細設計 Round 1 Codex レビューで指摘:
> `snapshot.positions=tuple(self._positions.values())` は mutable `Position` を保持。その後 `Position` が in-place 変更されると、cached `positions` は更新される一方で `equity/margin_used` は cache 値のまま不整合化。

### 変更箇所
`src/broker/orders.py:20` の Position dataclass に `frozen=True` を付与。

### 現行コード
```python
@dataclass
class Position:
    id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    entry_margin: Decimal
    leverage: int
```

### 変更後コード
```python
@dataclass(frozen=True)
class Position:
    id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    entry_margin: Decimal
    leverage: int
```

### 影響範囲検証（Pre-verify）

`grep -rn "Position(" src/ tests/` + field 書き込み検索で以下を確認済み:
- Position は `src/broker/mock.py:302` と tests/**/test_*.py の 5 箇所で生成されるのみ
- **Position のフィールドに書き込む箇所は存在しない**（read-only consumer: `pos.side` / `pos.entry_time` / `pos.units` / `pos.entry_price` / `pos.entry_margin` / `pos.id`）
- 既存 test は constructor 呼び出しのみ → frozen 化しても全て合格する想定

### 波及変更
- `AGENTS.md`: 不要（内部データクラス、契約不変）
- `.claude/skills/*/SKILL.md`: 不要
- `config/alpha_factory/default.yaml`: 不要
- `docs/alpha_factory/*.md`: 不要

### テスト計画
- 既存 `tests/broker/test_mock_broker.py` / `tests/broker/test_mock_multi_currency.py` / `tests/dsl/test_strategy.py` 等が全合格
- 新規 test は施策 3 の immutability test で Position frozen 化を明示的に検証

### リスク
- 将来 Position に `unrealized_pnl` のような時変フィールドを追加したい場合、frozen だと `dataclasses.replace` で新オブジェクト生成が必要。性能リスクは軽微（position 数は max_pos=1 が default）
- 本 TODO 時点ではそのような拡張は予定されていない

## 施策 1: MockBroker に per-bar snapshot cache を追加

### 変更箇所

`src/broker/mock.py::MockBroker`

### 波及変更

- `AGENTS.md`: 不要（内部最適化、インターフェース不変）
- `.claude/skills/zenigame-fx-*/SKILL.md`: 不要
- `config/alpha_factory/default.yaml`: 不要
- `docs/alpha_factory/*.md`: 不要（broker 内部実装、既存 docs は consumer 視点の言及のみ）

### 現行コード（抜粋）

```python
# mock.py:79-127 (__init__ 抜粋)
class MockBroker:
    def __init__(
        self,
        instrument_meta: InstrumentMeta,
        *,
        home_currency: str | None = None,
        maintenance_margin_level_pct: Decimal = Decimal("100"),
    ) -> None:
        # ... 既存初期化 ...
        self._meta = instrument_meta
        self._home = resolved_home
        self._maintenance_pct = maintenance_margin_level_pct
        self._cash = Decimal(0)
        self._positions: dict[int, Position] = {}
        self._trades: list[Trade] = []
        self._pending: list[tuple[OrderSignal, int]] = []
        self._next_position_id = 1
        self._last_bar: PriceBar | None = None
        self._max_spread_bps: Decimal | None = None
        self._last_close_spread_bps: Decimal | None = None
        self._holding_cost_by_position: dict[int, Decimal] = {}
```

```python
# mock.py:130-134 (deposit)
    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._cash += amount
```

```python
# mock.py:220-261 (apply_bar_holding_cost 抜粋)
    def apply_bar_holding_cost(
        self, bar: PriceBar, *, per_day_bps: Decimal, bar_minutes: int,
    ) -> Decimal:
        if per_day_bps <= 0 or bar_minutes <= 0 or not self._positions:
            return Decimal(0)
        # ... per_bar_bps / total_cost 計算 ...
        if total_cost > 0:
            self._cash -= total_cost
        return total_cost
```

```python
# mock.py:263-269 (force_close_if_margin_call)
    def force_close_if_margin_call(self, bar: PriceBar) -> list[Trade]:
        snap = self._snapshot_at(bar)
        if snap.margin_used == 0:
            return []
        if snap.margin_level_pct is not None and snap.margin_level_pct < self._maintenance_pct:
            return self._close_all_internal(bar, exit_kind="close", reason="margin_call")
        return []
```

```python
# mock.py:276-281 (snapshot)
    def snapshot(self) -> PortfolioSnapshot:
        if self._last_bar is None:
            return PortfolioSnapshot(
                cash=self._cash, equity=self._cash, margin_used=Decimal(0), margin_level_pct=None, positions=()
            )
        return self._snapshot_at(self._last_bar)
```

```python
# mock.py:297-316 (_open_position)
    def _open_position(
        self, side: PositionSide, units: int, entry_price: Decimal, entry_time, leverage: int
    ) -> Position:
        notional = notional_home_currency(units=units, price_quote_per_base=entry_price, quote_is_home=True)
        margin = required_margin(notional, leverage)
        pos = Position(
            id=self._next_position_id,
            # ... 省略 ...
        )
        self._next_position_id += 1
        self._positions[pos.id] = pos
        return pos
```

```python
# mock.py:318-343 (_close_one)
    def _close_one(self, position_id: int, bar: PriceBar, exit_kind: str, reason: ExitReason) -> Trade | None:
        pos = self._positions.pop(position_id, None)
        if pos is None:
            return None
        # ... raw_pnl / cost_accum / net_pnl 計算 ...
        self._cash += raw_pnl
        trade = Trade(...)
        self._trades.append(trade)
        return trade
```

```python
# mock.py:371-384 (_snapshot_at)
    def _snapshot_at(self, bar: PriceBar) -> PortfolioSnapshot:
        unrealized = sum((self._unrealized_pnl(p, bar) for p in self._positions.values()), Decimal(0))
        equity = self._cash + unrealized
        margin_used = sum((p.entry_margin for p in self._positions.values()), Decimal(0))
        margin_level: Decimal | None = None
        if margin_used > 0:
            margin_level = equity / margin_used * Decimal(100)
        return PortfolioSnapshot(
            cash=self._cash,
            equity=equity,
            margin_used=margin_used,
            margin_level_pct=margin_level,
            positions=tuple(self._positions.values()),
        )
```

### 変更後コード

```python
# mock.py:79-127 (__init__ 変更)
class MockBroker:
    def __init__(
        self,
        instrument_meta: InstrumentMeta,
        *,
        home_currency: str | None = None,
        maintenance_margin_level_pct: Decimal = Decimal("100"),
    ) -> None:
        # ... 既存初期化 (resolved_home 等) ...
        self._meta = instrument_meta
        self._home = resolved_home
        self._maintenance_pct = maintenance_margin_level_pct
        self._cash = Decimal(0)
        self._positions: dict[int, Position] = {}
        self._trades: list[Trade] = []
        self._pending: list[tuple[OrderSignal, int]] = []
        self._next_position_id = 1
        self._last_bar: PriceBar | None = None
        self._max_spread_bps: Decimal | None = None
        self._last_close_spread_bps: Decimal | None = None
        self._holding_cost_by_position: dict[int, Decimal] = {}
        # snapshot cache: per-bar PortfolioSnapshot を保持し
        # 3 calls/bar → 1 call/bar に削減する（O(N²)→O(N) 最適化）
        # 単一 tuple slot (bar, snapshot) で atomic 更新・None で invalidate
        # (Round 1 Warning #3 対応: 2 変数分離更新の中間状態を排除)
        self._snapshot_cache: tuple[PriceBar, PortfolioSnapshot] | None = None
```

```python
# mock.py: deposit に invalidate 追加
    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._cash += amount
        self._invalidate_snapshot_cache()
```

```python
# mock.py: apply_bar_holding_cost に invalidate 追加
    def apply_bar_holding_cost(
        self, bar: PriceBar, *, per_day_bps: Decimal, bar_minutes: int,
    ) -> Decimal:
        if per_day_bps <= 0 or bar_minutes <= 0 or not self._positions:
            return Decimal(0)
        # ... per_bar_bps / total_cost 計算 (不変) ...
        if total_cost > 0:
            self._cash -= total_cost
            self._invalidate_snapshot_cache()
        return total_cost
```

```python
# mock.py: _open_position に invalidate 追加
    def _open_position(
        self, side: PositionSide, units: int, entry_price: Decimal, entry_time, leverage: int
    ) -> Position:
        # ... 既存ロジック (notional / margin / Position 生成) 不変 ...
        self._next_position_id += 1
        self._positions[pos.id] = pos
        self._invalidate_snapshot_cache()
        return pos
```

```python
# mock.py: _close_one に invalidate 追加
    def _close_one(self, position_id: int, bar: PriceBar, exit_kind: str, reason: ExitReason) -> Trade | None:
        pos = self._positions.pop(position_id, None)
        if pos is None:
            return None
        # ... 既存ロジック (raw_pnl / cost_accum / net_pnl / trade 生成) 不変 ...
        self._cash += raw_pnl
        trade = Trade(...)
        self._trades.append(trade)
        self._invalidate_snapshot_cache()
        return trade
```

```python
# mock.py:371-384 (_snapshot_at) — cache 経路を先頭に追加
    def _snapshot_at(self, bar: PriceBar) -> PortfolioSnapshot:
        # cache hit: 単一 tuple slot で atomic に判定
        # (Round 1 Warning #3 対応: 例外時の中間状態排除)
        # (Round 3 Critical 対応: object reference で id 再利用回避)
        cache = self._snapshot_cache
        if cache is not None and cache[0] is bar:
            return cache[1]
        # cache miss: 既存ロジックで compute (ロジック本体は不変)
        unrealized = sum(
            (self._unrealized_pnl(p, bar) for p in self._positions.values()),
            Decimal(0),
        )
        equity = self._cash + unrealized
        margin_used = sum(
            (p.entry_margin for p in self._positions.values()),
            Decimal(0),
        )
        margin_level: Decimal | None = None
        if margin_used > 0:
            margin_level = equity / margin_used * Decimal(100)
        snapshot = PortfolioSnapshot(
            cash=self._cash,
            equity=equity,
            margin_used=margin_used,
            margin_level_pct=margin_level,
            positions=tuple(self._positions.values()),
        )
        # cache 書き込み: 1 回の tuple 代入で atomic に更新
        # 例外時はここに到達しないため中間状態が残らない
        self._snapshot_cache = (bar, snapshot)
        return snapshot

    def _invalidate_snapshot_cache(self) -> None:
        """次回 _snapshot_at 呼び出しで cache miss を強制する。

        cash / positions の変化時に呼ぶ。bar 進行による invalidate は
        `cache[0] is bar` の identity 比較で自動検出されるため不要。

        単一スロットに None 代入で invalidate 完了 (atomic)。
        """
        self._snapshot_cache = None
```

### ルックアヘッドバイアスチェック

- [x] 未来バー参照なし（broker 層の変更であり primitive / 指標計算は触らない）
- [x] 当日確定値の先取りなし
- [x] rolling window 方向が過去方向（N/A）
- [x] 正規化にローカル window or rolling 関数を使用（N/A）
- [x] バケット / グループ平均が因果的（N/A）
- [x] cumsum/accumulate が因果的方向（N/A）

### パフォーマンスチェック

- [x] `compute_all_bars()` が実装されている（N/A - primitive ではない）
- [x] 内側ループ内で NumPy 関数を呼んでいない（broker 層、numpy 未使用）
- [x] SoA プロパティ使用（N/A）
- [x] 同一配列のキャッシュ（**本施策が該当。PortfolioSnapshot object を per-bar でキャッシュ**）

### テスト計画

- [x] バグ修正ではないため「再現テスト先行」は不要。ただし **selection invariance test** を TDD で先行
- [x] 既存テスト更新: なし（インターフェース不変、既存テストは snapshot 値を確認するため変更不要）
- [x] 新規テスト: 施策 2-4 で定義

### リスク

- **cache miss のコスト**: cache hit 判定 1 つ追加により cache miss 時に 1 比較分のオーバーヘッド。profile では cache hit が 2/3 を占めるため、1/3 の cache miss 時に 1 比較 ≈ 2% 未満のオーバーヘッド。hit 時の削減（全体の 2/3 × compute 時間）がこれを大幅に上回る
- **Python identity 比較の fallback**: `bar is self._cached_bar` は `None is None` でも True を返すが、`_cached_snapshot is not None` との複合条件で保護しているため安全
- **thread safety**: MockBroker は元々 single-threaded 前提（GA worker は process-level 並列）。本変更でも前提は不変
- **例外時の cache 状態**: `_snapshot_at` 本体が例外を投げると cache が古いままになる可能性があるが、現行コードの例外経路は存在しない（Decimal 演算のみ）

## 施策 2: cache invariance / invalidation test 追加

### 変更箇所

`tests/broker/test_mock_snapshot_cache.py` (新規)

### 波及変更
- `AGENTS.md` / skills / config / docs: 不要

### テスト構造

```python
"""MockBroker snapshot cache の invariance / invalidation テスト。

broker-snapshot-caching (devnotes/20260425-0158-broker-snapshot-caching) で
導入した per-bar snapshot cache が以下を満たすことを検証する:
  - 同一 bar で複数回呼ぶと cache hit（同一オブジェクトを返す）
  - 新しい bar / position 変化 / cash 変化で cache miss（再計算される）
  - duplicate timestamp + 別 object でも cache miss（object identity 判定）
  - cache 有無で PortfolioSnapshot の数値が bit-identical
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.broker.mock import InstrumentMeta, MockBroker
from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import Ohlc, PriceBar


def _meta() -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def _bar(hour: int = 0, minute: int = 0, bid_close: str = "154.00") -> PriceBar:
    bt = datetime(2026, 4, 1, hour, minute, 0, tzinfo=UTC)
    b = Decimal(bid_close)
    a = b + Decimal("0.01")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(b, b, b, b),
        ask=Ohlc(a, a, a, a),
        volume=1,
        complete=True,
    )


def _broker_with_position(side: str = "open_long") -> tuple[MockBroker, PriceBar]:
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.submit(OrderSignal(kind=side, units=10000), leverage=10)  # type: ignore[arg-type]
    broker.fill_pending(bar)
    broker.mark_to_market(bar)
    return broker, bar


# Round 1 Warning #4 対応: long/short 両方向で cache invariance を検証
@pytest.mark.parametrize("side", ["open_long", "open_short"])
def test_snapshot_cache_hit_returns_identical_object(side: str) -> None:
    broker, bar = _broker_with_position(side=side)
    s1 = broker._snapshot_at(bar)
    s2 = broker._snapshot_at(bar)
    assert s1 is s2, "same bar should return cached object (is comparison)"


@pytest.mark.parametrize("side", ["open_long", "open_short"])
def test_snapshot_cache_values_symmetric_for_long_short(side: str) -> None:
    """long/short 両方向で cache hit / miss の値一貫性を確認。"""
    broker, bar = _broker_with_position(side=side)
    s1 = broker._snapshot_at(bar)
    broker._invalidate_snapshot_cache()
    s2 = broker._snapshot_at(bar)
    assert s1.cash == s2.cash
    assert s1.equity == s2.equity
    assert s1.margin_used == s2.margin_used
    assert s1.margin_level_pct == s2.margin_level_pct


def test_snapshot_cache_miss_on_new_bar() -> None:
    broker, bar = _broker_with_position()
    s1 = broker._snapshot_at(bar)
    next_bar = _bar(minute=1, bid_close="154.05")
    broker.mark_to_market(next_bar)
    s2 = broker._snapshot_at(next_bar)
    assert s1 is not s2


def test_snapshot_invalidates_on_position_open() -> None:
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.mark_to_market(bar)
    s_before = broker._snapshot_at(bar)
    # position を open
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_before.margin_used == Decimal(0)
    assert s_after.margin_used > Decimal(0)


def test_snapshot_invalidates_on_position_close() -> None:
    broker, bar = _broker_with_position()
    s_before = broker._snapshot_at(bar)
    # close all positions
    broker.close_all(bar, reason="signal")
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.margin_used == Decimal(0)


def test_snapshot_invalidates_on_holding_cost() -> None:
    broker, bar = _broker_with_position()
    s_before = broker._snapshot_at(bar)
    cost = broker.apply_bar_holding_cost(
        bar, per_day_bps=Decimal("10"), bar_minutes=1,
    )
    assert cost > 0
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.cash < s_before.cash


def test_snapshot_invalidates_on_deposit() -> None:
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.mark_to_market(bar)
    s_before = broker._snapshot_at(bar)
    broker.deposit(Decimal("500000"))
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.cash == s_before.cash + Decimal("500000")


def test_snapshot_invalidates_on_chained_close() -> None:
    """Round 1 Critical 対応: force_close_if_margin_call などで
    _close_all_internal → _close_one × N を実行した直後の snapshot が、
    毎回再計算された結果と一致すること。
    """
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)
    s_before = broker._snapshot_at(bar)
    assert s_before.margin_used > Decimal(0)
    # chain close: 全 position を同 bar で close
    broker.close_all(bar, reason="eod")
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.margin_used == Decimal(0)
    assert len(s_after.positions) == 0


def test_snapshot_duplicate_timestamp_different_prices() -> None:
    """Round 2 Critical 対応: 同一 bar_time を持つ異なる PriceBar オブジェクトを
    連続で渡した際に cache miss が発生して異なる snapshot を返すこと。
    bar_time のみで判定していると stale snapshot を返してしまう反証ケース。
    """
    broker, bar_a = _broker_with_position()
    # 同じ bar_time だが別 object (bid_close が異なる)
    bar_b = _bar(bid_close="154.50")
    assert bar_a.bar_time == bar_b.bar_time
    assert bar_a is not bar_b
    s_a = broker._snapshot_at(bar_a)
    s_b = broker._snapshot_at(bar_b)
    assert s_a is not s_b, "different bar objects should always miss cache"
    # 価格が違うので unrealized PnL も変わる → equity が異なる
    assert s_a.equity != s_b.equity


def test_snapshot_object_reference_identity() -> None:
    """Round 3 Critical 対応: object reference cache が id 再利用問題を
    回避することを模擬検証する。同一 bar_time + 同一内容だが別 object の
    PriceBar で cache miss を確認。
    """
    broker, bar_a = _broker_with_position()
    # 内容完全同一だが別 object
    bar_clone = PriceBar(
        pair_name=bar_a.pair_name,
        bar_time=bar_a.bar_time,
        bid=bar_a.bid,
        ask=bar_a.ask,
        volume=bar_a.volume,
        complete=bar_a.complete,
    )
    assert bar_a is not bar_clone
    assert bar_a == bar_clone  # frozen dataclass equality
    s_a = broker._snapshot_at(bar_a)
    s_clone = broker._snapshot_at(bar_clone)
    assert s_a is not s_clone  # reference 判定なので miss
    # ただし内容は同一なので値は一致
    assert s_a.cash == s_clone.cash
    assert s_a.equity == s_clone.equity
    assert s_a.margin_used == s_clone.margin_used


def test_snapshot_values_bit_identical_cache_vs_no_cache() -> None:
    """cache 有効 / 無効で equity / margin_used / margin_level_pct / positions
    が完全一致することを 100 bar 分 record して確認。selection invariance の
    原子的保証。
    """
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)

    bars = [
        _bar(hour=h, minute=m, bid_close=f"{154 + (h * 60 + m) * 0.001:.3f}")
        for h in range(5) for m in range(20)
    ]

    values_with_cache: list[tuple] = []
    for bar in bars:
        broker.fill_pending(bar)
        broker.mark_to_market(bar)
        s = broker.snapshot()
        values_with_cache.append(
            (s.cash, s.equity, s.margin_used, s.margin_level_pct)
        )

    # もう一度 broker を作り直して cache 無効化 (手動で invalidate を連打して
    # 常に miss を強制) で同じ bars を流す
    broker2 = MockBroker(instrument_meta=_meta())
    broker2.deposit(Decimal("1000000"))
    broker2.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    values_without_cache: list[tuple] = []
    for bar in bars:
        broker2.fill_pending(bar)
        broker2.mark_to_market(bar)
        broker2._invalidate_snapshot_cache()  # 毎回強制 miss
        s = broker2.snapshot()
        values_without_cache.append(
            (s.cash, s.equity, s.margin_used, s.margin_level_pct)
        )

    assert values_with_cache == values_without_cache, \
        "snapshot values must be bit-identical with/without cache"
```

### ルックアヘッドバイアスチェック / パフォーマンスチェック
- N/A（テストコード）

### リスク
- test fixture の bar 生成が重複して broker モジュールの内部参照に敏感。test_mock_broker.py 既存 fixture との整合性は確認済み（単純な PriceBar / InstrumentMeta）

## 施策 3: frozen Position の immutability test（Round 1 Warning 対応）

### 変更箇所

`tests/broker/test_mock_snapshot_invariance.py` (新規)

### 背景

詳細設計 Round 1 Codex レビュー指摘:
> 施策 3 の旧版 test (`sp is bp`) は identity を固定化し、将来の防御コピー/不変化リファクタを阻害する。identity ではなく「値一致 + mutation 不可」を検証すべき。

→ 施策 0 で Position を frozen 化したため、identity test ではなく **frozen 不変条件の test** に差し替える。

### 波及変更
- AGENTS.md / skills / config / docs: 不要

### テスト構造

```python
"""MockBroker snapshot の immutability invariance テスト。

施策 0 で Position を @dataclass(frozen=True) 化したことを受け、以下を検証:
  - Position field 書き換えが FrozenInstanceError を投げる
  - snapshot.positions の値が broker._positions.values() と等価 (==)
  - Position を mutate しようとすると即座に例外で失敗する
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.broker.mock import InstrumentMeta, MockBroker
from src.broker.orders import OrderSignal, Position


def _meta() -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def _bar():
    from src.domain.price import Ohlc, PriceBar
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    b = Decimal("154.00")
    a = b + Decimal("0.01")
    return PriceBar(
        pair_name="USD_JPY", bar_time=bt,
        bid=Ohlc(b, b, b, b), ask=Ohlc(a, a, a, a),
        volume=1, complete=True,
    )


def test_position_is_frozen() -> None:
    """Position が @dataclass(frozen=True) で field 書き換えが禁止されていること。"""
    pos = Position(
        id=1, instrument="USD_JPY", side="long", units=10000,
        entry_price=Decimal("154.00"),
        entry_time=datetime(2026, 4, 1, tzinfo=UTC),
        entry_margin=Decimal("5000"), leverage=10,
    )
    with pytest.raises(FrozenInstanceError):
        pos.entry_price = Decimal("155.00")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        pos.units = 20000  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        pos.entry_margin = Decimal("1000")  # type: ignore[misc]


def test_snapshot_positions_equal_broker_positions() -> None:
    """snapshot.positions の内容が broker._positions.values() と == で等価。

    identity ではなく equality で比較（将来の防御コピー化にも耐える）。
    """
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)
    snap = broker.snapshot()
    broker_positions = list(broker._positions.values())
    assert list(snap.positions) == broker_positions, (
        "snapshot.positions value must equal broker._positions.values()"
    )
```

### リスク
- Position に `replace`-based update が必要な将来設計では frozen 解除が必要。その場合 snapshot cache の invalidate 契約を見直す必要がある（design review でチェック）

## 施策 4: selection outcome invariance test 追加

### 変更箇所

`tests/alpha_factory/test_stage_gate_selection_invariance.py` (新規)

### 波及変更
- AGENTS.md / skills / config / docs: 不要

### テスト構造

```python
"""broker-snapshot-caching 導入前後で Stage A/B 通過判定が bit-identical で
あることを直接検証する selection outcome invariance テスト。

通常の unit test と違い、実際の DslStrategy + RegistryEvaluator +
run_backtest + evaluate_stage_a を通して PortfolioSnapshot の数値が GA
selection に影響しないことを保証する。

cache 無効化 (broker._invalidate_snapshot_cache() を on_bar 毎に手動呼び
出し) と有効化で、評価結果の各フィールドが完全一致することを確認。
"""

# （run_ga 既存 fixture が使えれば activate。なければ最小 Genome を組む）
```

注: このテストは既存の `tests/alpha_factory/test_stage_gate.py` のパターンを流用する。最小 Genome + F1 primitive で Stage A を走らせ、`cache enabled / cache disabled（invalidate 強制）` の 2 経路で `StageResult.passed` / `metrics["payload"]["fitness_pen"]` / `sharpe_raw` / `trade_count` が一致することを assert する。

実装細部は詳細設計レビュー後に codex と相談して確定する（既存 fixture の再利用範囲が広いため）。

### リスク
- 実装難易度は他 3 施策より高い（fixture 依存が深い）。ただし施策 2 の `test_snapshot_values_bit_identical_cache_vs_no_cache` で PortfolioSnapshot レベルの bit-identical は保証されるため、施策 4 は追加の safety net

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 既存 broker インターフェース不変、MockBroker 内部実装のみ。main branch に対する追加変更として小規模（1 file + 3 test files）。worktree で実装 → review → merge の標準フロー |
| 競合リスク | 現在 main にアクティブな broker 変更 TODO は無し（最後の mock.py 変更は T019 per-pair home mode, 2026-04-24）。conflict リスクはゼロ |
| 想定実装時間 | 短〜中（本体 ~1h + test ~2h + review ~30min = 合計 3-4h） |

## コミット計画

1. `feat(broker): add per-bar snapshot cache to MockBroker (T?????)`
   - `src/broker/mock.py` 変更
   - `tests/broker/test_mock_snapshot_cache.py` 追加
   - `tests/broker/test_mock_snapshot_invariance.py` 追加
2. `test(alpha_factory): selection invariance for broker snapshot cache`
   - `tests/alpha_factory/test_stage_gate_selection_invariance.py` 追加

## Phase 7 検証手順

1. `profile-optimize` Phase 7 で EUR_JPY + USD_JPY の 2 ペア × 2 seed で再プロファイル
2. `_snapshot_at` cumtime 削減率を測定（target: 60% 以上）
3. RUN 全体時間の短縮率を測定（target: 10% 以上）
4. 各プロファイル RUN の `best_genome.fitness_pen` / Stage A/B/C pass counts を baseline と比較（**bit-identical が必須**）
5. 結果が `INCONCLUSIVE` なら（n<3 で target 未達）、n を増やして再判定

## Round 1-4 Codex レビュー対応マップ（概念設計）

（conceptual-design.md の対応マップ参照）

## 詳細設計追記の対応マップ

- 冒頭の「前提 verify 完了」セクションで P4-P10 を Verified 化（実装開始条件を満たす）
- invalidate 網羅性チェックを具体的な grep 結果で記録（4 箇所特定）
- 各施策に波及変更 / LoB / パフォーマンスチェックを記述
- リスクセクションで cache miss オーバーヘッド / thread safety / 例外経路を明示
