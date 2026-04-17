from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.strategy.base import Strategy

_REGISTRY: dict[str, Callable[..., Strategy]] = {}


def register(name: str) -> Callable[[Callable[..., Strategy]], Callable[..., Strategy]]:
    def decorator(factory: Callable[..., Strategy]) -> Callable[..., Strategy]:
        if name in _REGISTRY:
            raise ValueError(f"strategy '{name}' already registered")
        _REGISTRY[name] = factory
        return factory

    return decorator


def build(name: str, **params: Any) -> Strategy:
    if name not in _REGISTRY:
        raise ValueError(f"unknown strategy: {name}. available: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**params)


def list_strategies() -> list[str]:
    return sorted(_REGISTRY.keys())
