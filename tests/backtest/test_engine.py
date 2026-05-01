from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from structlog.testing import capture_logs

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.session_block import SessionBlock
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


# -- T055: per-bar log 削除 + 集計サマリ化 ---------------------------------


def _backtest_config_with_session_close_at_hour_zero() -> BacktestConfig:
    """hour=0 を session close 時刻として扱う BacktestConfig。

    `make_bar(minute, day=1)` は `bar_time.hour == 0` （minute < 60）または >= 1 を生成する。
    """
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 5, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        session_close_utc_hours=frozenset({0}),
    )


def test_run_backtest_session_close_drop_open_count_in_summary() -> None:
    """session close bar 帯で strategy が出した open シグナルが drop され、
    backtest.finished の集計フィールドに反映される。"""
    bars = [
        # bar 0: minute=0 → hour=0 (session close) — open_long を出すと drop
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        # bar 1: minute=1 → hour=0 (session close) — open_short を出すと drop
        make_bar(1, bid_close="154.110", ask_close="154.120"),
        # bar 2: minute=120 → hour=2 (non-session) — drop されない
        make_bar(120, bid_close="154.120", ask_close="154.130"),
    ]
    strat = _ScriptedStrategy({
        0: [OrderSignal(kind="open_long", units=10000)],
        1: [OrderSignal(kind="open_short", units=10000)],
    })
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = _backtest_config_with_session_close_at_hour_zero()

    with capture_logs() as logs:
        run_backtest(bars, strat, broker, config)

    finished_logs = [log for log in logs if log.get("event") == "backtest.finished"]
    assert len(finished_logs) == 1
    finished = finished_logs[0]
    assert finished["session_close_drop_open_count"] == 2
    # 最初の drop は bar 0 で発生
    assert finished["first_drop_open_bar_time"] == bars[0].bar_time.isoformat()


def test_run_backtest_first_drop_open_bar_time_records_first_event() -> None:
    """drop_open が発生しないとき first_drop_open_bar_time は None。"""
    bars = [
        make_bar(120, bid_close="154.100", ask_close="154.110"),  # hour=2
        make_bar(121, bid_close="154.110", ask_close="154.120"),  # hour=2
    ]
    strat = _ScriptedStrategy({})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = _backtest_config_with_session_close_at_hour_zero()

    with capture_logs() as logs:
        run_backtest(bars, strat, broker, config)

    finished = next(log for log in logs if log.get("event") == "backtest.finished")
    assert finished["session_close_drop_open_count"] == 0
    assert finished["first_drop_open_bar_time"] is None


def test_run_backtest_session_close_drop_pending_count_in_summary() -> None:
    """non-session bar で submit された pending が、続く session close bar で drop され
    backtest.finished の session_close_drop_pending_count に集計される。"""
    bars = [
        # bar 0: minute=120 → hour=2 (non-session) — open_long を出して pending に入る
        make_bar(120, bid_close="154.100", ask_close="154.110"),
        # bar 1: minute=0 day=2 → hour=0 (session close) — pending が drop される
        make_bar(0, bid_close="154.110", ask_close="154.120", day=2),
        # bar 2: minute=120 day=2 → hour=2 — 走査継続
        make_bar(120, bid_close="154.120", ask_close="154.130", day=2),
    ]
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = _backtest_config_with_session_close_at_hour_zero()

    with capture_logs() as logs:
        run_backtest(bars, strat, broker, config)

    finished = next(log for log in logs if log.get("event") == "backtest.finished")
    assert finished["session_close_drop_pending_count"] == 1


