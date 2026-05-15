"""equity 時系列の lossless numpy 表現 (T105)。

backtest engine の equity_curve を ``list[tuple[datetime, Decimal]]`` から
専用型 :class:`EquityCurve` (事前確保 numpy 配列 2 本: UTC epoch int64 +
scaled-int64 equity) へ置き換えるための型・変換ヘルパ。

設計意図: ``run_backtest`` が bar ごとに生成する ``(datetime, Decimal)``
タプル (1 genome の Stage B 評価で約 90 万要素、backtest 寿命中 retain) が
≤512 byte の小オブジェクトとして pymalloc アリーナを断片化させ、per-worker
RSS 肥大の発生源になっている。numpy 連続バッファ化で蓄積される実体を
小オブジェクト群から配列 2 本に変える。

精度契約:
- equity の **保存表現** は scaled-int64 で lossless (``encode_equity`` の
  fail-closed guard で保証)。
- ``decode_equity`` で Decimal を復元すれば、現行と完全に同一の Decimal
  演算経路で gate-feeding 指標 (max_drawdown_pct / calmar 等) を bit-exact
  に再現できる。
- 金額計算そのもの (約定・margin・手数料) は本モジュールの対象外。Decimal
  のまま不変。

@ref: devnotes/20260515-0827-backtest-decimal-churn/
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "SCALE_DECIMAL_PLACES",
    "EquityCurve",
    "EquityCurveBuilder",
    "EquityCurveError",
    "EquityScaleError",
    "decode_epoch_ns",
    "decode_equity",
    "encode_epoch_ns",
    "encode_equity",
    "validate_equity_scale_contract",
]


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class EquityCurveError(RuntimeError):
    """EquityCurve の不変条件違反 / 不正入力。"""


class EquityScaleError(EquityCurveError):
    """equity の scaled-int 表現が lossless でない (桁あふれ / overflow)。"""


# ---------------------------------------------------------------------------
# scaled-int 変換
# ---------------------------------------------------------------------------

#: equity の固定スケール小数桁数。
#:
#: 根拠: AF 設定 (holding_cost_per_day_bps=0) では equity = cash + unrealized、
#: 両者とも ``Decimal(units:int) * price_diff`` (price quote 桁数 <=5) の積の
#: 和であり除算経路を含まない → equity の小数桁数は price quote 桁数
#: (非 JPY <=5、JPY <=3) に bounded。SCALE=8 は実需 (<=5) に 3 桁マージン。
#: holding_cost_per_day_bps > 0 を有効化すると除算経路が生き桁数前提が崩れ
#: 得るため、``encode_equity`` / ``validate_equity_scale_contract`` が
#: fail-closed で検知する。
SCALE_DECIMAL_PLACES = 8
_SCALE_FACTOR = 10**SCALE_DECIMAL_PLACES  # Python int

#: int64 上限。
#:
#: overflow 上界: ``max_abs_equity_bound * 10^SCALE < 2^63 - 1``。
#: 2^63 - 1 ≈ 9.22e18 を 10^8 で割ると 9.22e10 → max_abs_equity_bound は
#: 約 922 億まで許容。equity は home currency 建てで
#: ``max_abs_equity_bound = initial_cash + Σ|unrealized|_max`` のオーダー
#: (AF 既定 initial_cash=1,000,000 / units=10,000) では 1e8 オーダーに収まり
#: 900x 以上マージンがある。実行時は ``encode_equity`` の guard が最後の防壁。
_INT64_MAX = 2**63 - 1


def encode_equity(value: Decimal) -> int:
    """equity Decimal → scaled int。lossless でなければ fail-closed。

    手順: Python ``int`` で生成 → 整数性検証 → overflow 検証 → 返却。
    ``np.int64`` への cast は呼び出し側 (配列代入時) で行う。

    Raises:
        EquityScaleError: scaled 値が整数でない (SCALE を超える小数桁) /
            int64 範囲外。silent な precision loss を構造的に排除する。
    """
    scaled = value * _SCALE_FACTOR  # Decimal
    scaled_int = int(scaled)
    if scaled_int != scaled:
        raise EquityScaleError(
            f"equity {value} not representable at SCALE={SCALE_DECIMAL_PLACES} "
            "(holding_cost>0 等で桁数前提が崩れた可能性)"
        )
    if not -_INT64_MAX <= scaled_int <= _INT64_MAX:
        raise EquityScaleError(
            f"equity {value} overflows int64 at SCALE={SCALE_DECIMAL_PLACES}"
        )
    return scaled_int


def decode_equity(scaled_int: int) -> Decimal:
    """scaled int → equity Decimal。``encode_equity`` の逆。lossless。

    ``_SCALE_FACTOR`` は 10 の冪のため ``Decimal(int) / int`` は有限小数で
    厳密。
    """
    return Decimal(int(scaled_int)) / _SCALE_FACTOR


def validate_equity_scale_contract(holding_cost_per_day_bps: Decimal) -> None:
    """SCALE 契約の前提が成立するか backtest 開始前に検証する。

    holding cost が有効だと equity に除算経路 (bps / 時間按分) が入り、equity の
    小数桁数が SCALE を超え得る。本関数は backtest 開始前に **warning で早期可視化**
    する (Codex 詳細 R1 [Warning] の「起動時 fail-closed」の意図を反映しつつ、
    holding cost は engine の正規機能であり hard fail は機能破壊になるため warning
    に留める)。

    **実際の lossless 保証は ``encode_equity`` の per-bar fail-closed guard が担う**
    — equity が SCALE を実際に超えた bar でのみ ``EquityScaleError`` を raise する。
    holding cost が有効でも equity が SCALE 内に収まる限り正常動作する。

    AF 現行設定 (``holding_cost_per_day_bps=0``) では本 warning は出ない。

    Args:
        holding_cost_per_day_bps: ``BacktestConfig.holding_cost_per_day_bps``。
    """
    if holding_cost_per_day_bps > 0:
        logger.warning(
            "equity_curve.holding_cost_enabled_scale_risk",
            holding_cost_per_day_bps=str(holding_cost_per_day_bps),
            scale_decimal_places=SCALE_DECIMAL_PLACES,
            note=(
                "holding cost 有効: equity の小数桁数が SCALE を超えると "
                "encode_equity が per-bar で EquityScaleError を raise する"
            ),
        )


# ---------------------------------------------------------------------------
# UTC epoch 変換 (整数 arithmetic のみ、float 経由禁止)
# ---------------------------------------------------------------------------

_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def encode_epoch_ns(dt: datetime) -> int:
    """UTC-aware datetime → epoch ナノ秒 int。

    ``timedelta`` の ``.days / .seconds / .microseconds`` は全て int のため
    float 丸めが入らない。

    Raises:
        EquityCurveError: naive datetime (tzinfo=None) の場合。
    """
    if dt.tzinfo is None:
        raise EquityCurveError("bar_time must be tz-aware (UTC)")
    delta = dt.astimezone(UTC) - _UNIX_EPOCH  # timedelta
    return (
        (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    ) * 1_000


def decode_epoch_ns(epoch_ns: int) -> datetime:
    """epoch ナノ秒 → UTC-aware datetime。

    ns 端数 (1000 の非倍数) は黙って切り捨てず reject し lossless 契約を守る。
    ``encode_epoch_ns`` は μs 精度入力から ns を生成するため常に 1000 倍数に
    なる。この reject は不正な epoch_ns が外部から混入した場合の防壁。

    Raises:
        EquityCurveError: epoch_ns が 1000 の倍数でない (sub-microsecond 成分)。
    """
    epoch_ns = int(epoch_ns)
    if epoch_ns % 1_000 != 0:
        raise EquityCurveError(
            f"epoch_ns {epoch_ns} has sub-microsecond component "
            "(lossless 契約違反)"
        )
    return _UNIX_EPOCH + timedelta(microseconds=epoch_ns // 1_000)


# ---------------------------------------------------------------------------
# EquityCurve 型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EquityCurve:
    """backtest の equity 時系列。numpy 連続バッファ 2 本で小オブジェクト
    churn を排除した lossless 表現。

    不変条件 (``__post_init__`` で検証・fail-closed):
      - 入力配列を owned copy (int64 / C-contiguous) に正規化する。
        ``setflags(write=False)`` だけでは外部から渡された view の base
        配列経由の書き換えを防げないため、copy 正規化してから read-only 化。
      - 2 配列が同長。
      - ``epoch_ns`` が strict 昇順 (重複・逆順を reject)。
      - 正規化後、両配列を ``setflags(write=False)`` で物理的に read-only 化。

    空 curve (len 0) は許容する。
    """

    epoch_ns: np.ndarray  # int64, UTC epoch ナノ秒, strict 昇順, read-only
    equity_scaled: np.ndarray  # int64, equity * 10^SCALE_DECIMAL_PLACES, read-only

    def __post_init__(self) -> None:
        # owned copy (int64 / C-contiguous) に正規化。copy は O(n) 1 回 /
        # backtest で、削減する小オブジェクト churn に対し無視できるコスト。
        for name in ("epoch_ns", "equity_scaled"):
            arr = getattr(self, name)
            normalized = np.array(arr, dtype=np.int64, order="C", copy=True)
            object.__setattr__(self, name, normalized)
        if len(self.epoch_ns) != len(self.equity_scaled):
            raise EquityCurveError(
                f"epoch_ns / equity_scaled length mismatch: "
                f"{len(self.epoch_ns)} != {len(self.equity_scaled)}"
            )
        # strict 昇順検証。np.diff は int64 極値で overflow し得るため要素比較。
        if len(self.epoch_ns) >= 2 and not bool(
            np.all(self.epoch_ns[1:] > self.epoch_ns[:-1])
        ):
            raise EquityCurveError("epoch_ns must be strictly increasing")
        # 物理的 read-only 化 (検証通過後、owned copy に対して)。
        self.epoch_ns.setflags(write=False)
        self.equity_scaled.setflags(write=False)

    # -- 構築 --------------------------------------------------------------

    @classmethod
    def empty(cls) -> EquityCurve:
        """空 curve (len 0)。``BacktestResult`` の default_factory 用。"""
        return cls(
            np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
        )

    @classmethod
    def from_decimal_points(
        cls, points: Sequence[tuple[datetime, Decimal]]
    ) -> EquityCurve:
        """``list[tuple[datetime, Decimal]]`` から構築する。

        旧表現からの移行・shadow test 用。
        """
        n = len(points)
        epoch = np.empty(n, dtype=np.int64)
        equity = np.empty(n, dtype=np.int64)
        for i, (ts, eq) in enumerate(points):
            epoch[i] = encode_epoch_ns(ts)
            equity[i] = encode_equity(eq)
        return cls(epoch, equity)

    # -- 基本 --------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.epoch_ns)

    @property
    def is_empty(self) -> bool:
        return len(self.epoch_ns) == 0

    # -- 復元 access (transient な Decimal / datetime を返す) --------------

    def equity_at(self, i: int) -> Decimal:
        """index i の equity を Decimal で復元する。"""
        return decode_equity(int(self.equity_scaled[i]))

    def time_at(self, i: int) -> datetime:
        """index i の bar_time を UTC-aware datetime で復元する。"""
        return decode_epoch_ns(int(self.epoch_ns[i]))

    def final_equity(self) -> Decimal:
        """末尾 equity を Decimal で返す。空 curve は ``Decimal(0)``。"""
        if self.is_empty:
            return Decimal(0)
        return self.equity_at(-1)

    def iter_decimal(self) -> Iterator[tuple[datetime, Decimal]]:
        """``(datetime, Decimal)`` ペアを時系列順に yield する (後方互換)。

        消費時に transient な Decimal / datetime を生成するが、``EquityCurve``
        自体には retain されない。
        """
        for epoch_ns, equity_scaled in zip(
            self.epoch_ns, self.equity_scaled, strict=True
        ):
            yield decode_epoch_ns(int(epoch_ns)), decode_equity(
                int(equity_scaled)
            )


class EquityCurveBuilder:
    """``run_backtest`` 用の事前確保 incremental builder。

    bar 数を起動時に確定できる前提 (``run_backtest`` は ``bars_list =
    list(bars)`` で確定)。``np.empty(n, int64)`` を 2 本確保し index 代入で
    埋める → 小オブジェクトを蓄積しない。
    """

    def __init__(self, n: int) -> None:
        if n < 0:
            raise EquityCurveError(f"EquityCurveBuilder size must be >= 0: {n}")
        self._epoch = np.empty(n, dtype=np.int64)
        self._equity = np.empty(n, dtype=np.int64)
        self._i = 0

    def append(self, bar_time: datetime, equity: Decimal) -> None:
        """1 bar 分の (時刻, equity) を追記する。"""
        if self._i >= len(self._epoch):
            raise EquityCurveError(
                f"EquityCurveBuilder overfill: append > capacity "
                f"({len(self._epoch)})"
            )
        self._epoch[self._i] = encode_epoch_ns(bar_time)
        self._equity[self._i] = encode_equity(equity)
        self._i += 1

    def build(self) -> EquityCurve:
        """``EquityCurve`` を構築する。

        Raises:
            EquityCurveError: ``append`` 回数が確保サイズに満たない (埋め残し)。
        """
        if self._i != len(self._epoch):
            raise EquityCurveError(
                f"EquityCurveBuilder underfill: filled {self._i} of "
                f"{len(self._epoch)}"
            )
        return EquityCurve(self._epoch, self._equity)
