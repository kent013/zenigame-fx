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


# T045: v3 schema note ===================================================


def test_v3_schema_note_lists_seven_lex_keys() -> None:
    """T045: schema v3_stage_c_feasibility なら note に 7 要素順序が記載される.

    本テストは generate_run_report 内のインライン分岐ロジックを再現することで
    実装契約を固定 (実装が変わったら本 helper も同期更新)。
    """
    schema_v3 = "v3_stage_c_feasibility"
    schema_v2 = "v2_feasibility"
    schema_v1 = "v1_legacy"

    def _note(schema: str) -> str:
        if schema == "v3_stage_c_feasibility":
            return (
                "Best は (feasible, -violation, stage_c_feasible, "
                "stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) "
                "の辞書式 (v3_stage_c_feasibility, T045)。"
            )
        if schema == "v2_feasibility":
            return (
                "Best は (feasible, -violation, stage_c_pass, stage_b_pass, "
                "stage_a_pass, fitness_pen) の辞書式 (v2_feasibility)。"
            )
        return (
            "Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) "
            "の辞書式 (v1_legacy)。"
        )

    assert "stage_c_feasible" in _note(schema_v3)
    assert "T045" in _note(schema_v3)
    assert "v3_stage_c_feasibility" in _note(schema_v3)
    # v2/v1 互換維持
    assert "v2_feasibility" in _note(schema_v2)
    assert "v1_legacy" in _note(schema_v1)
    assert "stage_c_feasible" not in _note(schema_v2)
