from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.dsl.ast import BinOp, Compare, Const, Expr, IfThenElse, Indicator, Logical, Var
from src.dsl.genome import Genome


def expr_to_dict(expr: Expr) -> dict[str, Any]:
    if isinstance(expr, Const):
        return {"kind": "const", "value": str(expr.value)}
    if isinstance(expr, Var):
        return {"kind": "var", "name": expr.name}
    if isinstance(expr, Indicator):
        return {"kind": "indicator", "name": expr.kind, "window": expr.window, "of": expr_to_dict(expr.of)}
    if isinstance(expr, BinOp):
        return {"kind": "binop", "op": expr.op, "lhs": expr_to_dict(expr.lhs), "rhs": expr_to_dict(expr.rhs)}
    if isinstance(expr, Compare):
        return {"kind": "compare", "op": expr.op, "lhs": expr_to_dict(expr.lhs), "rhs": expr_to_dict(expr.rhs)}
    if isinstance(expr, Logical):
        return {"kind": "logical", "op": expr.op, "args": [expr_to_dict(a) for a in expr.args]}
    if isinstance(expr, IfThenElse):
        return {
            "kind": "ite",
            "cond": expr_to_dict(expr.cond),
            "then": expr_to_dict(expr.then),
            "otherwise": expr_to_dict(expr.otherwise),
        }
    raise TypeError(f"unknown expression type: {type(expr).__name__}")


def expr_from_dict(payload: dict[str, Any]) -> Expr:
    kind = payload["kind"]
    if kind == "const":
        return Const(Decimal(payload["value"]))
    if kind == "var":
        return Var(payload["name"])
    if kind == "indicator":
        return Indicator(payload["name"], int(payload["window"]), expr_from_dict(payload["of"]))
    if kind == "binop":
        return BinOp(payload["op"], expr_from_dict(payload["lhs"]), expr_from_dict(payload["rhs"]))
    if kind == "compare":
        return Compare(payload["op"], expr_from_dict(payload["lhs"]), expr_from_dict(payload["rhs"]))
    if kind == "logical":
        return Logical(payload["op"], tuple(expr_from_dict(a) for a in payload["args"]))
    if kind == "ite":
        return IfThenElse(
            expr_from_dict(payload["cond"]), expr_from_dict(payload["then"]), expr_from_dict(payload["otherwise"])
        )
    raise ValueError(f"unknown expression kind: {kind}")


def genome_to_dict(genome: Genome) -> dict[str, Any]:
    return {
        "name": genome.name,
        "units": genome.units,
        "entry_long": expr_to_dict(genome.entry_long),
        "entry_short": expr_to_dict(genome.entry_short),
        "exit_long": expr_to_dict(genome.exit_long),
        "exit_short": expr_to_dict(genome.exit_short),
    }


def genome_from_dict(payload: dict[str, Any]) -> Genome:
    return Genome(
        name=payload["name"],
        units=int(payload["units"]),
        entry_long=expr_from_dict(payload["entry_long"]),
        entry_short=expr_from_dict(payload["entry_short"]),
        exit_long=expr_from_dict(payload["exit_long"]),
        exit_short=expr_from_dict(payload["exit_short"]),
    )
