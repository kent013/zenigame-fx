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


# ---------------------------------------------------------------------------
# T088: Numba JIT 化 parity tests (rolling_max / rolling_min / _wilder_smooth)
# ---------------------------------------------------------------------------


def _rolling_max_oracle(values: np.ndarray, n: int) -> np.ndarray:
    """test 内 self-contained oracle: 現行 deque 版 rolling_max と同じロジック。

    T088 の Numba JIT 化版が numerically identical であることを保証するため、
    test 内で独立に同じ comparator (`<=` で右から drop) を再現する。
    """
    from collections import deque

    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    dq: deque[int] = deque()
    for i in range(length):
        while dq and dq[0] <= i - n:
            dq.popleft()
        while dq and values[dq[-1]] <= values[i]:
            dq.pop()
        dq.append(i)
        if i >= n - 1:
            out[i] = values[dq[0]]
    return out


def _rolling_min_oracle(values: np.ndarray, n: int) -> np.ndarray:
    """test 内 self-contained oracle: 現行 deque 版 rolling_min と同じロジック。"""
    from collections import deque

    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    dq: deque[int] = deque()
    for i in range(length):
        while dq and dq[0] <= i - n:
            dq.popleft()
        while dq and values[dq[-1]] >= values[i]:
            dq.pop()
        dq.append(i)
        if i >= n - 1:
            out[i] = values[dq[0]]
    return out


