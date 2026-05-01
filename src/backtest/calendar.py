"""DST/holiday session boundary contract (T072 cascade port v2 Phase 2 配線).

詳細設計 (devnotes/20260430-2036-todo-T072-dst-holiday-boundary/detailed-design.md
§ 1-9) に厳密準拠する broker / market 分離 layer。

責務分離 SSOT (概念 § 4.3 / § 4.4 / 詳細設計 § 1.4):
    - BrokerTradingSchedule: broker (OANDA) の date-aware 配信 schedule
      (= DST table + broker_full_close_holidays + date_overrides). bar 配信が
      存在する区間 = 半開区間 ``[start_min, end_min)`` を返す.
    - MarketHolidayCalendar: 単一市場の取引所公式 holiday (= 観測情報のみ).
      ObservabilityFlags.holiday_markets を埋めるための情報源で、 bar の
      期待数 / expected_bar_count には**触らない** (= collider bias 規範).

collider bias 規範 (詳細設計 § 1.4 / § 9.6):
    holiday_markets 単独で session_pass_pattern / SR 計算分母を drop / filter
    してはならない。 必ず stratified audit (= holiday_markets 値別の集計) を行い、
    conditioning set を明示する。 holiday を expected_bar_count に混ぜることは
    T072 SSOT で禁止。

半開区間規約 (詳細設計 § 3.1, Round D1 [C3]):
    すべての (start_minute, end_minute) は半開区間 ``[start, end)`` で統一。
    bucket UTC range / open_window / overlap / coverage 判定で同一規約。
    境界値 (start_a == end_b) → overlap 0.

YAML loader (詳細設計 § 4.8, Round D1 [C2] / Round D2 [C2]):
    _DuplicateKeyRejectLoader は duplicate key + merge key (``<<``) の双方を
    構造的に reject する SafeLoader subclass。 calendar 設定で ambiguity を
    YAML 段階で排除する。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

import yaml  # type: ignore[import-untyped]

from src.backtest.session_block import BLOCK_BUCKET_RANGES_UTC, SessionBlockBucket

__all__ = [
    "BROKER_SCHEDULE_VERSION",
    "BUCKET_FULL_MINUTES",
    "BUCKET_FULL_MINUTES_X60",
    "HOLIDAY_CALENDAR_VERSION",
    "M1_PLUS_GRANULARITIES",
    "RECORD_SCHEMA_VERSION",
    "SESSION_BLOCK_DERIVED_FIELD_PATHS",
    "SESSION_BLOCK_STORAGE_FIELDS",
    "BrokerSchedulingProvenance",
    "BrokerSeasonalCloseSpec",
    "BrokerTradingSchedule",
    "MarketCode",
    "MarketHolidayCalendar",
    "ObservabilityFlags",
    "ScheduleStatus",
    "compute_bucket_open_minutes",
    "compute_expected_bar_count",
    "compute_observability_flags",
    "is_dst_transition",
    "is_market_holiday",
    "load_broker_trading_schedule",
    "load_market_holiday_calendar",
    "validate_calendar_coverage",
]


ScheduleStatus = Literal["regular", "closed_full", "closed_partial"]
MarketCode = Literal["tokyo", "london", "ny"]


# ---------------------------------------------------------------------------
# Granularity SSOT (詳細設計 § 3.1, Round 4 [C1] [S1] / Round 5 [S1])
# ---------------------------------------------------------------------------
# すべて 28800 (= 8h × 3600) を割り切る integer granularity (= 8h block と整合).
# - S5/S10/S15/S30 は意図的に除外 (= session block は M1+ の complete candle 前提)
# - H3=10800 は 28800 % 10800 = 7200 で割り切らないため除外
# - D=86400 / W=604800 は session block の対象外
M1_PLUS_GRANULARITIES: Final[frozenset[int]] = frozenset(
    {
        60,  # M1
        120,  # M2
        240,  # M4
        300,  # M5
        600,  # M10
        900,  # M15
        1800,  # M30
        3600,  # H1
        7200,  # H2
        14400,  # H4
    }
)


HOLIDAY_CALENDAR_VERSION: Final[str] = "1.0.0"
BROKER_SCHEDULE_VERSION: Final[str] = "1.0.0"

# bucket full minutes (= 8h × 60) は SSOT 定数として保持
BUCKET_FULL_MINUTES: Final[int] = 8 * 60  # 480
BUCKET_FULL_MINUTES_X60: Final[int] = BUCKET_FULL_MINUTES * 60  # 28800


# Round D1 [C5] [S3] / Round D2 [C1] [S1]: to_record schema 定数
# bump 条件:
#   MAJOR: field 削除 / 意味変更 / 型変更 / nested path 変更
#   MINOR: field 追加
#   PATCH: 出力値の bug fix のみ (= schema 不変)
RECORD_SCHEMA_VERSION: Final[str] = "1.0.0"

SESSION_BLOCK_STORAGE_FIELDS: Final[tuple[str, ...]] = (
    "business_date",
    "bucket",
    "bar_count",
    "trade_count",
    "pnl_net",
    "pnl_before_costs",
    "spread_cost_total",
    "holding_cost_total",
    "open_minutes",
    "granularity_seconds",
    "observability_flags.dst_transition_markets",
    "observability_flags.holiday_markets",
)

SESSION_BLOCK_DERIVED_FIELD_PATHS: Final[tuple[str, ...]] = (
    "schedule_status",
    "expected_bar_count",
    "is_partial_bar_block",
    "observability_flags.all_g3_market_holiday",
)


# ---------------------------------------------------------------------------
# YAML loader: duplicate key + merge key reject (詳細設計 § 4.8)
# ---------------------------------------------------------------------------


class _DuplicateKeyRejectLoader(yaml.SafeLoader):
    """YAML duplicate key + merge key を reject する SafeLoader subclass.

    PyYAML default の SafeLoader は:
        - duplicate key を silently 最後勝ちで上書き
        - merge key ``<<`` を flatten_mapping で展開し、 元の duplicate を見えなくする
    本 subclass は両方を構造的に reject する.
    """


def _construct_mapping_no_duplicates(
    loader: _DuplicateKeyRejectLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    """duplicate key + merge key を reject する mapping constructor."""
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        # merge key `<<` 禁止 (= flatten 経由の重複迂回を防止)
        if key_node.tag == "tag:yaml.org,2002:merge":
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "YAML merge key '<<' is not allowed in calendar configs "
                "(prevents flatten-then-overwrite duplicate keys)",
                key_node.start_mark,
            )
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate key {key!r} found in YAML mapping",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_DuplicateKeyRejectLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrokerSeasonalCloseSpec:
    """DST season 別 close/reopen spec (詳細設計 § 3.2).

    SSOT (Round 3 [C4]):
        region_start <= region_end (inclusive).
        region は互いに disjoint.
        全 region で [period_start, period_end] を連続 cover (= 隙間なし).
        春切替日は当日が新 (DST) region の region_start.
    """

    name: str
    region_start: date
    region_end: date
    close_hour_utc: int
    reopen_hour_utc: int

    def __post_init__(self) -> None:
        if not (0 <= self.close_hour_utc <= 23):
            raise ValueError(
                f"close_hour_utc must be in 0..23, got {self.close_hour_utc} "
                f"(name={self.name!r})"
            )
        if not (0 <= self.reopen_hour_utc <= 23):
            raise ValueError(
                f"reopen_hour_utc must be in 0..23, got {self.reopen_hour_utc} "
                f"(name={self.name!r})"
            )
        if self.region_start > self.region_end:
            raise ValueError(
                f"region_start ({self.region_start}) > region_end ({self.region_end}) "
                f"(name={self.name!r})"
            )


@dataclass(frozen=True)
class BrokerSchedulingProvenance:
    """YAML schema provenance (詳細設計 § 3.3, Round 3 [W6])."""

    source: str
    verified_at: date
    confidence: Literal["high", "medium", "low"]
    notes: str

    def __post_init__(self) -> None:
        if self.confidence not in ("high", "medium", "low"):
            raise ValueError(
                f"confidence must be high/medium/low, got {self.confidence!r}"
            )


@dataclass(frozen=True)
class BrokerTradingSchedule:
    """broker (OANDA) の date-aware 配信 schedule SSOT (詳細設計 § 3.4).

    SSOT 優先順位 (Round 3 [C3] [S2]):
        1. date_overrides[d]              (= early close / late open / partial close)
        2. broker_full_close_holidays
        3. weekday=Sat                    → (0, 0)
        4. weekday=Sun                    → (reopen_hour_utc * 60, 1440)  # season 別
        5. weekday=Fri                    → (0, close_hour_utc * 60)       # season 別
        6. otherwise (Mon-Thu)            → (0, 1440)                      # full open

    DST season boundary semantics (Round 3 [C4]):
        region_start / region_end は inclusive、 disjoint、 連続 cover.
        春切替日は当日が新 region の region_start.

    Round 5 [W3]: 重複 reject の SSOT
        date_overrides ∩ broker_full_close_holidays == ∅ (= ambiguity 防止).
    """

    dst_aware_close_table: tuple[BrokerSeasonalCloseSpec, ...]
    broker_full_close_holidays: frozenset[date]
    date_overrides: Mapping[date, tuple[int, int]]
    period_start: date
    period_end: date
    provenance: BrokerSchedulingProvenance
    version: str

    def __post_init__(self) -> None:
        # I-1: version 整合 (= 最初に弾く、 旧 schema 流入を遮断)
        if self.version != BROKER_SCHEDULE_VERSION:
            raise ValueError(
                f"version must be {BROKER_SCHEDULE_VERSION!r}, got {self.version!r}"
            )

        # I-2: period 妥当性 (= 後続検証の前提)
        if self.period_start > self.period_end:
            raise ValueError(
                f"period_start ({self.period_start}) > period_end ({self.period_end})"
            )

        # I-3: dst_aware_close_table が period を連続 cover
        if not self.dst_aware_close_table:
            raise ValueError("dst_aware_close_table must be non-empty")
        sorted_specs = sorted(
            self.dst_aware_close_table, key=lambda s: s.region_start
        )
        if sorted_specs[0].region_start > self.period_start:
            raise ValueError(
                f"dst_aware_close_table starts at {sorted_specs[0].region_start}, "
                f"after period_start {self.period_start}"
            )
        if sorted_specs[-1].region_end < self.period_end:
            raise ValueError(
                f"dst_aware_close_table ends at {sorted_specs[-1].region_end}, "
                f"before period_end {self.period_end}"
            )
        # I-4: dst_aware_close_table 隣接 region の連続性 (= 隙間なし、 重複なし)
        for prev, curr in pairwise(sorted_specs):
            if prev.region_end + timedelta(days=1) != curr.region_start:
                raise ValueError(
                    f"region gap or overlap: {prev.name!r} ends {prev.region_end}, "
                    f"{curr.name!r} starts {curr.region_start}"
                )

        # I-5: broker_full_close_holidays ⊂ [period_start, period_end] (= I-2 後)
        for d in self.broker_full_close_holidays:
            if not (self.period_start <= d <= self.period_end):
                raise ValueError(
                    f"broker_full_close_holiday {d} out of period "
                    f"[{self.period_start}, {self.period_end}]"
                )

        # I-6: date_overrides の key / value 検証 (= I-2 後)
        # 半開区間 [start_min, end_min) 規約 (Round D1 [C3])
        for d, window in self.date_overrides.items():
            if not (self.period_start <= d <= self.period_end):
                raise ValueError(
                    f"date_override key {d} out of period "
                    f"[{self.period_start}, {self.period_end}]"
                )
            start_min, end_min = window
            if not (0 <= start_min <= end_min <= 1440):
                raise ValueError(
                    f"date_override[{d}] window invalid: ({start_min}, {end_min}). "
                    f"Required: 0 <= start <= end <= 1440 (半開区間 [start, end))"
                )

        # I-7: date_overrides ∩ broker_full_close_holidays == ∅ (Round 5 [W3])
        # 順序依存: I-5 (full_close 妥当) / I-6 (overrides 妥当) 後に重複検出
        overlap = set(self.date_overrides.keys()) & set(
            self.broker_full_close_holidays
        )
        if overlap:
            raise ValueError(
                f"date_overrides and broker_full_close_holidays must not overlap. "
                f"Overlapping dates: {sorted(overlap)}"
            )
        # I-8 (1 日 1 window) は YAML 段階で _DuplicateKeyRejectLoader 経由保証.

    def open_window_for_utc_date(self, d: date) -> tuple[int, int]:
        """SSOT 優先順位 (上記 docstring 参照).

        戻り値は半開区間 ``[start_min, end_min)``:
            - 0 <= start_min <= end_min <= 1440
            - start_min == end_min == 0 → 完全 closed (空区間)
            - start_min == 0, end_min == 1440 → 完全 open
            - 境界値 (= start == 他区間の end) は overlap 計算で 0 を返す

        Args:
            d: UTC date (= bar.bar_time.date() 想定).

        Returns:
            (start_min, end_min) 半開区間 [start_min, end_min).
        """
        # 1. date_overrides 最優先
        if d in self.date_overrides:
            return self.date_overrides[d]
        # 2. broker_full_close_holidays
        if d in self.broker_full_close_holidays:
            return (0, 0)
        # 3-6. weekday + season
        weekday = d.weekday()  # 0=Mon..6=Sun
        if weekday == 5:  # Saturday
            return (0, 0)
        spec = self._find_season(d)
        if weekday == 6:  # Sunday
            return (spec.reopen_hour_utc * 60, 1440)
        if weekday == 4:  # Friday
            return (0, spec.close_hour_utc * 60)
        # Mon-Thu
        return (0, 1440)

    def _find_season(self, d: date) -> BrokerSeasonalCloseSpec:
        """dst_aware_close_table から d を含む region を線形探索 (deterministic)."""
        for spec in self.dst_aware_close_table:
            if spec.region_start <= d <= spec.region_end:
                return spec
        # __post_init__ で連続 cover を検証済、 ここに到達しないはず
        raise AssertionError(
            f"date {d} not covered by dst_aware_close_table "
            f"(period: [{self.period_start}, {self.period_end}])"
        )


@dataclass(frozen=True)
class MarketHolidayCalendar:
    """単一市場の取引所公式 holiday (観測情報のみ、 詳細設計 § 3.5).

    SSOT (Round 2 [C2] [S2]):
        - 用途: ObservabilityFlags.holiday_markets を埋める観測情報.
        - expected_bar_count には touch しない
          (= broker 配信が継続している限り bar 出る).
        - caller (T071 等) は holiday_markets を任意の condition として
          stratified 使用 (= collider bias 規範).
    """

    market: MarketCode
    period_start: date
    period_end: date
    holidays: frozenset[date]
    schema_version: str

    def __post_init__(self) -> None:
        if self.market not in ("tokyo", "london", "ny"):
            raise ValueError(f"market must be tokyo/london/ny, got {self.market!r}")
        if self.schema_version != HOLIDAY_CALENDAR_VERSION:
            raise ValueError(
                f"schema_version must be {HOLIDAY_CALENDAR_VERSION!r}, "
                f"got {self.schema_version!r} (market={self.market!r})"
            )
        if self.period_start > self.period_end:
            raise ValueError(
                f"period_start ({self.period_start}) > period_end ({self.period_end}) "
                f"(market={self.market!r})"
            )
        for d in self.holidays:
            if not (self.period_start <= d <= self.period_end):
                raise ValueError(
                    f"holiday {d} out of period "
                    f"[{self.period_start}, {self.period_end}] (market={self.market!r})"
                )

    def contains(self, d: date) -> bool:
        """検証済 calendar の raw lookup (Round 1 [S5] / Round 2 [W3]).

        前提: validate_calendar_coverage が dataset_span を覆うことを load 時に
        集約検証済. period 外 d を渡すのは設計上の bug (= caller 違反).
        """
        return d in self.holidays


@dataclass(frozen=True)
class ObservabilityFlags:
    """schedule とは独立の audit / log 用 mark (詳細設計 § 3.6).

    Round 2 [W1] [W2] / Round 3 [S5]:
        - is_dst_transition (bool) → dst_transition_markets (frozenset[MarketCode]).
        - has_all_g3_holidays → all_g3_market_holiday rename.
    """

    dst_transition_markets: frozenset[MarketCode]
    holiday_markets: frozenset[MarketCode]

    def __post_init__(self) -> None:
        invalid_dst = self.dst_transition_markets - frozenset({"london", "ny"})
        if invalid_dst:
            raise ValueError(
                f"dst_transition_markets must be subset of {{'london', 'ny'}}, "
                f"got invalid: {invalid_dst}"
            )
        invalid_holiday = self.holiday_markets - frozenset(
            {"tokyo", "london", "ny"}
        )
        if invalid_holiday:
            raise ValueError(
                f"holiday_markets must be subset of {{'tokyo', 'london', 'ny'}}, "
                f"got invalid: {invalid_holiday}"
            )

    @property
    def all_g3_market_holiday(self) -> bool:
        """Round 3 [S5] rename: len(holiday_markets) == 3."""
        return len(self.holiday_markets) == 3


# ---------------------------------------------------------------------------
# Pure functions (詳細設計 § 4)
# ---------------------------------------------------------------------------


def is_dst_transition(market: MarketCode, d: date) -> bool:
    """d が market の DST 切替日なら True (London / NY のみ).

    SSOT: zoneinfo (IANA tz database) 経由で transition を deterministic 判定.
    判定方法: d 00:00 local と d+1 00:00 local の utcoffset が異なれば transition.
    Tokyo は常に False (= Asia/Tokyo は DST なし).
    """
    if market == "tokyo":
        return False
    if market == "london":
        tz: ZoneInfo = ZoneInfo("Europe/London")
    elif market == "ny":
        tz = ZoneInfo("America/New_York")
    else:
        raise ValueError(f"unknown market: {market!r}")

    midnight_today = datetime.combine(d, time(0, 0), tzinfo=tz)
    midnight_tomorrow = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=tz)
    return midnight_today.utcoffset() != midnight_tomorrow.utcoffset()


def is_market_holiday(
    market: MarketCode, d: date, calendar: MarketHolidayCalendar
) -> bool:
    """d が market の holiday なら True. calendar.market 一致確認 + raw lookup.

    前提: validate_calendar_coverage が dataset_span を覆うことを load 時に
    集約検証済.
    """
    if calendar.market != market:
        raise ValueError(
            f"calendar.market={calendar.market!r} != requested market={market!r}"
        )
    return calendar.contains(d)


def compute_observability_flags(
    business_date: date,
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
) -> ObservabilityFlags:
    """business_date 単位の observability flags 集計 (詳細設計 § 4.3)."""
    _DST_MARKETS: tuple[MarketCode, ...] = ("london", "ny")
    _ALL_MARKETS: tuple[MarketCode, ...] = ("tokyo", "london", "ny")
    dst_markets: frozenset[MarketCode] = frozenset(
        m for m in _DST_MARKETS if is_dst_transition(m, business_date)
    )
    holiday_markets: frozenset[MarketCode] = frozenset(
        m
        for m in _ALL_MARKETS
        if is_market_holiday(m, business_date, calendars[m])
    )
    return ObservabilityFlags(
        dst_transition_markets=dst_markets,
        holiday_markets=holiday_markets,
    )


def compute_bucket_open_minutes(
    business_date: date,
    bucket: SessionBlockBucket,
    broker_schedule: BrokerTradingSchedule,
) -> int:
    """指定 (date, bucket) の broker-open minutes (= bucket UTC ∩ broker open window).

    SSOT (Round 2 [C2] / 詳細設計 § 4.4): broker_schedule のみで決定、
    market holiday touch しない.

    Returns:
        int (0..480) = bucket UTC 区間の broker-open minutes.
    """
    open_start, open_end = broker_schedule.open_window_for_utc_date(business_date)
    start_hour, end_hour = BLOCK_BUCKET_RANGES_UTC[bucket]
    bucket_start_min = start_hour * 60
    bucket_end_min = end_hour * 60
    overlap_start = max(bucket_start_min, open_start)
    overlap_end = min(bucket_end_min, open_end)
    return max(0, overlap_end - overlap_start)


def compute_expected_bar_count(open_minutes: int, granularity_seconds: int) -> int:
    """granularity から期待 bar 数を導出 (詳細設計 § 4.5, Round 4 [S2]).

    complete candle 数を数えるため floor (= integer 切り捨て).
    例: H4 (granularity_seconds=14400) で open_minutes=120 →
        120 * 60 / 14400 = 0.5 → floor = 0 (= H4 candle 完成しない).
    open_minutes=120 自体は SessionBlock.open_minutes に保持、 partial 強度維持.
    """
    return open_minutes * 60 // granularity_seconds


def validate_calendar_coverage(
    calendars: Mapping[MarketCode, MarketHolidayCalendar],
    broker_schedule: BrokerTradingSchedule,
    dataset_span: tuple[date, date],
) -> None:
    """dataset 全期間が calendars + broker_schedule の period 内に収まるか一括検証.

    SSOT (Round 1 [S5] / Round 2 [W3] / Round D1 [C6]):
        load 時に caller が一回呼び、 検証済前提で contains() /
        open_window_for_utc_date() を raw lookup. per-call ValueError は廃止.

    Round D1 [C6]: dataset_span は両端 inclusive ``(start_inclusive, end_inclusive)``:
        - 検証条件 (両端 inclusive): start <= end / period_start <= start /
          period_end >= end
        - period も両端 inclusive (= MarketHolidayCalendar / BrokerTradingSchedule
          双方の SSOT)
        - bucket UTC range / open_window は半開区間だが、 date 単位の period /
          dataset_span は両端 inclusive.

    Raises:
        ValueError: いずれかの calendars / broker_schedule の period が
            dataset_span を覆わない.
        KeyError: calendars に "tokyo" / "london" / "ny" のいずれかが欠落.
    """
    start, end = dataset_span
    if start > end:
        raise ValueError(f"dataset_span start ({start}) > end ({end})")

    # broker_schedule period check
    if broker_schedule.period_start > start:
        raise ValueError(
            f"broker_schedule.period_start ({broker_schedule.period_start}) > "
            f"dataset_span start ({start})"
        )
    if broker_schedule.period_end < end:
        raise ValueError(
            f"broker_schedule.period_end ({broker_schedule.period_end}) < "
            f"dataset_span end ({end})"
        )

    # calendars period check (= 全 3 市場)
    for market in ("tokyo", "london", "ny"):
        cal = calendars[market]  # KeyError if missing
        if cal.period_start > start:
            raise ValueError(
                f"calendar[{market!r}].period_start ({cal.period_start}) > "
                f"dataset_span start ({start})"
            )
        if cal.period_end < end:
            raise ValueError(
                f"calendar[{market!r}].period_end ({cal.period_end}) < "
                f"dataset_span end ({end})"
            )


# ---------------------------------------------------------------------------
# YAML loaders (詳細設計 § 4.7 / § 4.8)
# ---------------------------------------------------------------------------


def load_market_holiday_calendar(
    market: MarketCode, yaml_path: Path
) -> MarketHolidayCalendar:
    """YAML から MarketHolidayCalendar を構築 (詳細設計 § 4.7).

    YAML schema (例 config/calendars/tokyo_market_holidays.yaml):
        market: "tokyo"
        schema_version: "1.0.0"
        period_start: "2022-01-01"
        period_end: "2027-12-31"
        provenance:
          source: "JPX 公式 holiday list 2022-2027"
          verified_at: "2026-04-30"
          confidence: "high"
          notes: "国民の祝日 + TSE 取引所 close 日"
        holidays:
          - "2022-01-01"
          - ...
    """
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.load(f, Loader=_DuplicateKeyRejectLoader)
    if data["market"] != market:
        raise ValueError(
            f"yaml market={data['market']!r} != requested market={market!r} "
            f"(yaml_path={yaml_path})"
        )
    return MarketHolidayCalendar(
        market=market,
        period_start=date.fromisoformat(data["period_start"]),
        period_end=date.fromisoformat(data["period_end"]),
        holidays=frozenset(date.fromisoformat(d) for d in data["holidays"]),
        schema_version=data["schema_version"],
    )


def load_broker_trading_schedule(yaml_path: Path) -> BrokerTradingSchedule:
    """YAML から BrokerTradingSchedule を構築 (詳細設計 § 4.8).

    Round D1 [C2] / Round D2 [C2] [S2]:
        _DuplicateKeyRejectLoader 使用で duplicate key + merge key を YAML 段階で reject.
    """
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.load(f, Loader=_DuplicateKeyRejectLoader)

    specs: tuple[BrokerSeasonalCloseSpec, ...] = tuple(
        BrokerSeasonalCloseSpec(
            name=s["name"],
            region_start=date.fromisoformat(s["region_start"]),
            region_end=date.fromisoformat(s["region_end"]),
            close_hour_utc=int(s["close_hour_utc"]),
            reopen_hour_utc=int(s["reopen_hour_utc"]),
        )
        for s in data["dst_aware_close_table"]
    )

    full_close: frozenset[date] = frozenset(
        date.fromisoformat(d) for d in data.get("broker_full_close_holidays") or []
    )

    overrides_raw = data.get("date_overrides") or {}
    overrides: dict[date, tuple[int, int]] = {}
    for k, v in overrides_raw.items():
        # YAML date key の場合と string key の場合の両方に対応
        d_key = k if isinstance(k, date) else date.fromisoformat(str(k))
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ValueError(
                f"date_override value for {d_key} must be a 2-element list/tuple, got {v!r}"
            )
        overrides[d_key] = (int(v[0]), int(v[1]))

    prov_data = data["provenance"]
    verified_at_raw = prov_data["verified_at"]
    verified_at = (
        verified_at_raw
        if isinstance(verified_at_raw, date)
        else date.fromisoformat(str(verified_at_raw))
    )
    provenance = BrokerSchedulingProvenance(
        source=prov_data["source"],
        verified_at=verified_at,
        confidence=prov_data["confidence"],
        notes=prov_data["notes"],
    )

    period_start_raw = data["period_start"]
    period_end_raw = data["period_end"]
    period_start = (
        period_start_raw
        if isinstance(period_start_raw, date)
        else date.fromisoformat(str(period_start_raw))
    )
    period_end = (
        period_end_raw
        if isinstance(period_end_raw, date)
        else date.fromisoformat(str(period_end_raw))
    )

    return BrokerTradingSchedule(
        dst_aware_close_table=specs,
        broker_full_close_holidays=full_close,
        date_overrides=overrides,
        period_start=period_start,
        period_end=period_end,
        provenance=provenance,
        version=str(data["version"]),
    )
