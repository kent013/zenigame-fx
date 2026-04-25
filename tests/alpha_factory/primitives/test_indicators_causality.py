"""技術指標 look-ahead bias 契約テスト。

定義（causality contract）:
    任意の indicator f について、各 index i での出力 f(values)[i] は
    values[:i+1] のみに依存する。すなわち
        f(values[:i+1])[i] == f(values)[i]
    が任意の i（出力が non-NaN）で成立する。

このテストは _indicators.py の各関数を deterministic な合成系列に対して
prefix 切り詰め検証することで、実装が future bar を参照していないことを
形式的に保証する（AGENTS.md C2 / 監査 recommendation 3 に対応）。

新しい indicator を _indicators.py に追加した場合、本テストの SCALAR_FNS
/ MULTI_INPUT_FNS / TUPLE_RETURN_FNS いずれかに登録すること。
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

LENGTH = 80
TOL = 1e-9


def _series(seed: int, length: int = LENGTH) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.cumsum(rng.normal(0.0, 1.0, length)) + 100.0
    return base.astype(np.float64)


def _ohlc(seed: int, length: int = LENGTH) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    close = np.cumsum(rng.normal(0.0, 1.0, length)) + 100.0
    spread = np.abs(rng.normal(0.0, 0.5, length)) + 0.1
    high = close + spread
    low = close - spread
    return high.astype(np.float64), low.astype(np.float64), close.astype(np.float64)


def _assert_causal_array(full: np.ndarray, prefix_at_i: float, i: int, name: str) -> None:
    """full[i] と prefix(values[:i+1])[i] が一致することを検証。

    NaN 同士は一致扱い。片方のみ NaN なら fail。
    """
    full_v = full[i]
    if np.isnan(full_v) and np.isnan(prefix_at_i):
        return
    assert not (np.isnan(full_v) ^ np.isnan(prefix_at_i)), (
        f"{name}: NaN mismatch at i={i} (full={full_v}, prefix={prefix_at_i})"
    )
    assert abs(full_v - prefix_at_i) < TOL, (
        f"{name}: causality violation at i={i} "
        f"(full={full_v}, prefix={prefix_at_i}, diff={full_v - prefix_at_i})"
    )


# ---------------------------------------------------------------------------
# 単一 series 入力 / 単一 array 出力
# ---------------------------------------------------------------------------

SCALAR_FNS = [
    ("rolling_sum", lambda v: rolling_sum(v, 5)),
    ("rolling_mean", lambda v: rolling_mean(v, 5)),
    ("sma", lambda v: sma(v, 5)),
    ("rolling_std", lambda v: rolling_std(v, 5)),
    ("rolling_max", lambda v: rolling_max(v, 5)),
    ("rolling_min", lambda v: rolling_min(v, 5)),
    ("ema", lambda v: ema(v, 5)),
    ("rsi", lambda v: rsi(v, 7)),
    ("zscore", lambda v: zscore(v, 5)),
    ("log_returns_from_close", log_returns_from_close),
]


@pytest.mark.parametrize("name,fn", SCALAR_FNS, ids=[n for n, _ in SCALAR_FNS])
def test_scalar_indicator_is_causal(name: str, fn) -> None:
    values = _series(seed=42)
    full = fn(values)
    assert len(full) == len(values), f"{name}: length mismatch"
    for i in range(len(values)):
        prefix_full = fn(values[: i + 1])
        _assert_causal_array(full, prefix_full[i], i, name)


def test_realized_vol_is_causal() -> None:
    """realized_vol は log_ret 系列を入力に取るため別ハンドル。"""
    close = _series(seed=43)
    log_ret = log_returns_from_close(close)
    full = realized_vol(log_ret, 5)
    assert len(full) == len(log_ret)
    for i in range(len(log_ret)):
        prefix = realized_vol(log_ret[: i + 1], 5)
        _assert_causal_array(full, prefix[i], i, "realized_vol")


def test_rolling_corr_is_causal() -> None:
    x = _series(seed=44)
    y = _series(seed=45)
    full = rolling_corr(x, y, 5)
    for i in range(len(x)):
        prefix = rolling_corr(x[: i + 1], y[: i + 1], 5)
        _assert_causal_array(full, prefix[i], i, "rolling_corr")


# ---------------------------------------------------------------------------
# 複数 array を返す indicator (tuple)
# ---------------------------------------------------------------------------


def _check_tuple_causal(name: str, full_tuple, prefix_fn, length: int) -> None:
    for i in range(length):
        prefix_tuple = prefix_fn(i)
        for k, (full_arr, prefix_arr) in enumerate(zip(full_tuple, prefix_tuple)):
            _assert_causal_array(full_arr, prefix_arr[i], i, f"{name}[{k}]")


def test_bollinger_is_causal() -> None:
    values = _series(seed=46)
    full = bollinger(values, 5, 2.0)
    _check_tuple_causal(
        "bollinger",
        full,
        lambda i: bollinger(values[: i + 1], 5, 2.0),
        len(values),
    )


def test_macd_is_causal() -> None:
    values = _series(seed=47)
    full = macd(values, 4, 9, 3)
    _check_tuple_causal(
        "macd",
        full,
        lambda i: macd(values[: i + 1], 4, 9, 3),
        len(values),
    )


def test_donchian_is_causal() -> None:
    high, low, _ = _ohlc(seed=48)
    full = donchian(high, low, 5)
    _check_tuple_causal(
        "donchian",
        full,
        lambda i: donchian(high[: i + 1], low[: i + 1], 5),
        len(high),
    )


def test_stochastic_is_causal() -> None:
    high, low, close = _ohlc(seed=49)
    full = stochastic(high, low, close, 5, 3)
    _check_tuple_causal(
        "stochastic",
        full,
        lambda i: stochastic(
            high[: i + 1], low[: i + 1], close[: i + 1], 5, 3
        ),
        len(high),
    )


def test_true_range_is_causal() -> None:
    high, low, close = _ohlc(seed=50)
    full = true_range(high, low, close)
    for i in range(len(high)):
        prefix = true_range(high[: i + 1], low[: i + 1], close[: i + 1])
        _assert_causal_array(full, prefix[i], i, "true_range")


def test_atr_is_causal() -> None:
    high, low, close = _ohlc(seed=51)
    full = atr(high, low, close, 5)
    for i in range(len(high)):
        prefix = atr(high[: i + 1], low[: i + 1], close[: i + 1], 5)
        _assert_causal_array(full, prefix[i], i, "atr")


def test_adx_is_causal() -> None:
    high, low, close = _ohlc(seed=52)
    full = adx(high, low, close, 5)
    _check_tuple_causal(
        "adx",
        full,
        lambda i: adx(high[: i + 1], low[: i + 1], close[: i + 1], 5),
        len(high),
    )


# ---------------------------------------------------------------------------
# 反証検証（regression guard）: 故意に未来参照を入れた偽 indicator が
# このテスト基盤で fail することを確認する。
# ---------------------------------------------------------------------------


def _peek_one_ahead(values: np.ndarray) -> np.ndarray:
    """index i で values[i+1] を参照する未来漏洩 indicator (テスト用 sentinel)。"""
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < 2:
        return out
    out[:-1] = values[1:]
    return out


def test_causality_test_detects_leak() -> None:
    """故意 leak indicator が causality 検証で必ず fail することを確認。

    本テストが pass することで、SCALAR_FNS 上の causality 検証が
    実際に未来参照を捕捉できる感度を持つことを保証する。
    """
    values = _series(seed=99)
    full = _peek_one_ahead(values)
    leaked = False
    for i in range(len(values)):
        prefix = _peek_one_ahead(values[: i + 1])
        full_v = full[i]
        prefix_v = prefix[i]
        if np.isnan(full_v) and np.isnan(prefix_v):
            continue
        if np.isnan(full_v) ^ np.isnan(prefix_v):
            leaked = True
            break
        if abs(full_v - prefix_v) >= TOL:
            leaked = True
            break
    assert leaked, "sentinel leak indicator was not detected (test infrastructure broken)"
