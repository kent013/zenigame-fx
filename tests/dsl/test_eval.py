from __future__ import annotations

from decimal import Decimal

from src.dsl.ast import BinOp, Compare, Const, Indicator, Logical, Var
from src.dsl.eval import EvalContext, evaluate, max_lookback
from tests._helpers import make_bar


def _ctx(bars) -> EvalContext:
    return EvalContext(bars=list(bars), i=len(bars) - 1)


def test_var_close_is_mid_of_bid_ask() -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    assert evaluate(Var("close"), _ctx([bar])) == Decimal("154.105")


def test_binop_addition() -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    expr = BinOp("+", Var("close"), Const(Decimal("1")))
    assert evaluate(expr, _ctx([bar])) == Decimal("155.105")


def test_sma_window3() -> None:
    bars = [
        make_bar(0, bid_close="100.000", ask_close="100.000"),
        make_bar(1, bid_close="102.000", ask_close="102.000"),
        make_bar(2, bid_close="104.000", ask_close="104.000"),
    ]
    sma = Indicator("sma", 3, Var("close"))
    assert evaluate(sma, _ctx(bars)) == Decimal("102")


def test_compare_less_than() -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    expr = Compare("<", Var("close"), Const(Decimal("155")))
    assert evaluate(expr, _ctx([bar])) is True


def test_logical_and() -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    cond1 = Compare("<", Var("close"), Const(Decimal("155")))
    cond2 = Compare(">", Var("close"), Const(Decimal("153")))
    assert evaluate(Logical("and", (cond1, cond2)), _ctx([bar])) is True


def test_division_by_zero_returns_zero() -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    expr = BinOp("/", Var("close"), Const(Decimal("0")))
    assert evaluate(expr, _ctx([bar])) == Decimal(0)


def test_max_lookback_for_nested_indicator() -> None:
    expr = Indicator("sma", 20, Var("close"))
    assert max_lookback(expr) == 20
    rsi = Indicator("rsi", 14, Var("close"))
    # rsi needs window+1
    assert max_lookback(rsi) == 15
