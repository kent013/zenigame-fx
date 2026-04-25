"""T031: generate_run_report.py の Feasibility 関連ユニットテスト.

Codex impl-review round 1 Warning 対応:
- archive_rows の trade_count が NaN / None / 文字列でも ValueError を起こさず 0 扱い。
"""

from __future__ import annotations

import math

from scripts.alpha_factory.generate_run_report import _as_int_safe


def test_as_int_safe_integer() -> None:
    assert _as_int_safe(5) == 5
    assert _as_int_safe(0) == 0
    assert _as_int_safe(-3) == -3


def test_as_int_safe_float_truncates() -> None:
    assert _as_int_safe(5.7) == 5
    assert _as_int_safe(-2.9) == -2


def test_as_int_safe_none_returns_zero() -> None:
    assert _as_int_safe(None) == 0


def test_as_int_safe_nan_returns_zero() -> None:
    assert _as_int_safe(float("nan")) == 0
    assert _as_int_safe(math.nan) == 0


def test_as_int_safe_inf_returns_zero() -> None:
    assert _as_int_safe(float("inf")) == 0
    assert _as_int_safe(float("-inf")) == 0


def test_as_int_safe_string_numeric() -> None:
    assert _as_int_safe("7") == 7
    assert _as_int_safe("3.5") == 3


def test_as_int_safe_string_garbage_returns_zero() -> None:
    assert _as_int_safe("abc") == 0
    assert _as_int_safe("") == 0


def test_as_int_safe_dict_returns_zero() -> None:
    """unsupported type は ValueError ではなく 0 にフォールバック."""
    assert _as_int_safe({"a": 1}) == 0
