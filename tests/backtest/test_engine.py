from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.backtest.engine import BacktestConfig, run_backtest
from src.broker import MockBroker, OrderSignal
from src.broker.orders import PortfolioSnapshot
from src.domain.price import PriceBar
from tests._helpers import make_bar, usd_jpy_meta


class _ScriptedStrategy:
    """指定したバー index で指定シグナルを返すテスト用戦略。"""

    def __init__(self, plan: dict[int, list[OrderSignal]]) -> None:
        self._plan = plan
        self._i = -1

    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        self._i += 1
        return list(self._plan.get(self._i, []))


def test_fills_at_next_bar_open_not_current() -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(1, bid_close="154.200", ask_close="154.210", bid_open="154.150", ask_open="154.160"),
        make_bar(2, bid_close="154.300", ask_close="154.310"),
    ]
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        # T009: 単一日 bars でもイントラデイ絶対制約を満たすため session_close_utc_hours を付与
        session_close_utc_hours=frozenset({23}),
    )
    result = run_backtest(bars, strat, broker, config)

    # シグナルは bar 0 で発生、約定は bar 1 の ask.open=154.160
    assert len(broker.open_positions) + len(result.trades) == 1
    entry = broker.open_positions[0].entry_price if broker.open_positions else result.trades[0].entry_price
    assert entry == Decimal("154.160")


def test_eod_force_close_on_day_boundary() -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110", day=1),
        make_bar(1, bid_close="154.200", ask_close="154.210", day=1, bid_open="154.150", ask_open="154.160"),
        make_bar(0, bid_close="154.300", ask_close="154.310", day=2),
    ]
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
    )
    result = run_backtest(bars, strat, broker, config)

    # bar 1 が day=1 の最終バー → EOD で強制決済
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.exit_reason == "eod"
    assert t.entry_price == Decimal("154.160")
    assert t.exit_price == bars[1].bid.close  # 154.200


def test_end_of_run_closes_remaining_position() -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(1, bid_close="154.200", ask_close="154.210", bid_open="154.150", ask_open="154.160"),
    ]
    # bar 0 で open。bar 1 が同日最終バー → EOD で決済される
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        # T009: 単一日 bars でもイントラデイ絶対制約を満たすため session_close_utc_hours を付与
        session_close_utc_hours=frozenset({23}),
    )
    result = run_backtest(bars, strat, broker, config)
    assert len(broker.open_positions) == 0
    assert len(result.trades) == 1
