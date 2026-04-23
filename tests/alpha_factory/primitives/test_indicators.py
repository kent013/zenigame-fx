"""T011 技術指標ヘルパー単体テスト。

各ヘルパーを既知入力に対して期待値と比較する。tolerance = 1e-9。
"""

from __future__ import annotations

import numpy as np
import pytest

from src.alpha_factory.primitives._indicators import (
    adx,
    atr,
    bollinger,
    donchian,
    ema,
    log_returns_from_close,
    macd,
    realized_vol,
    rolling_corr,
    rolling_max,
    rolling_mean,
    rolling_min,
    rolling_std,
    rolling_sum,
    rsi,
    sma,
    stochastic,
    true_range,
    zscore,
)


class TestRollingSum:
    def test_matches_prefix_sum(self):
        v = np.arange(10, dtype=np.float64)
        out = rolling_sum(v, 3)
        # warmup 先頭 2 個は NaN
        assert np.isnan(out[0]) and np.isnan(out[1])
        # [2] = 0+1+2 = 3, [3] = 1+2+3 = 6, [9] = 7+8+9 = 24
        assert out[2] == pytest.approx(3.0)
        assert out[3] == pytest.approx(6.0)
        assert out[9] == pytest.approx(24.0)

    def test_shorter_than_window_all_nan(self):
        v = np.array([1.0, 2.0], dtype=np.float64)
        out = rolling_sum(v, 5)
        assert np.all(np.isnan(out))

    def test_negative_n_raises(self):
        with pytest.raises(ValueError):
            rolling_sum(np.arange(5.0), 0)


class TestRollingMeanStd:
    def test_rolling_mean_matches_manual(self):
        v = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        out = rolling_mean(v, 3)
        assert np.isnan(out[0]) and np.isnan(out[1])
        assert out[2] == pytest.approx(2.0)
        assert out[3] == pytest.approx(3.0)
        assert out[4] == pytest.approx(4.0)

    def test_rolling_std_matches_numpy_population(self):
        rng = np.random.default_rng(42)
        v = rng.normal(size=50)
        out = rolling_std(v, 10, ddof=0)
        for i in range(9, 50):
            expected = np.std(v[i - 9 : i + 1], ddof=0)
            assert out[i] == pytest.approx(expected, abs=1e-10)

    def test_sma_equals_rolling_mean(self):
        v = np.arange(20, dtype=np.float64)
        np.testing.assert_allclose(sma(v, 5), rolling_mean(v, 5), equal_nan=True)


class TestRollingMaxMin:
    def test_rolling_max_matches_naive(self):
        v = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
        out = rolling_max(v, 3)
        expected = [np.nan, np.nan, 4.0, 4.0, 5.0, 9.0, 9.0, 9.0]
        np.testing.assert_allclose(out, expected, equal_nan=True)

    def test_rolling_min_matches_naive(self):
        v = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
        out = rolling_min(v, 3)
        expected = [np.nan, np.nan, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0]
        np.testing.assert_allclose(out, expected, equal_nan=True)

    def test_rolling_max_large_random_matches_naive(self):
        rng = np.random.default_rng(7)
        v = rng.normal(size=200)
        n = 15
        out = rolling_max(v, n)
        for i in range(n - 1, len(v)):
            assert out[i] == pytest.approx(np.max(v[i - n + 1 : i + 1]))


class TestRollingCorr:
    def test_matches_numpy_corrcoef(self):
        rng = np.random.default_rng(2026)
        x = rng.normal(size=60)
        y = 0.5 * x + rng.normal(size=60) * 0.3
        out = rolling_corr(x, y, 20)
        for i in range(19, 60):
            expected = np.corrcoef(x[i - 19 : i + 1], y[i - 19 : i + 1])[0, 1]
            assert out[i] == pytest.approx(expected, abs=1e-9)

    def test_constant_series_returns_nan(self):
        x = np.ones(30)
        y = np.arange(30, dtype=np.float64)
        out = rolling_corr(x, y, 10)
        # x の分散 0 → corr 定義不能 → NaN
        assert np.all(np.isnan(out[9:]))

    def test_result_bounded_minus_one_plus_one(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=100)
        y = rng.normal(size=100)
        out = rolling_corr(x, y, 15)
        valid = out[~np.isnan(out)]
        assert np.all(valid >= -1.0)
        assert np.all(valid <= 1.0)


