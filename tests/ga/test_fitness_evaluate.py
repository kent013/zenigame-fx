"""evaluate_genome テスト（T009）。

各 metric (total_pnl / sharpe / calmar) の正常系・metric 不能系・例外系を検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtest.engine import BacktestConfig
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.ga.fitness import _FAILURE_FITNESS, evaluate_genome
from tests._helpers import usd_jpy_meta
from tests.dsl.conftest import ConstantPrimitiveEvaluator


def _bar(minute: int, *, day: int = 1, hour: int = 0) -> PriceBar:
    bt = datetime(2026, 4, day, hour, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(Decimal("154.00"), Decimal("154.01"), Decimal("153.99"), Decimal("154.00")),
        ask=Ohlc(Decimal("154.01"), Decimal("154.02"), Decimal("154.00"), Decimal("154.01")),
        volume=10,
        complete=True,
    )


def _genome() -> Genome:
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


def _cfg() -> BacktestConfig:
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        session_close_utc_hours=frozenset({23}),
    )


def _bars_two_days() -> list[PriceBar]:
    bars = [_bar(i, day=1) for i in range(5)]
    bars.append(_bar(0, day=2))
    return bars


class TestTotalPnl:
    def test_returns_decimal_zero_for_no_trades(self) -> None:
        ev = ConstantPrimitiveEvaluator(value=0.0)  # entry threshold 未到達
        v = evaluate_genome(
            _genome(),
            _bars_two_days(),
            usd_jpy_meta(),
            _cfg(),
            ev,
            metric="total_pnl",
        )
        assert isinstance(v, Decimal)
        assert v == Decimal(0)


class TestSharpe:
    def test_returns_failure_when_insufficient_trades(self) -> None:
        # equity curve flat → std=0 → sharpe None → FAILURE
        ev = ConstantPrimitiveEvaluator(value=0.0)
        v = evaluate_genome(
            _genome(),
            _bars_two_days(),
            usd_jpy_meta(),
            _cfg(),
            ev,
            metric="sharpe",
        )
        assert v == _FAILURE_FITNESS


class TestCalmar:
    def test_returns_failure_when_no_drawdown(self) -> None:
        # DD = 0 → calmar None → FAILURE
        ev = ConstantPrimitiveEvaluator(value=0.0)
        v = evaluate_genome(
            _genome(),
            _bars_two_days(),
            usd_jpy_meta(),
            _cfg(),
            ev,
            metric="calmar",
        )
        assert v == _FAILURE_FITNESS


class TestSystemFailure:
    def test_evaluator_exception_returns_failure(self) -> None:
        class ExplodingEvaluator:
            def evaluate(self, bars, idx, signal):  # type: ignore[no-untyped-def]
                raise RuntimeError("boom")

        ev = ExplodingEvaluator()
        # entry signal を発生させるには ConstantPrimitive が必要だが、
        # evaluator が例外を出すなら DslStrategy.on_bar 内で catch されて
        # evaluate_genome 側の try/except に上がる
        # ConstantPrimitiveEvaluator の代わりに ExplodingEvaluator を使う
        # ただし composite=0 だと entry に至らず例外が呼ばれない可能性があるので
        # 強制的に entry が走る genome を使う
        v = evaluate_genome(
            _genome(),
            _bars_two_days(),
            usd_jpy_meta(),
            _cfg(),
            ev,
            metric="total_pnl",
        )
        # Strategy.on_bar 内で evaluator.evaluate が呼ばれて raise →
        # run_backtest の strategy.on_bar 呼び出しから上がって evaluate_genome の except へ
        assert v == _FAILURE_FITNESS

    def test_invalid_config_returns_failure(self) -> None:
        # 単一 UTC date + 空 session_close → run_backtest が ValueError raise
        ev = ConstantPrimitiveEvaluator(value=0.0)
        bars_single_date = [_bar(0, day=1), _bar(1, day=1)]
        cfg_no_intraday = BacktestConfig(
            instrument="USD_JPY",
            start=datetime(2026, 4, 1, tzinfo=UTC),
            end=datetime(2026, 4, 2, tzinfo=UTC),
            initial_cash=Decimal("1000000"),
            leverage=10,
            session_close_utc_hours=frozenset(),
        )
        v = evaluate_genome(
            _genome(), bars_single_date, usd_jpy_meta(), cfg_no_intraday, ev
        )
        assert v == _FAILURE_FITNESS


class TestUnknownMetric:
    def test_unknown_metric_raises_value_error(self) -> None:
        # unknown metric は try/except の外で raise する仕様
        ev = ConstantPrimitiveEvaluator(value=0.0)
        with pytest.raises(ValueError, match="unknown metric"):
            evaluate_genome(
                _genome(),
                _bars_two_days(),
                usd_jpy_meta(),
                _cfg(),
                ev,
                metric="bogus",  # type: ignore[arg-type]
            )
