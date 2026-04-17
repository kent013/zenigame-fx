from __future__ import annotations

import random
from decimal import Decimal

from src.dsl.ast import BinOp, Compare, Const, Expr, Indicator, Logical, Var
from src.dsl.genome import Genome

PRICE_VARS = ("close", "open", "high", "low")
MULTIPLIER_CONSTS = tuple(Decimal(s) for s in ("0.25", "0.5", "1.0", "1.5", "2.0", "2.5", "3.0"))
INDICATOR_NAMES = ("sma", "ema", "stddev", "rsi")
WINDOWS = (5, 10, 14, 20, 30, 50)
NUMERIC_BINOPS = ("+", "-", "*", "/")
COMPARE_OPS = ("<", "<=", ">", ">=")
LOGICAL_OPS = ("and", "or", "not")


def random_numeric(rng: random.Random, max_depth: int, depth: int = 0) -> Expr:
    """数値を返す Expr をランダム生成する。"""
    if depth >= max_depth or rng.random() < 0.35:
        choice = rng.randrange(3)
        if choice == 0:
            return Var(rng.choice(PRICE_VARS))
        if choice == 1:
            return Const(rng.choice(MULTIPLIER_CONSTS))
        return Indicator(
            rng.choice(INDICATOR_NAMES),
            rng.choice(WINDOWS),
            Var(rng.choice(PRICE_VARS)),
        )
    if rng.random() < 0.7:
        return BinOp(
            rng.choice(NUMERIC_BINOPS),
            random_numeric(rng, max_depth, depth + 1),
            random_numeric(rng, max_depth, depth + 1),
        )
    return Indicator(
        rng.choice(INDICATOR_NAMES),
        rng.choice(WINDOWS),
        random_numeric(rng, max_depth, depth + 1),
    )


def random_condition(rng: random.Random, max_depth: int, depth: int = 0) -> Expr:
    """bool を返す Expr をランダム生成する。"""
    if depth >= max_depth or rng.random() < 0.55:
        return Compare(
            rng.choice(COMPARE_OPS),
            random_numeric(rng, max_depth, depth),
            random_numeric(rng, max_depth, depth),
        )
    op = rng.choice(LOGICAL_OPS)
    if op == "not":
        return Logical("not", (random_condition(rng, max_depth, depth + 1),))
    return Logical(
        op,
        (
            random_condition(rng, max_depth, depth + 1),
            random_condition(rng, max_depth, depth + 1),
        ),
    )


def random_genome(rng: random.Random, name: str, units: int, max_depth: int = 4) -> Genome:
    return Genome(
        name=name,
        units=units,
        entry_long=random_condition(rng, max_depth),
        entry_short=random_condition(rng, max_depth),
        exit_long=random_condition(rng, max_depth),
        exit_short=random_condition(rng, max_depth),
    )
