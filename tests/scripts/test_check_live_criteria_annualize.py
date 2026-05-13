"""cycle 23 C1: `_check_live_criteria` の annualize 経路統一テスト。

bug fix の核心: trade-level sharpe vs annualized sharpe_min=1.0 の単位不整合を
解消し、 Stage C 内部判定 (evaluate_stage_c) と整合化する。

主要観点:
- annualize 適用 (trade-level → annualized で比較)
- trade_sharpe_stage_c 第一優先、 trade_sharpe_raw fallback
- raw fallback の window は stage_a_window_days (Codex Round 1 Warning 反映)
- value (annualized SSOT) と value_trade_level 併記
- sharpe_calc_version 拡張は summary 内専用 (archive 列は変更しない)
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest

from scripts.alpha_factory.run_ga import _check_live_criteria


def _make_row(
    *,
    trade_sharpe_stage_c: float | None = None,
    trade_sharpe_raw: float | None = None,
    trade_count: int = 51,
    total_pnl: float = 60000.0,
    max_drawdown_pct: float = 4.0,
    sharpe_calc_version: str = "v2_trade_level",
) -> dict[str, Any]:
    return {
        "trade_sharpe_stage_c": trade_sharpe_stage_c,
        "trade_sharpe_raw": trade_sharpe_raw,
        "trade_count": trade_count,
        "total_pnl": total_pnl,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_calc_version": sharpe_calc_version,
    }


_DEFAULT_CRITERIA: Mapping[str, float | int] = {
    "sharpe_min": 1.0,
    "total_pnl_min": 50000.0,
    "max_drawdown_max": 0.20,
    "trade_count_min": 50,
    "trade_count_max": 5000,
}


def test_annualize_applied_to_sharpe_comparison() -> None:
    """trade-level 0.184 + trade_count=51 + holdout=60 → annualized ≈ 2.69 ≥ 1.0 → pass=True.

    Stage C 内部判定 (evaluate_stage_c) と完全に同じ式で計算される。
    Run 75 best g60_i46 の実数値で検証。
    """
    row = _make_row(trade_sharpe_stage_c=0.184)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["pass"] is True
    annualized = float(sharpe["value"])
    assert math.isclose(annualized, 2.69, abs_tol=0.05)
    assert sharpe["value_trade_level"] == "0.184"


def test_trade_level_below_annualized_threshold_fails() -> None:
    """trade-level 0.05 + trade_count=51 + holdout=60 → annualized ≈ 0.73 < 1.0 → fail."""
    row = _make_row(trade_sharpe_stage_c=0.05)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["pass"] is False
    annualized = float(sharpe["value"])
    assert annualized < 1.0


def test_trade_sharpe_stage_c_preferred_over_raw() -> None:
    """trade_sharpe_stage_c が存在すれば trade_sharpe_raw より優先される。"""
    row = _make_row(trade_sharpe_stage_c=0.20, trade_sharpe_raw=0.05)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["sharpe_source"] == "trade_sharpe_stage_c"
    assert sharpe["value_trade_level"] == "0.2"


def test_fallback_to_trade_sharpe_raw_with_stage_a_window() -> None:
    """trade_sharpe_stage_c=None で trade_sharpe_raw fallback、 window は stage_a_window_days。"""
    row = _make_row(trade_sharpe_stage_c=None, trade_sharpe_raw=0.10)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["sharpe_source"] == "trade_sharpe_raw"
    assert sharpe["annualize_window_days"] == 60  # = stage_a_window_days


def test_fallback_window_uses_stage_a_window_not_holdout() -> None:
    """Codex Round 1 Warning: raw fallback は stage_a_window_days で annualize。

    holdout_days=120 と stage_a_window_days=60 を別値にすると、 raw fallback は
    stage_a (60) を使う。
    """
    row = _make_row(trade_sharpe_stage_c=None, trade_sharpe_raw=0.10)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=120, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["annualize_window_days"] == 60
    # stage_c (holdout=120) 経路を使うと window は別になるが、 fallback では stage_a (60) を使う


def test_both_sharpe_none_returns_pass_false() -> None:
    """trade_sharpe_stage_c も trade_sharpe_raw も None → pass=False、 value=None."""
    row = _make_row(trade_sharpe_stage_c=None, trade_sharpe_raw=None)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["pass"] is False
    assert sharpe["value"] is None
    assert sharpe["sharpe_source"] == "none"


def test_value_trade_level_co_recorded_with_value() -> None:
    """value (annualized SSOT) と value_trade_level (元値) が併記される。"""
    row = _make_row(trade_sharpe_stage_c=0.184)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert "value" in sharpe
    assert "value_trade_level" in sharpe
    assert sharpe["value"] != sharpe["value_trade_level"]


def test_v1_bar_annualized_archive_skipped() -> None:
    """v1 archive (sharpe_calc_version != v2_trade_level) → sharpe pass=False。"""
    row = _make_row(
        trade_sharpe_stage_c=0.184,
        sharpe_calc_version="v1_bar_annualized",
    )
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["pass"] is False
    assert sharpe["sharpe_source"] == "none"  # v1 では sharpe_trade_level は確定しない


def test_sharpe_calc_version_extended_to_annualized_live_in_summary_only() -> None:
    """sharpe_calc_version は summary 内で `<original>_annualized_live` に拡張。

    archive 列の sharpe_calc_version 自体は変更しない (Codex design-review Round 1
    Warning: archive consumer 互換性)。 本テストは summary 出力の version 表記を
    検証する。
    """
    row = _make_row(trade_sharpe_stage_c=0.184)
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    sharpe = res["checks"]["sharpe"]
    assert sharpe["sharpe_calc_version"] == "v2_trade_level_annualized_live"


def test_holdout_days_propagated_to_annualize() -> None:
    """holdout_days パラメータが annualize に渡される (= trade_count/holdout_days で λ_day)。

    trade_count=60, holdout=60 → λ_day=1.0 → S_annual=S_trade × sqrt(252)
    trade_count=120, holdout=60 → λ_day=2.0 → S_annual=S_trade × sqrt(504)
    """
    row1 = _make_row(trade_sharpe_stage_c=0.1, trade_count=60)
    res1 = _check_live_criteria(
        row1, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    val1 = float(res1["checks"]["sharpe"]["value"])
    assert math.isclose(val1, 0.1 * math.sqrt(252), abs_tol=0.01)

    row2 = _make_row(trade_sharpe_stage_c=0.1, trade_count=120)
    res2 = _check_live_criteria(
        row2, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    val2 = float(res2["checks"]["sharpe"]["value"])
    assert math.isclose(val2, 0.1 * math.sqrt(504), abs_tol=0.01)


def test_all_pass_when_all_4_criteria_met() -> None:
    """全 4 軸 pass で all_pass=True (Run 75 best g60_i46 相当)。"""
    row = _make_row(
        trade_sharpe_stage_c=0.184,
        trade_count=51,
        total_pnl=51540.0,
        max_drawdown_pct=3.74,
    )
    res = _check_live_criteria(
        row, _DEFAULT_CRITERIA, holdout_days=60, stage_a_window_days=60
    )
    assert res["all_pass"] is True


def test_keyword_only_arguments_required() -> None:
    """holdout_days / stage_a_window_days は keyword-only (positional 渡し禁止)."""
    row = _make_row(trade_sharpe_stage_c=0.184)
    with pytest.raises(TypeError):
        _check_live_criteria(row, _DEFAULT_CRITERIA, 60, 60)  # type: ignore[misc]
