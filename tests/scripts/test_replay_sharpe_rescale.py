"""T042: trade-level → annualized Sharpe 換算 replay テスト."""

from __future__ import annotations

import math

import pytest

from scripts.alpha_factory.replay_sharpe_rescale import (
    TRADING_DAYS_PER_YEAR,
    AnnualizationResult,
    annualize_population,
    annualize_trade_sharpe,
    summarize,
)


class TestAnnualizeTradeSharpe:
    """trade-level → annualized 換算式の単体検証."""

    def test_basic_conversion_formula(self) -> None:
        """S_annual = S_trade × sqrt(λ_day × 252).

        例: S_trade=0.2, trade_count=60, window_days=60 → λ_day=1.0
        S_annual = 0.2 × sqrt(252) ≈ 3.1749
        """
        result = annualize_trade_sharpe(
            trade_sharpe_raw=0.2, trade_count=60, window_days=60
        )
        assert result is not None
        assert result == pytest.approx(0.2 * math.sqrt(TRADING_DAYS_PER_YEAR), abs=1e-9)

    def test_higher_frequency_amplifies_sharpe(self) -> None:
        """λ_day が増えると annualized Sharpe も増える (頻度効果).

        Stage A 60 日で trade=600 → λ=10/day → S_annual = S_trade×sqrt(2520)
        """
        s_low = annualize_trade_sharpe(0.1, trade_count=60, window_days=60)
        s_high = annualize_trade_sharpe(0.1, trade_count=600, window_days=60)
        assert s_low is not None
        assert s_high is not None
        assert s_high > s_low
        # ratio = sqrt(10) ≈ 3.16
        assert s_high / s_low == pytest.approx(math.sqrt(10.0), abs=1e-9)

    def test_zero_trade_count_returns_none(self) -> None:
        assert annualize_trade_sharpe(0.5, trade_count=0, window_days=60) is None

    def test_negative_trade_count_returns_none(self) -> None:
        assert annualize_trade_sharpe(0.5, trade_count=-1, window_days=60) is None

    def test_zero_window_days_returns_none(self) -> None:
        assert annualize_trade_sharpe(0.5, trade_count=60, window_days=0) is None

    def test_nan_sharpe_returns_none(self) -> None:
        assert annualize_trade_sharpe(float("nan"), 60, 60) is None

    def test_inf_sharpe_returns_none(self) -> None:
        assert annualize_trade_sharpe(float("inf"), 60, 60) is None

    def test_negative_sharpe_preserves_sign(self) -> None:
        """負の Sharpe は負のまま annualize される (絶対値は scale)."""
        s = annualize_trade_sharpe(-0.3, trade_count=60, window_days=60)
        assert s is not None
        assert s < 0
        assert s == pytest.approx(-0.3 * math.sqrt(252.0), abs=1e-9)


class TestAnnualizePopulation:
    """archive list 全体換算の挙動."""

    def test_filters_invalid_rows(self) -> None:
        rows = [
            {"trade_sharpe_raw": 0.2, "trade_count": 60},
            {"trade_sharpe_raw": None, "trade_count": 60},  # invalid
            {"trade_sharpe_raw": 0.1, "trade_count": 0},  # invalid
            {"trade_sharpe_raw": float("nan"), "trade_count": 60},  # invalid
            {"trade_sharpe_raw": -0.05, "trade_count": 30},  # ok (negative ok)
        ]
        results = annualize_population(rows, window_days=60)
        assert len(results) == 2
        assert all(isinstance(r, AnnualizationResult) for r in results)

    def test_empty_population(self) -> None:
        assert annualize_population([], window_days=60) == []

    def test_lambda_day_calculation(self) -> None:
        rows = [
            {"trade_sharpe_raw": 0.1, "trade_count": 120},
        ]
        results = annualize_population(rows, window_days=60)
        assert len(results) == 1
        assert results[0].lambda_day == pytest.approx(2.0, abs=1e-9)


class TestSummarize:
    """population 統計と target_pass_rate 算出."""

    def test_recommended_threshold_at_target_pass_rate(self) -> None:
        """target_pass_rate=0.15 で 85%ile が出る."""
        # 100 個体、trade_sharpe_raw 0.00, 0.01, 0.02, ..., 0.99
        results = [
            AnnualizationResult(
                trade_sharpe_raw=i / 100.0,
                trade_count=60,
                lambda_day=1.0,
                sharpe_annualized=(i / 100.0) * math.sqrt(252.0),
            )
            for i in range(100)
        ]
        s = summarize(results, target_pass_rate=0.15)
        # idx = round((n-1) × (1 - 0.15)) = round(99 × 0.85) = 84 → values[84] = 0.84
        assert s["recommended_stage_a_threshold_trade_level"] == pytest.approx(
            0.84, abs=1e-9
        )

    def test_empty_results(self) -> None:
        s = summarize([], target_pass_rate=0.15)
        assert s["n_individuals"] == 0
        assert s["trade_sharpe_raw"] == {}
        assert "recommended_stage_a_threshold_trade_level" not in s

    def test_quantile_keys_present(self) -> None:
        results = [
            AnnualizationResult(0.1, 60, 1.0, 0.1 * math.sqrt(252)),
            AnnualizationResult(0.2, 60, 1.0, 0.2 * math.sqrt(252)),
            AnnualizationResult(0.3, 60, 1.0, 0.3 * math.sqrt(252)),
        ]
        s = summarize(results, target_pass_rate=0.15)
        for k in ("n", "min", "median", "q75", "q85", "q95", "max", "mean"):
            assert k in s["trade_sharpe_raw"], f"missing {k}"
            assert k in s["sharpe_annualized"], f"missing {k}"
