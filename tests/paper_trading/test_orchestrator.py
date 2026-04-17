from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from src.broker import MockBroker, OrderSignal
from src.broker.orders import PortfolioSnapshot
from src.domain.price import PriceBar
from src.paper_trading import EventLogger, PaperTradingOrchestrator, ReplayBarFeed
from tests._helpers import make_bar, usd_jpy_meta


class _ScriptedStrategy:
    def __init__(self, plan: dict[int, list[OrderSignal]]) -> None:
        self._plan = plan
        self._i = -1

    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        self._i += 1
        return list(self._plan.get(self._i, []))


def test_orchestrator_writes_signal_and_trade_events(tmp_path: Path) -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(1, bid_close="154.200", ask_close="154.210", bid_open="154.150", ask_open="154.160"),
        make_bar(2, bid_close="154.300", ask_close="154.310", bid_open="154.250", ask_open="154.260"),
    ]
    # bar 0 で open_long、bar 1 で close_position
    # position_id はまだ確定していないので「close_all」でシンプルに検証
    strat = _ScriptedStrategy(
        {
            0: [OrderSignal(kind="open_long", units=10000)],
            1: [OrderSignal(kind="close_all")],
        }
    )
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    ev = EventLogger(tmp_path)
    orch = PaperTradingOrchestrator(
        feed=ReplayBarFeed(bars, speedup=0),
        strategy=strat,
        broker=broker,
        logger_=ev,
        leverage=10,
        initial_cash=Decimal("1000000"),
    )
    orch.run()

    # events.jsonl の kind を集計
    kinds: list[str] = []
    with (tmp_path / "events.jsonl").open() as f:
        for line in f:
            kinds.append(json.loads(line)["kind"])

    assert "signal" in kinds  # open_long と close_all の 2 回
    assert "trade" in kinds  # close_all の fill
    assert "bar" in kinds  # 各 bar で記録


def test_orchestrator_end_of_run_closes_open_positions(tmp_path: Path) -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(1, bid_close="154.200", ask_close="154.210", bid_open="154.150", ask_open="154.160"),
    ]
    # bar 0 で open、以降 close なし → 終了時に end_of_run で決済される
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    ev = EventLogger(tmp_path)
    orch = PaperTradingOrchestrator(
        feed=ReplayBarFeed(bars, speedup=0),
        strategy=strat,
        broker=broker,
        logger_=ev,
        leverage=10,
        initial_cash=Decimal("1000000"),
    )
    orch.run()

    assert len(broker.open_positions) == 0
    assert len(broker.trades) == 1
    # 同じ日内なので EOD ではなく end_of_run になる
    assert broker.trades[0].exit_reason == "end_of_run"


def test_orchestrator_writes_daily_pnl_summary_on_day_change(tmp_path: Path) -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110", day=1),
        make_bar(1, bid_close="154.200", ask_close="154.210", day=1, bid_open="154.150", ask_open="154.160"),
        make_bar(0, bid_close="154.300", ask_close="154.310", day=2),
    ]
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    ev = EventLogger(tmp_path)
    orch = PaperTradingOrchestrator(
        feed=ReplayBarFeed(bars, speedup=0),
        strategy=strat,
        broker=broker,
        logger_=ev,
        leverage=10,
        initial_cash=Decimal("1000000"),
    )
    orch.run()

    daily = (tmp_path / "daily-pnl.md").read_text()
    assert "2026-04-01" in daily