class TestEma:
    def test_seed_is_sma(self):
        v = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        out = ema(v, 3)
        # seed at idx 2: mean([1,2,3]) = 2
        assert out[2] == pytest.approx(2.0)

    def test_recurrence_matches_manual(self):
        v = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        n = 3
        alpha = 2.0 / (n + 1.0)
        out = ema(v, n)
        expected3 = alpha * 4.0 + (1 - alpha) * 2.0  # seed=2, v[3]=4
        expected4 = alpha * 5.0 + (1 - alpha) * expected3
        assert out[3] == pytest.approx(expected3)
        assert out[4] == pytest.approx(expected4)

    def test_warmup_is_nan(self):
        v = np.arange(10.0)
        out = ema(v, 5)
        assert np.all(np.isnan(out[:4]))
        assert np.all(np.isfinite(out[4:]))


class TestTrueRangeAtr:
    def test_tr_first_bar_is_hl_range(self):
        h = np.array([10.0, 11.0, 12.0])
        low = np.array([9.0, 9.5, 11.0])
        c = np.array([9.5, 10.5, 11.5])
        tr = true_range(h, low, c)
        assert tr[0] == pytest.approx(1.0)  # 10 - 9
        # TR[1] = max(1.5, |11-9.5|, |9.5-9.5|) = 1.5
        assert tr[1] == pytest.approx(1.5)

    def test_atr_constant_price_is_zero(self):
        h = np.array([1.0] * 20)
        low = np.array([1.0] * 20)
        c = np.array([1.0] * 20)
        a = atr(h, low, c, 5)
        assert np.all(np.isnan(a[:4]))
        assert np.all(a[4:] == pytest.approx(0.0))

    def test_atr_matches_wilder_manual(self):
        h = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        low = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        c = np.array([1.5, 2.5, 3.5, 4.5, 5.5, 6.5])
        tr = true_range(h, low, c)
        n = 3
        # seed = mean(tr[:3])
        seed = float(tr[:3].mean())
        a = atr(h, low, c, n)
        assert a[2] == pytest.approx(seed)
        # a[3] = (seed*(n-1) + tr[3]) / n
        a3 = (seed * (n - 1) + tr[3]) / n
        assert a[3] == pytest.approx(a3)


class TestRsi:
    def test_all_rising_is_100(self):
        v = np.arange(1, 30, dtype=np.float64)
        out = rsi(v, 14)
        # 上昇のみ → avg_down=0 → rsi=100
        valid = out[~np.isnan(out)]
        assert np.all(valid == pytest.approx(100.0))

    def test_all_falling_is_0(self):
        v = np.arange(30, 1, -1, dtype=np.float64)
        out = rsi(v, 14)
        valid = out[~np.isnan(out)]
        assert np.all(valid == pytest.approx(0.0))


class TestBollinger:
    def test_mid_equals_sma(self):
        v = np.arange(30.0)
        mid, _std, _upper, _lower = bollinger(v, 10, 2.0)
        np.testing.assert_allclose(mid, sma(v, 10), equal_nan=True)

    def test_bands_symmetric(self):
        rng = np.random.default_rng(3)
        v = rng.normal(size=50)
        mid, _std, upper, lower = bollinger(v, 10, 2.0)
        np.testing.assert_allclose(upper - mid, mid - lower, equal_nan=True)


class TestStochastic:
    def test_range_within_0_100(self):
        rng = np.random.default_rng(4)
        h = rng.normal(size=50) + 2
        low = rng.normal(size=50) - 2
        c = (h + low) / 2 + rng.normal(size=50) * 0.1
        # ensure high >= low
        h = np.maximum(h, low + 0.01)
        k, _d = stochastic(h, low, c, 10)
        valid_k = k[~np.isnan(k)]
        assert np.all(valid_k >= -1e-9)
        assert np.all(valid_k <= 100.0 + 1e-9)

    def test_constant_price_stoch(self):
        h = np.ones(20)
        low = np.ones(20)
        c = np.ones(20)
        k, _d = stochastic(h, low, c, 5)
        # denom = 0 → 0 を返す（高値=安値=close の特殊ケース、neutral として定義）
        valid_k = k[~np.isnan(k)]
        assert np.all(valid_k == pytest.approx(0.0))


