"""max_lookback のネスト指標合成テスト（audit P2 follow-up）。

修正前は `max(own_window, max_lookback(of))` と単純最大を取っていたため、
`sma(sma(close, 5), 3)` は 5 本で warmup 完了となっていた。しかし実際には
内側 sma の値を 3 つ得るには 3 + 5 - 1 = 7 本必要。修正後は正しく 7 を返す。
"""

from __future__ import annotations

from decimal import Decimal

from src.dsl.ast import BinOp, Const, Indicator, Var
from src.dsl.eval import max_lookback


def test_single_indicator_returns_window() -> None:
    assert max_lookback(Indicator("sma", 20, Var("close"))) == 20


def test_rsi_requires_window_plus_one() -> None:
    assert max_lookback(Indicator("rsi", 14, Var("close"))) == 15


def test_nested_sma_composes_to_sum_minus_one() -> None:
    inner = Indicator("sma", 5, Var("close"))
    outer = Indicator("sma", 3, inner)
    # 3 個の inner 値を得るには 3 + 5 - 1 = 7 バー必要
    assert max_lookback(outer) == 7


def test_triple_nested_indicator_composes_correctly() -> None:
    innermost = Indicator("sma", 5, Var("close"))
    middle = Indicator("sma", 4, innermost)
    outermost = Indicator("sma", 3, middle)
    # middle=4+(5-1)=8、outermost=3+(8-1)=10
    assert max_lookback(outermost) == 10


def test_rsi_of_sma_composes() -> None:
    inner = Indicator("sma", 5, Var("close"))
    rsi = Indicator("rsi", 14, inner)
    # rsi own=15、inner=5 → 15 + (5-1) = 19
    assert max_lookback(rsi) == 19


def test_indicator_of_binop_without_inner_indicator() -> None:
    expr = Indicator("sma", 10, BinOp("+", Var("close"), Const(Decimal("1"))))
    # 内側 BinOp の lookback は 0、ただの値変換なので 10 で十分
    assert max_lookback(expr) == 10


def test_indicator_of_binop_with_inner_indicator() -> None:
    inner = Indicator("sma", 5, Var("close"))
    expr = Indicator("sma", 10, BinOp("+", Var("close"), inner))
    # inner BinOp の lookback = 5、outer own = 10、合成 10 + (5-1) = 14
    assert max_lookback(expr) == 14
