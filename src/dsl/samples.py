from __future__ import annotations

from decimal import Decimal

from src.dsl.ast import BinOp, Compare, Const, Indicator, Var
from src.dsl.genome import Genome


def bollinger_genome(window: int = 20, k: float = 2.0, units: int = 10000) -> Genome:
    k_const = Const(Decimal(str(k)))
    close = Var("close")
    sma = Indicator("sma", window, close)
    std = Indicator("stddev", window, close)
    upper = BinOp("+", sma, BinOp("*", k_const, std))
    lower = BinOp("-", sma, BinOp("*", k_const, std))
    return Genome(
        name=f"bollinger_w{window}_k{k}",
        units=units,
        entry_long=Compare("<", close, lower),
        entry_short=Compare(">", close, upper),
        exit_long=Compare(">=", close, sma),
        exit_short=Compare("<=", close, sma),
    )


def ma_crossover_genome(fast: int = 5, slow: int = 20, units: int = 10000) -> Genome:
    close = Var("close")
    fast_sma = Indicator("sma", fast, close)
    slow_sma = Indicator("sma", slow, close)
    return Genome(
        name=f"ma_crossover_f{fast}_s{slow}",
        units=units,
        entry_long=Compare(">", fast_sma, slow_sma),
        entry_short=Compare("<", fast_sma, slow_sma),
        exit_long=Compare("<=", fast_sma, slow_sma),
        exit_short=Compare(">=", fast_sma, slow_sma),
    )
