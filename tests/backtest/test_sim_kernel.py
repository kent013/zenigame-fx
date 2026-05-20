"""_sim_kernel.simulate の直接ユニットテスト (T108)。

overflow sentinel (積/加算) が STATUS_OVERFLOW を返すこと、_add_overflows の境界を検証する。
broker simulation の振る舞い parity は test_sim_kernel_parity.py が担う。
"""

from __future__ import annotations

import numpy as np

from src.backtest._sim_kernel import (
    STATUS_OK,
    STATUS_OVERFLOW,
    _add_overflows,
    simulate,
)

_INT64_MAX = 9223372036854775807


def _empty_outs(n: int):
    return [np.empty(n, dtype=np.int64) for _ in range(8)] + [np.empty(n, dtype=np.int64)]


def _call(bid_c_val: int, ask_h_val: int, units: int = 10000, n: int = 3):
    """最小構成で simulate を呼ぶ (price は scaled-int)。"""
    bid = np.full(n, bid_c_val, dtype=np.int64)
    ask = np.full(n, ask_h_val, dtype=np.int64)
    hour = np.zeros(n, dtype=np.int8)
    is_eod = np.zeros(n, dtype=np.bool_)
    is_eod[-1] = True
    epoch = (np.arange(n, dtype=np.int64) + 1) * 60_000_000_000
    composite = np.zeros(n, dtype=np.float64)
    session_mask = np.zeros(24, dtype=np.bool_)
    outs = _empty_outs(n)
    return simulate(
        bid, ask, bid, bid,          # bid o/h/l/c
        ask, ask, ask, ask,          # ask o/h/l/c
        hour, is_eod, epoch,
        composite, session_mask,
        0.5, 0.2, 0, units, 3,
        100, 1, True, 10, 1,
        1_000_000 * 10**8, 1000, 0,
        1, 1,  # T110: spread_cost_num, spread_cost_den (1,1 = 不変)
        *outs,
    )


def test_add_overflows_boundary() -> None:
    assert _add_overflows(_INT64_MAX, 1) is True
    assert _add_overflows(_INT64_MAX - 1, 1) is False
    assert _add_overflows(-_INT64_MAX, -1) is True
    assert _add_overflows(0, 0) is False


def test_simulate_returns_ok_for_normal_prices() -> None:
    status, *_ = _call(bid_c_val=15_400_000, ask_h_val=15_401_000)  # ~154.0 scaled
    assert status == STATUS_OK


def test_simulate_overflow_on_huge_price() -> None:
    # max_abs_price > pnl_safe (= INT64_MAX // (units*scale_ratio)) で積 overflow を検知。
    status, *_ = _call(bid_c_val=15_400_000, ask_h_val=10**12)
    assert status == STATUS_OVERFLOW


def test_simulate_overflow_on_huge_units() -> None:
    # units * scale_ratio が int64 を超える → pnl_factor overflow ガード。
    status, *_ = _call(bid_c_val=15_400_000, ask_h_val=15_401_000, units=10**18)
    assert status == STATUS_OVERFLOW


def test_simulate_overflow_on_margin_rhs_factor() -> None:
    # maint_num(100) * pnl_factor(units*1000) が int64 を超える境界 → STATUS_OVERFLOW。
    # pnl_factor 自体のガード (units*1000 <= INT64_MAX) は通り、max_abs_price ガードも
    # 通す (価格を極小にする) ことで、margin_rhs ガード単独の発火を分離検証する。
    units = _INT64_MAX // (1000 * 100) + 1
    status, *_ = _call(bid_c_val=2, ask_h_val=2, units=units)  # 極小価格で max_abs_price ガード回避
    assert status == STATUS_OVERFLOW
