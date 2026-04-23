"""primitives-registry 公開 API（T010 骨格）。

後続 primitive 実装 TODO は `_base` のみ import して register する規約。
外部 consumer（GA / DslStrategy）は本 __init__ の re-export を使う。
"""

from src.alpha_factory.primitives._base import (
    ComputeAllBarsFn,
    ComputeFn,
    EvaluationContext,
    GaSlot,
    ParamSpec,
    PrimitiveCategory,
    PrimitiveDomain,
    PrimitiveSpec,
    RequiredDataKey,
    is_valid_required_data,
    slot_from_category,
    validate_primitive_spec,
)
from src.alpha_factory.primitives._registry import (
    clear,
    ensure_registered,
    get_primitive,
    list_all,
    list_by_category,
    list_by_domain,
    register,
    register_if_absent,
)
from src.alpha_factory.primitives.evaluator import RegistryEvaluator

__all__ = [
    "ComputeAllBarsFn",
    "ComputeFn",
    "EvaluationContext",
    "GaSlot",
    "ParamSpec",
    "PrimitiveCategory",
    "PrimitiveDomain",
    "PrimitiveSpec",
    "RegistryEvaluator",
    "RequiredDataKey",
    "clear",
    "ensure_registered",
    "get_primitive",
    "is_valid_required_data",
    "list_all",
    "list_by_category",
    "list_by_domain",
    "register",
    "register_if_absent",
    "slot_from_category",
    "validate_primitive_spec",
]
