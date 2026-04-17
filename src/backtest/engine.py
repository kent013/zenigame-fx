from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import structlog

from src.broker.mock import MockBroker
from src.broker.orders import Trade
from src.domain.price import PriceBar
from src.strategy.base import Strategy

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BacktestConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]
    equity_curve: list[tuple[datetime, Decimal]] = field(default_factory=list)


def run_backtest(
    bars: Iterable[PriceBar],
    strategy: Strategy,
    broker: MockBroker,
    config: BacktestConfig,
) -> BacktestResult:
    broker.deposit(config.initial_cash)
    bars_list = list(bars)

    equity_curve: list[tuple[datetime, Decimal]] = []

    for i, bar in enumerate(bars_list):
        # 1. 前 bar で発注した注文を今 bar の始値で約定
        broker.fill_pending(bar)

        # 2. 現バー close で mark-to-market
        broker.mark_to_market(bar)

        # 3. マージンコール判定
        broker.force_close_if_margin_call(bar)

        # 4. 戦略判断（close までの情報を参照）
        snapshot = broker.snapshot()
        signals = strategy.on_bar(bar, snapshot)
        for signal in signals:
            broker.submit(signal, leverage=config.leverage)

        # 5. EOD（次バーが別 UTC 日 / 次バーが無い）なら強制クローズ
        next_bar = bars_list[i + 1] if i + 1 < len(bars_list) else None
        is_eod = next_bar is None or next_bar.bar_time.date() != bar.bar_time.date()
        if is_eod and broker.open_positions:
            broker.close_all(bar, reason="eod")

        # 6. equity curve 記録（EOD クローズ後の状態）
        equity_curve.append((bar.bar_time, broker.snapshot().equity))

    # 7. 最終バー以降に残っているはずのない注文だが、保険として端数決済
    if broker.open_positions and bars_list:
        broker.close_all(bars_list[-1], reason="end_of_run")

    logger.info(
        "backtest.finished",
        instrument=config.instrument,
        bars=len(bars_list),
        trades=len(broker.trades),
        final_equity=str(broker.snapshot().equity),
    )
    return BacktestResult(config=config, trades=broker.trades, equity_curve=equity_curve)
