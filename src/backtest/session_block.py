"""SessionBlock 集計と spread stress (T070 cascade port v2 Phase 2 配線).

synthesis § 4.4 / § 6.2 / § 6.3 / § 18.2 T913 に厳密準拠する 8h covering
partition による session bucket 集計層。 概念設計 §3.4.0 の会計契約 SSOT に
基づき、 Trade.spread_cost / Trade.holding_cost を block 集計する.

責務分離:
    - 本 module の `BLOCK_BUCKET_RANGES_UTC` (8h × 3 covering partition) と
      `src/alpha_factory/primitives/_indicators.py:51-55` の
      `_SESSION_RANGES_UTC` (9h overlap windows、 indicator 用) は **別責務**
      で並列管理する。 命名で独立性を担保 (= F18 防御).

会計契約 SSOT (概念設計 §3.4.0):
    - Trade.pnl は既存挙動: holding_cost 控除済 net pnl (raw_pnl - cost_accum).
    - Trade.holding_cost は `_holding_cost_by_position[pos.id]` の転記、 cash
      操作なし (= 監査用、 既存挙動を破壊しない).
    - Trade.spread_cost は entry/exit spread 推定値、 cash 操作なし、 既存
      Trade.pnl にも未反映 (= 監査・stress 用記録).
    - 集計式:
        pnl_net          = sum(t.pnl - t.spread_cost)
        pnl_before_costs = sum(t.pnl + t.holding_cost)
        spread_cost_total = sum(t.spread_cost)
        holding_cost_total = sum(t.holding_cost)
    - 不変条件: pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total

T072 (DST/holiday boundary contract) で BLOCK_BUCKET_RANGES_UTC への DST 例外
は別 layer で扱う。 T070 SSOT は UTC 単純基準で固定。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal

from src.broker.orders import Trade
from src.domain.price import PriceBar

__all__ = [
    "BLOCK_BUCKET_RANGES_UTC",
    "SessionBlock",
    "SessionBlockBucket",
    "aggregate_session_blocks",
    "apply_spread_stress",
    "compute_bucket_for_bar",
    "compute_bucket_for_trade",
]


SessionBlockBucket = Literal["tokyo", "london", "ny"]

# 8h covering partition (synthesis § 4.4 SSOT). primitives の 9h overlap
# windows (`src/alpha_factory/primitives/_indicators.py:51-55` の
# `_SESSION_RANGES_UTC`) とは別責務、 並列管理.
BLOCK_BUCKET_RANGES_UTC: Final[dict[SessionBlockBucket, tuple[int, int]]] = {
    "tokyo": (0, 8),    # [0, 8) UTC hour
    "london": (8, 16),  # [8, 16)
    "ny": (16, 24),     # [16, 24)
}

# SSOT 駆動 (概念設計 §3.1 / 詳細設計 §3.1)
_BUCKETS: Final[tuple[SessionBlockBucket, ...]] = tuple(BLOCK_BUCKET_RANGES_UTC.keys())
_M1_EXPECTED_BAR_COUNT: Final[int] = 480  # 8h × 60min


@dataclass(frozen=True)
class SessionBlock:
    """1 営業日 (UTC date) × 1 bucket = 1 block (synthesis § 4.4 SSOT).

    SSOT: 概念設計 §3.4 / §4.3.

    Attributes:
        business_date: UTC date (date object). T072 で営業日定義の精緻化予定.
        bucket: tokyo / london / ny.
        bar_count: block 内 bar 数 (M1 想定で 8h = 480 bars).
        trade_count: block 内 trade 数 (= trade.exit_time が本 block に属する).
        pnl_net: block 内 trade の全 cost 控除済 net 合計
            (= sum(t.pnl - t.spread_cost), holding は既に Trade.pnl に net、
            spread は block 集計時に別途控除. §3.4.0 SSOT 参照).
        pnl_before_costs: pnl_net + spread_cost_total + holding_cost_total
            (= 控除前 gross. = sum(t.pnl + t.holding_cost) と同値).
        spread_cost_total: block 内 trade の spread_cost 合計.
        holding_cost_total: block 内 trade の holding_cost 合計.

    不変条件 (`__post_init__` で検証):
        bar_count >= 0
        trade_count >= 0
        spread_cost_total >= 0
        holding_cost_total >= 0
        pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total
    """

    business_date: date
    bucket: SessionBlockBucket
    bar_count: int
    trade_count: int
    pnl_net: Decimal
    pnl_before_costs: Decimal
    spread_cost_total: Decimal
    holding_cost_total: Decimal

    def __post_init__(self) -> None:
        if self.bar_count < 0:
            raise ValueError(f"bar_count must be >= 0, got {self.bar_count}")
        if self.trade_count < 0:
            raise ValueError(f"trade_count must be >= 0, got {self.trade_count}")
        if self.spread_cost_total < 0:
            raise ValueError(
                f"spread_cost_total must be >= 0, got {self.spread_cost_total}"
            )
        if self.holding_cost_total < 0:
            raise ValueError(
                f"holding_cost_total must be >= 0, got {self.holding_cost_total}"
            )
        # F6 invariant: pnl_before_costs == pnl_net + spread + holding
        expected = self.pnl_net + self.spread_cost_total + self.holding_cost_total
        if self.pnl_before_costs != expected:
            raise ValueError(
                f"pnl_before_costs ({self.pnl_before_costs}) != "
                f"pnl_net + spread_cost_total + holding_cost_total ({expected})"
            )

    @property
    def is_empty_trade_block(self) -> bool:
        """trade_count == 0 (= synthesis § 6.3 0.5 neutral 対象).

        Round 1 [S1] 反映: T061 / T072 が neutral / boundary を機械判定.
        """
        return self.trade_count == 0

    @property
    def is_partial_bar_block(self) -> bool:
        """bar_count < 480 (= 末日・週末・holiday で 8h 不足).

        T072 で正確な期待 bar_count を計算する場合は本 property を上書き予定.
        T070 SSOT は M1 前提で `expected_bar_count = 480`.
        """
        return self.bar_count < _M1_EXPECTED_BAR_COUNT


def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から SessionBlockBucket を決定論的に割当.

    SSOT: 概念設計 §5.1. BLOCK_BUCKET_RANGES_UTC 駆動 (= 8 / 16 を直書きせず、
    単一 SSOT を参照、 Round 1 [C1] 反映).

    Args:
        bar_time: timezone-aware UTC datetime.

    Returns:
        SessionBlockBucket.

    Raises:
        ValueError: bar_time.tzinfo is None / 非 UTC offset.
        RuntimeError: BLOCK_BUCKET_RANGES_UTC が 24h covering を満たさない場合
            (= const 改変に対する defense-in-depth、 通常発生しない).
    """
    if bar_time.tzinfo is None:
        raise ValueError(
            f"bar_time must be timezone-aware (UTC), got naive: {bar_time}"
        )
    offset = bar_time.utcoffset()
    if offset != timedelta(0):
        raise ValueError(
            f"bar_time must be UTC offset, got offset={offset}: {bar_time}"
        )
    hour = bar_time.hour  # 0-23
    for bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
        if start <= hour < end:
            return bucket
    raise RuntimeError(
        f"hour {hour} not covered by BLOCK_BUCKET_RANGES_UTC "
        f"(= partition contract violation): {BLOCK_BUCKET_RANGES_UTC}"
    )


