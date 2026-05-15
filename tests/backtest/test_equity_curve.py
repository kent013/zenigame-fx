"""EquityCurve / encode-decode / guard のテスト (T105)。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.backtest.equity_curve import (
    SCALE_DECIMAL_PLACES,
    EquityCurve,
    EquityCurveBuilder,
    EquityCurveError,
    EquityScaleError,
    decode_epoch_ns,
    decode_equity,
    encode_epoch_ns,
    encode_equity,
    validate_equity_scale_contract,
)

# ---------------------------------------------------------------------------
# encode / decode equity
# ---------------------------------------------------------------------------


class TestEncodeDecodeEquity:
    def test_roundtrip_is_lossless_for_typical_equity(self) -> None:
        for raw in ("1000000", "1000000.5", "999999.12345", "0", "-4210.5"):
            value = Decimal(raw)
            assert decode_equity(encode_equity(value)) == value

    def test_roundtrip_at_scale_boundary(self) -> None:
        # SCALE_DECIMAL_PLACES 桁ちょうどは lossless
        value = Decimal("1." + "1" * SCALE_DECIMAL_PLACES)
        assert decode_equity(encode_equity(value)) == value

    def test_encode_raises_on_excess_precision(self) -> None:
        # SCALE を 1 桁超える小数 → fail-closed
        value = Decimal("1." + "1" * (SCALE_DECIMAL_PLACES + 1))
        with pytest.raises(EquityScaleError, match="not representable"):
            encode_equity(value)

    def test_encode_raises_on_int64_overflow(self) -> None:
        # equity * 10^SCALE が int64 を超える
        value = Decimal("1e30")
        with pytest.raises(EquityScaleError, match="overflows int64"):
            encode_equity(value)


# ---------------------------------------------------------------------------
# encode / decode epoch
# ---------------------------------------------------------------------------


class TestEncodeDecodeEpoch:
    def test_roundtrip_second_precision(self) -> None:
        dt = datetime(2026, 1, 15, 12, 34, 56, tzinfo=UTC)
        assert decode_epoch_ns(encode_epoch_ns(dt)) == dt

    def test_roundtrip_microsecond_precision(self) -> None:
        dt = datetime(2026, 1, 15, 12, 34, 56, 789_012, tzinfo=UTC)
        assert decode_epoch_ns(encode_epoch_ns(dt)) == dt

    def test_encode_rejects_naive_datetime(self) -> None:
        with pytest.raises(EquityCurveError, match="tz-aware"):
            encode_epoch_ns(datetime(2026, 1, 15, 12, 0, 0))

    def test_encode_normalizes_non_utc_to_utc(self) -> None:
        from datetime import timezone

        jst = timezone(timedelta(hours=9))
        dt_jst = datetime(2026, 1, 15, 21, 0, 0, tzinfo=jst)
        dt_utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        assert encode_epoch_ns(dt_jst) == encode_epoch_ns(dt_utc)

    def test_decode_rejects_sub_microsecond_component(self) -> None:
        # 1000 の非倍数 = sub-microsecond → silent 切り捨てせず reject
        with pytest.raises(EquityCurveError, match="sub-microsecond"):
            decode_epoch_ns(1_000_000_001)


# ---------------------------------------------------------------------------
# validate_equity_scale_contract
# ---------------------------------------------------------------------------


class TestValidateEquityScaleContract:
    def test_passes_silently_when_holding_cost_zero(self) -> None:
        from structlog.testing import capture_logs

        with capture_logs() as logs:
            validate_equity_scale_contract(Decimal("0"))
        assert logs == []  # holding cost 0 では warning なし

    def test_warns_when_holding_cost_positive(self) -> None:
        # hard fail はしない (holding cost は engine の正規機能)。warning で
        # 早期可視化し、実際の lossless 保証は encode_equity の per-bar guard。
        from structlog.testing import capture_logs

        with capture_logs() as logs:
            validate_equity_scale_contract(Decimal("1.5"))
        assert any(
            log.get("event") == "equity_curve.holding_cost_enabled_scale_risk"
            for log in logs
        )


# ---------------------------------------------------------------------------
# EquityCurve 不変条件
# ---------------------------------------------------------------------------


def _curve(times: list[datetime], equities: list[str]) -> EquityCurve:
    return EquityCurve.from_decimal_points(
        list(zip(times, (Decimal(e) for e in equities), strict=True))
    )


class TestEquityCurveInvariants:
    def test_rejects_length_mismatch(self) -> None:
        with pytest.raises(EquityCurveError, match="length mismatch"):
            EquityCurve(
                np.array([1, 2], dtype=np.int64),
                np.array([1], dtype=np.int64),
            )

    def test_rejects_non_increasing_epoch(self) -> None:
        with pytest.raises(EquityCurveError, match="strictly increasing"):
            EquityCurve(
                np.array([2, 1], dtype=np.int64),
                np.array([10, 20], dtype=np.int64),
            )

    def test_rejects_duplicate_epoch(self) -> None:
        with pytest.raises(EquityCurveError, match="strictly increasing"):
            EquityCurve(
                np.array([5, 5], dtype=np.int64),
                np.array([10, 20], dtype=np.int64),
            )

    def test_arrays_are_read_only_after_construction(self) -> None:
        ec = EquityCurve(
            np.array([1, 2], dtype=np.int64),
            np.array([10, 20], dtype=np.int64),
        )
        with pytest.raises(ValueError):
            ec.epoch_ns[0] = 999
        with pytest.raises(ValueError):
            ec.equity_scaled[0] = 999

    def test_is_owned_copy_of_input(self) -> None:
        # 入力 ndarray を後から書き換えても EquityCurve 内部は不変
        epoch_in = np.array([1, 2], dtype=np.int64)
        equity_in = np.array([10, 20], dtype=np.int64)
        ec = EquityCurve(epoch_in, equity_in)
        epoch_in[0] = 999
        equity_in[0] = 999
        assert int(ec.epoch_ns[0]) == 1
        assert int(ec.equity_scaled[0]) == 10

    def test_normalizes_non_int64_dtype(self) -> None:
        # int32 入力でも owned int64 copy に正規化される
        ec = EquityCurve(
            np.array([1, 2], dtype=np.int32),
            np.array([10, 20], dtype=np.int32),
        )
        assert ec.epoch_ns.dtype == np.int64
        assert ec.equity_scaled.dtype == np.int64


# ---------------------------------------------------------------------------
# EquityCurve access
# ---------------------------------------------------------------------------


class TestEquityCurveAccess:
    def test_empty_curve(self) -> None:
        ec = EquityCurve.empty()
        assert ec.is_empty
        assert len(ec) == 0
        assert ec.final_equity() == Decimal(0)

    def test_len_and_equity_at(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        ec = _curve(
            [t0, t0 + timedelta(minutes=1), t0 + timedelta(minutes=2)],
            ["1000000", "1000100.5", "999950.25"],
        )
        assert len(ec) == 3
        assert ec.equity_at(0) == Decimal("1000000")
        assert ec.equity_at(1) == Decimal("1000100.5")
        assert ec.equity_at(-1) == Decimal("999950.25")
        assert ec.final_equity() == Decimal("999950.25")

    def test_time_at_returns_utc_datetime(self) -> None:
        t0 = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
        ec = _curve([t0, t0 + timedelta(minutes=1)], ["1", "2"])
        assert ec.time_at(0) == t0
        assert ec.time_at(1) == t0 + timedelta(minutes=1)

    def test_iter_decimal_roundtrips_points(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        points = [
            (t0, Decimal("1000000")),
            (t0 + timedelta(minutes=1), Decimal("1000050.123")),
        ]
        ec = EquityCurve.from_decimal_points(points)
        assert list(ec.iter_decimal()) == points


# ---------------------------------------------------------------------------
# EquityCurveBuilder
# ---------------------------------------------------------------------------


class TestEquityCurveBuilder:
    def test_build_produces_equity_curve(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        builder = EquityCurveBuilder(2)
        builder.append(t0, Decimal("1000000"))
        builder.append(t0 + timedelta(minutes=1), Decimal("1000100"))
        ec = builder.build()
        assert len(ec) == 2
        assert ec.equity_at(0) == Decimal("1000000")
        assert ec.equity_at(1) == Decimal("1000100")

    def test_build_detects_underfill(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        builder = EquityCurveBuilder(3)
        builder.append(t0, Decimal("1000000"))
        with pytest.raises(EquityCurveError, match="underfill"):
            builder.build()

    def test_append_detects_overfill(self) -> None:
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        builder = EquityCurveBuilder(1)
        builder.append(t0, Decimal("1000000"))
        with pytest.raises(EquityCurveError, match="overfill"):
            builder.append(t0 + timedelta(minutes=1), Decimal("1000100"))

    def test_zero_size_builder_builds_empty_curve(self) -> None:
        ec = EquityCurveBuilder(0).build()
        assert ec.is_empty