def _wilder_smooth_oracle(values: np.ndarray, n: int) -> np.ndarray:
    """test 内 self-contained oracle: 現行 plain Python 版 _wilder_smooth と同じロジック。

    NaN 契約 (seed = nanmean if NaN含む else mean、 途中 NaN は前値維持) を再現。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    seed = (
        float(np.nanmean(values[:n]))
        if np.any(np.isnan(values[:n]))
        else float(values[:n].mean())
    )
    # 現行 plain Python 版は早期 return しない: seed が NaN/inf いずれでも
    # out[n-1]=seed → recurrence で伝播。 NaN→all NaN, inf→inf 伝播。
    out[n - 1] = seed
    prev = seed
    for i in range(n, length):
        v = values[i]
        if np.isnan(v):
            out[i] = prev
            continue
        cur = (prev * (n - 1) + v) / n
        out[i] = cur
        prev = cur
    return out


def _assert_arrays_identical_with_nan(
    actual: np.ndarray, expected: np.ndarray
) -> None:
    """NaN 同位置一致 + 有限値は厳密一致 (assert_array_equal) を確認。"""
    assert actual.shape == expected.shape
    nan_mask_actual = np.isnan(actual)
    nan_mask_expected = np.isnan(expected)
    np.testing.assert_array_equal(nan_mask_actual, nan_mask_expected)
    finite = ~nan_mask_actual
    np.testing.assert_array_equal(actual[finite], expected[finite])


class TestRollingMaxNumbaParity:
    """T088: rolling_max Numba JIT 化版が現行 deque 実装と numerically identical。"""

    def test_normal_input(self):
        rng = np.random.default_rng(42)
        v = rng.normal(size=200)
        for n in (3, 5, 14, 50):
            actual = rolling_max(v, n)
            expected = _rolling_max_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_n_equals_one(self):
        v = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
        actual = rolling_max(v, 1)
        expected = _rolling_max_oracle(v, 1)
        _assert_arrays_identical_with_nan(actual, expected)
        # n=1 では各点が自分自身
        np.testing.assert_array_equal(actual, v)

    def test_repeated_values(self):
        # 重複値が連続: comparator strict (`<=` で drop = 等値も drop) 確認
        v = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 1.0, 3.0, 3.0, 3.0])
        for n in (1, 2, 3, 5):
            actual = rolling_max(v, n)
            expected = _rolling_max_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_length_less_than_n(self):
        v = np.array([1.0, 2.0])
        actual = rolling_max(v, 5)
        expected = _rolling_max_oracle(v, 5)
        _assert_arrays_identical_with_nan(actual, expected)
        # length < n でも warmup NaN 条件で出力すべて NaN
        assert np.all(np.isnan(actual))


class TestRollingMinNumbaParity:
    """T088: rolling_min Numba JIT 化版が現行 deque 実装と numerically identical。"""

    def test_normal_input(self):
        rng = np.random.default_rng(7)
        v = rng.normal(size=200)
        for n in (3, 5, 14, 50):
            actual = rolling_min(v, n)
            expected = _rolling_min_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_n_equals_one(self):
        v = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
        actual = rolling_min(v, 1)
        expected = _rolling_min_oracle(v, 1)
        _assert_arrays_identical_with_nan(actual, expected)
        np.testing.assert_array_equal(actual, v)

    def test_repeated_values(self):
        v = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 1.0, 3.0, 3.0, 3.0])
        for n in (1, 2, 3, 5):
            actual = rolling_min(v, n)
            expected = _rolling_min_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_length_less_than_n(self):
        v = np.array([1.0, 2.0])
        actual = rolling_min(v, 5)
        expected = _rolling_min_oracle(v, 5)
        _assert_arrays_identical_with_nan(actual, expected)
        assert np.all(np.isnan(actual))


class TestWilderSmoothNumbaParity:
    """T088: _wilder_smooth Numba JIT 化版が現行 plain Python 実装と numerically identical。

    seed 計算は Python 側維持 (nanmean/mean)、 recurrence loop のみ JIT 化。
    NaN 同位置一致 + 有限値は assert_array_equal で bit-identical 確認。
    """

    def test_all_finite(self):
        # case (a): 全 finite 入力
        from src.alpha_factory.primitives._indicators import _wilder_smooth

        rng = np.random.default_rng(123)
        v = rng.normal(size=200)
        for n in (3, 5, 14, 30):
            actual = _wilder_smooth(v, n)
            expected = _wilder_smooth_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_leading_nan_in_seed(self):
        # case (b): 先頭 n 個に NaN 1 個 (seed が nanmean で計算される)
        from src.alpha_factory.primitives._indicators import _wilder_smooth

        v = np.array([1.0, np.nan, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        for n in (3, 5):
            actual = _wilder_smooth(v, n)
            expected = _wilder_smooth_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_mid_nan(self):
        # case (c): 途中に NaN 1 個 (前値維持の semantics 確認)
        from src.alpha_factory.primitives._indicators import _wilder_smooth

        v = np.array([1.0, 2.0, 3.0, 4.0, np.nan, 6.0, 7.0, 8.0, 9.0, 10.0])
        for n in (3, 5):
            actual = _wilder_smooth(v, n)
            expected = _wilder_smooth_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)

    def test_all_nan(self):
        # case (d): 全 NaN (seed = NaN → 全区間 NaN)
        from src.alpha_factory.primitives._indicators import _wilder_smooth

        v = np.full(20, np.nan, dtype=np.float64)
        for n in (3, 5, 10):
            actual = _wilder_smooth(v, n)
            expected = _wilder_smooth_oracle(v, n)
            _assert_arrays_identical_with_nan(actual, expected)
            assert np.all(np.isnan(actual))

    def test_length_less_than_n(self):
        # case (e): length < n
        from src.alpha_factory.primitives._indicators import _wilder_smooth

        v = np.array([1.0, 2.0, 3.0])
        actual = _wilder_smooth(v, 10)
        expected = _wilder_smooth_oracle(v, 10)
        _assert_arrays_identical_with_nan(actual, expected)
        assert np.all(np.isnan(actual))

    def test_seed_window_contains_inf(self):
        # case (f): 先頭 n 個に +inf / -inf を含むケース。 現行は seed=inf で
        # recurrence に流して inf を伝播させる。 Numba 化版もこれを破ってはならない
        # (Codex Round 1 Critical 対応: seed=inf で early return しないこと)。
        from src.alpha_factory.primitives._indicators import _wilder_smooth

        for inf_val in (np.inf, -np.inf):
            v = np.array(
                [1.0, inf_val, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
            )
            for n in (3, 5):
                actual = _wilder_smooth(v, n)
                expected = _wilder_smooth_oracle(v, n)
                _assert_arrays_identical_with_nan(actual, expected)


class TestAdxViaWilderSmoothNumbaParity:
    """T088: adx() 全体が _wilder_smooth Numba 化後も現行と numerically identical。"""

    def test_adx_atr_parity_with_oracle_wilder(self):
        """adx() の出力 (adx, +DI, -DI) が、 _wilder_smooth oracle 版で計算した
        参照実装と完全一致することを確認。 _wilder_smooth は adx 内の atr/+DI/-DI
        計算経路で 3 回呼ばれる。
        """
        rng = np.random.default_rng(2026)
        size = 150
        # OHLC 系列を擬似生成
        close = 100.0 + np.cumsum(rng.normal(scale=0.5, size=size))
        high = close + np.abs(rng.normal(scale=0.3, size=size))
        low = close - np.abs(rng.normal(scale=0.3, size=size))

        n = 14
        adx_actual, plus_di_actual, minus_di_actual = adx(high, low, close, n)

        # 参照実装: adx() 内のロジックを oracle wilder で再現
        from src.alpha_factory.primitives._indicators import true_range

        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]
        plus_dm = np.where(
            (up_move > down_move) & (up_move > 0), up_move, 0.0
        )
        minus_dm = np.where(
            (down_move > up_move) & (down_move > 0), down_move, 0.0
        )
        plus_dm_full = np.concatenate([[0.0], plus_dm])
        minus_dm_full = np.concatenate([[0.0], minus_dm])
        tr = true_range(high, low, close)
        sm_tr = _wilder_smooth_oracle(tr, n)
        sm_plus = _wilder_smooth_oracle(plus_dm_full, n)
        sm_minus = _wilder_smooth_oracle(minus_dm_full, n)
        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di_expected = np.where(
                sm_tr > 0, 100.0 * sm_plus / sm_tr, 0.0
            )
            minus_di_expected = np.where(
                sm_tr > 0, 100.0 * sm_minus / sm_tr, 0.0
            )
        plus_di_expected = np.where(
            np.isnan(sm_tr), np.nan, plus_di_expected
        )
        minus_di_expected = np.where(
            np.isnan(sm_tr), np.nan, minus_di_expected
        )
        di_sum = plus_di_expected + minus_di_expected
        with np.errstate(divide="ignore", invalid="ignore"):
            dx = np.where(
                di_sum > 0,
                100.0 * np.abs(plus_di_expected - minus_di_expected) / di_sum,
                0.0,
            )
        dx = np.where(
            np.isnan(plus_di_expected) | np.isnan(minus_di_expected),
            np.nan,
            dx,
        )
        adx_expected = _wilder_smooth_oracle(dx, n)

        _assert_arrays_identical_with_nan(adx_actual, adx_expected)
        _assert_arrays_identical_with_nan(plus_di_actual, plus_di_expected)
        _assert_arrays_identical_with_nan(minus_di_actual, minus_di_expected)
