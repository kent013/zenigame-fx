"""DslStrategy の flat cache / PreparedSignals invariance tests (Cycle 2 / T029).

Cycle 2 で prepare() の cache 構造を `PreparedSignals` NamedTuple に統合し、
on_bar hot path から `_signal_cache_key` を排除した。以下を検証:
  - `self._prepared` の単一 slot 化 (Round 1 Critical #2)
  - 同一 clause 内 signal.name 重複の __init__ fail-fast (Review R1 Warning #3)
  - genome identity 検証で mutation 検出 (Review R1 Critical #1/#2)
  - prepared / unprepared 経路が同じ vals を生成 (bit-identical)
  - NaN/inf 入力時の fallback (Review R1 Warning #4)
  - SignalConfig.params の immutability (Design Review Round 2 Critical #1)
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import (
    RegistryEvaluator,
    clear,
    ensure_registered,
)
from src.backtest.engine import BacktestConfig, run_backtest
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
from src.dsl.strategy import DslStrategy, PreparedSignals
from tests._helpers import usd_jpy_meta


# Review R1 Suggestion #6 + Review R2 Suggestion #4: registry isolation
@pytest.fixture(autouse=True)
def _registry_isolation():
    """各 test 前後で registry を clear + re-register し、global state の
    汚染を防ぐ (primitives-registry は global singleton なため)。

    teardown は `clear()` のみで後続テストに暗黙状態を注入しない。"""
    clear()
    ensure_registered()
    yield
    clear()


def _bar(i: int, base: Decimal = Decimal("154.00")) -> PriceBar:
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=i)
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


def _genome_simple() -> Genome:
    return Genome(
        name="g_flat",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F1", weight=1.0,
                        params={"fast_n": 5, "slow_n": 20, "atr_n": 10},
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.1, exit_threshold=0.05,
            max_pos=1, time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _empty_snapshot() -> PortfolioSnapshot:
    """空の PortfolioSnapshot fixture (cash / equity 1M、positions なし)。"""
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal(0),
        margin_level_pct=None,
        positions=(),
    )


def test_prepare_stores_single_slot_state() -> None:
    """Round 1 Critical #2: 2 重管理の排除を検証."""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_simple(), ev)
    assert strat._prepared is None
    bars = [_bar(i) for i in range(200)]
    strat.prepare(bars)
    assert isinstance(strat._prepared, PreparedSignals)
    # _precomputed は削除されている (旧 API なし)
    assert not hasattr(strat, "_precomputed")


def test_prepared_clauses_are_tuples_of_tuples() -> None:
    """clauses が immutable tuple で書き換え不可であること."""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_simple(), ev)
    strat.prepare([_bar(i) for i in range(200)])
    p = strat._prepared
    assert p is not None
    assert isinstance(p.clauses, tuple)
    for clause_entries in p.clauses:
        assert isinstance(clause_entries, tuple)
        assert len(clause_entries) == 2  # (directional, gate)
        dir_entries, gate_entries = clause_entries
        assert isinstance(dir_entries, tuple)
        assert isinstance(gate_entries, tuple)


