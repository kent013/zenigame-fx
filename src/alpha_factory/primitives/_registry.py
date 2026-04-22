"""primitives-registry の登録・取得 API（T010 骨格）。

registry は module-level dict。本 TODO では空のまま。
後続 primitive 実装 TODO で register されて埋まる。

並行性方針:
    本 registry は bootstrap 段階（プロセス起動直後の ensure_registered()）で
    書込が完了し、以降は read-only となる想定。ただし import 順序や
    テスト並列実行（pytest-xdist 等）で register/clear が多重呼び出しされる
    可能性を吸収するため、write 操作 (register / clear) は threading.Lock で
    保護する。read 操作 (get_primitive / list_*) はロックしない
    （CPython の dict は原子操作が多く、bootstrap 後は変更されない前提）。

Bootstrap 方針:
    production path (GA entry) から ensure_registered() を明示的に呼ぶ。
    副作用 import 単独には依存しない（登録漏れ検出のため）。
"""

from __future__ import annotations

import threading

from src.alpha_factory.primitives._base import (
    PrimitiveCategory,
    PrimitiveDomain,
    PrimitiveSpec,
    validate_primitive_spec,
)

_PRIMITIVES: dict[str, PrimitiveSpec] = {}
_LOCK = threading.Lock()


def register(spec: PrimitiveSpec) -> None:
    """PrimitiveSpec を registry に登録する。

    登録前に validate_primitive_spec で不変条件を検証する
    （required_data の canonical naming、param_schema 重複名、low/high/default
    整合など）。

    Raises:
        ValueError: 同じ id が既に登録されている、あるいは spec が不変条件違反。
                    silent override は許さない。
    """
    validate_primitive_spec(spec)
    with _LOCK:
        if spec.id in _PRIMITIVES:
            raise ValueError(f"primitive {spec.id!r} already registered")
        _PRIMITIVES[spec.id] = spec


def get_primitive(primitive_id: str) -> PrimitiveSpec:
    """id で PrimitiveSpec を取得する。

    Raises:
        KeyError: id が未登録の場合。
    """
    if primitive_id not in _PRIMITIVES:
        raise KeyError(f"primitive {primitive_id!r} not in registry")
    return _PRIMITIVES[primitive_id]


def list_all() -> tuple[PrimitiveSpec, ...]:
    """全 PrimitiveSpec を登録順（dict 挿入順）で返す。"""
    return tuple(_PRIMITIVES.values())


def list_by_category(
    category: PrimitiveCategory,
) -> tuple[PrimitiveSpec, ...]:
    """指定 category の PrimitiveSpec を登録順で返す。"""
    return tuple(
        spec for spec in _PRIMITIVES.values() if spec.category == category
    )


def list_by_domain(
    domain: PrimitiveDomain,
) -> tuple[PrimitiveSpec, ...]:
    """指定 domain の PrimitiveSpec を登録順で返す。"""
    return tuple(
        spec for spec in _PRIMITIVES.values() if spec.domain == domain
    )


def clear() -> None:
    """registry を空にする（テスト用）。

    本番 path では呼ばない。tests 内の fixture などで isolation のために使う。
    """
    with _LOCK:
        _PRIMITIVES.clear()


def ensure_registered() -> None:
    """primitive モジュールの明示的 bootstrap 関数（T010 骨格では no-op）。

    後続 TODO で primitive 実装モジュールを import してここから register を
    発火させる。冪等（複数回呼んでも 2 回目以降は既登録で no-op、ただし
    重複 register を避けるため各 primitive 側が id 済みチェックを行う）。

    production path (GA entry) から明示的に 1 回呼ぶ規約。
    並行呼び出しに対しては register() 内部 Lock で安全。
    """
    # 骨格では未登録。primitive 実装 TODO で埋まる。
    return None
