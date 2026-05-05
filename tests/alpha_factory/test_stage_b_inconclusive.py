"""is_stage_b_inconclusive helper のテスト (T087)."""
from __future__ import annotations

import math

import numpy as np

from src.alpha_factory.stage_b_inconclusive import is_stage_b_inconclusive


def test_inconclusive_when_n_fold_below_3() -> None:
    assert is_stage_b_inconclusive(0) is True
    assert is_stage_b_inconclusive(1) is True
    assert is_stage_b_inconclusive(2) is True


def test_not_inconclusive_when_n_fold_at_threshold() -> None:
    assert is_stage_b_inconclusive(3) is False


def test_not_inconclusive_when_n_fold_above_threshold() -> None:
    assert is_stage_b_inconclusive(5) is False
    assert is_stage_b_inconclusive(9) is False


def test_inconclusive_when_n_fold_none() -> None:
    assert is_stage_b_inconclusive(None) is True


def test_inconclusive_when_n_fold_nan() -> None:
    assert is_stage_b_inconclusive(float("nan")) is True


def test_inconclusive_when_n_fold_string() -> None:
    assert is_stage_b_inconclusive("3") is True


def test_inconclusive_when_n_fold_bool_true_excluded() -> None:
    """bool は Integral のサブクラスだが明示除外で inconclusive 扱い."""
    assert is_stage_b_inconclusive(True) is True
    assert is_stage_b_inconclusive(False) is True


def test_handles_numpy_integer_above_threshold() -> None:
    assert is_stage_b_inconclusive(np.int64(5)) is False
    assert is_stage_b_inconclusive(np.int32(3)) is False


def test_handles_numpy_integer_below_threshold() -> None:
    assert is_stage_b_inconclusive(np.int64(2)) is True


def test_handles_negative_int_as_inconclusive() -> None:
    assert is_stage_b_inconclusive(-1) is True


def test_handles_float_integer_as_inconclusive() -> None:
    """float の 5.0 は Integral ではないため inconclusive 扱い (型厳密)."""
    assert is_stage_b_inconclusive(5.0) is True
    # float NaN は別経路で処理されるため重複しないことも確認
    assert is_stage_b_inconclusive(math.nan) is True
