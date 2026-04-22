"""DslStrategy warmup_bars 境界テスト（T009 復活）。

`warmup_bars` 期間中は signal 評価を行わず空 list を返すこと、warmup 終了後は最初の bar
から評価が始まることを検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.broker.orders import PortfolioSnapshot
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests.dsl.conftest import ConstantPrimitiveEvaluator


def _bar(minute: int) -> PriceBar:
    bt = datetime(2026, 4, 1, tzinfo=UTC) + timedelta(minutes=minute)
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(Decimal("154.00"), Decimal("154.01"), Decimal("153.99"), Decimal("154.00")),
        ask=Ohlc(Decimal("154.01"), Decimal("154.02"), Decimal("154.00"), Decimal("154.01")),
        volume=10,
        complete=True,
    )


def _genome_strong_entry() -> Genome:
    """常に composite=1.0 (>=θ_on=0.5) でエントリーする genome。"""
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


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal(0),
        margin_level_pct=None,
        positions=(),
    )


class TestWarmup:
    def test_warmup_three_bars_no_signal_then_entry(self) -> None:
        ev = ConstantPrimitiveEvaluator(value=1.0)  # 常に θ_on 超
        strat = DslStrategy(_genome_strong_entry(), ev, warmup_bars=3)
        # idx 0,1 は warmup 中（len(_bars) < warmup_bars=3）→ 空
        assert strat.on_bar(_bar(0), _empty_snapshot()) == []
        assert strat.on_bar(_bar(1), _empty_snapshot()) == []
        # idx 2 で len(_bars)==3 == warmup → 評価が走り entry
        out = strat.on_bar(_bar(2), _empty_snapshot())
        assert len(out) == 1
        assert out[0].kind == "open_long"

    def test_warmup_zero_no_delay(self) -> None:
        ev = ConstantPrimitiveEvaluator(value=1.0)
        strat = DslStrategy(_genome_strong_entry(), ev, warmup_bars=0)
        out = strat.on_bar(_bar(0), _empty_snapshot())
        assert len(out) == 1
        assert out[0].kind == "open_long"

    def test_warmup_default_zero(self) -> None:
        ev = ConstantPrimitiveEvaluator(value=1.0)
        strat = DslStrategy(_genome_strong_entry(), ev)  # warmup_bars 省略 → 0
        out = strat.on_bar(_bar(0), _empty_snapshot())
        assert len(out) == 1
        assert out[0].kind == "open_long"
