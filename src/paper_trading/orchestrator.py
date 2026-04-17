from __future__ import annotations

import threading
from decimal import Decimal

import structlog

from src.broker.mock import MockBroker
from src.domain.price import PriceBar
from src.paper_trading.events import EventLogger
from src.paper_trading.feed import BarFeed
from src.strategy.base import Strategy

logger = structlog.get_logger(__name__)


class PaperTradingOrchestrator:
    def __init__(
        self,
        feed: BarFeed,
        strategy: Strategy,
        broker: MockBroker,
        logger_: EventLogger,
        leverage: int,
        initial_cash: Decimal,
    ) -> None:
        self._feed = feed
        self._strategy = strategy
        self._broker = broker
        self._event_logger = logger_
        self._leverage = leverage
        self._initial_cash = initial_cash
        self._stop_event = threading.Event()
        self._last_bar_date: str | None = None
        self._day_trades: list = []

    def request_stop(self) -> None:
        self._stop_event.set()
        self._feed.stop()

    def run(self) -> None:
        self._broker.deposit(self._initial_cash)
        last_bar: PriceBar | None = None

        try:
            for bar in self._feed:
                if self._stop_event.is_set():
                    break

                # 1. 前 bar の発注を約定
                fills = self._broker.fill_pending(bar)
                for trade in fills:
                    self._event_logger.log_trade(trade)
                    self._day_trades.append(trade)

                # 2. mark-to-market
                self._broker.mark_to_market(bar)

                # 3. margin call check
                mc_trades = self._broker.force_close_if_margin_call(bar)
                for trade in mc_trades:
                    self._event_logger.log_trade(trade)
                    self._day_trades.append(trade)

                # 4. EOD 判定: bar の UTC 日付が前回から変わったら、直前の bar_date 分を集計
                bar_date = bar.bar_time.date().isoformat()
                if self._last_bar_date is not None and bar_date != self._last_bar_date:
                    # 前日の残ポジションは前日最終バーで既に閉じていることが理想だが、
                    # ここでも保険として close する（Live では先読みできないため）
                    if last_bar is not None and self._broker.open_positions:
                        eod_trades = self._broker.close_all(last_bar, reason="eod")
                        for trade in eod_trades:
                            self._event_logger.log_trade(trade)
                            self._day_trades.append(trade)
                    self._event_logger.write_daily_summary(
                        self._last_bar_date, self._day_trades, self._broker.snapshot()
                    )
                    self._day_trades = []
                self._last_bar_date = bar_date

                # 5. 戦略判断
                snapshot = self._broker.snapshot()
                signals = self._strategy.on_bar(bar, snapshot)
                for signal in signals:
                    self._broker.submit(signal, leverage=self._leverage)
                    self._event_logger.log_signal(signal, bar, snapshot)

                # 6. bar サマリを log
                self._event_logger.log_bar(bar, self._broker.snapshot())
                last_bar = bar

        finally:
            # 終了時に残ポジションを end_of_run として決済
            if last_bar is not None and self._broker.open_positions:
                end_trades = self._broker.close_all(last_bar, reason="end_of_run")
                for trade in end_trades:
                    self._event_logger.log_trade(trade)
                    self._day_trades.append(trade)
            if self._last_bar_date is not None and self._day_trades:
                self._event_logger.write_daily_summary(self._last_bar_date, self._day_trades, self._broker.snapshot())
            self._event_logger.flush()
            logger.info(
                "paper_trading.finished",
                trades=len(self._broker.trades),
                final_equity=str(self._broker.snapshot().equity),
            )
