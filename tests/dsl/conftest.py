"""DslStrategy / 関連テスト共通 fixture（T009）。

実 primitive registry が無い段階でも、 evaluator Protocol を満たす最小スタブを
提供してテストを構築する。T010 primitives-registry で RegistryEvaluator が整備されたら
本 fixture は引き続き「決定論的に値を制御したいテスト」用として残す。
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from src.domain.price import PriceBar
from src.dsl.genome import SignalConfig


class ScriptedPrimitiveEvaluator:
    """bar index ごとに primitive 名→値辞書を事前設定する stub。

    使用例:
        ev = ScriptedPrimitiveEvaluator({
            0: {"D1": 0.8},
            1: {"D1": 0.9},
        })
        ev.evaluate(bars, idx, signal) で signal.name に対応する値を返す。
        未指定 name は 0.0（中立）。
    """

    def __init__(self, script: Mapping[int, Mapping[str, float]]) -> None:
        self._script = {idx: dict(vals) for idx, vals in script.items()}

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        vals = self._script.get(idx, {})
        if signal.name in vals:
            return float(vals[signal.name])
        return 0.0


class ConstantPrimitiveEvaluator:
    """常に固定値を返す stub（warmup テスト用）。"""

    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        return self._value


@pytest.fixture
def scripted_evaluator_factory():
    """scripted evaluator を作る factory fixture."""

    def _make(script: Mapping[int, Mapping[str, float]]) -> ScriptedPrimitiveEvaluator:
        return ScriptedPrimitiveEvaluator(script)

    return _make


@pytest.fixture
def constant_evaluator_factory():
    def _make(value: float = 0.0) -> ConstantPrimitiveEvaluator:
        return ConstantPrimitiveEvaluator(value)

    return _make
