"""DslStrategy.prepare() による O(N²)→O(N) 最適化の等価性テスト。

run_backtest は strategy が ``prepare(bars)`` を持つ場合、bars 全体を渡して
事前計算させる。primitive が look-ahead bias-free な前提で、prepared 経路と
従来 per-bar 経路は**同一の trade / equity** を生成する必要がある。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered
from src.backtest.engine import BacktestConfig, run_backtest
from src.broker.mock import MockBroker
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests._helpers import usd_jpy_meta


def _bar(i: int, base: Decimal) -> PriceBar:
    # 2 日跨ぐ bar (intraday 絶対制約を満たす)
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=i)
    # sin-like 波を価格に乗せて signal を動かす
    import math

    offset = Decimal(str(round(math.sin(i / 30.0) * 0.5, 5)))
    mid = base + offset
    bid = mid - Decimal("0.005")
    ask = mid + Decimal("0.005")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(bid, bid + Decimal("0.001"), bid - Decimal("0.001"), bid),
        ask=Ohlc(ask, ask + Decimal("0.001"), ask - Decimal("0.001"), ask),
        volume=10,
        complete=True,
    )


def _make_genome() -> Genome:
    # F1 TrendEMA (TREND_FOLLOW)
    return Genome(
        name="g_prep",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F1",
                        weight=1.0,
                        params={"fast_n": 5, "slow_n": 20, "atr_n": 10},
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.1, exit_threshold=0.05, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _cfg() -> BacktestConfig:
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        max_spread_bps=Decimal("10"),
        session_close_utc_hours=frozenset({21}),
        bar_minutes=1,
    )


def _bars(n: int) -> list[PriceBar]:
    return [_bar(i, Decimal("154.00")) for i in range(n)]


class _StripPreparedEvaluator:
    """RegistryEvaluator をラップして ``evaluate_all_bars`` を隠す.

    DslStrategy.prepare() は ``hasattr(evaluator, 'evaluate_all_bars')`` を見て
    fast-path に入るかを判定するため、このラッパを差し込むと per-bar 経路に
    強制できる。等価性検証の control 用。
    """

    def __init__(self, inner: RegistryEvaluator) -> None:
        self._inner = inner

    def evaluate(self, bars, idx, signal):  # type: ignore[no-untyped-def]
        return self._inner.evaluate(bars, idx, signal)


def test_prepare_produces_identical_trades_to_per_bar_path() -> None:
    ensure_registered()
    bars = _bars(400)  # 400 bars, intraday 跨ぎ
    genome = _make_genome()
    cfg = _cfg()
    meta = usd_jpy_meta()

    # Fast path (prepare 経由)
    ev_fast = RegistryEvaluator(pair="USD_JPY")
    strat_fast = DslStrategy(genome, ev_fast)
    broker_fast = MockBroker(instrument_meta=meta)
    result_fast = run_backtest(bars, strat_fast, broker_fast, cfg)

    # Slow path (per-bar evaluate、同一 evaluator だが evaluate_all_bars を隠す)
    ev_slow = _StripPreparedEvaluator(RegistryEvaluator(pair="USD_JPY"))
    strat_slow = DslStrategy(genome, ev_slow)
    broker_slow = MockBroker(instrument_meta=meta)
    result_slow = run_backtest(bars, strat_slow, broker_slow, cfg)

    # prepare 経路が使われたことを確認 (Cycle 2 / T029 で _prepared に移行)
    assert strat_fast._prepared is not None
    assert strat_slow._prepared is None

    # trade 件数・最終 equity が一致
    assert len(result_fast.trades) == len(result_slow.trades)
    assert (
        broker_fast.snapshot().equity == broker_slow.snapshot().equity
    ), f"equity mismatch: fast={broker_fast.snapshot().equity} vs slow={broker_slow.snapshot().equity}"

    # 各 trade の entry/exit 時刻・side・units が一致
    for tf, ts in zip(result_fast.trades, result_slow.trades, strict=True):
        assert tf.entry_time == ts.entry_time
        assert tf.exit_time == ts.exit_time
        assert tf.side == ts.side
        assert tf.units == ts.units
        assert tf.entry_price == ts.entry_price
        assert tf.exit_price == ts.exit_price


def test_prepare_noop_when_evaluator_lacks_evaluate_all_bars() -> None:
    """evaluate_all_bars を持たない evaluator では prepare は NoOp (live feed 互換)。"""
    ensure_registered()
    bars = _bars(200)
    genome = _make_genome()

    ev = _StripPreparedEvaluator(RegistryEvaluator(pair="USD_JPY"))
    strat = DslStrategy(genome, ev)
    # prepare 呼んでも prepared は埋まらない (Cycle 2 / T029)
    strat.prepare(bars)
    assert strat._prepared is None


def test_prepare_reuses_cache_across_duplicate_signals() -> None:
    """同一 (name, params) の signal が複数 clause に現れても compute_all_bars は 1 回だけ。"""
    ensure_registered()
    bars = _bars(100)

    call_count = {"n": 0}

    class CountingEvaluator:
        def __init__(self) -> None:
            self._inner = RegistryEvaluator(pair="USD_JPY")

        def evaluate(self, bars_, idx, signal):  # type: ignore[no-untyped-def]
            return self._inner.evaluate(bars_, idx, signal)

        def evaluate_all_bars(self, bars_, signal):  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            return self._inner.evaluate_all_bars(bars_, signal)

    # 同一 F1(fast_n=5,slow_n=20,atr_n=10) を 2 clause で使う
    shared_sig = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    genome = Genome(
        name="g_dup",
        units=10000,
        clauses=(
            ClauseConfig(directional=(shared_sig,), local_gate=(), weight=1.0),
            ClauseConfig(directional=(shared_sig,), local_gate=(), weight=1.0),
        ),
        position=PositionConfig(
            entry_threshold=0.1, exit_threshold=0.05, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )

    ev = CountingEvaluator()
    strat = DslStrategy(genome, ev)
    strat.prepare(bars)
    # 重複は 1 回に収束
    assert call_count["n"] == 1
