"""DslStrategy warmup 境界の回帰テスト（Phase 4f Bug #1: off-by-one fix）。

修正前は `len(self._bars) <= self._warmup` で return しており、warmup=N のとき
実際に最初の信号を出すのは N+1 本目だった。これを N 本目から信号を出せるよう修正。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.broker.orders import PortfolioSnapshot
from src.dsl.ast import Compare, Const, Indicator, Var
from src.dsl.eval import max_lookback
from src.dsl.genome import DslStrategy, Genome


def _snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"), equity=Decimal("1000000"), margin_used=Decimal(0), margin_level_pct=None
    )


def _bar(i: int, price: str = "154.000"):
    from src.domain.price import Ohlc, PriceBar

    return PriceBar(
        pair_name="USD_JPY",
        bar_time=datetime(2026, 4, 1, tzinfo=UTC) + timedelta(minutes=i),
        bid=Ohlc(open=Decimal(price), high=Decimal(price), low=Decimal(price), close=Decimal(price)),
        ask=Ohlc(open=Decimal(price), high=Decimal(price), low=Decimal(price), close=Decimal(price)),
        volume=10,
        complete=True,
    )


def _always_true_genome(window: int) -> Genome:
    """sma(close, window) >= 0 で必ず真になる entry_long を持つ Genome。

    warmup 境界で「信号が出るか」をシンプルに観測する目的。
    """
    true_cond = Compare(">=", Indicator("sma", window, Var("close")), Const(Decimal("0")))
    false_cond = Compare("<", Const(Decimal("0")), Const(Decimal("0")))
    return Genome(
        name="warmup_test",
        units=1000,
        entry_long=true_cond,
        entry_short=false_cond,
        exit_long=false_cond,
        exit_short=false_cond,
    )


def test_dsl_strategy_emits_signal_exactly_at_warmup_bar() -> None:
    window = 5
    genome = _always_true_genome(window)
    expected_warmup = max_lookback(genome.entry_long)
    assert expected_warmup == window

    strat = DslStrategy(genome)
    # warmup より前のバーでは信号無し
    for i in range(window - 1):
        assert strat.on_bar(_bar(i), _snapshot()) == []
    # window 本目 (index=window-1) でちょうど warmup 相当のバー数が揃い、信号を出すべき
    signals = strat.on_bar(_bar(window - 1), _snapshot())
    assert len(signals) == 1, f"expected 1 signal at bar {window}, got {signals}"
    assert signals[0].kind == "open_long"


def test_dsl_strategy_warmup_bars_matches_actual_emission_start() -> None:
    """warmup_bars() が返す値と、実際に信号が出始めるバー番号が一致することを確認。"""
    window = 7
    strat = DslStrategy(_always_true_genome(window))
    warmup = strat.warmup_bars()

    emission_bar = None
    for i in range(warmup + 5):
        signals = strat.on_bar(_bar(i), _snapshot())
        if signals and emission_bar is None:
            emission_bar = i + 1  # 1-indexed
            break

    assert emission_bar == warmup, (
        f"warmup_bars()={warmup} だが信号開始は {emission_bar} 本目。off-by-one の疑い"
    )
