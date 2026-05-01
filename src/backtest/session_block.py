"""SessionBlock 集計と spread stress (T070 + T072 cascade port v2 Phase 2 配線).

synthesis § 4.4 / § 6.2 / § 6.3 / § 18.2 T913 に厳密準拠する 8h covering
partition による session bucket 集計層。 概念設計 §3.4.0 の会計契約 SSOT に
基づき、 Trade.spread_cost / Trade.holding_cost を block 集計する.

T072 (= DST/holiday boundary contract) で:
    - SessionBlock に open_minutes / granularity_seconds / observability_flags
      の 3 field を追加 (= primary key、 詳細設計 § 3.7).
    - is_partial_bar_block / expected_bar_count / schedule_status を property 化.
    - aggregate_session_blocks の signature を拡張 (mode 必須、 broker_schedule /
      calendars / granularity_seconds optional).
    - aggregate_session_blocks_production wrapper を新設 (production caller 専用).

責務分離:
    - 本 module の `BLOCK_BUCKET_RANGES_UTC` (8h × 3 covering partition) と
      `src/alpha_factory/primitives/_indicators.py:51-55` の
      `_SESSION_RANGES_UTC` (9h overlap windows、 indicator 用) は **別責務**
      で並列管理する。 命名で独立性を担保.

会計契約 SSOT (概念設計 §3.4.0):
    - 集計式:
        pnl_net          = sum(t.pnl - t.spread_cost)
        pnl_before_costs = sum(t.pnl + t.holding_cost)
        spread_cost_total = sum(t.spread_cost)
        holding_cost_total = sum(t.holding_cost)
    - 不変条件: pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total

T072 collider bias 規範 (詳細設計 § 1.4 / § 9.6):
    holiday_markets 単独で session_pass_pattern / SR 計算分母を drop / filter
    してはならない。 必ず stratified audit を行い、 conditioning set を明示する.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal

from src.broker.orders import Trade
from src.domain.price import PriceBar

if TYPE_CHECKING:
    from src.backtest.calendar import (
        BrokerTradingSchedule,
        MarketCode,
        MarketHolidayCalendar,
        ObservabilityFlags,
        ScheduleStatus,
    )

__all__ = [
    "BLOCK_BUCKET_RANGES_UTC",
    "SessionBlock",
    "SessionBlockBucket",
    "aggregate_session_blocks",
    "aggregate_session_blocks_production",
    "apply_spread_stress",
    "compute_bucket_for_bar",
    "compute_bucket_for_trade",
]


logger = logging.getLogger(__name__)


SessionBlockBucket = Literal["tokyo", "london", "ny"]

# 8h covering partition (synthesis § 4.4 SSOT). primitives の 9h overlap
# windows (`src/alpha_factory/primitives/_indicators.py:51-55` の
# `_SESSION_RANGES_UTC`) とは別責務、 並列管理.
BLOCK_BUCKET_RANGES_UTC: Final[dict[SessionBlockBucket, tuple[int, int]]] = {
    "tokyo": (0, 8),  # [0, 8) UTC hour
    "london": (8, 16),  # [8, 16)
    "ny": (16, 24),  # [16, 24)
}

# SSOT 駆動 (概念設計 §3.1 / 詳細設計 §3.1)
_BUCKETS: Final[tuple[SessionBlockBucket, ...]] = tuple(BLOCK_BUCKET_RANGES_UTC.keys())
_M1_EXPECTED_BAR_COUNT: Final[int] = 480  # 8h × 60min


def _default_observability_flags() -> ObservabilityFlags:
    """Lazy import で ObservabilityFlags の default 値を返す (= 循環 import 回避)."""
    from src.backtest.calendar import ObservabilityFlags

    return ObservabilityFlags(
        dst_transition_markets=frozenset(),
        holiday_markets=frozenset(),
    )


@dataclass(frozen=True)
class SessionBlock:
    """1 営業日 (UTC date) × 1 bucket = 1 block (synthesis § 4.4 SSOT).

    SSOT: 概念設計 §3.4 / §4.3、 詳細設計 § 3.7 (T072 改造).

    T070 既存 fields (不変):
        business_date: UTC date.
        bucket: tokyo / london / ny.
        bar_count: block 内 bar 数 (M1 想定で 8h = 480 bars).
        trade_count: block 内 trade 数 (= trade.exit_time が本 block に属する).
        pnl_net / pnl_before_costs / spread_cost_total / holding_cost_total

    T072 追加 fields (default で T070 単独 merge 互換):
        open_minutes: bucket UTC ∩ broker open window の minutes (primary).
            0..480、 default = 480 (= full open).
        granularity_seconds: bar の granularity (= M1 だと 60).
            M1_PLUS_GRANULARITIES に含まれること (60..14400 で 28800 を割り切る値).
        observability_flags: dst_transition_markets + holiday_markets.

    不変条件 (`__post_init__` で検証):
        bar_count >= 0 / trade_count >= 0 / spread_cost_total >= 0 /
        holding_cost_total >= 0
        pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total
        granularity_seconds in M1_PLUS_GRANULARITIES
        BUCKET_FULL_MINUTES_X60 % granularity_seconds == 0
        0 <= open_minutes <= 480

    derived (property):
        expected_bar_count = open_minutes * 60 // granularity_seconds (floor)
        schedule_status = "regular" / "closed_full" / "closed_partial"
        is_partial_bar_block = bar_count < expected_bar_count
    """

    business_date: date
    bucket: SessionBlockBucket
    bar_count: int
    trade_count: int
    pnl_net: Decimal
    pnl_before_costs: Decimal
    spread_cost_total: Decimal
    holding_cost_total: Decimal

    # T072 追加 (default で T070 単独 merge 互換)
    open_minutes: int = _M1_EXPECTED_BAR_COUNT  # = 480
    granularity_seconds: int = 60
    observability_flags: ObservabilityFlags = field(
        default_factory=_default_observability_flags
    )

    def __post_init__(self) -> None:
        # T070 既存 invariant
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
        expected_total = (
            self.pnl_net + self.spread_cost_total + self.holding_cost_total
        )
        if self.pnl_before_costs != expected_total:
            raise ValueError(
                f"pnl_before_costs ({self.pnl_before_costs}) != "
                f"pnl_net + spread_cost_total + holding_cost_total ({expected_total})"
            )

        # T072 invariant (Lazy import で循環回避)
        from src.backtest.calendar import (
            BUCKET_FULL_MINUTES,
            BUCKET_FULL_MINUTES_X60,
            M1_PLUS_GRANULARITIES,
        )

        if self.granularity_seconds not in M1_PLUS_GRANULARITIES:
            raise ValueError(
                f"granularity_seconds must be in M1_PLUS_GRANULARITIES "
                f"(= {sorted(M1_PLUS_GRANULARITIES)}), got {self.granularity_seconds}"
            )
        if BUCKET_FULL_MINUTES_X60 % self.granularity_seconds != 0:
            raise ValueError(
                f"granularity_seconds {self.granularity_seconds} does not divide "
                f"BUCKET_FULL_MINUTES_X60 ({BUCKET_FULL_MINUTES_X60})"
            )
        if not (0 <= self.open_minutes <= BUCKET_FULL_MINUTES):
            raise ValueError(
                f"open_minutes must be in [0, {BUCKET_FULL_MINUTES}], got {self.open_minutes}"
            )

        # I8 tolerance check (Round 3 [W5] / Round 5 [W4]):
        # warning は logger 経由で発火、 ここでは raise しない.
        expected_bars = self.expected_bar_count
        if self.open_minutes > 0:
            tolerance = max(5, int(-(-expected_bars // 100)))  # ceil(expected*0.01)
            if self.bar_count > expected_bars + tolerance:
                logger.warning(
                    "session_block_bar_count_exceeds_tolerance",
                    extra={
                        "business_date": str(self.business_date),
                        "bucket": self.bucket,
                        "bar_count": self.bar_count,
                        "expected_bar_count": expected_bars,
                        "tolerance": tolerance,
                        "open_minutes": self.open_minutes,
                        "granularity_seconds": self.granularity_seconds,
                    },
                )
        else:
            # open_minutes == 0 → closed_full block (= bar_count == 0 を厳密期待)
            if self.bar_count > 0:
                logger.warning(
                    "closed_full_unexpected_bars",
                    extra={
                        "business_date": str(self.business_date),
                        "bucket": self.bucket,
                        "bar_count": self.bar_count,
                        "open_minutes": self.open_minutes,
                        "granularity_seconds": self.granularity_seconds,
                    },
                )

    @property
    def is_empty_trade_block(self) -> bool:
        """trade_count == 0 (= synthesis § 6.3 0.5 neutral 対象)."""
        return self.trade_count == 0

    @property
    def expected_bar_count(self) -> int:
        """T072 derived (詳細設計 § 4.5). open_minutes + granularity_seconds から floor."""
        return self.open_minutes * 60 // self.granularity_seconds

    @property
    def schedule_status(self) -> ScheduleStatus:
        """T072 derived.

        open_minutes == BUCKET_FULL_MINUTES (= 480) → "regular"
        open_minutes == 0                            → "closed_full"
        else                                         → "closed_partial"

        例: H4 で Sunday NY 120 min →
            open_minutes=120 / expected_bar_count=0 / schedule_status="closed_partial".
        """
        if self.open_minutes == _M1_EXPECTED_BAR_COUNT:
            return "regular"
        if self.open_minutes == 0:
            return "closed_full"
        return "closed_partial"

    @property
    def is_partial_bar_block(self) -> bool:
        """T070 後方互換 + T072 改訂 (詳細設計 § 3.7)."""
        return self.bar_count < self.expected_bar_count

    def to_record(self, *, include_derived: bool = False) -> dict:
        """T072 audit/export contract (詳細設計 § 3.7).

        SSOT 出力 schema (= SESSION_BLOCK_STORAGE_FIELDS / SESSION_BLOCK_DERIVED_FIELD_PATHS):
            include_derived=False: SESSION_BLOCK_STORAGE_FIELDS の 12 path
                (= 9 top-level + 2 nested observability_flags + 1 record_schema_version).
            include_derived=True : 上記 + SESSION_BLOCK_DERIVED_FIELD_PATHS の 4 path
                (= 3 top-level + 1 nested observability_flags.all_g3_market_holiday).

        **audit / export caller は必ず include_derived=True を使うこと**.

        record_schema_version = RECORD_SCHEMA_VERSION (= "1.0.0").
        bump 条件:
            MAJOR: field 削除 / 意味変更 / 型変更 / nested path 変更
            MINOR: field 追加
            PATCH: 出力値の bug fix のみ
        """
        from src.backtest.calendar import RECORD_SCHEMA_VERSION

        record: dict = {
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "business_date": self.business_date,
            "bucket": self.bucket,
            "bar_count": self.bar_count,
            "trade_count": self.trade_count,
            "pnl_net": self.pnl_net,
            "pnl_before_costs": self.pnl_before_costs,
            "spread_cost_total": self.spread_cost_total,
            "holding_cost_total": self.holding_cost_total,
            "open_minutes": self.open_minutes,
            "granularity_seconds": self.granularity_seconds,
            "observability_flags": {
                "dst_transition_markets": sorted(
                    self.observability_flags.dst_transition_markets
                ),
                "holiday_markets": sorted(self.observability_flags.holiday_markets),
            },
        }
        if include_derived:
            record["schedule_status"] = self.schedule_status
            record["expected_bar_count"] = self.expected_bar_count
            record["is_partial_bar_block"] = self.is_partial_bar_block
            record["observability_flags"]["all_g3_market_holiday"] = (
                self.observability_flags.all_g3_market_holiday
            )
        return record


def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から SessionBlockBucket を決定論的に割当.

    SSOT: 概念設計 §5.1. BLOCK_BUCKET_RANGES_UTC 駆動.

    Raises:
        ValueError: bar_time.tzinfo is None / 非 UTC offset.
        RuntimeError: BLOCK_BUCKET_RANGES_UTC が 24h covering を満たさない場合.
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
    hour = bar_time.hour
    for bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
        if start <= hour < end:
            return bucket
    raise RuntimeError(
        f"hour {hour} not covered by BLOCK_BUCKET_RANGES_UTC "
        f"(= partition contract violation): {BLOCK_BUCKET_RANGES_UTC}"
    )


def compute_bucket_for_trade(trade: Trade) -> SessionBlockBucket:
    """trade 帰属 bucket を決定論的に算出 (= trade.exit_time 基準)."""
    return compute_bucket_for_bar(trade.exit_time)


def aggregate_session_blocks(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
    *,
    mode: Literal["production", "test"],
    broker_schedule: BrokerTradingSchedule | None = None,
    calendars: Mapping[MarketCode, MarketHolidayCalendar] | None = None,
    granularity_seconds: int = 60,
) -> tuple[SessionBlock, ...]:
    """bars と trades から SessionBlock 配列を構築する (pure function).

    T072 改訂 (詳細設計 § 4.9, Round D1 [C4]): mode は **必須引数**.

    SSOT (概念設計 §3.4.0 / §5.2 / 詳細設計 § 4.9):
        date universe: bars が触れた UTC date set ∪ trades.exit_time が触れた
            UTC date set × 3 bucket. empty block も含む (T070 SSOT 不変).
        open_minutes 駆動:
            broker_schedule provided → compute_bucket_open_minutes(d, bucket, schedule)
            broker_schedule None    → BUCKET_FULL_MINUTES (= 480) default
        observability_flags 駆動:
            calendars provided → compute_observability_flags(d, calendars)
            calendars None    → ObservabilityFlags(frozenset(), frozenset())

    部分構成 (Round 5 [W2] / Round D1 [C4]):
        mode="production": broker_schedule + calendars 両方 provided 必須.
            T070 互換 (両方 None) も production では reject.
        mode="test": 4 通り全許容 (両方 None / どちらかのみ / 両方 provided).
            test/debug 用.

    Args:
        bars: backtest 期間の全 bar (時系列順、 UTC tz-aware).
        trades: backtest で生成された全 trade.
        mode: production / test.
        broker_schedule: BrokerTradingSchedule (optional in test mode).
        calendars: 全 3 市場の MarketHolidayCalendar (optional in test mode).
        granularity_seconds: bar の granularity.

    Returns:
        SessionBlock の tuple. (date, bucket) で sort.

    Raises:
        ValueError: mode="production" で部分構成、 bar_time / trade.exit_time 非 UTC.
    """
    # production mode reject (Round 5 [W2])
    if mode == "production" and (broker_schedule is None or calendars is None):
        raise ValueError(
            "production mode requires both broker_schedule and calendars to be provided. "
            "T070 互換 (両方 None) は test/debug 専用. "
            "片方のみ提供は誤用 (= T072 SSOT で部分構成は禁止)."
        )

    # Lazy import で循環回避
    from src.backtest.calendar import (
        BUCKET_FULL_MINUTES,
        ObservabilityFlags,
        compute_bucket_open_minutes,
        compute_observability_flags,
    )

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
        date_set.add(d)
        key = (d, bucket)
        trade_groups.setdefault(key, []).append(trade)

    # 3. date universe = bars + trades が触れた全 UTC date × 3 bucket
    blocks: list[SessionBlock] = []
    default_flags = ObservabilityFlags(
        dst_transition_markets=frozenset(),
        holiday_markets=frozenset(),
    )
    for d in sorted(date_set):
        flags = (
            compute_observability_flags(d, calendars)
            if calendars is not None
            else default_flags
        )
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

            # T072 open_minutes
            if broker_schedule is not None:
                open_min = compute_bucket_open_minutes(d, bucket, broker_schedule)
            else:
                open_min = BUCKET_FULL_MINUTES

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
                    open_minutes=open_min,
                    granularity_seconds=granularity_seconds,
                    observability_flags=flags,
                )
            )

    return tuple(blocks)


def aggregate_session_blocks_production(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
    *,
    broker_schedule: BrokerTradingSchedule,
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
    granularity_seconds: int = 60,
) -> tuple[SessionBlock, ...]:
    """Round D2 [C3] [S3]: production-only wrapper.

    production caller (= run_ga.py / backtest_runner、 Phase 2 配線) は
    本 wrapper のみ呼ぶ. mode 引数を内部で "production" 固定するため、
    caller が誤って "test" を渡す経路がない.

    aggregate_session_blocks(mode=...) 直接呼出は test/debug 限定.
    """
    return aggregate_session_blocks(
        bars,
        trades,
        mode="production",
        broker_schedule=broker_schedule,
        calendars=calendars,
        granularity_seconds=granularity_seconds,
    )


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

    multiplier=1 で no-op.

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
