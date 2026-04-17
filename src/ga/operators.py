from __future__ import annotations

import random
from dataclasses import replace
from decimal import Decimal

from src.dsl.ast import BinOp, Compare, Const, Expr, IfThenElse, Indicator, Logical
from src.dsl.genome import Genome
from src.ga.random_gen import WINDOWS, random_condition

_SLOTS = ("entry_long", "entry_short", "exit_long", "exit_short")


def crossover(a: Genome, b: Genome, rng: random.Random) -> tuple[Genome, Genome]:
    """4 式からランダムに 1 つ選んで親 A/B 間で入れ替えて子 2 体を返す。"""
    slot = rng.choice(_SLOTS)
    a_child = replace(a, name=f"{a.name}_x{slot}_{b.name}", **{slot: getattr(b, slot)})
    b_child = replace(b, name=f"{b.name}_x{slot}_{a.name}", **{slot: getattr(a, slot)})
    return a_child, b_child


def _collect_consts(expr: Expr) -> list[Const]:
    found: list[Const] = []

    def walk(e: Expr) -> None:
        if isinstance(e, Const):
            found.append(e)
        elif isinstance(e, Indicator):
            walk(e.of)
        elif isinstance(e, BinOp | Compare):
            walk(e.lhs)
            walk(e.rhs)
        elif isinstance(e, Logical):
            for arg in e.args:
                walk(arg)
        elif isinstance(e, IfThenElse):
            walk(e.cond)
            walk(e.then)
            walk(e.otherwise)

    walk(expr)
    return found


def _collect_indicators(expr: Expr) -> list[Indicator]:
    found: list[Indicator] = []

    def walk(e: Expr) -> None:
        if isinstance(e, Indicator):
            found.append(e)
            walk(e.of)
        elif isinstance(e, BinOp | Compare):
            walk(e.lhs)
            walk(e.rhs)
        elif isinstance(e, Logical):
            for arg in e.args:
                walk(arg)
        elif isinstance(e, IfThenElse):
            walk(e.cond)
            walk(e.then)
            walk(e.otherwise)

    walk(expr)
    return found


def _replace_node(expr: Expr, target: Expr, replacement: Expr) -> Expr:
    if expr is target:
        return replacement
    if isinstance(expr, Indicator):
        return Indicator(expr.kind, expr.window, _replace_node(expr.of, target, replacement))
    if isinstance(expr, BinOp):
        return BinOp(
            expr.op,
            _replace_node(expr.lhs, target, replacement),
            _replace_node(expr.rhs, target, replacement),
        )
    if isinstance(expr, Compare):
        return Compare(
            expr.op,
            _replace_node(expr.lhs, target, replacement),
            _replace_node(expr.rhs, target, replacement),
        )
    if isinstance(expr, Logical):
        return Logical(expr.op, tuple(_replace_node(a, target, replacement) for a in expr.args))
    if isinstance(expr, IfThenElse):
        return IfThenElse(
            _replace_node(expr.cond, target, replacement),
            _replace_node(expr.then, target, replacement),
            _replace_node(expr.otherwise, target, replacement),
        )
    return expr


def _perturb_const(expr: Expr, rng: random.Random) -> Expr:
    consts = _collect_consts(expr)
    if not consts:
        return expr
    target = rng.choice(consts)
    factor = Decimal("0.8") + Decimal(str(rng.random() * 0.4))  # 0.8〜1.2
    new_value = target.value * factor
    return _replace_node(expr, target, Const(new_value))


def _perturb_window(expr: Expr, rng: random.Random) -> Expr:
    indicators = _collect_indicators(expr)
    if not indicators:
        return expr
    target = rng.choice(indicators)
    idx = WINDOWS.index(target.window) if target.window in WINDOWS else rng.randrange(len(WINDOWS))
    new_idx = max(0, min(len(WINDOWS) - 1, idx + rng.choice((-1, 1))))
    new_window = WINDOWS[new_idx]
    if new_window == target.window:
        return expr
    return _replace_node(expr, target, Indicator(target.kind, new_window, target.of))


def mutate(genome: Genome, rng: random.Random, mutation_rate: float, max_depth: int = 4) -> Genome:
    """mutation_rate の確率で 1 ヶ所を変異させたゲノムを返す。発生しなかった場合は元のゲノム。"""
    if rng.random() >= mutation_rate:
        return genome

    slot = rng.choice(_SLOTS)
    original: Expr = getattr(genome, slot)
    mode = rng.choice(("replace", "const", "window"))
    if mode == "replace":
        new_expr: Expr = random_condition(rng, max_depth)
    elif mode == "const":
        new_expr = _perturb_const(original, rng)
        if new_expr is original:
            new_expr = random_condition(rng, max_depth)
    else:
        new_expr = _perturb_window(original, rng)
        if new_expr is original:
            new_expr = random_condition(rng, max_depth)
    return replace(genome, **{slot: new_expr})
