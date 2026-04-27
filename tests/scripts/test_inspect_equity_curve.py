"""T048: inspect_equity_curve helper unit tests."""

from __future__ import annotations

from typing import Any

import pytest

from scripts.alpha_factory.inspect_equity_curve import (
    _find_individual,
    _select_bars,
)


class _DummyBundle:
    def __init__(self) -> None:
        self.bars_stage_a = ["A_bar"]
        self.bars_stage_b = ["B_bar"]
        self.bars_holdout = ["C_bar"]


def _row(name: str) -> dict[str, Any]:
    return {"individual_name": name}


class TestFindIndividual:
    def test_found(self) -> None:
        rows = [_row("a"), _row("b"), _row("c")]
        assert _find_individual(rows, "b")["individual_name"] == "b"

    def test_not_found(self) -> None:
        rows = [_row("a"), _row("b")]
        assert _find_individual(rows, "x") is None


class TestSelectBars:
    def test_stage_a(self) -> None:
        bundle = _DummyBundle()
        assert _select_bars(bundle, "a") == ["A_bar"]

    def test_stage_b(self) -> None:
        bundle = _DummyBundle()
        assert _select_bars(bundle, "b") == ["B_bar"]

    def test_stage_c(self) -> None:
        bundle = _DummyBundle()
        assert _select_bars(bundle, "c") == ["C_bar"]

    def test_unknown_raises(self) -> None:
        bundle = _DummyBundle()
        with pytest.raises(ValueError, match="unknown stage"):
            _select_bars(bundle, "x")