def compute_bucket_for_trade(trade: Trade) -> SessionBlockBucket:
    """trade 帰属 bucket を決定論的に算出 (= trade.exit_time 基準).

    SSOT: 概念設計 §5.1 / §3.4.1 (全 cost を exit bucket 一括帰属).

    Args:
        trade: Trade dataclass.

    Returns:
        SessionBlockBucket (= compute_bucket_for_bar(trade.exit_time) と同義).
    """
    return compute_bucket_for_bar(trade.exit_time)


def aggregate_session_blocks(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
) -> tuple[SessionBlock, ...]:
    """bars と trades から SessionBlock 配列を構築する (pure function).

    SSOT: 概念設計 §3.4.0 / §5.2.

    集計式 (§3.4.0 SSOT):
        pnl_net = sum(t.pnl - t.spread_cost for t in trades_in_block)
        pnl_before_costs = sum(t.pnl + t.holding_cost for t in trades_in_block)
        spread_cost_total = sum(t.spread_cost for t in trades_in_block)
        holding_cost_total = sum(t.holding_cost for t in trades_in_block)

    date universe (Round 1 [W1] SSOT):
        bars が触れた UTC date set ∪ trades.exit_time が触れた UTC date set
        × 3 bucket. empty block (trade_count=0 / bar_count=0) も含む.

    Args:
        bars: backtest 期間中の全 bar (時系列順、 UTC tz-aware).
        trades: backtest で生成された全 trade.

    Returns:
        SessionBlock の tuple. (date, bucket) で sort.

    Raises:
        ValueError: bar_time / trade.exit_time が naive / 非 UTC.
    """
    # 1. bars を (date, bucket) でグループ化、 bar_count を集計
    bar_count_map: dict[tuple[date, SessionBlockBucket], int] = {}
    date_set: set[date] = set()
    for bar in bars:
        bucket = compute_bucket_for_bar(bar.bar_time)
        d = bar.bar_time.date()
        date_set.add(d)
        key = (d, bucket)
        bar_count_map[key] = bar_count_map.get(key, 0) + 1

    # 2. trades を (date, bucket) でグループ化
    trade_groups: dict[tuple[date, SessionBlockBucket], list[Trade]] = {}
    for trade in trades:
        bucket = compute_bucket_for_trade(trade)
        d = trade.exit_time.date()
        date_set.add(d)  # trade exit_time が bars 範囲外でも include
        key = (d, bucket)
        trade_groups.setdefault(key, []).append(trade)

    # 3. date universe = bars + trades が触れた全 UTC date × 3 bucket
    blocks: list[SessionBlock] = []
    for d in sorted(date_set):
        for bucket in _BUCKETS:
            key = (d, bucket)
            bar_count = bar_count_map.get(key, 0)
            block_trades = trade_groups.get(key, [])
            trade_count = len(block_trades)

            # §3.4.0 SSOT 集計式
            pnl_net = sum(
                (t.pnl - t.spread_cost for t in block_trades),
                start=Decimal(0),
            )
            pnl_before_costs = sum(
                (t.pnl + t.holding_cost for t in block_trades),
                start=Decimal(0),
            )
            spread_cost_total = sum(
                (t.spread_cost for t in block_trades),
                start=Decimal(0),
            )
            holding_cost_total = sum(
                (t.holding_cost for t in block_trades),
                start=Decimal(0),
            )

            blocks.append(
                SessionBlock(
                    business_date=d,
                    bucket=bucket,
                    bar_count=bar_count,
                    trade_count=trade_count,
                    pnl_net=pnl_net,
                    pnl_before_costs=pnl_before_costs,
                    spread_cost_total=spread_cost_total,
                    holding_cost_total=holding_cost_total,
                )
            )

    return tuple(blocks)


