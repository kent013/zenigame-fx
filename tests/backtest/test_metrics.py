from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.backtest.equity_curve import EquityCurve, decode_equity
from src.backtest.metrics import (
    SHARPE_CALC_VERSION_V2,
    compute_metrics,
)
from src.broker.orders import Trade


def _trade(
    pnl: Decimal,
    pid: int = 1,
    equity_at_entry: Decimal = Decimal("1000000"),
) -> Trade:
    entry = datetime(2026, 4, 1, tzinfo=UTC) + timedelta(minutes=pid)
    return Trade(
        position_id=pid,
        instrument="USD_JPY",
        side="long",
        units=10000,
        entry_price=Decimal("154.000"),
        entry_time=entry,
        exit_price=Decimal("154.000") + pnl / Decimal(10000),
        exit_time=entry + timedelta(minutes=10),
        pnl=pnl,
        exit_reason="signal",
        equity_at_entry=equity_at_entry,
    )


def test_win_rate_and_profit_factor() -> None:
    trades = [_trade(Decimal("100"), 1), _trade(Decimal("-50"), 2), _trade(Decimal("200"), 3)]
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    assert m.trade_count == 3
    assert m.win_count == 2
    assert m.loss_count == 1
    assert m.win_rate == Decimal(2) / Decimal(3)
    assert m.total_pnl == Decimal("250")
    assert m.profit_factor == Decimal("300") / Decimal("50")


def test_profit_factor_is_none_when_no_losses() -> None:
    trades = [_trade(Decimal("100")), _trade(Decimal("50"))]
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    assert m.profit_factor is None


def test_max_drawdown_on_rising_then_falling_curve() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = EquityCurve.from_decimal_points(
        [
            (base + timedelta(minutes=i), Decimal(v))
            for i, v in enumerate([1000, 1200, 1500, 1100, 900, 950])
        ]
    )
    m = compute_metrics([], curve)
    # ピーク 1500 → トラフ 900 → DD 600、pct = 600/1500 * 100 = 40
    assert m.max_drawdown == Decimal("600")
    assert m.max_drawdown_pct == Decimal("600") / Decimal("1500") * Decimal("100")


def test_max_drawdown_zero_on_monotonic_rise() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = EquityCurve.from_decimal_points(
        [
            (base + timedelta(minutes=i), Decimal(v))
            for i, v in enumerate([1000, 1100, 1200])
        ]
    )
    m = compute_metrics([], curve)
    assert m.max_drawdown == Decimal(0)


# ---------------------------------------------------------------------------
# T-sharpe Phase 1A: trade-level Sharpe (`trade_sharpe_raw`) のテスト
# ---------------------------------------------------------------------------


def _make_trades(n: int, pnl_pattern: list[Decimal] | None = None) -> list[Trade]:
    """N 個の Trade を生成する。pnl_pattern を循環適用する。"""
    if pnl_pattern is None:
        pnl_pattern = [Decimal("100"), Decimal("-30")]
    return [
        _trade(pnl_pattern[i % len(pnl_pattern)], pid=i + 1)
        for i in range(n)
    ]


def test_trade_sharpe_raw_returns_none_when_trade_count_below_minimum() -> None:
    """trade_count < trade_count_min_for_sharpe → None (sample-size guard)."""
    trades = _make_trades(20)  # default 30 未満
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    assert m.trade_sharpe_raw is None


def test_trade_sharpe_raw_returns_value_with_sufficient_trades() -> None:
    """trade_count >= 30 + 分散有 → 有限値の trade_sharpe_raw."""
    trades = _make_trades(30)
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    assert m.trade_sharpe_raw is not None
    # win=15, loss=15, mean>0 だが std>0 なので有限
    val = float(m.trade_sharpe_raw)
    assert val == val  # not NaN


def test_trade_sharpe_raw_matches_manual_calculation() -> None:
    """式の厳密検証: 固定 returns 列で mean / std を手計算と照合する."""
    import math
    # 30 trade、equity_at_entry=1_000_000 一定で returns = pnl / 1_000_000
    pnls = [Decimal(str(p)) for p in [
        100.0, -50.0, 200.0, -30.0, 150.0,
        -80.0, 120.0, -40.0, 90.0, -20.0,
        110.0, -60.0, 180.0, -10.0, 70.0,
        -90.0, 140.0, -100.0, 130.0, -25.0,
        160.0, -55.0, 95.0, -35.0, 105.0,
        -45.0, 175.0, -65.0, 115.0, -75.0,
    ]]
    trades = [_trade(p, pid=i + 1) for i, p in enumerate(pnls)]
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    rets = [float(p) / 1_000_000 for p in pnls]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    std = math.sqrt(var)
    expected = mean / std
    assert m.trade_sharpe_raw is not None
    assert float(m.trade_sharpe_raw) == pytest.approx(expected, rel=1e-9)


