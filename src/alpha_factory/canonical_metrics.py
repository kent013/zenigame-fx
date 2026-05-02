"""T061: canonical 5 engine — synthesis § 6 数式仕様の単一実装.

詳細:
- 概念設計: ``devnotes/20260429-2300-todo-T061-canonical-five-engine/conceptual-design.md``
- 詳細設計: ``devnotes/20260429-2300-todo-T061-canonical-five-engine/detailed-design.md``
- synthesis § 6 (canonical 5 + Pareto 3 数式仕様)、 § 17 (用語)
- T060 依存: :class:`~src.alpha_factory.partition.Period` 同規約 (UTC 厳密、 frozen dataclass)

Phase 1 (本 TODO = T061 PR 1): 単体実装 + テストのみ、 ``stage_gate.py`` /
``swim_lane.py`` / ``archive.py`` / ``cross_pair.py`` / ``config.py`` /
``default.yaml`` への組込は **Phase 2 (別 PR、 T063-T064 と同時)** で実施。
T061 PR 1 単独 merge で runtime に影響なし。

学術引用 (HAC variance):
    Newey, W. K., & West, K. D. (1987). "A Simple, Positive Semi-Definite,
    Heteroskedasticity and Autocorrelation Consistent Covariance Matrix."
    Econometrica, 55(3), 703-708.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

__all__ = [
    "DENOM_FLOOR",
    "GATE_PASS_TOLERANCE",
    "HAC_BARTLETT_DEFAULT_Q",
    "LOG_PF_CLIP_RANGE",
    "LOG_PF_SMOOTH",
    "LOW_SAMPLE_BLOCK_THRESHOLD",
    "MAX_DD_DENOM_FLOOR",
    "N_BLOCKS_PER_YEAR",
    "SIGMA2_LR_EPS",
    "BarEquityInvalidError",
    "BarEquityPoint",
    "BarEquitySeries",
    "CanonicalFiveResult",
    "CanonicalFiveThresholds",
    "CanonicalMetricsInputError",
    "InfeasibleReasonCode",
    "InvariantFlags",
    "SessionBlockSummary",
    "SessionBucket",
    "SessionBucketBoundaryProvider",
    "ThresholdsInvalidError",
    "TradeRecord",
    "TradeRecordInvalidError",
    "compute_max_dd",
    "compute_session_block_win_rate_worst",
    "compute_session_blocks",
    "compute_signed_slacks",
    "compute_sr_session_worst",
    "evaluate_canonical_five",
    "log_pf_clip",
    "slack_to_range",
]


# ---------------------------------------------------------------------------
# Constants (synthesis § 6 厳密準拠)
# ---------------------------------------------------------------------------

DENOM_FLOOR: Final[float] = 1e-6
"""synthesis § 6.1 確定値。 5 指標 signed slack の denom floor 共通値."""

N_BLOCKS_PER_YEAR: Final[int] = 756
"""252 営業日 × 3 session bucket。 SR block-scale → annual-scale 換算用 const.

T072 (DST/holiday) 確定後、 holiday 補正で ``n_blocks_observed`` 実測ベースに切替する場合は
本 const を関数引数化 (T072 申し送り)。
"""

GATE_PASS_TOLERANCE: Final[float] = 1e-9
"""concept Round 3 [W2] 反映: 浮動小数誤差許容、 gate_pass <=> gate_worst_gap <= 1e-9.
denom_floor=1e-6 より十分小さい桁。
"""

HAC_BARTLETT_DEFAULT_Q: Final[int] = 5
"""synthesis § 6.2 確定値。 Bartlett kernel lag (1 週間相当)."""

SIGMA2_LR_EPS: Final[float] = 1e-12
"""HAC long-run variance の floor (zero-variance 系列保護).
concept Round 1 [C3] 反映: hard fail を入れず eps floor で対応."""

MAX_DD_DENOM_FLOOR: Final[float] = 1e-12
"""max_dd 計算時の running_max 分母 floor (detail Round 1 [C3] 反映).
running_max <= 0 の bar は drawdown 計算からスキップ、 全 bar negative なら
max_dd=1.0 (full drawdown sentinel)."""

LOG_PF_CLIP_RANGE: Final[tuple[float, float]] = (-2.0, 2.0)
"""synthesis § 6.4 確定値。 archive lex 末端 tie-break 用."""

LOG_PF_SMOOTH: Final[float] = 1e-6
"""log_pf_clip の smoothing constant: log((GP+ε)/(GL+ε))."""

LOW_SAMPLE_BLOCK_THRESHOLD: Final[int] = 30
"""concept Round 1 [C3] 反映: bucket 内 block 数 < 30 を low_sample で診断出力 (hard fail なし)."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionBucket(StrEnum):
    """8h × 3 bucket 固定 (synthesis § 5 / § 17 確定、 6 bucket 不採用).

    boundary は T070 backtest engine / T072 DST contract が確定。
    T061 はラベル済 :class:`TradeRecord` を consume するのみ。
    """

    TOKYO = "tokyo"
    LONDON = "london"
    NY = "ny"


class InfeasibleReasonCode(StrEnum):
    """``infeasible_reason_codes`` の prefix 規約を型で強制 (detail Round 1 [S1] 反映).

    ``strategic_*`` prefix: synthesis § 6.6 由来の戦略的 fail-fast 2 種
    ``input_*`` prefix: engine 検出の入力不正 (provider 例外含む)
    """

    # synthesis § 6.6 戦略的 fail-fast (TradeRecord フラグ集計由来)
    STRATEGIC_SESSION_CLOSE_DROP = "strategic_session_close_drop"
    STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN = "strategic_negative_equity_drop_open"
    # engine 検出の入力不正
    INPUT_INVALID_BAR_SERIES = "input_invalid_bar_series"
    INPUT_BUCKET_ATTRIBUTION_MISMATCH = "input_bucket_attribution_mismatch"
    INPUT_BUCKET_VALIDATOR_EXCEPTION = "input_bucket_validator_exception"
    INPUT_EMPTY_TRADE_LIST = "input_empty_trade_list"
    INPUT_EMPTY_BUSINESS_DAY_UNIVERSE = "input_empty_business_day_universe"
    INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH = "input_business_day_universe_mismatch"
    INPUT_NON_FINITE_PNL = "input_non_finite_pnl"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CanonicalMetricsInputError(ValueError):
    """canonical_metrics 入力 dataclass の不変条件違反 (基底クラス).

    本基底例外を直接 raise しない (detail Round 1 [W1] 反映、 例外階層の一貫性)。
    ``__post_init__`` では必ず派生例外 (:class:`TradeRecordInvalidError` /
    :class:`BarEquityInvalidError` / :class:`ThresholdsInvalidError`) を raise する。
    """


