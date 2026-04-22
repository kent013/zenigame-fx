"""Clause DslStrategy の統合テスト（T009 復活）。

ヒステリシス（θ_on / θ_off 境界）・time_stop・session close（Strategy 内 fail-safe）の
振る舞いを stub PrimitiveEvaluator で精密に検証する。`test_strategy.py` と内容が
重複する箇所もあるが、本ファイルは「実 backtest 統合手前の単体検証」を担う。
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from src.broker.orders import PortfolioSnapshot, Position
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests.dsl.conftest import ScriptedPrimitiveEvaluator


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


def _genome(
    *, entry_th: float = 0.5, exit_th: float = 0.2, time_stop_min: int = 0
) -> Genome:
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
            entry_threshold=entry_th,
            exit_threshold=exit_th,
            max_pos=1,
            time_stop_min=time_stop_min,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal(0),
        margin_level_pct=None,
        positions=(),
    )


def _snapshot_with_position(side: str, entry_time: datetime) -> PortfolioSnapshot:
    pos = Position(
        id=1,
        instrument="USD_JPY",
        side=side,  # type: ignore[arg-type]
        units=10000,
        entry_price=Decimal("154.00"),
        entry_time=entry_time,
        entry_margin=Decimal("5000"),
        leverage=10,
    )
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("5000"),
        margin_level_pct=Decimal("2000"),
        positions=(pos,),
    )


class TestHysteresis:
    def test_entry_long_at_theta_on(self) -> None:
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.5}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _empty_snapshot())
        assert len(out) == 1
        assert out[0].kind == "open_long"

    def test_entry_short_at_theta_on(self) -> None:
        ev = ScriptedPrimitiveEvaluator({0: {"D1": -0.5}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _empty_snapshot())
        assert len(out) == 1
        assert out[0].kind == "open_short"

    def test_no_entry_below_theta_on(self) -> None:
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.3}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _empty_snapshot())
        assert out == []

    def test_hold_between_theta_off_and_theta_on_long(self) -> None:
        # composite=0.3, long 保有、θ_off=0.2 < 0.3 < θ_on=0.5 → 何もしない
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.3}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _snapshot_with_position("long", _bar(0).bar_time))
        assert out == []

    def test_hold_between_theta_off_and_theta_on_short(self) -> None:
        # composite=-0.3, short 保有、θ_off=0.2 < 0.3 < θ_on=0.5 → 何もしない
        ev = ScriptedPrimitiveEvaluator({0: {"D1": -0.3}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _snapshot_with_position("short", _bar(0).bar_time))
        assert out == []

    def test_exit_long_below_theta_off(self) -> None:
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.1}})  # < exit_th=0.2
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _snapshot_with_position("long", _bar(0).bar_time))
        assert len(out) == 1
        assert out[0].kind == "close_position"

    def test_exit_short_when_neg_composite_below_theta_off(self) -> None:
        # short 保有、composite=-0.1、-composite=0.1 < exit_th=0.2 → close
        ev = ScriptedPrimitiveEvaluator({0: {"D1": -0.1}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        out = strat.on_bar(_bar(0), _snapshot_with_position("short", _bar(0).bar_time))
        assert len(out) == 1
        assert out[0].kind == "close_position"


class TestTimeStop:
    def test_time_stop_forces_close(self) -> None:
        ev = ScriptedPrimitiveEvaluator({})
        genome = _genome(time_stop_min=60)
        strat = DslStrategy(genome, ev)
        entry_time = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        out = strat.on_bar(_bar(60), _snapshot_with_position("long", entry_time))
        assert len(out) == 1
        assert out[0].kind == "close_position"

    def test_time_stop_not_triggered_before(self) -> None:
        # composite=0.3 → hold（θ_off < 0.3 < θ_on）、まだ time_stop も未到達
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.3}})
        genome = _genome(entry_th=0.5, exit_th=0.2, time_stop_min=60)
        strat = DslStrategy(genome, ev)
        entry_time = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        out = strat.on_bar(_bar(59), _snapshot_with_position("long", entry_time))
        assert out == []

    def test_time_stop_disabled_when_zero(self) -> None:
        # time_stop_min=0 なら経過時間で close しない（composite=0.3 で hold）
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.3}})
        genome = _genome(entry_th=0.5, exit_th=0.2, time_stop_min=0)
        strat = DslStrategy(genome, ev)
        entry_time = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
        out = strat.on_bar(_bar(1000), _snapshot_with_position("long", entry_time))
        assert out == []


class TestSessionCloseStrategy:
    def test_session_close_forces_close(self) -> None:
        ev = ScriptedPrimitiveEvaluator({})
        strat = DslStrategy(_genome(), ev, session_close_utc=time(21, 0))
        bar = _bar(0, hour=21)
        out = strat.on_bar(bar, _snapshot_with_position("long", bar.bar_time))
        assert len(out) == 1
        assert out[0].kind == "close_position"

    def test_session_close_none_no_force(self) -> None:
        # session_close_utc=None → engine 側に委譲、Strategy では自発 close しない
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.3}})
        strat = DslStrategy(_genome(entry_th=0.5, exit_th=0.2), ev)
        bar = _bar(0, hour=21)
        out = strat.on_bar(bar, _snapshot_with_position("long", bar.bar_time))
        assert out == []

    def test_session_close_before_time_no_force(self) -> None:
        ev = ScriptedPrimitiveEvaluator({0: {"D1": 0.3}})
        strat = DslStrategy(
            _genome(entry_th=0.5, exit_th=0.2), ev, session_close_utc=time(21, 0)
        )
        # 20:59 → セッションクローズ前
        bar = _bar(59, hour=20)
        out = strat.on_bar(bar, _snapshot_with_position("long", bar.bar_time))
        assert out == []
