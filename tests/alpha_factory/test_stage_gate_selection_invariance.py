"""T028 selection outcome invariance テスト。

broker-snapshot-caching (T028) 導入前後で Stage A 通過判定が bit-identical で
あることを直接検証する。実際の DslStrategy + ConstantPrimitiveEvaluator +
run_backtest + evaluate_stage_a を通して PortfolioSnapshot の数値が GA
selection に影響しないことを保証する。

cache 有効化 (デフォルト) と cache 無効化 (monkeypatch で
MockBroker._snapshot_at を cache を一切書かない版に差し替え) の 2 経路で
StageResult.passed / fitness_pen / trade_sharpe_raw / trade_count が完全一致
することを assert する。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest

from src.alpha_factory.stage_gate import (
    StageGateConfig,
    StageResult,
    evaluate_stage_a,
)
from src.backtest.engine import BacktestConfig
from src.broker.mock import MockBroker
from src.broker.orders import PortfolioSnapshot
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from tests._helpers import usd_jpy_meta


def _make_oscillating_bars(n_days: int, bars_per_day: int = 4) -> list[PriceBar]:
    """value が 1 bar ごとに up/down する bars (取引によって PnL が出やすい)。"""
    bars: list[PriceBar] = []
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    n = 0
    for d in range(n_days):
        for h in range(bars_per_day):
            t = base + timedelta(days=d, hours=h * (24 // max(bars_per_day, 1)))
            offset = (n % 4) - 2
            base_price = Decimal("154.00") + Decimal(offset) * Decimal("0.05")
            bid_close = base_price
            ask_close = base_price + Decimal("0.01")
            bars.append(
                PriceBar(
                    pair_name="USD_JPY",
                    bar_time=t,
                    bid=Ohlc(bid_close, bid_close, bid_close, bid_close),
                    ask=Ohlc(ask_close, ask_close, ask_close, ask_close),
                    volume=10,
                    complete=True,
                )
            )
            n += 1
    return bars


class _AlternatingEvaluator:
    """bar idx ごとに 1.0 / 0.0 を交互に返す evaluator (entry → exit パターン)。"""

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        cycle = idx % 4
        if cycle == 0:
            return 1.0
        if cycle == 1:
            return 0.1
        return 0.0


def _one_clause_genome(name: str = "g") -> Genome:
    return Genome(
        name=name,
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="D1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2027, 1, 1, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        max_spread_bps=Decimal("100"),
        holding_cost_per_day_bps=Decimal("0"),
        session_close_utc_hours=frozenset({23}),
    )


def _payload(result: StageResult) -> dict[str, Any]:
    env = cast(dict[str, Any], dict(result.metrics))
    return cast(dict[str, Any], env["payload"])


def _snapshot_at_no_cache(
    self: MockBroker, bar: PriceBar
) -> PortfolioSnapshot:
    """Cache を使わない _snapshot_at の置き換え実装。

    cache 書き込み / 読み取り経路を完全に skip し、毎回ゼロから compute する。
    cache 有無で bit-identical を検証するための test 用フック。既存の compute
    ロジックと完全に同一の演算順序を維持する。
    """
    unrealized = sum(
        (self._unrealized_pnl(p, bar) for p in self._positions.values()),
        Decimal(0),
    )
    equity = self._cash + unrealized
    margin_used = sum(
        (p.entry_margin for p in self._positions.values()), Decimal(0),
    )
    margin_level: Decimal | None = None
    if margin_used > 0:
        margin_level = equity / margin_used * Decimal(100)
    return PortfolioSnapshot(
        cash=self._cash,
        equity=equity,
        margin_used=margin_used,
        margin_level_pct=margin_level,
        positions=tuple(self._positions.values()),
    )


@pytest.fixture
def no_cache_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """MockBroker._snapshot_at を cache を使わない版に差し替える。"""
    monkeypatch.setattr(MockBroker, "_snapshot_at", _snapshot_at_no_cache)


def test_stage_a_outcome_bit_identical_with_and_without_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage A 評価が cache 有効 / 無効で完全一致することを検証する。

    - passed / reason_codes が一致
    - payload の fitness_raw / fitness_pen / trade_sharpe_raw / trade_count / threshold
      が bit-identical
    """
    bars = _make_oscillating_bars(5, bars_per_day=4)
    ev = _AlternatingEvaluator()
    cfg = _backtest_config()
    stage_cfg = StageGateConfig()

    # 1) cache enabled (default MockBroker implementation)
    res_with_cache = evaluate_stage_a(
        _one_clause_genome("g_cache_on"),
        bars,
        usd_jpy_meta(),
        cfg,
        ev,
        stage_cfg,
    )

    # 2) cache disabled: monkeypatch _snapshot_at to never cache
    monkeypatch.setattr(MockBroker, "_snapshot_at", _snapshot_at_no_cache)
    res_without_cache = evaluate_stage_a(
        _one_clause_genome("g_cache_off"),
        bars,
        usd_jpy_meta(),
        cfg,
        ev,
        stage_cfg,
    )

    # passed / reason が一致
    assert res_with_cache.passed == res_without_cache.passed
    assert res_with_cache.reason_codes == res_without_cache.reason_codes

    # payload の数値が完全一致 (bit-identical)
    p_on = _payload(res_with_cache)
    p_off = _payload(res_without_cache)
    for key in ("fitness_raw", "fitness_pen", "trade_sharpe_raw", "trade_count", "threshold", "size_norm", "alpha_a"):
        assert p_on[key] == p_off[key], (
            f"payload[{key!r}] mismatch: cache_on={p_on[key]!r} "
            f"cache_off={p_off[key]!r}"
        )


def test_stage_a_trade_count_bit_identical_with_and_without_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """trade_count が cache 有無で一致することの独立 assert。"""
    bars = _make_oscillating_bars(7, bars_per_day=4)
    ev = _AlternatingEvaluator()
    cfg = _backtest_config()
    stage_cfg = StageGateConfig()

    res_with_cache = evaluate_stage_a(
        _one_clause_genome("g_tc_on"),
        bars,
        usd_jpy_meta(),
        cfg,
        ev,
        stage_cfg,
    )

    monkeypatch.setattr(MockBroker, "_snapshot_at", _snapshot_at_no_cache)
    res_without_cache = evaluate_stage_a(
        _one_clause_genome("g_tc_off"),
        bars,
        usd_jpy_meta(),
        cfg,
        ev,
        stage_cfg,
    )

    p_on = _payload(res_with_cache)
    p_off = _payload(res_without_cache)
    assert p_on["trade_count"] == p_off["trade_count"]
    # trade_sharpe_raw も一致 (trade_count が同じなら sharpe も bit-identical のはず)
    assert p_on["trade_sharpe_raw"] == p_off["trade_sharpe_raw"]
