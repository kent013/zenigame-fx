"""PriceBar list の columnar scaled-int 表現 (T108)。

backtest hot loop を numba njit kernel (``_sim_kernel.simulate``) に畳むための
事前ベクトル化レイヤ。per-bar の Decimal オブジェクト走査・datetime tz 変換を
backtest 開始時 1 回の O(n) 変換に置き換える。

精度契約:
- price は ``PRICE_SCALE`` (=1e5) 倍した scaled-int64 で **lossless** に保持する
  (``_to_price_scaled`` の fail-closed guard で保証)。OANDA quote 桁数は非 JPY <=5 /
  JPY <=3 のため 1e5 で吸収できる。桁あふれは ``ColumnarScaleError`` を raise する。
- ``cash / equity / pnl`` は CASH_SCALE (=1e8、``equity_curve.SCALE_DECIMAL_PLACES``)
  で表現する (kernel 内部)。price→cash の換算は ``SCALE_RATIO`` (=1e3) 倍。
- datetime は ``encode_epoch_ns`` で int64 epoch ナノ秒に一括変換する
  (per-bar ``astimezone`` を排除)。

@ref: devnotes/20260520-1949-handoff-backtest-engine-numba/detailed-design.md §施策1
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from src.backtest.equity_curve import SCALE_DECIMAL_PLACES, encode_epoch_ns
from src.domain.price import PriceBar

__all__ = [
    "CASH_SCALE",
    "PRICE_SCALE",
    "SCALE_RATIO",
    "ColumnarBars",
    "ColumnarScaleError",
    "bars_to_columnar",
    "price_to_scaled",
    "scaled_to_price",
]

#: price の固定スケール。OANDA quote 桁数 (非 JPY <=5 / JPY <=3) を吸収する。
PRICE_SCALE = 10**5
#: cash / equity / pnl の固定スケール (equity_curve と共有、lossless 復元用)。
CASH_SCALE = 10**SCALE_DECIMAL_PLACES
#: price(1e5) → cash(1e8) 換算係数。
SCALE_RATIO = CASH_SCALE // PRICE_SCALE  # = 1000

_PRICE_SCALE_DEC = Decimal(PRICE_SCALE)


class ColumnarScaleError(ValueError):
    """price が ``PRICE_SCALE`` で lossless に整数化できない (桁あふれ)。"""


def price_to_scaled(value: Decimal) -> int:
    """price Decimal → scaled int。lossless でなければ fail-closed。

    Raises:
        ColumnarScaleError: ``value * PRICE_SCALE`` が整数でない (桁数超過)。
    """
    scaled = value * _PRICE_SCALE_DEC
    scaled_int = int(scaled)
    if scaled_int != scaled:
        raise ColumnarScaleError(
            f"price {value} not representable at PRICE_SCALE={PRICE_SCALE} "
            "(quote 桁数が想定 (<=5) を超えた可能性)"
        )
    return scaled_int


def scaled_to_price(scaled_int: int) -> Decimal:
    """scaled int → price Decimal。``price_to_scaled`` の逆 (lossless)。"""
    return Decimal(int(scaled_int)) / _PRICE_SCALE_DEC


@dataclass(frozen=True)
class ColumnarBars:
    """PriceBar list の SoA (Structure-of-Arrays) scaled-int 表現。

    全配列は長さ ``n_bars`` で read-only。price 系は int64 (PRICE_SCALE 単位)。
    kernel (``_sim_kernel.simulate``) に直接渡せる contiguous 配列。
    """

    bid_o: np.ndarray
    bid_h: np.ndarray
    bid_l: np.ndarray
    bid_c: np.ndarray
    ask_o: np.ndarray
    ask_h: np.ndarray
    ask_l: np.ndarray
    ask_c: np.ndarray
    hour: np.ndarray  # int8: bar_time.hour (UTC)
    is_eod: np.ndarray  # bool: 次 bar と UTC date 不一致 (末尾は True)
    epoch_ns: np.ndarray  # int64: UTC epoch ナノ秒 (equity curve / time_stop 用)

    def __len__(self) -> int:
        return len(self.bid_c)


def bars_to_columnar(bars: list[PriceBar]) -> ColumnarBars:
    """PriceBar list を ColumnarBars (scaled-int SoA) に変換する。

    1 パスで price scaled 化 / hour / is_eod / epoch_ns を構築し、per-bar の
    Decimal 走査・``astimezone`` をループ外の 1 回に集約する。

    ``is_eod[i]`` は ``engine.run_backtest`` の EOD 判定 (現行 L189-190) と同義:
    ``(i == n-1) or bars[i+1].bar_time.date() != bars[i].bar_time.date()``。

    Raises:
        ColumnarScaleError: いずれかの price が PRICE_SCALE で lossless 化できない。
    """
    n = len(bars)
    bid_o = np.empty(n, dtype=np.int64)
    bid_h = np.empty(n, dtype=np.int64)
    bid_l = np.empty(n, dtype=np.int64)
    bid_c = np.empty(n, dtype=np.int64)
    ask_o = np.empty(n, dtype=np.int64)
    ask_h = np.empty(n, dtype=np.int64)
    ask_l = np.empty(n, dtype=np.int64)
    ask_c = np.empty(n, dtype=np.int64)
    hour = np.empty(n, dtype=np.int8)
    is_eod = np.zeros(n, dtype=np.bool_)
    epoch_ns = np.empty(n, dtype=np.int64)

    for i, bar in enumerate(bars):
        bid = bar.bid
        ask = bar.ask
        bid_o[i] = price_to_scaled(bid.open)
        bid_h[i] = price_to_scaled(bid.high)
        bid_l[i] = price_to_scaled(bid.low)
        bid_c[i] = price_to_scaled(bid.close)
        ask_o[i] = price_to_scaled(ask.open)
        ask_h[i] = price_to_scaled(ask.high)
        ask_l[i] = price_to_scaled(ask.low)
        ask_c[i] = price_to_scaled(ask.close)
        bt = bar.bar_time
        hour[i] = bt.hour
        epoch_ns[i] = encode_epoch_ns(bt)
        if i == n - 1 or bars[i + 1].bar_time.date() != bt.date():
            is_eod[i] = True

    for arr in (bid_o, bid_h, bid_l, bid_c, ask_o, ask_h, ask_l, ask_c,
                hour, is_eod, epoch_ns):
        arr.setflags(write=False)

    return ColumnarBars(
        bid_o=bid_o, bid_h=bid_h, bid_l=bid_l, bid_c=bid_c,
        ask_o=ask_o, ask_h=ask_h, ask_l=ask_l, ask_c=ask_c,
        hour=hour, is_eod=is_eod, epoch_ns=epoch_ns,
    )
