"""Clause DslStrategy + run_backtest 統合テスト（T009）。

spread フィルタ / session close（hour 強制クローズ + pending open drop）/ holding cost /
イントラデイ絶対制約（単一日 + session close 空 → ValueError）を検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import compute_metrics
from src.broker.mock import MockBroker
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests._helpers import usd_jpy_meta
from tests.dsl.conftest import ConstantPrimitiveEvaluator, ScriptedPrimitiveEvaluator


def _bar(
    minute: int,
    *,
    hour: int = 0,
    day: int = 1,
    bid_close: str = "154.00",
    ask_close: str = "154.01",
    bid_open: str | None = None,
    ask_open: str | None = None,
) -> PriceBar:
    bt = datetime(2026, 4, day, hour, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    bid_o = Decimal(bid_open or bid_close)
    ask_o = Decimal(ask_open or ask_close)
    bid_c = Decimal(bid_close)
    ask_c = Decimal(ask_close)
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(bid_o, max(bid_o, bid_c), min(bid_o, bid_c), bid_c),
        ask=Ohlc(ask_o, max(ask_o, ask_c), min(ask_o, ask_c), ask_c),
        volume=10,
        complete=True,
    )


def _one_clause_genome() -> Genome:
    return Genome(
        name="g",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="D1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _cfg(
    *,
    max_spread_bps: Decimal | None = None,
    holding_cost_per_day_bps: Decimal = Decimal("0"),
    session_close_utc_hours: frozenset[int] = frozenset(),
    bar_minutes: int = 1,
) -> BacktestConfig:
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        max_spread_bps=max_spread_bps,
        holding_cost_per_day_bps=holding_cost_per_day_bps,
        session_close_utc_hours=session_close_utc_hours,
        bar_minutes=bar_minutes,
    )


# --- BacktestConfig validation ---


class TestBacktestConfigValidation:
    def test_negative_holding_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="holding_cost_per_day_bps"):
            BacktestConfig(
                instrument="X",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 4, 2, tzinfo=UTC),
                initial_cash=Decimal("1000000"),
                leverage=10,
                holding_cost_per_day_bps=Decimal("-1"),
            )

    def test_negative_max_spread_raises(self) -> None:
        with pytest.raises(ValueError, match="max_spread_bps"):
            BacktestConfig(
                instrument="X",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 4, 2, tzinfo=UTC),
                initial_cash=Decimal("1000000"),
                leverage=10,
                max_spread_bps=Decimal("-0.1"),
            )

    def test_invalid_bar_minutes_raises(self) -> None:
        with pytest.raises(ValueError, match="bar_minutes"):
            BacktestConfig(
                instrument="X",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 4, 2, tzinfo=UTC),
                initial_cash=Decimal("1000000"),
                leverage=10,
                bar_minutes=0,
            )

    def test_invalid_session_close_hour_raises(self) -> None:
        with pytest.raises(ValueError, match="session_close_utc_hours"):
            BacktestConfig(
                instrument="X",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 4, 2, tzinfo=UTC),
                initial_cash=Decimal("1000000"),
                leverage=10,
                session_close_utc_hours=frozenset({24}),
            )


# --- イントラデイ絶対制約 ---


class TestIntradayAbsoluteConstraint:
    def test_single_date_empty_session_close_raises(self) -> None:
        bars = [_bar(0, day=1), _bar(1, day=1)]
        ev = ConstantPrimitiveEvaluator(value=0.0)
        strat = DslStrategy(_one_clause_genome(), ev)
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        cfg = _cfg()  # empty session_close_utc_hours, single-date bars
        with pytest.raises(ValueError, match="Intraday absolute constraint"):
            run_backtest(bars, strat, broker, cfg)

    def test_multi_date_bars_without_session_close_ok(self) -> None:
        bars = [_bar(0, day=1), _bar(0, day=2)]
        ev = ConstantPrimitiveEvaluator(value=0.0)
        strat = DslStrategy(_one_clause_genome(), ev)
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        cfg = _cfg()  # multi-date でクリア
        # raise しないこと
        run_backtest(bars, strat, broker, cfg)

    def test_session_close_with_single_date_ok(self) -> None:
        bars = [_bar(0, hour=0, day=1), _bar(0, hour=21, day=1)]
        ev = ConstantPrimitiveEvaluator(value=0.0)
        strat = DslStrategy(_one_clause_genome(), ev)
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        cfg = _cfg(session_close_utc_hours=frozenset({21}))
        run_backtest(bars, strat, broker, cfg)


# --- Clause Genome 統合 ---


class TestClauseDslStrategyIntegration:
    def test_basic_entry_and_exit(self) -> None:
        # bar0: entry signal (composite=1.0)
        # bar1: 約定 + composite=0.1 → exit 発注
        # bar2: exit 約定 (day boundary 前)
        ev = ScriptedPrimitiveEvaluator(
            {
                0: {"D1": 1.0},
                1: {"D1": 0.1},
                2: {"D1": 0.0},
            }
        )
        strat = DslStrategy(_one_clause_genome(), ev)
        bars = [
            _bar(0, day=1),
            _bar(1, day=1, bid_open="154.05", ask_open="154.06"),
            _bar(2, day=1, bid_open="154.04", ask_open="154.05"),
            _bar(0, day=2),
        ]
        cfg = _cfg(session_close_utc_hours=frozenset({23}))
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        assert len(result.trades) >= 1
        # 全 trade は instrument が一致
        for t in result.trades:
            assert t.instrument == "USD_JPY"


# --- Spread フィルタ ---


class TestSpreadFilter:
    def test_open_rejected_when_previous_bar_spread_exceeds(self) -> None:
        # bar0: 通常 spread, evaluator は何もしない
        # bar1: wide spread (bid 153.99 / ask 154.11 = 約 7.79 bps), evaluator は entry signal
        # bar2: bar1 close spread が前バーとして判定 → reject
        # 仕掛けた entry signal は bar1 終了で submit される（bar1 で signal 評価）
        # bar2 の fill_pending で _last_close_spread_bps（bar1 の spread）を見て reject
        ev = ScriptedPrimitiveEvaluator(
            {
                0: {"D1": 0.0},
                1: {"D1": 1.0},  # 発注（pending）
                2: {"D1": 0.0},
                3: {"D1": 0.0},
            }
        )
        strat = DslStrategy(_one_clause_genome(), ev)
        bars = [
            _bar(0, day=1),
            _bar(1, day=1, bid_close="153.99", ask_close="154.11"),  # wide
            _bar(2, day=1, bid_open="154.00", ask_open="154.02"),
            _bar(0, day=2),
        ]
        cfg = _cfg(
            max_spread_bps=Decimal("5"), session_close_utc_hours=frozenset({23})
        )
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        # spread filter で reject → trade 0、open_positions 0
        assert len(result.trades) == 0
        assert len(broker.open_positions) == 0

    def test_open_accepted_when_previous_bar_spread_within(self) -> None:
        # 同様の発注パターンで bar1 の spread が narrow なら通常通り約定
        ev = ScriptedPrimitiveEvaluator(
            {
                0: {"D1": 0.0},
                1: {"D1": 1.0},
                2: {"D1": 0.0},
                3: {"D1": 0.0},
            }
        )
        strat = DslStrategy(_one_clause_genome(), ev)
        bars = [
            _bar(0, day=1),
            _bar(1, day=1),  # narrow spread (154.00 / 154.01 = ~0.65 bps)
            _bar(2, day=1, bid_open="154.00", ask_open="154.02"),
            _bar(0, day=2),
        ]
        cfg = _cfg(
            max_spread_bps=Decimal("5"), session_close_utc_hours=frozenset({23})
        )
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        # 何らかの形で約定が発生した（trade or open_position）
        assert len(result.trades) + len(broker.open_positions) >= 1


# --- Session close (engine 強制) ---


class TestSessionCloseEngine:
    def test_session_close_hour_forces_close(self) -> None:
        # bar0 (20:00): entry signal → bar1 (20:01) で約定
        # bar2 (21:00): session close → 強制クローズ
        ev = ScriptedPrimitiveEvaluator(
            {
                0: {"D1": 1.0},
                1: {"D1": 0.3},  # hold (θ_off < 0.3 < θ_on)
                2: {"D1": 0.3},  # hold だが engine が強制クローズ
            }
        )
        strat = DslStrategy(_one_clause_genome(), ev)
        bars = [
            _bar(0, hour=20, day=1),
            _bar(1, hour=20, day=1, bid_open="154.05", ask_open="154.06"),
            _bar(0, hour=21, day=1),  # session close hour
            _bar(0, day=2),
        ]
        cfg = _cfg(session_close_utc_hours=frozenset({21}))
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        # session close で eod reason の trade が存在
        eod_trades = [t for t in result.trades if t.exit_reason == "eod"]
        assert len(eod_trades) >= 1

    def test_session_close_drops_pending_open(self) -> None:
        # bar3 (20:03) で entry signal → bar4 (21:00 session close) で pending drop
        # 強条件: 結果として trades 0 件 + 保有 0 件
        ev = ScriptedPrimitiveEvaluator(
            {
                0: {"D1": 0.0},
                1: {"D1": 0.0},
                2: {"D1": 0.0},
                3: {"D1": 1.0},  # entry signal pending
                4: {"D1": 0.0},
            }
        )
        strat = DslStrategy(_one_clause_genome(), ev)
        bars = [
            _bar(0, hour=20, day=1),
            _bar(1, hour=20, day=1),
            _bar(2, hour=20, day=1),
            _bar(3, hour=20, day=1),  # ここで pending open
            _bar(0, hour=21, day=1),  # session close → pending drop
            _bar(0, day=2),
        ]
        cfg = _cfg(session_close_utc_hours=frozenset({21}))
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        assert len(result.trades) == 0
        assert len(broker.open_positions) == 0


# --- Holding cost ---


class TestHoldingCost:
    def test_holding_cost_reflected_in_trade_pnl(self) -> None:
        # bar0: entry signal → bar1 開で約定
        # bar1〜bar4: 保有
        # bar4: exit signal → bar5 開で約定
        # holding cost が Trade.pnl に反映されることを no-cost と比較して検証
        bars = [
            _bar(0, day=1),
            _bar(1, day=1, bid_open="154.05", ask_open="154.06"),
            _bar(2, day=1),
            _bar(3, day=1),
            _bar(4, day=1),
            _bar(5, day=1, bid_open="154.04", ask_open="154.05"),
            _bar(0, day=2),
        ]
        # without holding cost
        strat_no = DslStrategy(
            _one_clause_genome(),
            ScriptedPrimitiveEvaluator(
                {
                    0: {"D1": 1.0},
                    1: {"D1": 0.3},
                    2: {"D1": 0.3},
                    3: {"D1": 0.3},
                    4: {"D1": 0.1},
                }
            ),
        )
        cfg_no_cost = _cfg(session_close_utc_hours=frozenset({23}))
        broker_no_cost = MockBroker(instrument_meta=usd_jpy_meta())
        r_no = run_backtest(bars, strat_no, broker_no_cost, cfg_no_cost)

        # with holding cost
        strat_cost = DslStrategy(
            _one_clause_genome(),
            ScriptedPrimitiveEvaluator(
                {
                    0: {"D1": 1.0},
                    1: {"D1": 0.3},
                    2: {"D1": 0.3},
                    3: {"D1": 0.3},
                    4: {"D1": 0.1},
                }
            ),
        )
        cfg_cost = _cfg(
            holding_cost_per_day_bps=Decimal("1440"),
            session_close_utc_hours=frozenset({23}),
        )
        broker_cost = MockBroker(instrument_meta=usd_jpy_meta())
        r_cost = run_backtest(bars, strat_cost, broker_cost, cfg_cost)

        assert len(r_no.trades) == 1
        assert len(r_cost.trades) == 1
        # holding cost あり → pnl はより小さくなる
        assert r_cost.trades[0].pnl < r_no.trades[0].pnl
        # total_pnl も同様
        m_no = compute_metrics(r_no.trades, r_no.equity_curve)
        m_cost = compute_metrics(r_cost.trades, r_cost.equity_curve)
        assert m_cost.total_pnl < m_no.total_pnl

    def test_holding_cost_recovered_on_eod_close(self) -> None:
        # eod 強制クローズ経路でも holding cost が Trade.pnl に反映されることを検証
        bars = [
            _bar(0, day=1),
            _bar(1, day=1, bid_open="154.05", ask_open="154.06"),
            _bar(2, day=1),
            _bar(0, day=2),  # day boundary → 前日最終 bar (bar2) で eod クローズ
        ]
        strat = DslStrategy(
            _one_clause_genome(),
            ScriptedPrimitiveEvaluator(
                {
                    0: {"D1": 1.0},  # entry
                    1: {"D1": 0.3},
                    2: {"D1": 0.3},
                }
            ),
        )
        cfg = _cfg(holding_cost_per_day_bps=Decimal("1440"))
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        # 1 trade、reason="eod"、holding cost が反映済（raw_pnl > net_pnl）
        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == "eod"
        # raw_pnl は entry 154.06 → exit 154.00 (bid_close), units=10000 → -600
        # cost が適用されるため、pnl は -600 よりさらに小さい
        # （bar1, bar2 mark-to-market 時に cost 控除）
        # 厳密値ではなく「holding cost が反映されている」傾向のみ検証
        raw_pnl_estimate = Decimal("10000") * (Decimal("154.00") - Decimal("154.06"))
        assert result.trades[0].pnl < raw_pnl_estimate


class TestPnlCashConsistency:
    def test_sum_trade_pnl_equals_final_minus_initial_cash(self) -> None:
        # 不変条件: sum(Trade.pnl) == broker.cash - initial_cash
        # holding cost 経路で二重控除がないことの確認
        bars = [
            _bar(0, day=1),
            _bar(1, day=1, bid_open="154.05", ask_open="154.06"),
            _bar(2, day=1),
            _bar(3, day=1),
            _bar(4, day=1),
            _bar(5, day=1, bid_open="154.04", ask_open="154.05"),
            _bar(0, day=2),
        ]
        strat = DslStrategy(
            _one_clause_genome(),
            ScriptedPrimitiveEvaluator(
                {
                    0: {"D1": 1.0},
                    1: {"D1": 0.3},
                    2: {"D1": 0.3},
                    3: {"D1": 0.3},
                    4: {"D1": 0.1},
                }
            ),
        )
        initial_cash = Decimal("1000000")
        cfg = _cfg(
            holding_cost_per_day_bps=Decimal("1440"),
            session_close_utc_hours=frozenset({23}),
        )
        broker = MockBroker(instrument_meta=usd_jpy_meta())
        result = run_backtest(bars, strat, broker, cfg)
        sum_pnl = sum((t.pnl for t in result.trades), Decimal(0))
        # cash - initial == sum(Trade.pnl)
        # （raw_pnl による cash 増分 - holding cost による cash 控除 == net_pnl 合計）
        assert broker.cash - initial_cash == sum_pnl