class TradeRecordInvalidError(CanonicalMetricsInputError):
    """:class:`TradeRecord` ``__post_init__`` 不変条件違反."""


class BarEquityInvalidError(CanonicalMetricsInputError):
    """:class:`BarEquitySeries` ``__post_init__`` 不変条件違反 (sorted/no-dup/UTC-aware/finite)."""


class ThresholdsInvalidError(CanonicalMetricsInputError):
    """:class:`CanonicalFiveThresholds` ``__post_init__`` 不変条件違反."""


# ---------------------------------------------------------------------------
# Provider protocol (concept Round 1 [W1] / Round 3 [S2] 反映)
# ---------------------------------------------------------------------------


class SessionBucketBoundaryProvider:
    """T072 で実装する session bucket boundary 契約 (T061 では interface のみ).

    T064 統合時に provider を ``_validate_trade_attribution`` に注入して、
    ``TradeRecord.session_bucket`` / ``business_day_index`` が boundary 契約に
    整合するか double-check する.

    本 module では Protocol-like base class で signature のみ定義。 T072 で具体実装する.
    """

    @property
    def version(self) -> str:
        """provider 識別子 (例: ``'session_bucket_boundary_v1'``). 監査ログに残す."""
        raise NotImplementedError

    def expected_bucket(self, exit_time_utc: datetime) -> SessionBucket:
        """``exit_time_utc`` が属する正規 bucket. T064 で ``TradeRecord.session_bucket`` と比較."""
        raise NotImplementedError

    def expected_business_day_index(self, exit_time_utc: datetime) -> int:
        """``exit_time_utc`` が属する business day index. T064 で
        ``TradeRecord.business_day_index`` と比較."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Input DataClasses
# ---------------------------------------------------------------------------


def _validate_utc_aware(
    name: str,
    dt: datetime,
    *,
    exc_class: type[CanonicalMetricsInputError],
) -> None:
    """UTC-aware + ``utcoffset() == 0`` 厳密 (T060 :class:`Period` 同規約).

    detail Round 1 [W1] 反映: caller が派生例外クラス
    (:class:`TradeRecordInvalidError` / :class:`BarEquityInvalidError` /
    :class:`ThresholdsInvalidError`) を指定し、 例外階層の一貫性を保つ.
    """
    if dt.tzinfo is None:
        raise exc_class(
            f"{name} must be timezone-aware datetime, got naive: {dt!r}"
        )
    offset = dt.utcoffset()
    if offset is None or offset != timedelta(0):
        raise exc_class(
            f"{name} must be UTC (utcoffset=0), got offset={offset}: {dt!r}"
        )


@dataclass(frozen=True)
class TradeRecord:
    """1 trade (intraday close-out 前提).

    invariant (``__post_init__`` で fail-fast):
    - ``entry_time_utc`` / ``exit_time_utc`` は UTC-aware + ``utcoffset() == 0``
    - ``entry_time_utc < exit_time_utc``
    - ``pnl_net`` は finite (NaN/Inf なら raise → caller 側で
      ``input_non_finite_pnl`` reason に変換)
    - ``business_day_index >= 0``
    - ``spread_cost`` / ``holding_cost`` は finite + ``>= 0`` (T078 追加、
      stage_bc_evaluator.apply_spread_stress 利用、 既存 caller は default 0.0
      で backward compatible)

    ``session_bucket`` / ``business_day_index`` の T070 整合性は
    ``_validate_trade_attribution(provider)`` で別経路 double-check
    (concept Round 1 [W1] 反映).

    ``spread_cost`` / ``holding_cost`` の伝搬経路 (= backtest engine →
    TradeRecord 構築時の値伝搬) は本 dataclass のスコープ外、 後続別 TODO で
    配線 (= T078 では schema 拡張 + apply_spread_stress 正式実装まで).
    """

    entry_time_utc: datetime
    exit_time_utc: datetime
    pnl_net: float
    session_bucket: SessionBucket
    business_day_index: int
    is_session_close_drop: bool
    is_negative_equity_drop_open: bool
    # T078 追加 (default 0.0 で backward compatible、 概念設計 § 改訂 1):
    # apply_spread_stress 利用、 caller (backtest engine) が値を伝搬する
    spread_cost: float = 0.0
    holding_cost: float = 0.0

    def __post_init__(self) -> None:
        _validate_utc_aware(
            "TradeRecord.entry_time_utc",
            self.entry_time_utc,
            exc_class=TradeRecordInvalidError,
        )
        _validate_utc_aware(
            "TradeRecord.exit_time_utc",
            self.exit_time_utc,
            exc_class=TradeRecordInvalidError,
        )
        if self.exit_time_utc <= self.entry_time_utc:
            raise TradeRecordInvalidError(
                f"TradeRecord.exit_time_utc ({self.exit_time_utc}) "
                f"must be > entry_time_utc ({self.entry_time_utc})"
            )
        if self.business_day_index < 0:
            raise TradeRecordInvalidError(
                f"TradeRecord.business_day_index must be >= 0: {self.business_day_index}"
            )
        if not math.isfinite(self.pnl_net):
            raise TradeRecordInvalidError(
                f"TradeRecord.pnl_net must be finite: {self.pnl_net}"
            )
        # T078 invariant: spread_cost / holding_cost は finite + >= 0
        if not math.isfinite(self.spread_cost):
            raise TradeRecordInvalidError(
                f"TradeRecord.spread_cost must be finite: {self.spread_cost}"
            )
        if self.spread_cost < 0:
            raise TradeRecordInvalidError(
                f"TradeRecord.spread_cost must be >= 0: {self.spread_cost}"
            )
        if not math.isfinite(self.holding_cost):
            raise TradeRecordInvalidError(
                f"TradeRecord.holding_cost must be finite: {self.holding_cost}"
            )
        if self.holding_cost < 0:
            raise TradeRecordInvalidError(
                f"TradeRecord.holding_cost must be >= 0: {self.holding_cost}"
            )


@dataclass(frozen=True)
class BarEquityPoint:
    """1 bar の equity (max_dd 計算用、 :class:`BarEquitySeries` 内部要素)."""

    timestamp_utc: datetime
    equity: float


@dataclass(frozen=True)
class BarEquitySeries:
    """max_dd 計算 input contract.

    invariant (``__post_init__`` で fail-fast、 concept Round 1 [W2] 反映):
    - ``len(points) >= 1``
    - 全 ``timestamp_utc`` が UTC-aware + ``utcoffset == 0``
    - timestamps strict monotone increasing (sorted + 重複なし)
    - 全 ``equity`` が finite (NaN/Inf 検出時は :class:`BarEquityInvalidError`)
    """

    points: tuple[BarEquityPoint, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 1:
            raise BarEquityInvalidError("BarEquitySeries.points must have len >= 1")
        prev_ts: datetime | None = None
        for i, p in enumerate(self.points):
            _validate_utc_aware(
                f"BarEquitySeries.points[{i}].timestamp_utc",
                p.timestamp_utc,
                exc_class=BarEquityInvalidError,
            )
            if not math.isfinite(p.equity):
                raise BarEquityInvalidError(
                    f"BarEquitySeries.points[{i}].equity must be finite: {p.equity}"
                )
            if prev_ts is not None and p.timestamp_utc <= prev_ts:
                raise BarEquityInvalidError(
                    f"BarEquitySeries.points must be strictly monotone increasing: "
                    f"index {i}: {p.timestamp_utc} <= prev {prev_ts}"
                )
            prev_ts = p.timestamp_utc


@dataclass(frozen=True)
class SessionBlockSummary:
    """``(business_day_index, session_bucket)`` 単位の集約結果 (内部 use)."""

    business_day_index: int
    session_bucket: SessionBucket
    pnl_net_block: float
    trade_count_block: int


@dataclass(frozen=True)
class CanonicalFiveThresholds:
    """``live_criteria`` + supplementary thresholds (T061 入力契約).

    field:
    - ``sharpe_min``: annual Sharpe 下限 (例 1.0、 ``live_criteria.sharpe_min``)
    - ``net_pnl_min``: 期間内合計 PnL 下限 (例 50000、 ``live_criteria.total_pnl_min``)
    - ``max_dd_max``: 最大 DD 上限 (例 0.20 ratio、 ``live_criteria.max_drawdown_max``)
    - ``trade_count_min``, ``trade_count_max``: trade_count [L, U] range
      (例 [50, 5000]、 ``live_criteria.trade_count_min/max``)
    - ``win_rate_min``: ``session_block_win_rate_worst`` の最低許容
      (例 0.45、 ``live_criteria.win_rate_min`` を Phase 2 で追加)

    invariant (``__post_init__`` で fail-fast):
    - 全 field finite
    - ``sharpe_min``, ``net_pnl_min``, ``max_dd_max``, ``win_rate_min`` > 0
    - ``0 < trade_count_min <= trade_count_max``
    - ``0 < win_rate_min < 1``
    - ``0 < max_dd_max < 1``
    """

    sharpe_min: float
    net_pnl_min: float
    max_dd_max: float
    trade_count_min: int
    trade_count_max: int
    win_rate_min: float

    def __post_init__(self) -> None:
        for name, value in (
            ("sharpe_min", self.sharpe_min),
            ("net_pnl_min", self.net_pnl_min),
            ("max_dd_max", self.max_dd_max),
            ("win_rate_min", self.win_rate_min),
        ):
            if not math.isfinite(value):
                raise ThresholdsInvalidError(
                    f"CanonicalFiveThresholds.{name} must be finite: {value}"
                )
            if value <= 0.0:
                raise ThresholdsInvalidError(
                    f"CanonicalFiveThresholds.{name} must be > 0: {value}"
                )
        if not (0 < self.trade_count_min <= self.trade_count_max):
            raise ThresholdsInvalidError(
                f"CanonicalFiveThresholds: 0 < trade_count_min ({self.trade_count_min}) "
                f"<= trade_count_max ({self.trade_count_max})"
            )
        if not (0.0 < self.win_rate_min < 1.0):
            raise ThresholdsInvalidError(
                f"CanonicalFiveThresholds.win_rate_min must be in (0, 1): {self.win_rate_min}"
            )
        if not (0.0 < self.max_dd_max < 1.0):
            raise ThresholdsInvalidError(
                f"CanonicalFiveThresholds.max_dd_max must be in (0, 1): {self.max_dd_max}"
            )


# ---------------------------------------------------------------------------
# Output DataClasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantFlags:
    """fail-fast 用 flag (synthesis § 6.6 + concept Round 3 [W1] 分類強化).

    ``infeasible_reason_codes`` は 2 分類 prefix で区別:

    ``strategic_*``: synthesis § 6.6 由来の戦略的 fail-fast 2 種
        - ``"strategic_session_close_drop"`` (``session_close_drop_count > 0``)
        - ``"strategic_negative_equity_drop_open"``
          (``negative_equity_drop_open_count > 0``)

    ``input_*``: engine 検出の入力不正
        - ``"input_invalid_bar_series"`` (:class:`BarEquitySeries` 不変条件違反)
        - ``"input_bucket_attribution_mismatch"`` (provider double-check 失敗)
        - ``"input_empty_trade_list"`` (trades 空) etc.
    """

    session_close_drop_count: int
    negative_equity_drop_open_count: int
    infeasible_reason_codes: frozenset[InfeasibleReasonCode]

    @property
    def is_feasible(self) -> bool:
        """全 invariant が違反なし."""
        return (
            self.session_close_drop_count == 0
            and self.negative_equity_drop_open_count == 0
            and len(self.infeasible_reason_codes) == 0
        )


@dataclass(frozen=True)
class CanonicalFiveResult:
    """canonical 5 worst aggregation の結果 (T061 出力契約).

    raw values (block-scale → annual-scale 換算後):
        ``sr_session_worst_block_scale``: 3 bucket SR block-scale の min
            (HAC Bartlett q=5)
        ``sr_session_worst_annual_estimate``: block-scale を
            ``sqrt(N_BLOCKS_PER_YEAR)`` 倍した推定値
        ``net_pnl_after_cost``: 期間内合計 net PnL
        ``max_dd``: 最大 DD (>=0、 ratio スケール、 値域 [0.0, 1.0])
        ``trade_count``: 期間内 trade 数
        ``session_block_win_rate_worst``: 3 bucket WR の min

    per-bucket diagnostics (T071 observability で消費):
        ``per_bucket_sr``: ``{SessionBucket: SR block-scale}``
        ``per_bucket_wr``: ``{SessionBucket: WR}``
        ``low_sample_buckets``: block 数 < 30 の bucket 集合
            (concept Round 1 [C3] 反映)

    signed slack (synthesis § 6.1 厳密、 全 ``denom_floor=1e-6``):
        ``slack_sharpe``, ``slack_pnl``, ``slack_dd``, ``slack_tc``, ``slack_wr``

    集約 (synthesis § 6.4):
        ``gate_worst_gap = max_m max(0, -slack_m)``
        ``gate_pass = (gate_worst_gap <= GATE_PASS_TOLERANCE) AND
        invariants.is_feasible``

    auxiliary (synthesis § 6.4 / § 6.7):
        ``log_pf_clip``: archive 末端 tie-break (-2 to 2)
        ``bucket_validator_version``: provider double-check 時の version 文字列
            (Round 3 [S2])、 default ``"unvalidated"`` (provider=None で skip 時)
        ``invariants``: :class:`InvariantFlags`
    """

    # raw metrics
    sr_session_worst_block_scale: float
    sr_session_worst_annual_estimate: float
    net_pnl_after_cost: float
    max_dd: float
    trade_count: int
    session_block_win_rate_worst: float
    # per-bucket diagnostics
    per_bucket_sr: dict[SessionBucket, float]
    per_bucket_wr: dict[SessionBucket, float]
    low_sample_buckets: frozenset[SessionBucket]
    # signed slack
    slack_sharpe: float
    slack_pnl: float
    slack_dd: float
    slack_tc: float
    slack_wr: float
    # aggregate
    gate_worst_gap: float
    gate_pass: bool
    # auxiliary
    log_pf_clip: float
    bucket_validator_version: str
    invariants: InvariantFlags


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


class _BusinessDayUniverseMismatch(Exception):
    """internal: ``compute_session_blocks`` が universe に無い ``business_day_index``
    を検出した場合に raise (caller `evaluate_canonical_five` が catch して
    ``INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH`` reason に変換する)."""


def compute_session_blocks(
    trades: Iterable[TradeRecord],
    business_day_universe: dict[SessionBucket, frozenset[int]],
) -> dict[SessionBucket, list[SessionBlockSummary]]:
    """trade-level PnL を ``(business_day_index, session_bucket)`` 単位の block に集約.

    detail Round 1 [C1] 反映: WR neutral 0.5 規約 (synthesis § 6.3) を本流で
    有効化するため、 ``business_day_universe`` を入力に取り、 trade=0 でも
    空 block (``trade_count_block=0``, ``pnl_net_block=0.0``) を生成する。
    T070 backtest engine が「評価期間で発生し得た全 (bucket, business_day_index)
    ペア」 を ``business_day_universe`` として渡す責務を持つ.

    attribution rule = ``exit_time_utc`` (concept § 重要な設計判断 1):
    すべての trade は ``exit_time_utc`` 時点の ``session_bucket`` /
    ``business_day_index`` に attribute される (T070 が確定済の TradeRecord
    field を信頼).

    Args:
        trades: :class:`TradeRecord` iterable
        business_day_universe: ``{SessionBucket: frozenset[business_day_index]}``
            T070 が evaluation period に含まれる全 (bucket, day) ペアを列挙

    Returns:
        ``{SessionBucket: [SessionBlockSummary, ...]}``
        各 bucket 内 list は ``business_day_index`` 昇順.

    Raises:
        _BusinessDayUniverseMismatch: trade の ``business_day_index`` が
            ``business_day_universe[bucket]`` に存在しない場合
            (caller :func:`evaluate_canonical_five` が catch して reason に変換).
    """
    # Step 1: business_day_universe 全 (bucket, day) ペアで空 block grid を初期化.
    # accum[bucket][day] = (pnl, count) の形で保持する.
    accum: dict[SessionBucket, dict[int, list[float]]] = {}
    for bucket, day_set in business_day_universe.items():
        accum[bucket] = {}
        for day in day_set:
            # list[pnl_net_block, trade_count_block] (mutable accumulator)
            accum[bucket][day] = [0.0, 0]

    # Step 2: trades を走査し、 (trade.session_bucket, trade.business_day_index)
    # の block に pnl_net を加算、 count を +1.
    for t in trades:
        bucket_map = accum.get(t.session_bucket)
        if bucket_map is None or t.business_day_index not in bucket_map:
            # Step 3: universe 未登録 → fail-fast (caller が reason に変換).
            raise _BusinessDayUniverseMismatch(
                f"trade with session_bucket={t.session_bucket.value!r} "
                f"business_day_index={t.business_day_index} not in business_day_universe"
            )
        slot = bucket_map[t.business_day_index]
        slot[0] += t.pnl_net
        slot[1] += 1

    # Step 4: 各 bucket 内を business_day_index 昇順でソートして dataclass 化.
    result: dict[SessionBucket, list[SessionBlockSummary]] = {}
    for bucket, day_map in accum.items():
        sorted_days = sorted(day_map.keys())
        result[bucket] = [
            SessionBlockSummary(
                business_day_index=day,
                session_bucket=bucket,
                pnl_net_block=day_map[day][0],
                trade_count_block=int(day_map[day][1]),
            )
            for day in sorted_days
        ]
    return result


def _hac_long_run_variance(
    series: list[float],
    q: int,
    eps: float,
) -> float:
    """Bartlett kernel HAC long-run variance (Newey-West 1987).

    population formula (mean-centered):
        gamma(0) = (1/n) Σ x_t^2
        gamma(k) = (1/n) Σ_{t=k+1..n} x_t * x_{t-k}, k>=1
        sigma2_LR = gamma(0) + 2 Σ_{k=1..q} (1 - k/(q+1)) * gamma(k)

    n = len(series). 中心化済 (caller で mean を引く)。
    n <= 1 の場合 0.0 を返す。
    """
    n = len(series)
    if n <= 1:
        return 0.0
    # gamma(0): population variance
    gamma_0 = math.fsum(x * x for x in series) / n
    sigma2 = gamma_0
    # k = 1..q
    max_k = min(q, n - 1)
    for k in range(1, max_k + 1):
        weight = 1.0 - k / (q + 1)
        gamma_k = math.fsum(
            series[t] * series[t - k] for t in range(k, n)
        ) / n
        sigma2 += 2.0 * weight * gamma_k
    return max(sigma2, eps)


def compute_sr_session_worst(
    blocks_by_bucket: dict[SessionBucket, list[SessionBlockSummary]],
    q: int = HAC_BARTLETT_DEFAULT_Q,
    eps: float = SIGMA2_LR_EPS,
) -> tuple[float, dict[SessionBucket, float], frozenset[SessionBucket]]:
    """3 bucket の HAC 補正 SR を計算し、 block-scale worst (= min) を返す.

    Bartlett kernel (Newey-West 1987):
        ``gamma_b(k)`` = lag-k autocovariance (population formula、 mean-centered)
        ``sigma2_LR_b = gamma_b(0) + 2 Σ_{k=1..q}((1 - k/(q+1)) * gamma_b(k))``
        ``SR_b = mu_b / sqrt(max(sigma2_LR_b, eps))``

    ガード:
    - bucket が dict に欠損 or block 数 == 0 → ``SR_b = -inf``
      (worst-case fallback、 ``gate_worst_gap`` で fail させる経路、 hard fail はしない)
    - block 数 < ``LOW_SAMPLE_BLOCK_THRESHOLD`` (=30) の bucket は
      ``low_sample_buckets`` に追加
    - block 数 == 1 → ``SR_b = -inf`` (variance 計算不可)

    Returns:
        ``(sr_worst_block, per_bucket_sr_block, low_sample_buckets)``
    """
    per_bucket: dict[SessionBucket, float] = {}
    low_sample: set[SessionBucket] = set()
    # 全 3 bucket を走査 (欠損 bucket も -inf を入れるため)
    for bucket in SessionBucket:
        blocks = blocks_by_bucket.get(bucket, [])
        n = len(blocks)
        if n < LOW_SAMPLE_BLOCK_THRESHOLD:
            low_sample.add(bucket)
        if n == 0 or n == 1:
            per_bucket[bucket] = float("-inf")
            continue
        # mean-centered series
        pnls = [b.pnl_net_block for b in blocks]
        mu = math.fsum(pnls) / n
        centered = [x - mu for x in pnls]
        sigma2 = _hac_long_run_variance(centered, q=q, eps=eps)
        # eps floor で sigma2 > 0 が保証される
        sr = mu / math.sqrt(sigma2)
        per_bucket[bucket] = sr
    sr_worst = min(per_bucket.values())
    return sr_worst, per_bucket, frozenset(low_sample)


def compute_session_block_win_rate_worst(
    blocks_by_bucket: dict[SessionBucket, list[SessionBlockSummary]],
) -> tuple[float, dict[SessionBucket, float]]:
    """3 bucket WR worst (synthesis § 6.3、 trade=0 block は 0.5 neutral).

    各 block で:
        ``if trade_count_block > 0:``
            ``win_{b,t} = 1.0 if pnl_net_block > 0 else 0.0``
        ``else:``
            ``win_{b,t} = 0.5``

    ``WR_b = mean(win_{b,t})``
    bucket 内 block 数 == 0 → ``WR_b = 0.0`` (worst-case fallback、
    ``gate_worst_gap`` で fail).

    Returns:
        ``(wr_worst, per_bucket_wr)``
    """
    per_bucket: dict[SessionBucket, float] = {}
    for bucket in SessionBucket:
        blocks = blocks_by_bucket.get(bucket, [])
        if len(blocks) == 0:
            per_bucket[bucket] = 0.0
            continue
        wins: list[float] = []
        for b in blocks:
            if b.trade_count_block > 0:
                wins.append(1.0 if b.pnl_net_block > 0.0 else 0.0)
            else:
                wins.append(0.5)
        per_bucket[bucket] = math.fsum(wins) / len(wins)
    wr_worst = min(per_bucket.values())
    return wr_worst, per_bucket


def compute_max_dd(bars: BarEquitySeries) -> float:
    """equity series 上の max drawdown を比率で返す.

    値域 (detail Round 1 [C3] / [S3] 反映): **[0.0, 1.0] に clip**。
    1.0 は full drawdown sentinel (全 bar で ``running_max <= 0`` の異常系で割当)。

    手順:
    1. 各 bar を時系列順に走査、 ``running_max = max(running_max, equity_t)`` を更新
    2. ``running_max <= 0`` の bar は drawdown 計算からスキップ (= 寄与 0、
       detail Round 1 [C3])
    3. ``running_max > 0`` の bar:
       ``bar_dd = max(0, (running_max - equity_t)) /
       max(running_max, MAX_DD_DENOM_FLOOR)``
    4. ``max_dd = max_t bar_dd``
    5. 全 bar が ``running_max <= 0`` (有効寄与なし) なら ``max_dd = 1.0``
    6. final clip: ``min(1.0, max(0.0, max_dd))``

    Note: equity が一時的に負値でも数学的に成立。
    ``negative_equity_drop_open`` は invariant flag で別経路、
    max_dd 計算は補助的にしか使われない (gate_pass=False が確定する).
    """
    running_max = -math.inf
    max_dd = 0.0
    has_positive_running_max = False
    for p in bars.points:
        if p.equity > running_max:
            running_max = p.equity
        if running_max <= 0.0:
            # Step 2: skip (drawdown 計算からスキップ)
            continue
        has_positive_running_max = True
        # Step 3: drawdown 計算 (denom floor で zero-division 保護)
        denom = max(running_max, MAX_DD_DENOM_FLOOR)
        bar_dd = max(0.0, running_max - p.equity) / denom
        if bar_dd > max_dd:
            max_dd = bar_dd
    if not has_positive_running_max:
        # Step 5: 全 bar で running_max <= 0 (full drawdown sentinel)
        return 1.0
    # Step 6: clip [0, 1]
    return min(1.0, max(0.0, max_dd))


def slack_to_range(value: float, lower: float, upper: float) -> float:
    """trade_count [L, U] range の signed numerator を返す (denom 化は呼出側).

    sign convention:
        ``value < lower``:                ``return value - lower`` (負値、 不足)
        ``lower <= value <= upper``:      ``return min((value - lower), (upper - value))``
            (正値、 中央余裕最大、 境界 0)
        ``value > upper``:                ``return upper - value`` (負値、 超過)

    Note: synthesis § 6.1 の
    ``slack_tc = slack_to_range(tc, [TC_min, TC_max]) / max(TC_min, 1e-6)``
    に従い、 caller (:func:`compute_signed_slacks`) が
    ``/ max(|TC_min|, DENOM_FLOOR)`` で正規化.
    """
    if value < lower:
        return value - lower
    if value > upper:
        return upper - value
    # lower <= value <= upper
    return min(value - lower, upper - value)


def log_pf_clip(gross_profit: float, gross_loss: float) -> float:
    """log Profit Factor を [-2, 2] に clip (synthesis § 6.4 厳密).

    GP = sum(positive trade ``pnl_net``)、 GL = sum(|negative trade ``pnl_net``|)
    ``log_pf = log((GP + LOG_PF_SMOOTH) / (GL + LOG_PF_SMOOTH))``
    ``return clip(log_pf, -2, 2)``
    """
    gp = max(gross_profit, 0.0) + LOG_PF_SMOOTH
    gl = max(gross_loss, 0.0) + LOG_PF_SMOOTH
    log_pf = math.log(gp / gl)
    lo, hi = LOG_PF_CLIP_RANGE
    return min(hi, max(lo, log_pf))


def compute_signed_slacks(
    sr_worst_block_scale: float,
    net_pnl_after_cost: float,
    max_dd: float,
    trade_count: int,
    session_block_win_rate_worst: float,
    thresholds: CanonicalFiveThresholds,
) -> dict[str, float]:
    """5 指標の signed slack を計算 (synthesis § 6.1 厳密).

    SR annual 換算は本関数内で完結 (concept Round 1 [C2] 反映、 責務単一化):
        ``sharpe_ann_estimate = sr_worst_block_scale * sqrt(N_BLOCKS_PER_YEAR)``

    全 ``denom_floor = DENOM_FLOOR (=1e-6)``.

    Returns:
        ``{
            "sharpe": (sharpe_ann_estimate - sharpe_min) / max(|sharpe_min|, DENOM_FLOOR),
            "pnl":    (net_pnl_after_cost - net_pnl_min) / max(|net_pnl_min|, DENOM_FLOOR),
            "dd":     (max_dd_max - max_dd) / max(max_dd_max, DENOM_FLOOR),
            "tc":     slack_to_range(trade_count, [tc_min, tc_max]) /
                      max(|tc_min|, DENOM_FLOOR),
            "wr":     (wr_worst - win_rate_min) / max(win_rate_min, DENOM_FLOOR),
        }``

    ``sr_worst_block_scale = -inf`` 等の非有限値受領時は
    ``slack_sharpe = -inf`` を返す (fail propagation).
    """
    # SR annual conversion
    if math.isfinite(sr_worst_block_scale):
        sharpe_ann_estimate = sr_worst_block_scale * math.sqrt(N_BLOCKS_PER_YEAR)
    else:
        sharpe_ann_estimate = sr_worst_block_scale  # propagate -inf / inf

    if math.isfinite(sharpe_ann_estimate):
        slack_sharpe = (
            sharpe_ann_estimate - thresholds.sharpe_min
        ) / max(abs(thresholds.sharpe_min), DENOM_FLOOR)
    else:
        # -inf / +inf は除算で値が不安定 → 直接 propagate
        slack_sharpe = sharpe_ann_estimate

    slack_pnl = (
        net_pnl_after_cost - thresholds.net_pnl_min
    ) / max(abs(thresholds.net_pnl_min), DENOM_FLOOR)

    slack_dd = (
        thresholds.max_dd_max - max_dd
    ) / max(thresholds.max_dd_max, DENOM_FLOOR)

    slack_tc = slack_to_range(
        float(trade_count),
        float(thresholds.trade_count_min),
        float(thresholds.trade_count_max),
    ) / max(abs(float(thresholds.trade_count_min)), DENOM_FLOOR)

    slack_wr = (
        session_block_win_rate_worst - thresholds.win_rate_min
    ) / max(thresholds.win_rate_min, DENOM_FLOOR)

    return {
        "sharpe": slack_sharpe,
        "pnl": slack_pnl,
        "dd": slack_dd,
        "tc": slack_tc,
        "wr": slack_wr,
    }


def _validate_trade_attribution(
    trades: Iterable[TradeRecord],
    provider: SessionBucketBoundaryProvider | None,
) -> tuple[bool, str]:
    """provider 注入時に T070 の bucket / business_day attribution を double-check.

    ``provider=None`` なら skip 戻り値 ``(True, "unvalidated")``
    (concept Round 3 [S2] 反映).
    ``provider != None`` なら全 trade を検証、 1 件でも mismatch があれば
    ``(False, provider.version)``.
    """
    if provider is None:
        return True, "unvalidated"
    version = provider.version
    for t in trades:
        if provider.expected_bucket(t.exit_time_utc) != t.session_bucket:
            return False, version
        if provider.expected_business_day_index(t.exit_time_utc) != t.business_day_index:
            return False, version
    return True, version


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def evaluate_canonical_five(
    trades: Iterable[TradeRecord],
    bars: BarEquitySeries,
    thresholds: CanonicalFiveThresholds,
    business_day_universe: dict[SessionBucket, frozenset[int]],
    *,
    bucket_validator: SessionBucketBoundaryProvider | None = None,
    q_bartlett: int = HAC_BARTLETT_DEFAULT_Q,
) -> CanonicalFiveResult:
    """canonical 5 engine top-level entry.

    no-raise 契約の境界 (detail Round 1 [C2] / Round 2 [W2] 反映):
    - **「有効 instance」 = ``__post_init__`` を例外なく通過した frozen dataclass instance**
      (:class:`TradeRecord` / :class:`BarEquityPoint` / :class:`BarEquitySeries` /
      :class:`SessionBlockSummary` / :class:`CanonicalFiveThresholds` 全て同様)。
      caller は dataclass 構築時に raise を捕捉する責務を負う。
    - 本関数の no-raise 契約は **有効 instance 受領後の内部処理** のみ。
      内部 helper (provider call / HAC 計算 / max_dd / signed slack 計算 /
      ``business_day_universe`` mismatch 検出) の例外は catch して
      :class:`InfeasibleReasonCode` に変換、 deterministic な戻り値を保証。

    例外 → :class:`InfeasibleReasonCode` 変換マップ (catch 境界):

    - ``BarEquityInvalidError``: → ``INPUT_INVALID_BAR_SERIES``
    - ``bucket_validator.expected_*()`` 例外: → ``INPUT_BUCKET_VALIDATOR_EXCEPTION``
    - ``bucket_validator`` mismatch (return False): → ``INPUT_BUCKET_ATTRIBUTION_MISMATCH``
    - ``len(trades) == 0``: → ``INPUT_EMPTY_TRADE_LIST``
    - ``business_day_universe`` の任意 bucket key で空集合:
      → ``INPUT_EMPTY_BUSINESS_DAY_UNIVERSE``
    - ``compute_session_blocks`` 内で trade.business_day_index が universe に未登録:
      → ``INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH``

    Args:
        trades: :class:`TradeRecord` iterable
            (T070 が ``session_bucket`` / ``business_day_index`` 確定済).
        bars: :class:`BarEquitySeries` (max_dd 計算用、 構築時に
            sorted/no-dup/UTC-aware/finite 検証済).
        thresholds: :class:`CanonicalFiveThresholds`
            (live_criteria + ``win_rate_min``、 構築時検証済).
        business_day_universe: T070 が確定する
            ``{SessionBucket: frozenset[business_day_index]}``
            (synthesis § 6.3 の trade=0 block neutral 0.5 を有効化するため必須、
            detail Round 1 [C1]).
        bucket_validator: T072 で実装する provider、 None なら attribution check skip.
        q_bartlett: HAC Bartlett lag (default 5、 synthesis 確定値).

    Returns:
        :class:`CanonicalFiveResult` (全 field 必須、 frozen).

    Raises:
        該当なし (有効 instance 受領後の内部処理は no-raise).
    """
    # ------------------------------------------------------------------
    # Step 0: trades を materialize (Iterable は 1 度しか走査できないため)
    # ------------------------------------------------------------------
    trade_list: list[TradeRecord] = list(trades)
    reason_codes: set[InfeasibleReasonCode] = set()

    # ------------------------------------------------------------------
    # Step 1: 空 trade list 検出
    # ------------------------------------------------------------------
    if len(trade_list) == 0:
        reason_codes.add(InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST)

    # ------------------------------------------------------------------
    # Step 2: 空 business_day_universe 検出 (T070 入力契約違反)
    # ------------------------------------------------------------------
    universe_bucket_count_zero = any(
        len(day_set) == 0 for day_set in business_day_universe.values()
    )
    if len(business_day_universe) == 0 or universe_bucket_count_zero:
        reason_codes.add(InfeasibleReasonCode.INPUT_EMPTY_BUSINESS_DAY_UNIVERSE)

    # ------------------------------------------------------------------
    # Step 3: provider double-check (T070 整合性、 例外は catch して reason に変換)
    # ------------------------------------------------------------------
    bucket_validator_version = "unvalidated"
    try:
        attr_ok, bucket_validator_version = _validate_trade_attribution(
            trade_list, bucket_validator
        )
        if not attr_ok:
            reason_codes.add(InfeasibleReasonCode.INPUT_BUCKET_ATTRIBUTION_MISMATCH)
    except Exception:
        reason_codes.add(InfeasibleReasonCode.INPUT_BUCKET_VALIDATOR_EXCEPTION)
        if bucket_validator is not None:
            try:
                bucket_validator_version = bucket_validator.version
            except Exception:
                bucket_validator_version = "unvalidated"

    # ------------------------------------------------------------------
    # Step 4: session blocks 集約 (universe mismatch は catch して reason に変換)
    # ------------------------------------------------------------------
    blocks_by_bucket: dict[SessionBucket, list[SessionBlockSummary]] = {}
    try:
        blocks_by_bucket = compute_session_blocks(trade_list, business_day_universe)
    except _BusinessDayUniverseMismatch:
        reason_codes.add(InfeasibleReasonCode.INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH)
        # 部分集計続行のため、 fallback として空 grid を構築 (universe ベース、 trade は加算しない)
        blocks_by_bucket = {}
        for bucket, day_set in business_day_universe.items():
            blocks_by_bucket[bucket] = [
                SessionBlockSummary(
                    business_day_index=day,
                    session_bucket=bucket,
                    pnl_net_block=0.0,
                    trade_count_block=0,
                )
                for day in sorted(day_set)
            ]

    # ------------------------------------------------------------------
    # Step 5: HAC SR worst (block-scale) + per_bucket_sr + low_sample_buckets
    # ------------------------------------------------------------------
    try:
        sr_worst_block, per_bucket_sr, low_sample_buckets = compute_sr_session_worst(
            blocks_by_bucket, q=q_bartlett, eps=SIGMA2_LR_EPS,
        )
    except Exception:
        # 数値計算で予期せぬ例外 (zero-length series 等) が出ても deterministic に -inf
        reason_codes.add(InfeasibleReasonCode.INPUT_INVALID_BAR_SERIES)
        sr_worst_block = float("-inf")
        per_bucket_sr = {b: float("-inf") for b in SessionBucket}
        low_sample_buckets = frozenset(SessionBucket)

    # ------------------------------------------------------------------
    # Step 6: WR worst + per_bucket_wr
    # ------------------------------------------------------------------
    wr_worst, per_bucket_wr = compute_session_block_win_rate_worst(blocks_by_bucket)

    # ------------------------------------------------------------------
    # Step 7: max_dd (no-raise 内部処理、 例外時は INPUT_INVALID_BAR_SERIES)
    # ------------------------------------------------------------------
    try:
        max_dd_value = compute_max_dd(bars)
    except Exception:
        reason_codes.add(InfeasibleReasonCode.INPUT_INVALID_BAR_SERIES)
        max_dd_value = 1.0  # full drawdown sentinel

    # ------------------------------------------------------------------
    # Step 8-10: aggregate trade-level metrics + log_pf_clip
    # ------------------------------------------------------------------
    pnls = [t.pnl_net for t in trade_list]
    if any(not math.isfinite(x) for x in pnls):
        reason_codes.add(InfeasibleReasonCode.INPUT_NON_FINITE_PNL)
        net_pnl_after_cost = 0.0
    else:
        net_pnl_after_cost = math.fsum(pnls)
    trade_count = len(trade_list)
    gp = math.fsum(x for x in pnls if math.isfinite(x) and x > 0.0)
    gl = math.fsum(-x for x in pnls if math.isfinite(x) and x < 0.0)
    lpf = log_pf_clip(gp, gl)

    # ------------------------------------------------------------------
    # Step 11: signed slacks (annual-scale 換算済)
    # ------------------------------------------------------------------
    slacks = compute_signed_slacks(
        sr_worst_block,
        net_pnl_after_cost,
        max_dd_value,
        trade_count,
        wr_worst,
        thresholds,
    )
    sharpe_ann_estimate = (
        sr_worst_block * math.sqrt(N_BLOCKS_PER_YEAR)
        if math.isfinite(sr_worst_block)
        else sr_worst_block
    )

    # ------------------------------------------------------------------
    # Step 12: gate_worst_gap = max_m max(0, -slack_m)
    # ------------------------------------------------------------------
    gaps: list[float] = []
    for v in slacks.values():
        if math.isfinite(v):
            gaps.append(max(0.0, -v))
        else:
            # -inf → +inf gap、 +inf → 0 gap
            if v == float("-inf"):
                gaps.append(float("inf"))
            else:
                gaps.append(0.0)
    gate_worst_gap = max(gaps) if gaps else 0.0

    # ------------------------------------------------------------------
    # Step 13: invariants (strategic_* 集計 + reason_codes 統合)
    # ------------------------------------------------------------------
    session_close_drop_count = sum(1 for t in trade_list if t.is_session_close_drop)
    negative_equity_drop_open_count = sum(
        1 for t in trade_list if t.is_negative_equity_drop_open
    )
    if session_close_drop_count > 0:
        reason_codes.add(InfeasibleReasonCode.STRATEGIC_SESSION_CLOSE_DROP)
    if negative_equity_drop_open_count > 0:
        reason_codes.add(InfeasibleReasonCode.STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN)
    invariants = InvariantFlags(
        session_close_drop_count=session_close_drop_count,
        negative_equity_drop_open_count=negative_equity_drop_open_count,
        infeasible_reason_codes=frozenset(reason_codes),
    )

    # ------------------------------------------------------------------
    # Step 14: gate_pass = (gate_worst_gap <= GATE_PASS_TOLERANCE) AND is_feasible
    # ------------------------------------------------------------------
    gate_pass = (
        math.isfinite(gate_worst_gap)
        and gate_worst_gap <= GATE_PASS_TOLERANCE
        and invariants.is_feasible
    )

    # ------------------------------------------------------------------
    # Step 15: CanonicalFiveResult を frozen で返す
    # ------------------------------------------------------------------
    return CanonicalFiveResult(
        sr_session_worst_block_scale=sr_worst_block,
        sr_session_worst_annual_estimate=sharpe_ann_estimate,
        net_pnl_after_cost=net_pnl_after_cost,
        max_dd=max_dd_value,
        trade_count=trade_count,
        session_block_win_rate_worst=wr_worst,
        per_bucket_sr=dict(per_bucket_sr),
        per_bucket_wr=dict(per_bucket_wr),
        low_sample_buckets=low_sample_buckets,
        slack_sharpe=slacks["sharpe"],
        slack_pnl=slacks["pnl"],
        slack_dd=slacks["dd"],
        slack_tc=slacks["tc"],
        slack_wr=slacks["wr"],
        gate_worst_gap=gate_worst_gap,
        gate_pass=gate_pass,
        log_pf_clip=lpf,
        bucket_validator_version=bucket_validator_version,
        invariants=invariants,
    )
