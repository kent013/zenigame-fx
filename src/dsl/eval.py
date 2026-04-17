from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.domain.price import PriceBar
from src.dsl.ast import BinOp, Compare, Const, Expr, IfThenElse, Indicator, Logical, Var

_VAR_NAMES = {"close", "open", "high", "low", "volume", "bid_close", "ask_close", "spread"}
_INDICATOR_NAMES = {"sma", "ema", "stddev", "rsi"}


@dataclass
class EvalContext:
    bars: list[PriceBar]
    i: int
    _cache: dict[Any, Any] = field(default_factory=dict)


def _var_value(name: str, bar: PriceBar) -> Decimal:
    if name == "close":
        return (bar.bid.close + bar.ask.close) / Decimal(2)
    if name == "open":
        return (bar.bid.open + bar.ask.open) / Decimal(2)
    if name == "high":
        return (bar.bid.high + bar.ask.high) / Decimal(2)
    if name == "low":
        return (bar.bid.low + bar.ask.low) / Decimal(2)
    if name == "volume":
        return Decimal(bar.volume)
    if name == "bid_close":
        return bar.bid.close
    if name == "ask_close":
        return bar.ask.close
    if name == "spread":
        return bar.ask.close - bar.bid.close
    raise ValueError(f"unknown var name: {name}")


def _collect_values(expr: Expr, ctx: EvalContext, lookback: int) -> list[Decimal]:
    values: list[Decimal] = []
    for offset in range(lookback, 0, -1):
        idx = ctx.i - offset + 1
        if idx < 0:
            continue
        sub = EvalContext(bars=ctx.bars, i=idx, _cache={})
        values.append(_as_decimal(evaluate(expr, sub)))
    return values


def _sma(values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("sma requires at least one value")
    return sum(values, Decimal(0)) / Decimal(len(values))


def _ema(values: list[Decimal], window: int) -> Decimal:
    if not values:
        raise ValueError("ema requires at least one value")
    alpha = Decimal(2) / Decimal(window + 1)
    ema = values[0]
    for v in values[1:]:
        ema = ema + alpha * (v - ema)
    return ema


def _stddev(values: list[Decimal]) -> Decimal:
    if len(values) < 2:
        return Decimal(0)
    mean = _sma(values)
    var = sum(((v - mean) ** 2 for v in values), Decimal(0)) / Decimal(len(values))
    return Decimal(str(math.sqrt(float(var))))


def _rsi(values: list[Decimal], window: int) -> Decimal:
    if len(values) < 2:
        return Decimal(50)
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for prev, cur in itertools.pairwise(values):
        d = cur - prev
        gains.append(d if d > 0 else Decimal(0))
        losses.append(-d if d < 0 else Decimal(0))
    # Wilder 平滑化: 初期 window 期間を単純平均、それ以降は指数平滑
    if len(gains) < window:
        avg_gain = sum(gains, Decimal(0)) / Decimal(max(len(gains), 1))
        avg_loss = sum(losses, Decimal(0)) / Decimal(max(len(losses), 1))
    else:
        avg_gain = sum(gains[:window], Decimal(0)) / Decimal(window)
        avg_loss = sum(losses[:window], Decimal(0)) / Decimal(window)
        w = Decimal(window)
        for g, lo in zip(gains[window:], losses[window:], strict=False):
            avg_gain = (avg_gain * (w - 1) + g) / w
            avg_loss = (avg_loss * (w - 1) + lo) / w
    if avg_loss == 0:
        return Decimal(100)
    rs = avg_gain / avg_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + rs)


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # 先に検査（bool は int のサブクラス）
        return Decimal(1) if value else Decimal(0)
    if isinstance(value, int | float):
        return Decimal(str(value))
    raise TypeError(f"cannot coerce to Decimal: {value!r}")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return value != 0
    raise TypeError(f"cannot coerce to bool: {value!r}")


def evaluate(expr: Expr, ctx: EvalContext) -> Decimal | bool:
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, Var):
        if expr.name not in _VAR_NAMES:
            raise ValueError(f"unknown var: {expr.name}")
        return _var_value(expr.name, ctx.bars[ctx.i])
    if isinstance(expr, Indicator):
        if expr.kind not in _INDICATOR_NAMES:
            raise ValueError(f"unknown indicator: {expr.kind}")
        if expr.window < 1:
            raise ValueError("indicator window must be >= 1")
        values = _collect_values(expr.of, ctx, expr.window if expr.kind != "rsi" else expr.window + 1)
        if expr.kind == "sma":
            return _sma(values)
        if expr.kind == "ema":
            return _ema(values, expr.window)
        if expr.kind == "stddev":
            return _stddev(values)
        if expr.kind == "rsi":
            return _rsi(values, expr.window)
    if isinstance(expr, BinOp):
        lhs = _as_decimal(evaluate(expr.lhs, ctx))
        rhs = _as_decimal(evaluate(expr.rhs, ctx))
        if expr.op == "+":
            return lhs + rhs
        if expr.op == "-":
            return lhs - rhs
        if expr.op == "*":
            return lhs * rhs
        if expr.op == "/":
            if rhs == 0:
                return Decimal(0)  # ゼロ除算は 0 を返す（戦略の安全装置）
            return lhs / rhs
        raise ValueError(f"unknown binop: {expr.op}")
    if isinstance(expr, Compare):
        lhs = _as_decimal(evaluate(expr.lhs, ctx))
        rhs = _as_decimal(evaluate(expr.rhs, ctx))
        ops = {"<": lhs < rhs, "<=": lhs <= rhs, ">": lhs > rhs, ">=": lhs >= rhs, "==": lhs == rhs}
        if expr.op not in ops:
            raise ValueError(f"unknown compare op: {expr.op}")
        return ops[expr.op]
    if isinstance(expr, Logical):
        if expr.op == "not":
            if len(expr.args) != 1:
                raise ValueError("'not' takes 1 argument")
            return not _as_bool(evaluate(expr.args[0], ctx))
        if expr.op == "and":
            return all(_as_bool(evaluate(a, ctx)) for a in expr.args)
        if expr.op == "or":
            return any(_as_bool(evaluate(a, ctx)) for a in expr.args)
        raise ValueError(f"unknown logical op: {expr.op}")
    if isinstance(expr, IfThenElse):
        return evaluate(expr.then if _as_bool(evaluate(expr.cond, ctx)) else expr.otherwise, ctx)
    raise TypeError(f"unhandled expr type: {type(expr).__name__}")


def max_lookback(expr: Expr) -> int:
    if isinstance(expr, Const | Var):
        return 0
    if isinstance(expr, Indicator):
        # RSI は window+1 バー必要、他は window バー
        extra = 1 if expr.kind == "rsi" else 0
        return max(expr.window + extra, max_lookback(expr.of))
    if isinstance(expr, BinOp | Compare):
        return max(max_lookback(expr.lhs), max_lookback(expr.rhs))
    if isinstance(expr, Logical):
        return max((max_lookback(a) for a in expr.args), default=0)
    if isinstance(expr, IfThenElse):
        return max(max_lookback(expr.cond), max_lookback(expr.then), max_lookback(expr.otherwise))
    return 0
