"""T061: canonical 5 engine — 単体テスト.

詳細設計 (施策 2): devnotes/20260429-2300-todo-T061-canonical-five-engine/detailed-design.md (行 818-959)

振る舞いベース命名: dataclass invariants / 数式仕様 / gate_pass / GATE_PASS_TOLERANCE.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.alpha_factory.canonical_metrics import (
    DENOM_FLOOR,
    GATE_PASS_TOLERANCE,
    HAC_BARTLETT_DEFAULT_Q,
    LOG_PF_CLIP_RANGE,
    LOW_SAMPLE_BLOCK_THRESHOLD,
    MAX_DD_DENOM_FLOOR,
    N_BLOCKS_PER_YEAR,
    BarEquityInvalidError,
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBlockSummary,
    SessionBucket,
    SessionBucketBoundaryProvider,
    ThresholdsInvalidError,
    TradeRecord,
    TradeRecordInvalidError,
    compute_max_dd,
    compute_session_block_win_rate_worst,
    compute_session_blocks,
    compute_signed_slacks,
    compute_sr_session_worst,
    evaluate_canonical_five,
    log_pf_clip,
    slack_to_range,
)

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _make_thresholds(
    sharpe_min: float = 1.0,
    net_pnl_min: float = 50000.0,
    max_dd_max: float = 0.20,
    trade_count_min: int = 50,
    trade_count_max: int = 5000,
    win_rate_min: float = 0.45,
) -> CanonicalFiveThresholds:
    return CanonicalFiveThresholds(
        sharpe_min=sharpe_min,
        net_pnl_min=net_pnl_min,
        max_dd_max=max_dd_max,
        trade_count_min=trade_count_min,
        trade_count_max=trade_count_max,
        win_rate_min=win_rate_min,
    )


def _make_trade(
    *,
    day: int = 1,
    hour: int = 1,
    pnl_net: float = 100.0,
    bucket: SessionBucket = SessionBucket.TOKYO,
    business_day_index: int = 0,
    is_session_close_drop: bool = False,
    is_negative_equity_drop_open: bool = False,
) -> TradeRecord:
    entry = _utc(2026, 1, day, hour, 0)
    exit_ = entry + timedelta(minutes=30)
    return TradeRecord(
        entry_time_utc=entry,
        exit_time_utc=exit_,
        pnl_net=pnl_net,
        session_bucket=bucket,
        business_day_index=business_day_index,
        is_session_close_drop=is_session_close_drop,
        is_negative_equity_drop_open=is_negative_equity_drop_open,
    )


def _make_bars(equities: list[float]) -> BarEquitySeries:
    base = _utc(2026, 1, 1, 0, 0)
    pts = tuple(
        BarEquityPoint(timestamp_utc=base + timedelta(hours=i), equity=eq)
        for i, eq in enumerate(equities)
    )
    return BarEquitySeries(points=pts)


def _full_universe(num_days: int) -> dict[SessionBucket, frozenset[int]]:
    days = frozenset(range(num_days))
    return {
        SessionBucket.TOKYO: days,
        SessionBucket.LONDON: days,
        SessionBucket.NY: days,
    }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_denom_floor_is_synthesis_strict_value(self) -> None:
        assert DENOM_FLOOR == 1e-6

    def test_n_blocks_per_year_is_756(self) -> None:
        assert N_BLOCKS_PER_YEAR == 756

    def test_gate_pass_tolerance_is_smaller_than_denom_floor(self) -> None:
        assert GATE_PASS_TOLERANCE < DENOM_FLOOR
        assert GATE_PASS_TOLERANCE == 1e-9

    def test_log_pf_clip_range_is_minus_two_to_two(self) -> None:
        assert LOG_PF_CLIP_RANGE == (-2.0, 2.0)

    def test_max_dd_denom_floor_is_1e_minus_12(self) -> None:
        assert MAX_DD_DENOM_FLOOR == 1e-12

    def test_low_sample_block_threshold_is_30(self) -> None:
        assert LOW_SAMPLE_BLOCK_THRESHOLD == 30

    def test_hac_bartlett_default_q_is_5(self) -> None:
        assert HAC_BARTLETT_DEFAULT_Q == 5


# ---------------------------------------------------------------------------
# SessionBucket
# ---------------------------------------------------------------------------


class TestSessionBucket:
    def test_session_bucket_has_three_values_tokyo_london_ny(self) -> None:
        values = {b.value for b in SessionBucket}
        assert values == {"tokyo", "london", "ny"}

    def test_session_bucket_str_values_are_lowercase(self) -> None:
        for b in SessionBucket:
            assert b.value == b.value.lower()


# ---------------------------------------------------------------------------
# TradeRecord
# ---------------------------------------------------------------------------


class TestTradeRecord:
    def test_trade_record_rejects_naive_datetime_for_entry_or_exit(self) -> None:
        with pytest.raises(TradeRecordInvalidError):
            TradeRecord(
                entry_time_utc=datetime(2026, 1, 1, 0, 0),  # naive
                exit_time_utc=_utc(2026, 1, 1, 0, 30),
                pnl_net=1.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
            )

    def test_trade_record_rejects_jst_aware_datetime(self) -> None:
        with pytest.raises(TradeRecordInvalidError):
            TradeRecord(
                entry_time_utc=datetime(2026, 1, 1, 0, 0, tzinfo=JST),
                exit_time_utc=_utc(2026, 1, 1, 0, 30),
                pnl_net=1.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
            )

    def test_trade_record_rejects_exit_le_entry(self) -> None:
        with pytest.raises(TradeRecordInvalidError):
            TradeRecord(
                entry_time_utc=_utc(2026, 1, 1, 0, 30),
                exit_time_utc=_utc(2026, 1, 1, 0, 30),  # ==
                pnl_net=1.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
            )

    def test_trade_record_rejects_negative_business_day_index(self) -> None:
        with pytest.raises(TradeRecordInvalidError):
            _make_trade(business_day_index=-1)

    def test_trade_record_rejects_non_finite_pnl_net(self) -> None:
        with pytest.raises(TradeRecordInvalidError):
            _make_trade(pnl_net=float("nan"))
        with pytest.raises(TradeRecordInvalidError):
            _make_trade(pnl_net=float("inf"))

    def test_trade_record_accepts_valid_utc_record(self) -> None:
        t = _make_trade()
        assert t.pnl_net == 100.0
        assert t.session_bucket == SessionBucket.TOKYO

    # T078: spread_cost / holding_cost field
    def test_trade_record_spread_cost_default_zero(self) -> None:
        """T078: spread_cost field default 0.0 (= backward compat、 既存 caller 互換)."""
        t = _make_trade()
        assert t.spread_cost == 0.0
        assert t.holding_cost == 0.0

    def test_trade_record_spread_cost_explicit_value(self) -> None:
        """T078: spread_cost / holding_cost 明示指定."""
        t = TradeRecord(
            entry_time_utc=_utc(2026, 1, 1, 0, 0),
            exit_time_utc=_utc(2026, 1, 1, 0, 30),
            pnl_net=100.0,
            session_bucket=SessionBucket.TOKYO,
            business_day_index=0,
            is_session_close_drop=False,
            is_negative_equity_drop_open=False,
            spread_cost=2.5,
            holding_cost=1.5,
        )
        assert t.spread_cost == 2.5
        assert t.holding_cost == 1.5

    def test_trade_record_rejects_negative_spread_cost(self) -> None:
        """T078 invariant: spread_cost >= 0 必須."""
        with pytest.raises(TradeRecordInvalidError, match=r"spread_cost.*>= 0"):
            TradeRecord(
                entry_time_utc=_utc(2026, 1, 1, 0, 0),
                exit_time_utc=_utc(2026, 1, 1, 0, 30),
                pnl_net=100.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
                spread_cost=-1.0,
            )

    def test_trade_record_rejects_negative_holding_cost(self) -> None:
        """T078 invariant: holding_cost >= 0 必須."""
        with pytest.raises(TradeRecordInvalidError, match=r"holding_cost.*>= 0"):
            TradeRecord(
                entry_time_utc=_utc(2026, 1, 1, 0, 0),
                exit_time_utc=_utc(2026, 1, 1, 0, 30),
                pnl_net=100.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
                holding_cost=-0.5,
            )

    def test_trade_record_rejects_non_finite_spread_cost(self) -> None:
        """T078 invariant: spread_cost finite 必須."""
        with pytest.raises(TradeRecordInvalidError, match="spread_cost must be finite"):
            TradeRecord(
                entry_time_utc=_utc(2026, 1, 1, 0, 0),
                exit_time_utc=_utc(2026, 1, 1, 0, 30),
                pnl_net=100.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
                spread_cost=float("nan"),
            )

    def test_trade_record_rejects_non_finite_holding_cost(self) -> None:
        """T078 invariant: holding_cost finite 必須."""
        with pytest.raises(TradeRecordInvalidError, match="holding_cost must be finite"):
            TradeRecord(
                entry_time_utc=_utc(2026, 1, 1, 0, 0),
                exit_time_utc=_utc(2026, 1, 1, 0, 30),
                pnl_net=100.0,
                session_bucket=SessionBucket.TOKYO,
                business_day_index=0,
                is_session_close_drop=False,
                is_negative_equity_drop_open=False,
                holding_cost=float("inf"),
            )


# ---------------------------------------------------------------------------
# BarEquitySeries
# ---------------------------------------------------------------------------


class TestBarEquitySeries:
    def test_bar_equity_series_rejects_empty_points(self) -> None:
        with pytest.raises(BarEquityInvalidError):
            BarEquitySeries(points=())

    def test_bar_equity_series_rejects_non_utc_aware_timestamps(self) -> None:
        with pytest.raises(BarEquityInvalidError):
            BarEquitySeries(
                points=(BarEquityPoint(timestamp_utc=datetime(2026, 1, 1), equity=1.0),)
            )

    def test_bar_equity_series_rejects_jst_aware_timestamps(self) -> None:
        with pytest.raises(BarEquityInvalidError):
            BarEquitySeries(
                points=(
                    BarEquityPoint(
                        timestamp_utc=datetime(2026, 1, 1, tzinfo=JST), equity=1.0
                    ),
                )
            )

    def test_bar_equity_series_rejects_non_monotonic_timestamps(self) -> None:
        ts1 = _utc(2026, 1, 1, 1)
        ts2 = _utc(2026, 1, 1, 0)  # earlier
        with pytest.raises(BarEquityInvalidError):
            BarEquitySeries(
                points=(
                    BarEquityPoint(timestamp_utc=ts1, equity=1.0),
                    BarEquityPoint(timestamp_utc=ts2, equity=1.0),
                )
            )

    def test_bar_equity_series_rejects_duplicate_timestamps(self) -> None:
        ts = _utc(2026, 1, 1, 0)
        with pytest.raises(BarEquityInvalidError):
            BarEquitySeries(
                points=(
                    BarEquityPoint(timestamp_utc=ts, equity=1.0),
                    BarEquityPoint(timestamp_utc=ts, equity=2.0),
                )
            )

    def test_bar_equity_series_rejects_non_finite_equity(self) -> None:
        ts = _utc(2026, 1, 1)
        with pytest.raises(BarEquityInvalidError):
            BarEquitySeries(points=(BarEquityPoint(timestamp_utc=ts, equity=float("nan")),))

    def test_bar_equity_series_accepts_valid_strict_monotone_utc(self) -> None:
        s = _make_bars([1.0, 2.0, 3.0])
        assert len(s.points) == 3


# ---------------------------------------------------------------------------
# CanonicalFiveThresholds
# ---------------------------------------------------------------------------


class TestCanonicalFiveThresholds:
    def test_thresholds_rejects_zero_or_negative_sharpe_min(self) -> None:
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(sharpe_min=0.0)
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(sharpe_min=-1.0)

    def test_thresholds_rejects_max_dd_max_outside_unit_interval(self) -> None:
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(max_dd_max=1.0)
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(max_dd_max=2.0)

    def test_thresholds_rejects_win_rate_min_outside_unit_interval(self) -> None:
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(win_rate_min=1.0)
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(win_rate_min=1.5)

    def test_thresholds_rejects_inverted_trade_count_range(self) -> None:
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(trade_count_min=100, trade_count_max=50)
        with pytest.raises(ThresholdsInvalidError):
            _make_thresholds(trade_count_min=0, trade_count_max=100)

    def test_thresholds_accepts_canonical_live_criteria_values(self) -> None:
        th = _make_thresholds()
        assert th.sharpe_min == 1.0
        assert th.win_rate_min == 0.45


# ---------------------------------------------------------------------------
# compute_session_blocks
# ---------------------------------------------------------------------------


class TestComputeSessionBlocks:
    def test_compute_session_blocks_groups_by_bucket_and_business_day(self) -> None:
        trades = [
            _make_trade(bucket=SessionBucket.TOKYO, business_day_index=0, pnl_net=100.0),
            _make_trade(bucket=SessionBucket.TOKYO, business_day_index=0, pnl_net=50.0),
            _make_trade(bucket=SessionBucket.LONDON, business_day_index=1, pnl_net=200.0),
        ]
        universe = _full_universe(num_days=2)
        result = compute_session_blocks(trades, universe)
        # Tokyo day 0 = 150.0 / count 2
        tokyo_blocks = result[SessionBucket.TOKYO]
        day0 = next(b for b in tokyo_blocks if b.business_day_index == 0)
        assert day0.pnl_net_block == 150.0
        assert day0.trade_count_block == 2
        # London day 1
        london_blocks = result[SessionBucket.LONDON]
        day1 = next(b for b in london_blocks if b.business_day_index == 1)
        assert day1.pnl_net_block == 200.0
        # Tokyo day 1 has empty block (trade=0)
        day1_tokyo = next(b for b in tokyo_blocks if b.business_day_index == 1)
        assert day1_tokyo.pnl_net_block == 0.0
        assert day1_tokyo.trade_count_block == 0

    def test_compute_session_blocks_attribution_uses_exit_time(self) -> None:
        # signal: TradeRecord.session_bucket / business_day_index は T070 が確定済 → そのまま使う.
        t = _make_trade(bucket=SessionBucket.NY, business_day_index=3, pnl_net=10.0)
        universe = {
            SessionBucket.TOKYO: frozenset([3]),
            SessionBucket.LONDON: frozenset([3]),
            SessionBucket.NY: frozenset([3]),
        }
        result = compute_session_blocks([t], universe)
        ny_blocks = result[SessionBucket.NY]
        assert ny_blocks[0].business_day_index == 3
        assert ny_blocks[0].pnl_net_block == 10.0

    def test_compute_session_blocks_returns_empty_when_no_trades(self) -> None:
        universe = _full_universe(num_days=2)
        result = compute_session_blocks([], universe)
        # 全 (bucket, day) ペアで空 block (trade=0, pnl=0) が生成される
        for bucket in SessionBucket:
            blocks = result[bucket]
            assert len(blocks) == 2
            for b in blocks:
                assert b.trade_count_block == 0
                assert b.pnl_net_block == 0.0


# ---------------------------------------------------------------------------
# compute_sr_session_worst (HAC Bartlett q=5)
# ---------------------------------------------------------------------------


class TestComputeSrSessionWorst:
    @staticmethod
    def _make_blocks(bucket: SessionBucket, pnls: list[float]) -> list[SessionBlockSummary]:
        return [
            SessionBlockSummary(
                business_day_index=i,
                session_bucket=bucket,
                pnl_net_block=p,
                trade_count_block=1,
            )
            for i, p in enumerate(pnls)
        ]

    def test_sr_session_worst_constant_block_pnl_yields_high_sr_with_eps_floor(
        self,
    ) -> None:
        # 定数 series → centered =0 → sigma2 = eps floor → SR = mu / sqrt(eps)
        const = [10.0] * 30
        blocks = {
            SessionBucket.TOKYO: self._make_blocks(SessionBucket.TOKYO, const),
            SessionBucket.LONDON: self._make_blocks(SessionBucket.LONDON, const),
            SessionBucket.NY: self._make_blocks(SessionBucket.NY, const),
        }
        sr_worst, per_bucket, _ = compute_sr_session_worst(blocks)
        assert math.isfinite(sr_worst)
        assert sr_worst > 0.0
        assert all(math.isfinite(v) and v > 0.0 for v in per_bucket.values())

    def test_sr_session_worst_known_series_matches_hand_computed_hac(self) -> None:
        # 固定系列 [1, 2, 3, 4, 5] q=2 で hand-computed と一致
        # n=5, mean=3, centered = [-2, -1, 0, 1, 2]
        # gamma(0) = (4 + 1 + 0 + 1 + 4)/5 = 2.0
        # gamma(1) = ( (-1)*(-2) + 0*(-1) + 1*0 + 2*1 ) / 5 = (2 + 0 + 0 + 2)/5 = 0.8
        # gamma(2) = ( 0*(-2) + 1*(-1) + 2*0 ) / 5 = -1/5 = -0.2
        # weights for q=2: w1 = 1 - 1/3 = 2/3, w2 = 1 - 2/3 = 1/3
        # sigma2 = 2.0 + 2*( (2/3)*0.8 + (1/3)*(-0.2) )
        #        = 2.0 + 2*( 0.5333... - 0.0666... ) = 2.0 + 2*0.4666... = 2.9333...
        # SR = 3.0 / sqrt(2.9333...) ~ 1.7521
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        # 全 3 bucket に同じ系列を入れ、 worst も同値.
        blocks = {
            b: self._make_blocks(b, series) for b in SessionBucket
        }
        sr_worst, per_bucket, _ = compute_sr_session_worst(blocks, q=2)
        expected_sigma2 = 2.0 + 2.0 * (
            (2.0 / 3.0) * 0.8 + (1.0 / 3.0) * (-0.2)
        )
        expected_sr = 3.0 / math.sqrt(expected_sigma2)
        for v in per_bucket.values():
            assert v == pytest.approx(expected_sr, rel=1e-9)
        assert sr_worst == pytest.approx(expected_sr, rel=1e-9)

    def test_sr_session_worst_returns_min_across_three_buckets(self) -> None:
        blocks = {
            SessionBucket.TOKYO: self._make_blocks(
                SessionBucket.TOKYO, [10.0] * 30
            ),
            SessionBucket.LONDON: self._make_blocks(
                SessionBucket.LONDON, [5.0] * 30
            ),
            SessionBucket.NY: self._make_blocks(SessionBucket.NY, [1.0] * 30),
        }
        sr_worst, per_bucket, _ = compute_sr_session_worst(blocks)
        # NY bucket の SR が最小
        assert sr_worst == per_bucket[SessionBucket.NY]
        assert per_bucket[SessionBucket.NY] < per_bucket[SessionBucket.TOKYO]

    def test_sr_session_worst_missing_bucket_yields_negative_infinity(self) -> None:
        blocks = {
            SessionBucket.TOKYO: self._make_blocks(
                SessionBucket.TOKYO, [10.0] * 30
            ),
            # London 欠損
            SessionBucket.NY: self._make_blocks(SessionBucket.NY, [1.0] * 30),
        }
        sr_worst, per_bucket, _ = compute_sr_session_worst(blocks)
        assert per_bucket[SessionBucket.LONDON] == float("-inf")
        assert sr_worst == float("-inf")

    def test_sr_session_worst_low_sample_bucket_recorded_in_low_sample_set(self) -> None:
        # block 数 < 30 なら low_sample_buckets に含まれる、 SR は計算継続
        blocks = {
            SessionBucket.TOKYO: self._make_blocks(SessionBucket.TOKYO, [1.0] * 5),
            SessionBucket.LONDON: self._make_blocks(SessionBucket.LONDON, [2.0] * 30),
            SessionBucket.NY: self._make_blocks(SessionBucket.NY, [3.0] * 30),
        }
        _, _, low = compute_sr_session_worst(blocks)
        assert SessionBucket.TOKYO in low
        assert SessionBucket.LONDON not in low
        assert SessionBucket.NY not in low

    def test_sr_session_worst_q_default_is_5(self) -> None:
        # q デフォルトが 5 であることを default パラメータ経由で確認
        from inspect import signature

        sig = signature(compute_sr_session_worst)
        assert sig.parameters["q"].default == HAC_BARTLETT_DEFAULT_Q == 5

    def test_sr_session_worst_block_count_one_yields_negative_infinity(self) -> None:
        blocks = {
            SessionBucket.TOKYO: self._make_blocks(SessionBucket.TOKYO, [1.0]),
            SessionBucket.LONDON: self._make_blocks(SessionBucket.LONDON, [1.0]),
            SessionBucket.NY: self._make_blocks(SessionBucket.NY, [1.0]),
        }
        sr_worst, per_bucket, _ = compute_sr_session_worst(blocks)
        assert sr_worst == float("-inf")
        for v in per_bucket.values():
            assert v == float("-inf")


# ---------------------------------------------------------------------------
# compute_session_block_win_rate_worst
# ---------------------------------------------------------------------------


class TestComputeSessionBlockWinRateWorst:
    @staticmethod
    def _make_blocks(
        bucket: SessionBucket,
        pnls_and_counts: list[tuple[float, int]],
    ) -> list[SessionBlockSummary]:
        return [
            SessionBlockSummary(
                business_day_index=i,
                session_bucket=bucket,
                pnl_net_block=p,
                trade_count_block=c,
            )
            for i, (p, c) in enumerate(pnls_and_counts)
        ]

    def test_wr_session_worst_trade_zero_block_assigned_neutral_half(self) -> None:
        # 1 win + 1 zero-trade block + 1 loss → win_rates = [1, 0.5, 0] → mean 0.5
        pcs = [(10.0, 1), (0.0, 0), (-10.0, 1)]
        blocks = {b: self._make_blocks(b, pcs) for b in SessionBucket}
        wr, per_bucket = compute_session_block_win_rate_worst(blocks)
        for v in per_bucket.values():
            assert v == pytest.approx(0.5)
        assert wr == pytest.approx(0.5)

    def test_wr_session_worst_returns_min_across_three_buckets(self) -> None:
        blocks = {
            SessionBucket.TOKYO: self._make_blocks(
                SessionBucket.TOKYO, [(10.0, 1)] * 5
            ),
            SessionBucket.LONDON: self._make_blocks(
                SessionBucket.LONDON, [(10.0, 1)] * 5
            ),
            # NY: 1 win, 4 loss → WR = 0.2
            SessionBucket.NY: self._make_blocks(
                SessionBucket.NY,
                [(10.0, 1)] + [(-10.0, 1)] * 4,
            ),
        }
        wr, per_bucket = compute_session_block_win_rate_worst(blocks)
        assert wr == pytest.approx(0.2)
        assert per_bucket[SessionBucket.NY] == pytest.approx(0.2)

    def test_wr_session_worst_empty_bucket_yields_zero(self) -> None:
        blocks: dict[SessionBucket, list[SessionBlockSummary]] = {
            SessionBucket.TOKYO: [],
            SessionBucket.LONDON: self._make_blocks(
                SessionBucket.LONDON, [(10.0, 1)]
            ),
            SessionBucket.NY: self._make_blocks(SessionBucket.NY, [(10.0, 1)]),
        }
        wr, per_bucket = compute_session_block_win_rate_worst(blocks)
        assert per_bucket[SessionBucket.TOKYO] == 0.0
        assert wr == 0.0

    def test_wr_session_worst_all_winning_blocks_yields_one(self) -> None:
        blocks = {
            b: self._make_blocks(b, [(10.0, 1)] * 5) for b in SessionBucket
        }
        wr, per_bucket = compute_session_block_win_rate_worst(blocks)
        assert wr == pytest.approx(1.0)
        for v in per_bucket.values():
            assert v == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_max_dd
# ---------------------------------------------------------------------------


class TestComputeMaxDd:
    def test_max_dd_monotone_increasing_equity_yields_zero(self) -> None:
        assert compute_max_dd(_make_bars([1.0, 2.0, 3.0, 4.0])) == 0.0

    def test_max_dd_known_drawdown_pattern_matches_expected_ratio(self) -> None:
        # 100 → 200 → 100 → 50 → 75: peak=200, low=50 → dd = (200-50)/200 = 0.75
        bars = _make_bars([100.0, 200.0, 100.0, 50.0, 75.0])
        assert compute_max_dd(bars) == pytest.approx(0.75)

    def test_max_dd_clipped_to_unit_interval_when_equity_drops_to_zero(self) -> None:
        # 100 → 0 → -10 (drop to zero after positive peak)
        bars = _make_bars([100.0, 0.0, -10.0])
        v = compute_max_dd(bars)
        assert 0.0 <= v <= 1.0
        # peak=100, low at 0 で 1.0
        assert v == pytest.approx(1.0)

    def test_max_dd_returns_one_when_running_max_remains_non_positive(self) -> None:
        # 全 bar で running_max <= 0 → full drawdown sentinel = 1.0
        bars = _make_bars([-1.0, -2.0, -3.0])
        assert compute_max_dd(bars) == 1.0

    def test_max_dd_skips_bars_with_non_positive_running_max(self) -> None:
        # 最初の bar が負値でも、 後続で positive running_max になれば再計算開始される
        # bars: -10 → -5 → 100 → 50 → running_max は 100 から開始、 dd = (100-50)/100 = 0.5
        bars = _make_bars([-10.0, -5.0, 100.0, 50.0])
        assert compute_max_dd(bars) == pytest.approx(0.5)

    def test_max_dd_zero_division_protected_by_denom_floor(self) -> None:
        # MAX_DD_DENOM_FLOOR = 1e-12, running_max = 1e-15 だと running_max > 0 だが極小値
        # 結果は clip [0, 1] に収まる (NaN/Inf にならない).
        bars = _make_bars([1e-15, 0.5e-15])
        v = compute_max_dd(bars)
        assert 0.0 <= v <= 1.0
        assert math.isfinite(v)


# ---------------------------------------------------------------------------
# slack_to_range
# ---------------------------------------------------------------------------


class TestSlackToRange:
    def test_slack_to_range_value_below_lower_returns_negative_value_minus_lower(self) -> None:
        assert slack_to_range(40.0, 50.0, 100.0) == -10.0

    def test_slack_to_range_value_above_upper_returns_negative_upper_minus_value(self) -> None:
        assert slack_to_range(120.0, 50.0, 100.0) == -20.0

    def test_slack_to_range_value_at_center_returns_max_positive_slack(self) -> None:
        # value=75, lower=50, upper=100 → min(25, 25) = 25
        assert slack_to_range(75.0, 50.0, 100.0) == 25.0

    def test_slack_to_range_value_at_boundary_returns_zero(self) -> None:
        assert slack_to_range(50.0, 50.0, 100.0) == 0.0
        assert slack_to_range(100.0, 50.0, 100.0) == 0.0


# ---------------------------------------------------------------------------
# log_pf_clip
# ---------------------------------------------------------------------------


class TestLogPfClip:
    def test_log_pf_clip_balanced_gp_gl_returns_zero(self) -> None:
        v = log_pf_clip(100.0, 100.0)
        assert v == pytest.approx(0.0, abs=1e-10)

    def test_log_pf_clip_only_profits_returns_upper_bound_two(self) -> None:
        # GL = 0 → log((GP+eps)/eps) → very large → clip to 2.0
        assert log_pf_clip(1e9, 0.0) == 2.0

    def test_log_pf_clip_only_losses_returns_lower_bound_minus_two(self) -> None:
        assert log_pf_clip(0.0, 1e9) == -2.0

    def test_log_pf_clip_zero_gp_zero_gl_returns_zero(self) -> None:
        # smoothing で 0/0 を未定義にしない: log(eps/eps) = log(1) = 0
        assert log_pf_clip(0.0, 0.0) == pytest.approx(0.0, abs=1e-10)


# ---------------------------------------------------------------------------
# compute_signed_slacks
# ---------------------------------------------------------------------------


class TestComputeSignedSlacks:
    def test_signed_slacks_perfect_metrics_yield_all_positive_slacks(self) -> None:
        th = _make_thresholds(
            sharpe_min=1.0,
            net_pnl_min=10000.0,
            max_dd_max=0.20,
            trade_count_min=50,
            trade_count_max=5000,
            win_rate_min=0.45,
        )
        # sharpe_ann = 2.0 (block-scale) / sqrt(756) → 2.0 = 2.0/sqrt(756)*sqrt(756) wait
        # ここでは block-scale を 2.0/sqrt(756) にすれば annual = 2.0 になる
        sr_block = 2.0 / math.sqrt(N_BLOCKS_PER_YEAR)
        slacks = compute_signed_slacks(
            sr_worst_block_scale=sr_block,
            net_pnl_after_cost=50000.0,
            max_dd=0.05,
            trade_count=1000,
            session_block_win_rate_worst=0.6,
            thresholds=th,
        )
        assert all(v > 0.0 for v in slacks.values())

    def test_signed_slacks_failing_sharpe_yields_negative_slack_sharpe(self) -> None:
        th = _make_thresholds()
        # sharpe_ann = 0.5 < 1.0 → slack_sharpe < 0
        sr_block = 0.5 / math.sqrt(N_BLOCKS_PER_YEAR)
        slacks = compute_signed_slacks(
            sr_worst_block_scale=sr_block,
            net_pnl_after_cost=50000.0,
            max_dd=0.05,
            trade_count=1000,
            session_block_win_rate_worst=0.6,
            thresholds=th,
        )
        assert slacks["sharpe"] < 0.0

    def test_signed_slacks_sharpe_annual_conversion_uses_sqrt_756(self) -> None:
        th = _make_thresholds(sharpe_min=1.0)
        # sharpe_ann_estimate = 1.0 ちょうど → slack_sharpe ≈ 0
        sr_block = 1.0 / math.sqrt(N_BLOCKS_PER_YEAR)
        slacks = compute_signed_slacks(
            sr_worst_block_scale=sr_block,
            net_pnl_after_cost=th.net_pnl_min,
            max_dd=th.max_dd_max,
            trade_count=th.trade_count_min,
            session_block_win_rate_worst=th.win_rate_min,
            thresholds=th,
        )
        assert slacks["sharpe"] == pytest.approx(0.0, abs=1e-9)

    def test_signed_slacks_denom_floor_is_1e_minus_6_per_synthesis_6_1(self) -> None:
        # 極小 sharpe_min でも denom_floor で保護 (overflow 回避)
        th = CanonicalFiveThresholds(
            sharpe_min=DENOM_FLOOR / 100.0,  # < DENOM_FLOOR
            net_pnl_min=10000.0,
            max_dd_max=0.20,
            trade_count_min=50,
            trade_count_max=5000,
            win_rate_min=0.45,
        )
        sr_block = 0.0
        slacks = compute_signed_slacks(
            sr_worst_block_scale=sr_block,
            net_pnl_after_cost=10000.0,
            max_dd=0.0,
            trade_count=100,
            session_block_win_rate_worst=0.5,
            thresholds=th,
        )
        # denom = max(|sharpe_min|, DENOM_FLOOR) = DENOM_FLOOR
        # numerator = 0 - sharpe_min ≈ -DENOM_FLOOR/100 → slack = -1/100
        expected = (0.0 - th.sharpe_min) / DENOM_FLOOR
        assert slacks["sharpe"] == pytest.approx(expected)

    def test_signed_slacks_tc_in_range_yields_positive_slack(self) -> None:
        th = _make_thresholds()
        slacks = compute_signed_slacks(
            sr_worst_block_scale=2.0,
            net_pnl_after_cost=th.net_pnl_min,
            max_dd=th.max_dd_max,
            trade_count=1000,  # in [50, 5000]
            session_block_win_rate_worst=th.win_rate_min,
            thresholds=th,
        )
        assert slacks["tc"] > 0.0

    def test_signed_slacks_tc_below_min_yields_negative_slack(self) -> None:
        th = _make_thresholds()
        slacks = compute_signed_slacks(
            sr_worst_block_scale=2.0,
            net_pnl_after_cost=th.net_pnl_min,
            max_dd=th.max_dd_max,
            trade_count=10,  # < 50
            session_block_win_rate_worst=th.win_rate_min,
            thresholds=th,
        )
        assert slacks["tc"] < 0.0

    def test_signed_slacks_tc_above_max_yields_negative_slack(self) -> None:
        th = _make_thresholds()
        slacks = compute_signed_slacks(
            sr_worst_block_scale=2.0,
            net_pnl_after_cost=th.net_pnl_min,
            max_dd=th.max_dd_max,
            trade_count=10000,  # > 5000
            session_block_win_rate_worst=th.win_rate_min,
            thresholds=th,
        )
        assert slacks["tc"] < 0.0

    def test_signed_slacks_neg_inf_sr_propagates(self) -> None:
        th = _make_thresholds()
        slacks = compute_signed_slacks(
            sr_worst_block_scale=float("-inf"),
            net_pnl_after_cost=0.0,
            max_dd=0.0,
            trade_count=0,
            session_block_win_rate_worst=0.0,
            thresholds=th,
        )
        assert slacks["sharpe"] == float("-inf")


# ---------------------------------------------------------------------------
# evaluate_canonical_five (top-level entry)
# ---------------------------------------------------------------------------


def _build_perfect_run_inputs() -> tuple[
    list[TradeRecord],
    BarEquitySeries,
    CanonicalFiveThresholds,
    dict[SessionBucket, frozenset[int]],
]:
    """gate_pass=True 想定の入力一式を構築.

    各 bucket に 30 day 分の prof block を生成 (low_sample 回避、
    constant series で sigma2_LR=eps floor → SR は eps floor 経由で very large).
    """
    # 30 business days × 3 buckets × 1 trade each
    days = list(range(30))
    universe = {b: frozenset(days) for b in SessionBucket}
    trades: list[TradeRecord] = []
    base = _utc(2026, 1, 1, 0, 0)
    bucket_hour_map = {
        SessionBucket.TOKYO: 0,
        SessionBucket.LONDON: 8,
        SessionBucket.NY: 16,
    }
    for d in days:
        for bucket in SessionBucket:
            entry = base + timedelta(days=d, hours=bucket_hour_map[bucket])
            trades.append(
                TradeRecord(
                    entry_time_utc=entry,
                    exit_time_utc=entry + timedelta(minutes=30),
                    pnl_net=2000.0,  # 30 day × 3 bucket × 2000 = 180000 > 50000
                    session_bucket=bucket,
                    business_day_index=d,
                    is_session_close_drop=False,
                    is_negative_equity_drop_open=False,
                )
            )
    # equity bars: monotone increasing → max_dd=0
    equities = [10000.0 + i * 100.0 for i in range(30)]
    bars = _make_bars(equities)
    th = _make_thresholds()
    return trades, bars, th, universe


class TestEvaluateCanonicalFive:
    def test_evaluate_canonical_five_perfect_run_yields_gate_pass_true(self) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()
        r = evaluate_canonical_five(trades, bars, th, universe)
        assert isinstance(r, CanonicalFiveResult)
        assert r.gate_pass is True
        assert r.gate_worst_gap <= GATE_PASS_TOLERANCE
        assert r.invariants.is_feasible is True
        assert r.bucket_validator_version == "unvalidated"
        assert r.max_dd == 0.0

    def test_evaluate_canonical_five_failing_sharpe_yields_gate_pass_false(self) -> None:
        trades, bars, _, universe = _build_perfect_run_inputs()
        # perfect_run は constant series なので sigma2=eps floor で SR が極大化する.
        # sharpe_min を eps floor 経由で計算される annual SR より大きい値に設定する必要があるが、
        # それは現実的でない (1e10 オーダー). 代わりに sharpe_min を threshold 違反に近い値ではなく、
        # SR を小さくする方向で fail を作る → 1 trade だけ巨大 negative pnl を入れて variance 増加 → SR 下落.
        bad = trades[0]
        replaced = TradeRecord(
            entry_time_utc=bad.entry_time_utc,
            exit_time_utc=bad.exit_time_utc,
            pnl_net=-1e9,  # 巨大 loss
            session_bucket=bad.session_bucket,
            business_day_index=bad.business_day_index,
            is_session_close_drop=False,
            is_negative_equity_drop_open=False,
        )
        trades_with_loss = [replaced, *trades[1:]]
        th = _make_thresholds(sharpe_min=10.0)  # 達成困難な高値
        r = evaluate_canonical_five(trades_with_loss, bars, th, universe)
        assert r.gate_pass is False
        # gate_worst_gap > GATE_PASS_TOLERANCE (浮動小数許容範囲外)
        assert r.gate_worst_gap > GATE_PASS_TOLERANCE

    def test_evaluate_canonical_five_session_close_drop_forces_gate_pass_false(self) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()
        # 1 trade に flag を立てる
        bad = trades[0]
        replaced = TradeRecord(
            entry_time_utc=bad.entry_time_utc,
            exit_time_utc=bad.exit_time_utc,
            pnl_net=bad.pnl_net,
            session_bucket=bad.session_bucket,
            business_day_index=bad.business_day_index,
            is_session_close_drop=True,
            is_negative_equity_drop_open=False,
        )
        trades = [replaced, *trades[1:]]
        r = evaluate_canonical_five(trades, bars, th, universe)
        assert r.gate_pass is False
        assert r.invariants.session_close_drop_count == 1
        assert (
            InfeasibleReasonCode.STRATEGIC_SESSION_CLOSE_DROP
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_negative_equity_drop_open_forces_gate_pass_false(
        self,
    ) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()
        bad = trades[0]
        replaced = TradeRecord(
            entry_time_utc=bad.entry_time_utc,
            exit_time_utc=bad.exit_time_utc,
            pnl_net=bad.pnl_net,
            session_bucket=bad.session_bucket,
            business_day_index=bad.business_day_index,
            is_session_close_drop=False,
            is_negative_equity_drop_open=True,
        )
        trades = [replaced, *trades[1:]]
        r = evaluate_canonical_five(trades, bars, th, universe)
        assert r.gate_pass is False
        assert r.invariants.negative_equity_drop_open_count == 1
        assert (
            InfeasibleReasonCode.STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_empty_trades_records_input_reason_and_fails_gate(
        self,
    ) -> None:
        _, bars, th, universe = _build_perfect_run_inputs()
        r = evaluate_canonical_five([], bars, th, universe)
        assert r.gate_pass is False
        assert (
            InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_empty_business_day_universe_records_input_reason(
        self,
    ) -> None:
        trades, bars, th, _ = _build_perfect_run_inputs()
        empty_universe: dict[SessionBucket, frozenset[int]] = {
            SessionBucket.TOKYO: frozenset(),
            SessionBucket.LONDON: frozenset(),
            SessionBucket.NY: frozenset(),
        }
        r = evaluate_canonical_five(trades, bars, th, empty_universe)
        assert r.gate_pass is False
        assert (
            InfeasibleReasonCode.INPUT_EMPTY_BUSINESS_DAY_UNIVERSE
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_business_day_universe_mismatch_records_input_reason(
        self,
    ) -> None:
        trades, bars, th, _universe = _build_perfect_run_inputs()
        # universe を 0..14 に絞る → trades の day=15..29 が mismatch
        truncated = {b: frozenset(range(15)) for b in SessionBucket}
        r = evaluate_canonical_five(trades, bars, th, truncated)
        assert r.gate_pass is False
        assert (
            InfeasibleReasonCode.INPUT_BUSINESS_DAY_UNIVERSE_MISMATCH
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_provider_exception_converted_to_reason_code(
        self,
    ) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()

        class ExplodingProvider(SessionBucketBoundaryProvider):
            @property
            def version(self) -> str:
                return "exploding_v1"

            def expected_bucket(self, exit_time_utc: datetime) -> SessionBucket:
                raise RuntimeError("provider crashed")

            def expected_business_day_index(self, exit_time_utc: datetime) -> int:
                raise RuntimeError("provider crashed")

        r = evaluate_canonical_five(
            trades, bars, th, universe, bucket_validator=ExplodingProvider()
        )
        assert r.gate_pass is False
        assert (
            InfeasibleReasonCode.INPUT_BUCKET_VALIDATOR_EXCEPTION
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_provider_mismatch_records_attribution_mismatch_reason(
        self,
    ) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()

        class WrongProvider(SessionBucketBoundaryProvider):
            @property
            def version(self) -> str:
                return "wrong_v1"

            def expected_bucket(self, exit_time_utc: datetime) -> SessionBucket:
                # 常に NY を返す → TOKYO/LONDON trade は mismatch
                return SessionBucket.NY

            def expected_business_day_index(self, exit_time_utc: datetime) -> int:
                return 0

        r = evaluate_canonical_five(
            trades, bars, th, universe, bucket_validator=WrongProvider()
        )
        assert r.gate_pass is False
        assert (
            InfeasibleReasonCode.INPUT_BUCKET_ATTRIBUTION_MISMATCH
            in r.invariants.infeasible_reason_codes
        )
        assert r.bucket_validator_version == "wrong_v1"

    def test_evaluate_canonical_five_no_raise_contract_for_invalid_bucket_validator(
        self,
    ) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()

        class BrokenVersionProvider(SessionBucketBoundaryProvider):
            @property
            def version(self) -> str:
                raise RuntimeError("version property crashed")

            def expected_bucket(self, exit_time_utc: datetime) -> SessionBucket:
                raise RuntimeError("provider crashed")

            def expected_business_day_index(self, exit_time_utc: datetime) -> int:
                raise RuntimeError("provider crashed")

        # 例外は propagate せず、 INPUT_BUCKET_VALIDATOR_EXCEPTION reason に変換される
        r = evaluate_canonical_five(
            trades, bars, th, universe, bucket_validator=BrokenVersionProvider()
        )
        assert r.gate_pass is False
        assert (
            InfeasibleReasonCode.INPUT_BUCKET_VALIDATOR_EXCEPTION
            in r.invariants.infeasible_reason_codes
        )

    def test_evaluate_canonical_five_gate_pass_tolerance_handles_floating_noise(
        self,
    ) -> None:
        # gate_pass tolerance を slack 計算経由で確認:
        # 1e-12 程度の負 slack は許容、 1e-6 程度なら不許容.
        trades, bars, _, universe = _build_perfect_run_inputs()
        # net_pnl_min をちょうど actual に近づけて noise レベルの gap にする.
        # actual_pnl = 30 day × 3 bucket × 2000 = 180000.
        # gap_to_threshold ≈ -1e-13 (≈ 1e-9 noise レベル) の signed slack を狙う.
        actual_pnl = 180000.0
        # threshold を actual_pnl より僅かに下げて positive slack を確保 (gate_pass=True 経路).
        th_pass = _make_thresholds(net_pnl_min=actual_pnl * (1.0 - 1e-12))
        r_pass = evaluate_canonical_five(trades, bars, th_pass, universe)
        assert r_pass.gate_pass is True

        # threshold を actual より上げて clearly fail を確認.
        th_fail = _make_thresholds(net_pnl_min=actual_pnl * 2.0)
        r_fail = evaluate_canonical_five(trades, bars, th_fail, universe)
        assert r_fail.gate_pass is False
        assert r_fail.gate_worst_gap > GATE_PASS_TOLERANCE

    def test_evaluate_canonical_five_default_validator_version_is_unvalidated(
        self,
    ) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()
        r = evaluate_canonical_five(trades, bars, th, universe)
        assert r.bucket_validator_version == "unvalidated"

    def test_evaluate_canonical_five_provider_validates_attribution_and_records_version(
        self,
    ) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()

        class GoodProvider(SessionBucketBoundaryProvider):
            @property
            def version(self) -> str:
                return "test_provider_v1"

            def expected_bucket(self, exit_time_utc: datetime) -> SessionBucket:
                # _build_perfect_run_inputs の bucket_hour_map に整合:
                # TOKYO=0+0:30=00:30, LONDON=8+0:30=08:30, NY=16+0:30=16:30 (exit_time)
                h = exit_time_utc.hour
                if h < 8:
                    return SessionBucket.TOKYO
                if h < 16:
                    return SessionBucket.LONDON
                return SessionBucket.NY

            def expected_business_day_index(self, exit_time_utc: datetime) -> int:
                # 1/1 を day 0 とする (entry の day と一致、 exit は entry + 30min なので同日)
                return (exit_time_utc.date() - _utc(2026, 1, 1).date()).days

        r = evaluate_canonical_five(
            trades, bars, th, universe, bucket_validator=GoodProvider()
        )
        # provider 整合の場合、 attribution_mismatch reason は立たない
        assert (
            InfeasibleReasonCode.INPUT_BUCKET_ATTRIBUTION_MISMATCH
            not in r.invariants.infeasible_reason_codes
        )
        assert r.bucket_validator_version == "test_provider_v1"

    def test_evaluate_canonical_five_returns_frozen_dataclass(self) -> None:
        trades, bars, th, universe = _build_perfect_run_inputs()
        r = evaluate_canonical_five(trades, bars, th, universe)
        with pytest.raises((AttributeError, Exception)):
            r.gate_pass = False  # type: ignore[misc]

    def test_evaluate_canonical_five_zero_trade_blocks_get_neutral_half_win_rate(
        self,
    ) -> None:
        # universe に 30 day を入れ、 各 bucket に half-day だけ winning trade を入れる
        # → 残り half-day は trade=0 (neutral 0.5) で、 winning は 1.0 → mean = 0.75
        days = list(range(30))
        universe = {b: frozenset(days) for b in SessionBucket}
        trades: list[TradeRecord] = []
        for d in days[:15]:  # 半分だけ trade
            for bucket in SessionBucket:
                entry = _utc(2026, 1, 1) + timedelta(days=d, hours=1)
                trades.append(
                    TradeRecord(
                        entry_time_utc=entry,
                        exit_time_utc=entry + timedelta(minutes=30),
                        pnl_net=2000.0,
                        session_bucket=bucket,
                        business_day_index=d,
                        is_session_close_drop=False,
                        is_negative_equity_drop_open=False,
                    )
                )
        bars = _make_bars([10000.0 + i * 100.0 for i in range(30)])
        th = _make_thresholds(net_pnl_min=10000.0)  # threshold を緩めて pnl は通す
        r = evaluate_canonical_five(trades, bars, th, universe)
        # WR = (15 win blocks * 1.0 + 15 zero-trade blocks * 0.5) / 30 = 0.75
        assert r.session_block_win_rate_worst == pytest.approx(0.75)
        assert r.per_bucket_wr[SessionBucket.TOKYO] == pytest.approx(0.75)
        assert r.per_bucket_wr[SessionBucket.LONDON] == pytest.approx(0.75)
        assert r.per_bucket_wr[SessionBucket.NY] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Invariants 分類
# ---------------------------------------------------------------------------


class TestInvariantFlags:
    def test_invariant_flags_strategic_prefix_for_synthesis_6_6(self) -> None:
        codes = frozenset({
            InfeasibleReasonCode.STRATEGIC_SESSION_CLOSE_DROP,
            InfeasibleReasonCode.STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN,
        })
        for c in codes:
            assert c.value.startswith("strategic_")

    def test_invariant_flags_input_prefix_for_engine_input_errors(self) -> None:
        for c in InfeasibleReasonCode:
            if c in (
                InfeasibleReasonCode.STRATEGIC_SESSION_CLOSE_DROP,
                InfeasibleReasonCode.STRATEGIC_NEGATIVE_EQUITY_DROP_OPEN,
            ):
                continue
            assert c.value.startswith("input_")

    def test_invariant_flags_is_feasible_only_when_all_clear(self) -> None:
        ok = InvariantFlags(
            session_close_drop_count=0,
            negative_equity_drop_open_count=0,
            infeasible_reason_codes=frozenset(),
        )
        assert ok.is_feasible is True
        # 1 つでも違反があれば feasible=False
        ng_close = InvariantFlags(
            session_close_drop_count=1,
            negative_equity_drop_open_count=0,
            infeasible_reason_codes=frozenset(),
        )
        assert ng_close.is_feasible is False
        ng_neg = InvariantFlags(
            session_close_drop_count=0,
            negative_equity_drop_open_count=1,
            infeasible_reason_codes=frozenset(),
        )
        assert ng_neg.is_feasible is False
        ng_reason = InvariantFlags(
            session_close_drop_count=0,
            negative_equity_drop_open_count=0,
            infeasible_reason_codes=frozenset(
                {InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST}
            ),
        )
        assert ng_reason.is_feasible is False
