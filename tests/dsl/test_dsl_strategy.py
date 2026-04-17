from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.backtest import BacktestConfig, run_backtest
from src.broker import MockBroker
from src.dsl import DslStrategy, bollinger_genome
from tests._helpers import make_bar, usd_jpy_meta


def test_dsl_strategy_warmup_bars_equals_indicator_window() -> None:
    strat = DslStrategy(bollinger_genome(window=20, k=2.0, units=1000))
    assert strat.warmup_bars() == 20


def test_dsl_bollinger_produces_trades_on_downtrend() -> None:
    # 下落で band 下抜け → long、SMA 戻りで close
    prices = ["154.500"] * 5 + ["153.000"] * 3 + ["154.500"] * 5
    bars = []
    for i, p in enumerate(prices):
        bars.append(make_bar(i, bid_close=p, ask_close=str(Decimal(p) + Decimal("0.010"))))

    broker = MockBroker(instrument_meta=usd_jpy_meta())
    strat = DslStrategy(bollinger_genome(window=3, k=1.0, units=1000))
    config = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
    )
    result = run_backtest(bars, strat, broker, config)
    # 少なくとも 1 件のトレードが発生
    assert len(result.trades) >= 1