def test_trade_sharpe_raw_returns_none_when_std_is_zero() -> None:
    """全 trade pnl が同じ → std=0 → None."""
    trades = [_trade(Decimal("100"), pid=i + 1) for i in range(35)]
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    assert m.trade_sharpe_raw is None


def test_trade_sharpe_raw_skips_trades_with_zero_equity_at_entry() -> None:
    """equity_at_entry=0 の trade はスキップされる (warning + 計算除外)."""
    trades = [
        _trade(Decimal("100"), pid=1, equity_at_entry=Decimal(0)),
        _trade(Decimal("-50"), pid=2, equity_at_entry=Decimal(0)),
    ]
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    # 全 trade スキップ → returns 空 → None
    assert m.trade_sharpe_raw is None


def test_trade_sharpe_raw_threshold_override() -> None:
    """trade_count_min_for_sharpe を低くすると 2 trade でも計算される."""
    trades = _make_trades(2)
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve, trade_count_min_for_sharpe=2)
    assert m.trade_sharpe_raw is not None


def test_compute_metrics_sharpe_calc_version_is_v2() -> None:
    """sharpe_calc_version は常に v2_trade_level."""
    trades = _make_trades(35)
    curve = EquityCurve.from_decimal_points(
        [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    )
    m = compute_metrics(trades, curve)
    assert m.sharpe_calc_version == SHARPE_CALC_VERSION_V2


def test_compute_metrics_legacy_sharpe_still_populated_for_backward_compat() -> None:
    """v1 bar-level sharpe は Phase 2 まで埋め続ける (非 AF consumer 後方互換)."""
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = EquityCurve.from_decimal_points(
        [
            (base + timedelta(minutes=i), Decimal(str(1_000_000 + i * 100)))
            for i in range(50)
        ]
    )
    m = compute_metrics([], curve)
    assert m.sharpe is not None  # v1 bar-level Sharpe は equity_curve から計算される


# ---------------------------------------------------------------------------
# T105: EquityCurve 移行の shadow / tie-break / serialized parity テスト
# ---------------------------------------------------------------------------


def _decimal_reference_metrics(
    points: list[tuple[datetime, Decimal]],
) -> dict[str, Decimal | None]:
    """旧 list[(datetime, Decimal)] ベースの pure-Decimal 参照実装。

    T105 改修前の compute_metrics の gate-feeding 指標ロジックをそのまま
    インライン展開したもの。新実装 (EquityCurve 経由) がこれと bit-exact
    一致することを shadow test で固定する。
    """
    max_drawdown = Decimal(0)
    max_drawdown_pct = Decimal(0)
    peak = Decimal(0)
    for _, equity in points:
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = peak - equity
            if dd > max_drawdown:
                max_drawdown = dd
                max_drawdown_pct = dd / peak * Decimal(100)
    final_equity = points[-1][1] if points else Decimal(0)
    # calmar (旧 _calmar 相当)
    calmar: Decimal | None = None
    if len(points) >= 2 and max_drawdown_pct != 0:
        start_time, start_equity = points[0]
        end_time, end_equity = points[-1]
        if start_equity > 0:
            period_days = (end_time - start_time).total_seconds() / 86400
            if period_days > 0:
                total_return_pct = (
                    (end_equity - start_equity) / start_equity * Decimal(100)
                )
                annual_return_pct = (
                    total_return_pct * Decimal(365) / Decimal(str(period_days))
                )
                calmar = annual_return_pct / max_drawdown_pct
    return {
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "final_equity": final_equity,
        "calmar": calmar,
    }


def _varied_equity_points() -> list[tuple[datetime, Decimal]]:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    # 上昇 → ドローダウン → 回復 → 再ドローダウン、 端数小数を含む
    values = [
        "1000000", "1000123.45", "1000500", "1000200.5", "999800.25",
        "1001000", "1000750.75", "1002000", "1001234.5", "1003000.125",
    ]
    return [
        (base + timedelta(minutes=i), Decimal(v)) for i, v in enumerate(values)
    ]


def test_compute_metrics_gate_feeding_metrics_match_decimal_reference() -> None:
    """shadow test: gate-feeding 指標 (max_drawdown / max_drawdown_pct /
    final_equity / calmar) が旧 pure-Decimal 参照実装と value bit-exact 一致。"""
    points = _varied_equity_points()
    ref = _decimal_reference_metrics(points)
    m = compute_metrics([], EquityCurve.from_decimal_points(points))
    assert m.max_drawdown == ref["max_drawdown"]
    assert m.max_drawdown_pct == ref["max_drawdown_pct"]
    assert m.final_equity == ref["final_equity"]
    assert m.calmar == ref["calmar"]


def test_compute_metrics_gate_feeding_metrics_serialized_float_parity() -> None:
    """serialized parity: archive は max_drawdown_pct 等を float64 で保存する。
    新実装の float() 変換が旧参照実装と完全一致することを固定する。"""
    points = _varied_equity_points()
    ref = _decimal_reference_metrics(points)
    m = compute_metrics([], EquityCurve.from_decimal_points(points))
    assert float(m.max_drawdown) == float(ref["max_drawdown"])  # type: ignore[arg-type]
    assert float(m.max_drawdown_pct) == float(ref["max_drawdown_pct"])  # type: ignore[arg-type]
    assert float(m.final_equity) == float(ref["final_equity"])  # type: ignore[arg-type]
    assert m.calmar is not None and ref["calmar"] is not None
    assert float(m.calmar) == float(ref["calmar"])
    # max_drawdown_pct / calmar は除算結果 → Decimal context で正規化され
    # 文字列表現も一致する (Codex 詳細 R1 [Warning] serialized parity)。
    assert str(m.max_drawdown_pct) == str(ref["max_drawdown_pct"])
    assert str(m.calmar) == str(ref["calmar"])


def test_max_drawdown_tie_break_equal_dd_different_peak() -> None:
    """同一 max_dd 絶対額が異なる peak で複数回出現する系列で、整数経路が
    「最初に最大 dd を達成した点の peak」を選ぶ現行 strict 比較挙動を維持する
    (Codex 詳細 R1 [Warning] tie-break 固定)。"""
    base = datetime(2026, 4, 1, tzinfo=UTC)
    # peak=1000 → dd=100 (peak 1000)、その後 peak=2000 → dd=100 (peak 2000)。
    # 旧 strict `dd > max_dd` は最初の dd=100 (peak=1000) を採り、
    # max_drawdown_pct = 100/1000*100 = 10。 後の dd=100 (peak=2000、5%) では
    # 更新されない。
    values = ["1000", "900", "1000", "2000", "1900", "2000"]
    points = [
        (base + timedelta(minutes=i), Decimal(v)) for i, v in enumerate(values)
    ]
    ref = _decimal_reference_metrics(points)
    m = compute_metrics([], EquityCurve.from_decimal_points(points))
    assert m.max_drawdown == Decimal("100")
    # tie-break: 最初の peak=1000 を採用 → pct = 10 (5 ではない)
    assert m.max_drawdown_pct == Decimal("100") / Decimal("1000") * Decimal(100)
    assert m.max_drawdown_pct == ref["max_drawdown_pct"]


def test_max_drawdown_no_int64_overflow_near_boundary() -> None:
    """max_drawdown 整数経路が int64 境界近傍値で wrap しない。

    peak が +2^62、trough が -2^62 のとき dd = 2^63 で int64 を 1 超える。
    np.int64 のままだと silent wrap して負値になるが、ループ先頭の
    int() 変換 (Python 任意精度 int) により正しく計算される
    (Codex impl-review Round 1 [Warning] 反映)。
    """
    big = 2**62
    # epoch は ns 精度 (1000 の倍数)。decode_epoch_ns の sub-microsecond
    # reject に掛からない値を使う。
    epoch = np.array([1_000_000_000, 2_000_000_000], dtype=np.int64)
    equity_scaled = np.array([big, -big], dtype=np.int64)
    ec = EquityCurve(epoch, equity_scaled)
    m = compute_metrics([], ec)
    assert m.max_drawdown == decode_equity(2 * big)  # = 2^63、wrap なし
    assert m.max_drawdown > 0  # wrap していれば負値になる
