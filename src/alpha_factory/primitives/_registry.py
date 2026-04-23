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


def register_if_absent(spec: PrimitiveSpec) -> bool:
    """原子的に登録する。既登録なら False、新規登録なら True を返す。

    T011 の ensure_registered で冪等かつ並行安全な登録パスを提供するため追加。
    `try get_primitive / except KeyError: register` は非原子的で、並行時に
    `register` 側 `ValueError` を引き起こすため、本関数で lock 内に存在確認＋
    登録を atomic に閉じ込める。

    Notes:
        validate_primitive_spec は既存チェック前に呼ぶ。新規 spec の健全性は
        常に検証する（既存 id でも spec 側が壊れていれば silent skip せず fail する）。

    Raises:
        ValueError: spec が不変条件違反。
    """
    validate_primitive_spec(spec)
    with _LOCK:
        if spec.id in _PRIMITIVES:
            return False
        _PRIMITIVES[spec.id] = spec
        return True


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
    """primitive モジュールの明示的 bootstrap 関数。

    T011 で `directional_generic` の 14 primitive 登録を橋渡しする。
    冪等（複数回呼んでも 2 回目以降は既登録 spec は register_if_absent で skip）。
    並行呼び出しに対しては register_if_absent 内部 Lock で安全。

    production path (GA entry) から明示的に 1 回呼ぶ規約。
    """
    # 遅延 import（循環回避）。_base.py は触らずに実装モジュールだけ呼ぶ。
    from src.alpha_factory.primitives.directional_generic import (
        ensure_registered as _reg_directional_generic,
    )

    _reg_directional_generic()
