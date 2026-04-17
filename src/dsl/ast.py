from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Union

Expr = Union["Const", "Var", "Indicator", "BinOp", "Compare", "Logical", "IfThenElse"]


@dataclass(frozen=True)
class Const:
    value: Decimal


@dataclass(frozen=True)
class Var:
    name: str
    # 許容される名前: close, open, high, low, volume, bid_close, ask_close, spread


@dataclass(frozen=True)
class Indicator:
    kind: str  # "sma" | "ema" | "stddev" | "rsi"
    window: int
    of: Expr


@dataclass(frozen=True)
class BinOp:
    op: str  # "+" | "-" | "*" | "/"
    lhs: Expr
    rhs: Expr


@dataclass(frozen=True)
class Compare:
    op: str  # "<" | "<=" | ">" | ">=" | "=="
    lhs: Expr
    rhs: Expr


@dataclass(frozen=True)
class Logical:
    op: str  # "and" | "or" | "not"
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class IfThenElse:
    cond: Expr
    then: Expr
    otherwise: Expr