def test_prepare_rejects_duplicate_signal_names_in_clause() -> None:
    """Round 1 Critical #3: 同一 clause 内 signal.name 重複を fail-fast."""
    ev = RegistryEvaluator(pair="USD_JPY")
    dup_sig_a = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    dup_sig_b = SignalConfig(
        name="F1", weight=0.5, params={"fast_n": 3, "slow_n": 15, "atr_n": 7}
    )
    genome = Genome(
        name="g_dup",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(dup_sig_a, dup_sig_b),  # 同名重複
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    # __init__ で既に検出される (unprepared path も含め契約を強制)
    with pytest.raises(ValueError, match=r"duplicate signal\.name"):
        DslStrategy(genome, ev)


def test_prepare_shares_arrays_across_duplicate_signals_between_clauses() -> None:
    """同一 (name, params) の signal が別 clause にあれば arrays dict を共有."""
    ev = RegistryEvaluator(pair="USD_JPY")
    shared = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    genome = Genome(
        name="g_share",
        units=10000,
        clauses=(
            ClauseConfig(directional=(shared,), local_gate=(), weight=1.0),
            ClauseConfig(directional=(shared,), local_gate=(), weight=1.0),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    strat = DslStrategy(genome, ev)
    strat.prepare([_bar(i) for i in range(100)])
    p = strat._prepared
    assert p is not None
    # arrays dict は 1 entry のみ (共有)
    assert len(p.arrays) == 1
    # 両 clause の directional entries は同じ arr object を参照
    arr_c0 = p.clauses[0][0][0][1]  # clause 0 directional[0] arr
    arr_c1 = p.clauses[1][0][0][1]  # clause 1 directional[0] arr
    assert arr_c0 is arr_c1


def test_on_bar_prepared_equivalent_to_unprepared() -> None:
    """Round 1: prepared / unprepared 経路が同じ trades / equity を生成."""
    bars = [_bar(i) for i in range(400)]
    cfg = BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        max_spread_bps=Decimal("10"),
        session_close_utc_hours=frozenset({21}),
        bar_minutes=1,
    )

    class _NoPrepareEvaluator:
        """evaluate_all_bars を持たないラッパ (prepared を抑制)."""

        def __init__(self, inner: RegistryEvaluator) -> None:
            self._inner = inner

        def evaluate(self, bars_, idx, sig):  # type: ignore[no-untyped-def]
            return self._inner.evaluate(bars_, idx, sig)

    ev_fast = RegistryEvaluator(pair="USD_JPY")
    strat_fast = DslStrategy(_genome_simple(), ev_fast)
    broker_fast = MockBroker(instrument_meta=usd_jpy_meta())
    result_fast = run_backtest(bars, strat_fast, broker_fast, cfg)

    ev_slow = _NoPrepareEvaluator(RegistryEvaluator(pair="USD_JPY"))
    strat_slow = DslStrategy(_genome_simple(), ev_slow)
    broker_slow = MockBroker(instrument_meta=usd_jpy_meta())
    result_slow = run_backtest(bars, strat_slow, broker_slow, cfg)

    assert strat_fast._prepared is not None
    assert strat_slow._prepared is None

    assert len(result_fast.trades) == len(result_slow.trades)
    assert broker_fast.snapshot().equity == broker_slow.snapshot().equity
    for tf, ts in zip(result_fast.trades, result_slow.trades, strict=True):
        assert tf.entry_time == ts.entry_time
        assert tf.exit_time == ts.exit_time
        assert tf.side == ts.side
        assert tf.entry_price == ts.entry_price
        assert tf.exit_price == ts.exit_price


def test_prepare_resets_stale_state_on_repeated_call() -> None:
    """Round 1 Warning: 再 prepare() で stale state を除去."""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_simple(), ev)
    strat.prepare([_bar(i) for i in range(100)])
    first = strat._prepared
    assert first is not None
    # 再 prepare (別 bars)
    strat.prepare([_bar(i) for i in range(200)])
    second = strat._prepared
    assert second is not None
    assert second is not first  # 新規 state
    assert strat._bar_count == 0  # reset されている


def test_genome_identity_mismatch_raises_on_swap() -> None:
    """Round 2 Warning 2 + Review R1 Critical #2: prepare() 後に別 genome を
    self._genome にセットすると O(1) identity 検査で fail-fast。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    g1 = _genome_simple()
    g2 = Genome(
        name="g_swap",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F2", weight=1.0,
                        params={
                            "fast_n": 8, "slow_n": 20,
                            "signal_n": 9, "scale_n": 30,
                        },
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    strat = DslStrategy(g1, ev)
    strat.prepare([_bar(i) for i in range(100)])
    # lifecycle 違反: genome instance を差し替え
    strat._genome = g2  # type: ignore[assignment]
    with pytest.raises(AssertionError, match="inconsistent with current"):
        strat.on_bar(_bar(0), _empty_snapshot())


def test_clause_boundary_and_weight_change_detected() -> None:
    """Review R1 Critical #1 対応: directional/local_gate 境界変更や
    clause.weight / signal.weight 変更でも identity 比較で検出 (別 instance)。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    g1 = _genome_simple()
    # 同じ signal name/params だが clause.weight が異なる
    g1_weight_changed = Genome(
        name=g1.name, units=g1.units,
        clauses=(
            ClauseConfig(
                directional=g1.clauses[0].directional,
                local_gate=g1.clauses[0].local_gate,
                weight=0.5,  # 変更
            ),
        ),
        position=g1.position, risk=g1.risk,
    )
    assert g1 is not g1_weight_changed
    strat = DslStrategy(g1, ev)
    strat.prepare([_bar(i) for i in range(100)])
    strat._genome = g1_weight_changed  # type: ignore[assignment]
    with pytest.raises(AssertionError):
        strat.on_bar(_bar(0), _empty_snapshot())


def test_duplicate_name_rejected_in_init_without_prepare() -> None:
    """Review R1 Warning #3: name uniqueness は __init__ で強制 (prepare 不要)。
    unprepared (paper trading) path も含めて守られる。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    dup_sig_a = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    dup_sig_b = SignalConfig(
        name="F1", weight=0.5, params={"fast_n": 3, "slow_n": 15, "atr_n": 7}
    )
    genome = Genome(
        name="g_dup_init",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(dup_sig_a, dup_sig_b),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(0.1, 0.05, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )
    with pytest.raises(ValueError, match=r"duplicate signal\.name"):
        DslStrategy(genome, ev)


def _genome_negative_entry() -> Genome:
    """entry_threshold が負 (-0.1) の genome。NaN fallback か NaN 伝播かを
    明確に識別するため使う (Review R2 Warning 対応)。

    composite=0.0 なら composite >= -0.1 が True → open_long 発生。
    composite=NaN なら NaN >= -0.1 は False → signal 空。
    """
    return Genome(
        name="g_neg_entry",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(
                        name="F1", weight=1.0,
                        params={"fast_n": 5, "slow_n": 20, "atr_n": 10},
                    ),
                ),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=-0.1, exit_threshold=-0.2,
            max_pos=1, time_stop_min=0,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def test_prepared_path_nan_falls_back_to_zero() -> None:
    """warmup 期 (NaN) で prepared path が 0.0 fallback (NaN 伝播ではない)
    を検証。NaN 伝播だと composite=NaN で `NaN >= -0.1` が False になり
    signal が発生しないが、0.0 fallback なら `0.0 >= -0.1` で open_long が
    発生する (Review R2 Warning 対応: 識別力を強化)。"""
    ev = RegistryEvaluator(pair="USD_JPY")
    strat = DslStrategy(_genome_negative_entry(), ev)
    bars = [_bar(i) for i in range(30)]
    strat.prepare(bars)
    p = strat._prepared
    assert p is not None
    arr = p.clauses[0][0][0][1]
    # warmup 領域は NaN
    assert np.isnan(arr[0])
    # on_bar は NaN を 0.0 に fallback するため、composite=0.0 で
    # open_long が発生する (entry_threshold=-0.1 < 0.0)
    signals = strat.on_bar(bars[0], _empty_snapshot())
    assert len(signals) == 1
    assert signals[0].kind == "open_long"


def test_signal_config_params_immutable() -> None:
    """施策 0: MappingProxyType で sig.params mutation が TypeError になる."""
    sig = SignalConfig(
        name="F1", weight=1.0, params={"fast_n": 5, "slow_n": 20, "atr_n": 10}
    )
    with pytest.raises(TypeError):
        sig.params["fast_n"] = 999  # type: ignore[index]


def test_prepare_noop_when_evaluator_lacks_evaluate_all_bars() -> None:
    """live feed evaluator は prepared state を作らない (paper trading 互換)."""

    class _LiveLikeEvaluator:
        def __init__(self) -> None:
            self._inner = RegistryEvaluator(pair="USD_JPY")

        def evaluate(self, bars_, idx, sig):  # type: ignore[no-untyped-def]
            return self._inner.evaluate(bars_, idx, sig)

    strat = DslStrategy(_genome_simple(), _LiveLikeEvaluator())
    strat.prepare([_bar(i) for i in range(100)])
    assert strat._prepared is None
