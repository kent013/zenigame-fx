"""統計検定最小セットのテスト。

対象: src/alpha_factory/statistics.py
  - deflated_sharpe_ratio
  - fold_sign_ratio
  - block_bootstrap_sharpe_ci
  - 内部: _norm_cdf, _norm_ppf
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest

from src.alpha_factory.statistics import (
    _EULER_GAMMA,
    _norm_cdf,
    _norm_ppf,
    block_bootstrap_sharpe_ci,
    deflated_sharpe_ratio,
    fold_sign_ratio,
)

# ---------------------------------------------------------------------------
# 内部関数: _norm_cdf / _norm_ppf
# ---------------------------------------------------------------------------


class TestNormCdf:
    def test_zero(self) -> None:
        assert _norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)

    def test_positive_1_96(self) -> None:
        # Phi(1.96) ≈ 0.9750021048517795
        assert _norm_cdf(1.96) == pytest.approx(0.9750021048517795, abs=1e-6)

    def test_negative_1_96(self) -> None:
        assert _norm_cdf(-1.96) == pytest.approx(0.02499789514822101, abs=1e-6)

    def test_symmetry(self) -> None:
        # Phi(x) + Phi(-x) == 1
        for x in [0.5, 1.0, 2.0, 3.5]:
            assert _norm_cdf(x) + _norm_cdf(-x) == pytest.approx(1.0, abs=1e-12)


class TestNormPpf:
    def test_median(self) -> None:
        assert _norm_ppf(0.5) == pytest.approx(0.0, abs=1e-9)

    def test_known_points(self) -> None:
        # 文献値（例: scipy.stats.norm.ppf、tolerance 1e-6）
        # 0.975 -> 1.959963984540054
        assert _norm_ppf(0.975) == pytest.approx(1.959963984540054, abs=1e-6)
        assert _norm_ppf(0.025) == pytest.approx(-1.959963984540054, abs=1e-6)
        assert _norm_ppf(0.999) == pytest.approx(3.090232306167813, abs=1e-6)
        assert _norm_ppf(0.001) == pytest.approx(-3.090232306167813, abs=1e-6)

    def test_symmetry(self) -> None:
        for p in [0.1, 0.3, 0.45, 0.7, 0.9]:
            assert _norm_ppf(p) == pytest.approx(-_norm_ppf(1.0 - p), abs=1e-9)

    def test_round_trip_with_cdf(self) -> None:
        for x in [-2.5, -1.0, 0.3, 1.0, 2.5]:
            assert _norm_ppf(_norm_cdf(x)) == pytest.approx(x, abs=1e-6)

    @pytest.mark.parametrize("bad_p", [0.0, 1.0, -0.1, 1.1, float("nan"), float("inf")])
    def test_invalid_p_raises(self, bad_p: float) -> None:
        with pytest.raises(ValueError):
            _norm_ppf(bad_p)


# ---------------------------------------------------------------------------
# deflated_sharpe_ratio
# ---------------------------------------------------------------------------


def _reference_dsr(
    sr: float,
    n_trials: int,
    t_obs: int,
    skew: float,
    kurt: float,
    mean_sr: float,
    std_sr: float,
) -> float:
    """テスト内で独立に組み立て直した DSR 計算（Eq.(7)/(9) の素朴な再展開）。

    本関数は `deflated_sharpe_ratio` と同じ数式を独立に再実装しており、写し間違い
    検出のための比較ターゲット。CDF は ``math.erf`` を直接使い実装側 `_norm_cdf`
    との共有依存を減らす。inverse CDF のみ `_norm_ppf`（Acklam 近似）に依存する。
    """
    q1 = _norm_ppf(1.0 - 1.0 / n_trials)
    q2 = _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    expected_max_sr = mean_sr + std_sr * ((1.0 - _EULER_GAMMA) * q1 + _EULER_GAMMA * q2)
    denom_sq = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    z = ((sr - expected_max_sr) * math.sqrt(t_obs - 1)) / math.sqrt(denom_sq)
    # 独立に math.erf から CDF を組み立てる（`_norm_cdf` に依存しない）
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class TestDeflatedSharpeRatio:
    def test_monotonic_in_sharpe(self) -> None:
        """SR を増やすと DSR は単調増加（同一試行条件で）。

        バー単位 Sharpe はスケールが小さく、std_sr_trials も試行間分散のリアリスティック
        なスケール（実務的に 0.02 程度）で DSR が (0, 1) の中間で単調に動くことを確認。
        """
        kwargs = dict(
            n_trials=10,
            n_observations=1000,
            skew=0.0,
            kurtosis=3.0,
            mean_sr_trials=0.0,
            std_sr_trials=0.02,
        )
        vals = [
            deflated_sharpe_ratio(sharpe_ratio=sr, **kwargs)
            for sr in [0.01, 0.03, 0.05, 0.07, 0.10]
        ]
        for a, b in pairwise(vals):
            assert a < b
        # 端点は 0 と 1 の両側に分かれる（有意性グラデーション）
        assert vals[0] < 0.5 < vals[-1]

    def test_decreases_with_more_trials(self) -> None:
        """n_trials を増やすと DSR は低下（補正が厳しくなる）。"""
        kwargs = dict(
            sharpe_ratio=0.05,
            n_observations=1000,
            skew=0.0,
            kurtosis=3.0,
            mean_sr_trials=0.0,
            std_sr_trials=0.02,
        )
        vals = [deflated_sharpe_ratio(n_trials=n, **kwargs) for n in [2, 5, 10, 50, 100]]
        for a, b in pairwise(vals):
            assert a > b

    def test_matches_independent_calculation_n_trials_2(self) -> None:
        """独立計算値との照合（n_trials=2）。"""
        kwargs = dict(
            sharpe_ratio=0.05,
            n_trials=2,
            n_observations=1000,
            skew=0.0,
            kurtosis=3.0,
            mean_sr_trials=0.0,
            std_sr_trials=1.0,
        )
        expected = _reference_dsr(
            sr=0.05,
            n_trials=2,
            t_obs=1000,
            skew=0.0,
            kurt=3.0,
            mean_sr=0.0,
            std_sr=1.0,
        )
        actual = deflated_sharpe_ratio(**kwargs)
        assert actual == pytest.approx(expected, abs=1e-6)

    def test_matches_independent_calculation_n_trials_10(self) -> None:
        """独立計算値との照合（n_trials=10、q1 と q2 両方が効くケース）。"""
        kwargs = dict(
            sharpe_ratio=0.05,
            n_trials=10,
            n_observations=1000,
            skew=-0.3,
            kurtosis=4.5,
            mean_sr_trials=0.02,
            std_sr_trials=0.5,
        )
        expected = _reference_dsr(
            sr=0.05,
            n_trials=10,
            t_obs=1000,
            skew=-0.3,
            kurt=4.5,
            mean_sr=0.02,
            std_sr=0.5,
        )
        actual = deflated_sharpe_ratio(**kwargs)
        assert actual == pytest.approx(expected, abs=1e-6)

    def test_negative_skew_fat_tail_reduces_dsr(self) -> None:
        """negative skew + excess kurtosis で DSR が低下する方向性確認。

        分母補正項 ``1 - skew*SR + ((kurt-1)/4)*SR^2`` は skew<0, kurt>3 で
        増加し、同一 SR でも z 値が小さくなる → DSR 低下。
        """
        baseline = deflated_sharpe_ratio(
            sharpe_ratio=0.05,
            n_trials=10,
            n_observations=1000,
            skew=0.0,
            kurtosis=3.0,
            mean_sr_trials=0.0,
            std_sr_trials=0.02,
        )
        fat_tail = deflated_sharpe_ratio(
            sharpe_ratio=0.05,
            n_trials=10,
            n_observations=1000,
            skew=-1.0,
            kurtosis=9.0,
            mean_sr_trials=0.0,
            std_sr_trials=0.02,
        )
        assert fat_tail < baseline
        # 両方とも 0/1 の端点に張り付いていないこと（意味のある比較になっている）
        assert 0.0 < fat_tail < 1.0
        assert 0.0 < baseline < 1.0

    def test_raises_on_n_trials_below_2(self) -> None:
        with pytest.raises(ValueError, match="n_trials"):
            deflated_sharpe_ratio(
                sharpe_ratio=0.05,
                n_trials=1,
                n_observations=1000,
                skew=0.0,
                kurtosis=3.0,
                mean_sr_trials=0.0,
                std_sr_trials=1.0,
            )

    def test_raises_on_n_observations_below_2(self) -> None:
        with pytest.raises(ValueError, match="n_observations"):
            deflated_sharpe_ratio(
                sharpe_ratio=0.05,
                n_trials=10,
                n_observations=1,
                skew=0.0,
                kurtosis=3.0,
                mean_sr_trials=0.0,
                std_sr_trials=1.0,
            )

    @pytest.mark.parametrize("bad_std", [0.0, -0.1, -1.0])
    def test_raises_on_non_positive_std_sr_trials(self, bad_std: float) -> None:
        with pytest.raises(ValueError, match="std_sr_trials"):
            deflated_sharpe_ratio(
                sharpe_ratio=0.05,
                n_trials=10,
                n_observations=1000,
                skew=0.0,
                kurtosis=3.0,
                mean_sr_trials=0.0,
                std_sr_trials=bad_std,
            )

    @pytest.mark.parametrize(
        "name,value",
        [
            ("sharpe_ratio", float("nan")),
            ("sharpe_ratio", float("inf")),
            ("skew", float("nan")),
            ("kurtosis", float("inf")),
            ("mean_sr_trials", float("nan")),
            ("std_sr_trials", float("inf")),
        ],
    )
    def test_raises_on_non_finite_floats(self, name: str, value: float) -> None:
        kwargs = dict(
            sharpe_ratio=0.05,
            n_trials=10,
            n_observations=1000,
            skew=0.0,
            kurtosis=3.0,
            mean_sr_trials=0.0,
            std_sr_trials=1.0,
        )
        kwargs[name] = value
        with pytest.raises(ValueError, match=name):
            deflated_sharpe_ratio(**kwargs)

    def test_returns_probability_in_unit_interval(self) -> None:
        val = deflated_sharpe_ratio(
            sharpe_ratio=0.05,
            n_trials=10,
            n_observations=1000,
            skew=0.0,
            kurtosis=3.0,
            mean_sr_trials=0.0,
            std_sr_trials=1.0,
        )
        assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# fold_sign_ratio
# ---------------------------------------------------------------------------


class TestFoldSignRatio:
    def test_full_alternation(self) -> None:
        assert fold_sign_ratio([1.0, -1.0, 1.0, -1.0]) == pytest.approx(1.0)

    def test_all_same_sign(self) -> None:
        assert fold_sign_ratio([1.0, 1.0, 1.0]) == pytest.approx(0.0)
        assert fold_sign_ratio([-1.0, -1.0, -1.0]) == pytest.approx(0.0)

    def test_empty(self) -> None:
        assert fold_sign_ratio([]) == 0.0

    def test_single_element(self) -> None:
        assert fold_sign_ratio([1.0]) == 0.0

    def test_zero_between_reversal(self) -> None:
        # [+, 0, -] -> carry-forward で + と - の比較、1 回反転 / denom=2
        assert fold_sign_ratio([1.0, 0.0, -1.0]) == pytest.approx(0.5)

    def test_leading_zeros(self) -> None:
        # [0, 0, +] -> 0 反転（最初の非ゼロが + のみ）/ denom=2
        assert fold_sign_ratio([0.0, 0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_without_reversal(self) -> None:
        # [-, 0, 0, -] -> carry-forward で - と - の比較、0 反転 / denom=3
        assert fold_sign_ratio([-1.0, 0.0, 0.0, -1.0]) == pytest.approx(0.0)

    def test_partial_alternation(self) -> None:
        # [+, +, -] -> 1 反転 / 2
        assert fold_sign_ratio([1.0, 1.0, -1.0]) == pytest.approx(0.5)

    def test_small_magnitudes(self) -> None:
        # 符号だけ見るので magnitude は関係ない
        assert fold_sign_ratio([0.001, -0.002, 0.0005]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# block_bootstrap_sharpe_ci
# ---------------------------------------------------------------------------


class TestBlockBootstrapSharpeCi:
    @pytest.fixture
    def normal_returns(self) -> np.ndarray:
        # mu=0.0001, sigma=0.01, n=10000 の正規分布
        rng = np.random.default_rng(0)
        return rng.normal(loc=0.0001, scale=0.01, size=10000)

    def test_ci_contains_analytic_bar_sharpe(self, normal_returns: np.ndarray) -> None:
        """解析的 bar Sharpe (mu/sigma ≈ 0.01) が 95% CI に含まれる。"""
        lower, upper = block_bootstrap_sharpe_ci(
            normal_returns, block_size=20, n_bootstrap=1000, alpha=0.05, seed=42
        )
        analytic_sharpe = float(normal_returns.mean() / normal_returns.std(ddof=1))
        assert lower < upper
        assert lower <= analytic_sharpe <= upper

    def test_reproducible_with_seed(self, normal_returns: np.ndarray) -> None:
        a = block_bootstrap_sharpe_ci(
            normal_returns, block_size=20, n_bootstrap=200, alpha=0.05, seed=42
        )
        b = block_bootstrap_sharpe_ci(
            normal_returns, block_size=20, n_bootstrap=200, alpha=0.05, seed=42
        )
        assert a == b

    def test_different_seeds_differ(self, normal_returns: np.ndarray) -> None:
        a = block_bootstrap_sharpe_ci(
            normal_returns, block_size=20, n_bootstrap=200, alpha=0.05, seed=1
        )
        b = block_bootstrap_sharpe_ci(
            normal_returns, block_size=20, n_bootstrap=200, alpha=0.05, seed=2
        )
        assert a != b

    @pytest.mark.parametrize("block_size", [5, 20, 50])
    def test_block_size_variants(self, normal_returns: np.ndarray, block_size: int) -> None:
        lower, upper = block_bootstrap_sharpe_ci(
            normal_returns,
            block_size=block_size,
            n_bootstrap=200,
            alpha=0.05,
            seed=42,
        )
        assert lower < upper

    def test_raises_on_short_returns(self) -> None:
        with pytest.raises(ValueError, match="length"):
            block_bootstrap_sharpe_ci(
                np.array([1.0]), block_size=1, n_bootstrap=10, alpha=0.05, seed=42
            )

    def test_raises_on_block_size_gt_length(self) -> None:
        arr = np.random.default_rng(0).normal(0, 1, size=10)
        with pytest.raises(ValueError, match="block_size"):
            block_bootstrap_sharpe_ci(
                arr, block_size=20, n_bootstrap=10, alpha=0.05, seed=42
            )

    def test_raises_on_block_size_below_1(self) -> None:
        arr = np.random.default_rng(0).normal(0, 1, size=10)
        with pytest.raises(ValueError, match="block_size"):
            block_bootstrap_sharpe_ci(
                arr, block_size=0, n_bootstrap=10, alpha=0.05, seed=42
            )

    def test_raises_on_zero_variance(self) -> None:
        arr = np.full(100, 0.5)
        with pytest.raises(ValueError, match="zero variance"):
            block_bootstrap_sharpe_ci(
                arr, block_size=10, n_bootstrap=10, alpha=0.05, seed=42
            )

    def test_raises_on_non_finite_returns(self) -> None:
        arr = np.array([0.1, 0.2, float("nan"), 0.3, 0.4] * 10)
        with pytest.raises(ValueError, match="non-finite"):
            block_bootstrap_sharpe_ci(
                arr, block_size=5, n_bootstrap=10, alpha=0.05, seed=42
            )

    @pytest.mark.parametrize("bad_alpha", [0.0, 1.0, -0.1, 1.1])
    def test_raises_on_invalid_alpha(
        self, normal_returns: np.ndarray, bad_alpha: float
    ) -> None:
        with pytest.raises(ValueError, match="alpha"):
            block_bootstrap_sharpe_ci(
                normal_returns,
                block_size=20,
                n_bootstrap=10,
                alpha=bad_alpha,
                seed=42,
            )

    def test_raises_on_zero_n_bootstrap(self, normal_returns: np.ndarray) -> None:
        with pytest.raises(ValueError, match="n_bootstrap"):
            block_bootstrap_sharpe_ci(
                normal_returns,
                block_size=20,
                n_bootstrap=0,
                alpha=0.05,
                seed=42,
            )

    def test_raises_on_non_int_seed(self, normal_returns: np.ndarray) -> None:
        with pytest.raises(TypeError, match="seed"):
            block_bootstrap_sharpe_ci(
                normal_returns,
                block_size=20,
                n_bootstrap=10,
                alpha=0.05,
                seed="42",  # type: ignore[arg-type]
            )

    def test_seed_is_keyword_only(self, normal_returns: np.ndarray) -> None:
        # positional では渡せない
        with pytest.raises(TypeError):
            block_bootstrap_sharpe_ci(normal_returns, 20, 10, 0.05, 42)  # type: ignore[misc]