class TestMacd:
    def test_macd_matches_ema_diff(self):
        v = np.arange(50.0)
        m, _s, _hist = macd(v, 12, 26, 9)
        ef = ema(v, 12)
        es = ema(v, 26)
        np.testing.assert_allclose(m, ef - es, equal_nan=True)


class TestDonchian:
    def test_mid_is_avg_of_hilo(self):
        rng = np.random.default_rng(5)
        h = rng.normal(size=30) + 3
        low = rng.normal(size=30) - 3
        h = np.maximum(h, low + 0.5)
        hi, lo, mid = donchian(h, low, 10)
        np.testing.assert_allclose(mid, (hi + lo) / 2.0, equal_nan=True)

    def test_donchian_brackets_data(self):
        v_h = np.array([5, 3, 7, 2, 9, 1, 8, 4, 6, 10.0])
        v_l = v_h - 1
        hi, lo, _mid = donchian(v_h, v_l, 5)
        # warmup OK
        assert hi[4] == 9.0  # max of [5,3,7,2,9]
        assert lo[4] == 1.0  # min of [4,2,6,1,8]


class TestAdx:
    def test_constant_price_adx_is_nan_or_zero(self):
        h = np.ones(30)
        low = np.ones(30)
        c = np.ones(30)
        adx_arr, _plus_di, _minus_di = adx(h, low, c, 14)
        # 価格変動なし → +DM=-DM=0、TR=0 → DI=0, DX=0 (TR=0 で DI=0 ガード), ADX=0
        valid = adx_arr[~np.isnan(adx_arr)]
        assert np.all(valid == pytest.approx(0.0))

    def test_adx_returns_three_arrays(self):
        rng = np.random.default_rng(6)
        c = np.cumsum(rng.normal(size=100)) + 100
        h = c + np.abs(rng.normal(size=100)) * 0.1
        low = c - np.abs(rng.normal(size=100)) * 0.1
        adx_arr, plus_di, minus_di = adx(h, low, c, 14)
        assert adx_arr.shape == c.shape
        assert plus_di.shape == c.shape
        assert minus_di.shape == c.shape


class TestRealizedVol:
    def test_sqrt_sum_sq(self):
        r = np.array([np.nan, 0.01, -0.02, 0.015, -0.01, 0.02, -0.015])
        rv = realized_vol(r, 5)
        # i=5 → r[1..5] square mean
        expected = np.sqrt((0.01**2 + 0.02**2 + 0.015**2 + 0.01**2 + 0.02**2) / 5)
        assert rv[5] == pytest.approx(expected, abs=1e-12)


class TestZscore:
    def test_mean_zero_std_one_on_constant_chunk(self):
        # 定数データ上で std=0 → NaN
        v = np.ones(20)
        out = zscore(v, 5)
        assert np.all(np.isnan(out[4:]))

    def test_linear_data(self):
        v = np.arange(20.0)
        out = zscore(v, 5)
        # 毎 window の std は同じ、(x - mean)/std の最終 idx 値は一致
        for i in range(4, 20):
            w = v[i - 4 : i + 1]
            expected = (v[i] - w.mean()) / w.std()
            assert out[i] == pytest.approx(expected, abs=1e-10)


class TestLogReturns:
    def test_first_is_nan(self):
        c = np.array([100.0, 101.0, 102.0])
        r = log_returns_from_close(c)
        assert np.isnan(r[0])
        assert r[1] == pytest.approx(np.log(101.0 / 100.0))
        assert r[2] == pytest.approx(np.log(102.0 / 101.0))

    def test_zero_close_returns_nan(self):
        c = np.array([1.0, 0.0, 1.0])
        r = log_returns_from_close(c)
        assert np.isnan(r[1])
        assert np.isnan(r[2])