def test_run_backtest_no_per_bar_drop_log_emitted() -> None:
    """T055: per-bar drop 系の logger.info 呼び出しが完全削除されていること。"""
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),  # session close, drop_open
        make_bar(120, bid_close="154.110", ask_close="154.120"),  # non-session, submit ok
        make_bar(0, bid_close="154.120", ask_close="154.130", day=2),  # session close, drop_pending
        make_bar(120, bid_close="154.130", ask_close="154.140", day=2),
    ]
    strat = _ScriptedStrategy({
        0: [OrderSignal(kind="open_long", units=10000)],
        1: [OrderSignal(kind="open_short", units=10000)],
    })
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = _backtest_config_with_session_close_at_hour_zero()

    with capture_logs() as logs:
        run_backtest(bars, strat, broker, config)

    forbidden_events = {
        "backtest.session_close.drop_open_from_strategy",
        "backtest.session_close.drop_pending",
        "broker.drop_pending_open",
    }
    emitted_events = {log.get("event") for log in logs}
    assert forbidden_events.isdisjoint(emitted_events), (
        f"per-bar drop log が削除されていない: emitted={emitted_events & forbidden_events}"
    )


def test_run_backtest_finished_summary_smoke_consumer_compat() -> None:
    """V7(c): consumer 互換 smoke — backtest.finished に既存 fields が維持され、
    新規 fields が ignore されても KeyError 等を引き起こさないことを simulate する。"""
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(120, bid_close="154.110", ask_close="154.120"),
    ]
    strat = _ScriptedStrategy({})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = _backtest_config_with_session_close_at_hour_zero()

    with capture_logs() as logs:
        run_backtest(bars, strat, broker, config)

    finished = next(log for log in logs if log.get("event") == "backtest.finished")
    # 既存 fields が維持されていること（consumer 後方互換性）
    for required_key in ("instrument", "bars", "trades", "final_equity"):
        assert required_key in finished, f"既存 field が消えている: {required_key}"
    # 追加 fields は consumer が ignore しても問題ない（dict なので不要 key は無視可能）
    consumer_view = {
        "instrument": finished["instrument"],
        "bars": finished["bars"],
        "trades": finished["trades"],
        "final_equity": finished["final_equity"],
    }
    assert consumer_view["instrument"] == "USD_JPY"
    assert consumer_view["bars"] == 2


# -- T056: negative equity drop count を summary に集計 ---------------------------------


def test_run_backtest_negative_equity_drop_count_in_summary() -> None:
    """T056: 破産シナリオで backtest.finished log の negative_equity_drop_open_count が
    正確な件数を持つこと。

    bar 0 で open_long を発注 → bar 1 で約定後、強制的に cash を負にして
    bar 2 で更に open_long を試みると L1 で drop される。
    """
    bars = [
        # bar 0: minute=120 → hour=2 (non-session) — open_long submit
        make_bar(120, bid_close="154.100", ask_close="154.110"),
        # bar 1: minute=121 → hour=2 — fill
        make_bar(121, bid_close="154.150", ask_close="154.160"),
        # bar 2: minute=122 → hour=2 — 別 open_long を試みる（cash を負にしてあるので drop されたい）
        make_bar(122, bid_close="154.200", ask_close="154.210"),
        # bar 3: minute=123 → hour=2
        make_bar(123, bid_close="154.250", ask_close="154.260"),
    ]
    strat = _ScriptedStrategy({
        0: [OrderSignal(kind="open_long", units=10000)],
        1: [OrderSignal(kind="open_long", units=10000)],
    })
    config = _backtest_config_with_session_close_at_hour_zero()

    # bar 1 fill 直後 (= bar 2 fill_pending 前) に cash を負に強制したいが、
    # _ScriptedStrategy には介入 hook がないため、別アプローチ:
    # 大量 units で margin call 発火を狙うか、broker._cash を直接操作する。
    # ここでは subclass で fill_pending を hook して cash を捻じ曲げる。
    class _CrashBroker(MockBroker):
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            super().__init__(*args, **kwargs)
            self._bar_count = 0

        def fill_pending(self, bar):  # type: ignore[no-untyped-def]
            # bar 2 の fill_pending に入る前に cash を負にする
            if self._bar_count == 2:
                self._cash = Decimal("-10000000")
                self._invalidate_snapshot_cache()
            self._bar_count += 1
            return super().fill_pending(bar)

    crash_broker = _CrashBroker(instrument_meta=usd_jpy_meta())

    with capture_logs() as logs:
        run_backtest(bars, strat, crash_broker, config)

    finished = next(log for log in logs if log.get("event") == "backtest.finished")
    assert "negative_equity_drop_open_count" in finished
    # bar 2 で 1 件 drop された
    assert finished["negative_equity_drop_open_count"] == 1


