"""``src.ga.random_gen`` 用 primitive registry bridge (T018).

``src.alpha_factory.primitives._registry`` (完全 PrimitiveSpec + ComputeFn) を
``src.ga.random_gen.PrimitiveRegistry`` (``{id -> random_gen.PrimitiveSpec}``)
に変換する。Category は :func:`slot_from_category` (SSOT) を経由して
directional / modulator に射影する (R2: 将来 category 追加時のドリフト防止)。
"""

from __future__ import annotations

from typing import Literal

from src.alpha_factory.primitives._base import (
    ParamSpec,
    slot_from_category,
)
from src.alpha_factory.primitives._base import (
    PrimitiveCategory as _FullCategory,
)
from src.alpha_factory.primitives._registry import (
    ensure_registered,
    list_all,
)
from src.ga.random_gen import ParamRange
from src.ga.random_gen import PrimitiveSpec as RandomGenSpec

__all__ = ["build_random_gen_registry"]


def _category_to_random_gen(
    cat: _FullCategory,
) -> Literal["directional", "modulator"]:
    """primitives ``PrimitiveCategory`` を ``random_gen`` の 2 値 category に
    射影する。SSOT の ``slot_from_category`` を経由する。"""
    slot = slot_from_category(cat)  # "directional" | "local_gate"
    return "modulator" if slot == "local_gate" else "directional"


def _param_spec_to_range(p: ParamSpec) -> ParamRange:
    if p.is_int:
        return (int(p.low), int(p.high))
    return (float(p.low), float(p.high))


def build_random_gen_registry() -> dict[str, RandomGenSpec]:
    """``ensure_registered()`` 後の full registry を ``random_gen`` 用に変換する。

    Returns:
        ``{primitive_id -> RandomGenSpec}`` (random_gen が期待する
        ``PrimitiveRegistry`` と互換)。
    """
    ensure_registered()
    out: dict[str, RandomGenSpec] = {}
    for spec in list_all():
        out[spec.id] = RandomGenSpec(
            id=spec.id,
            category=_category_to_random_gen(spec.category),
            domain=spec.domain,
            param_schema={
                p.name: _param_spec_to_range(p) for p in spec.param_schema
            },
        )
    return out