def apply_spread_stress(
    trades: Sequence[Trade],
    multiplier: Decimal,
) -> tuple[Trade, ...]:
    """各 trade の spread_cost を multiplier 倍にして pnl を再計算した tuple を返す.

    SSOT: 概念設計 §5.3 / §3.4.0. T064 で `NotImplementedError` raise していた
    skeleton を T070 で正式実装に置換 (Phase 2 で stage_bc_evaluator が
    本関数を import).

    Stress 適用式 (= 既存 broker は spread を pnl 控除していないため、 stress
    倍率による余計分のみを pnl から控除する):

        delta_spread = trade.spread_cost * (multiplier - Decimal(1))
        new_pnl = trade.pnl - delta_spread
        new_spread_cost = trade.spread_cost * multiplier
        new_holding_cost = trade.holding_cost  # 不変 (stress は spread 専用)

    multiplier=1 で no-op (delta=0、 new_pnl=trade.pnl,
    new_spread_cost=trade.spread_cost).

    ### 契約境界 (Round 1 [C2] / [S1] 反映、 Trade(normal) vs Trade(stressed) 分離)

    **Trade(normal)** (= 通常 broker 出力 / aggregate_session_blocks 入力):
        invariant: `Trade.pnl + Trade.holding_cost == raw_pnl` (price-diff pnl).

    **Trade(stressed)** (= 本関数の出力):
        invariant: `Trade.pnl + Trade.holding_cost == raw_pnl - delta_spread`
        (= 元 raw_pnl から余計 spread を控除した擬似 pnl).
        F13 invariant は **適用しない** (= stress 済 trade は通常会計と別レイヤー).
        下流 (T064 stress evaluator) は「stress 済 trade は集計・SR 計算用、
        broker.cash には反映されない」 を契約として扱う.

    aggregate_session_blocks は Trade(normal) を入力前提 (= caller が stress 済
    trade を渡した場合の SessionBlock invariant 保証は別途 caller 責務).

    Args:
        trades: 元 Trade(normal) sequence.
        multiplier: spread cost 倍率 (>= 1.0、 finite).

    Returns:
        新 Trade(stressed) tuple (元 tuple は不変、 frozen dataclass).

    Raises:
        ValueError: multiplier < 1.0 / NaN / Infinite.
    """
    if not multiplier.is_finite():
        raise ValueError(f"multiplier must be finite, got {multiplier}")
    if multiplier < Decimal(1):
        raise ValueError(f"multiplier must be >= 1.0, got {multiplier}")

    delta_factor = multiplier - Decimal(1)
    return tuple(
        replace(
            t,
            pnl=t.pnl - t.spread_cost * delta_factor,
            spread_cost=t.spread_cost * multiplier,
        )
        for t in trades
    )