# -- T070: BacktestResult.session_blocks 同梱 (F4 / F16) -------------------


def test_F4_run_backtest_returns_session_blocks() -> None:
    """F4: BacktestResult.session_blocks が同梱され、 1 day で 3 bucket 分生成."""
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(120, bid_close="154.110", ask_close="154.120"),
    ]
    strat = _ScriptedStrategy({})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        session_close_utc_hours=frozenset({23}),
    )
    result = run_backtest(bars, strat, broker, config)

    assert isinstance(result.session_blocks, tuple)
    # 1 day × 3 bucket
    assert len(result.session_blocks) == 3
    assert all(isinstance(b, SessionBlock) for b in result.session_blocks)
    # bars が tokyo (hour=0/2) のみなら他 bucket は bar_count=0
    tokyo = next(b for b in result.session_blocks if b.bucket == "tokyo")
    london = next(b for b in result.session_blocks if b.bucket == "london")
    assert tokyo.bar_count == 2
    assert london.bar_count == 0


def test_F16_session_blocks_use_exit_time_for_attribution() -> None:
    """F16: trade.exit_time の bucket に集計される (= exit bucket 一括帰属)."""
    # bar 0: hour=0 (tokyo) で open_long → bar 1: hour=0 同 day で fill (= entry tokyo)
    # → bar 2: 翌日 hour=0 で eod close (= exit tokyo)
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),  # day1 hour=0 tokyo
        make_bar(1, bid_close="154.150", ask_close="154.160"),  # day1 hour=0 tokyo
        make_bar(0, bid_close="154.200", ask_close="154.210", day=2),  # day2 hour=0 tokyo
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

    # 1 trade、 exit_time = bar 1 の bid.close (= EOD close、 hour=0 / day=1)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_time.date() == bars[1].bar_time.date()

    # session_blocks に trade が tokyo bucket でカウントされている
    target_block = next(
        b for b in result.session_blocks
        if b.bucket == "tokyo" and b.business_date == trade.exit_time.date()
    )
    assert target_block.trade_count == 1


def test_F4_session_blocks_invariant_holds_after_run() -> None:
    """F4 補強: session_blocks の各 invariant (pnl_before == net + spread + holding)."""
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(60, bid_close="154.150", ask_close="154.160"),  # hour=1 tokyo
        make_bar(120, bid_close="154.200", ask_close="154.210"),  # hour=2 tokyo
    ]
    strat = _ScriptedStrategy({0: [OrderSignal(kind="open_long", units=10000)]})
    broker = MockBroker(instrument_meta=usd_jpy_meta())
    config = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        session_close_utc_hours=frozenset({23}),
        holding_cost_per_day_bps=Decimal("36"),
        bar_minutes=60,
    )
    result = run_backtest(bars, strat, broker, config)

    for b in result.session_blocks:
        assert b.pnl_before_costs == (
            b.pnl_net + b.spread_cost_total + b.holding_cost_total
        )
        assert b.spread_cost_total >= Decimal(0)
        assert b.holding_cost_total >= Decimal(0)


def test_F4_default_session_blocks_is_empty_tuple() -> None:
    """BacktestResult.session_blocks default は空 tuple (= backward-compat).

    既存 caller が session_blocks を渡さない場合の default_factory 検証.
    """
    from src.backtest.engine import BacktestConfig, BacktestResult

    config = BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        session_close_utc_hours=frozenset({23}),
    )
    result = BacktestResult(config=config, trades=[], equity_curve=[])
    assert result.session_blocks == ()
