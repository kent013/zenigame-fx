"""T007: DslStrategy (Clause 版) のヒステリシス / time_stop / session close テスト。

PrimitiveEvaluator は Stub（ScriptedEvaluator）で composite を直接制御する。
idx に対して返すスカラー値を事前に仕込み、境界条件を直接検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal

from src.broker.orders import OrderSignal, PortfolioSnapshot, Position
from src.domain.price import PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests._helpers import make_bar


class ScriptedEvaluator:
    """bar index ごとに signal 値を返す stub evaluator。

    `script[idx][signal_name] = value` の形で事前に仕込む。
    """

    def __init__(self, script: dict[int, dict[str, float]]):
        self._script = script

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        return self._script[idx][signal.name]


def _mk_genome(
    entry_threshold: float = 0.3,
    exit_threshold: float = 0.1,
    time_stop_min: int = 0,
) -> Genome:
    return Genome(
        name="g",
        units=1000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            max_pos=1,
            time_stop_min=time_stop_min,
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal(0),
        margin_level_pct=None,
    )


def _long_snapshot(entry_time: datetime) -> PortfolioSnapshot:
    pos = Position(
        id=1,
        instrument="USD_JPY",
        side="long",
        units=1000,
        entry_price=Decimal("154.0"),
        entry_time=entry_time,
        entry_margin=Decimal("6000"),
        leverage=25,
    )
    return PortfolioSnapshot(
        cash=Decimal("994000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("6000"),
        margin_level_pct=None,
        positions=(pos,),
    )


def _short_snapshot(entry_time: datetime) -> PortfolioSnapshot:
    pos = Position(
        id=2,
        instrument="USD_JPY",
        side="short",
        units=1000,
        entry_price=Decimal("154.0"),
        entry_time=entry_time,
        entry_margin=Decimal("6000"),
        leverage=25,
    )
    return PortfolioSnapshot(
        cash=Decimal("994000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("6000"),
        margin_level_pct=None,
        positions=(pos,),
    )


def _bar(minute: int) -> PriceBar:
    return make_bar(minute, bid_close="154.0", ask_close="154.01")


# ---- warmup ----


def test_warmup_no_signals() -> None:
    g = _mk_genome()
    # composite = 1.0 (entry 成立するはず) を仕込んでも warmup 中なので空
    evaluator = ScriptedEvaluator({i: {"F1": 1.0} for i in range(10)})
    strat = DslStrategy(g, evaluator, warmup_bars=3)
    assert strat.on_bar(_bar(0), _empty_snapshot()) == []
    assert strat.on_bar(_bar(1), _empty_snapshot()) == []
    # 3 本目で warmup を満たす
    result = strat.on_bar(_bar(2), _empty_snapshot())
    assert result == [OrderSignal(kind="open_long", units=1000)]


# ---- entry boundary ----


def test_entry_long_at_theta_on_equal() -> None:
    # composite == entry_threshold (=0.3) → >= なので open_long
    g = _mk_genome(entry_threshold=0.3)
    evaluator = ScriptedEvaluator({0: {"F1": 0.3}})
    strat = DslStrategy(g, evaluator)
    result = strat.on_bar(_bar(0), _empty_snapshot())
    assert result == [OrderSignal(kind="open_long", units=1000)]


def test_entry_short_at_theta_on_equal() -> None:
    # composite = -0.3, -composite = 0.3 == entry_threshold → open_short
    g = _mk_genome(entry_threshold=0.3)
    evaluator = ScriptedEvaluator({0: {"F1": -0.3}})
    strat = DslStrategy(g, evaluator)
    result = strat.on_bar(_bar(0), _empty_snapshot())
    assert result == [OrderSignal(kind="open_short", units=1000)]


def test_no_entry_just_below_theta_on() -> None:
    g = _mk_genome(entry_threshold=0.3)
    evaluator = ScriptedEvaluator({0: {"F1": 0.29}})
    strat = DslStrategy(g, evaluator)
    assert strat.on_bar(_bar(0), _empty_snapshot()) == []


# ---- hysteresis hold region ----


def test_hold_between_theta_off_and_theta_on_long() -> None:
    # long 保有中、θ_off (=0.1) <= composite < θ_on (=0.3): 何もしない
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.2}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _long_snapshot(entry_time))
    assert result == []


def test_hold_between_theta_off_and_theta_on_short() -> None:
    # short 保有中、θ_off (=0.1) <= -composite < θ_on (=0.3): 何もしない
    # composite = -0.2 なので -composite = 0.2
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": -0.2}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _short_snapshot(entry_time))
    assert result == []


# ---- exit boundary ----


def test_exit_long_below_theta_off() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.05}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _long_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_exit_at_theta_off_equal_long_no_close() -> None:
    # long 保有 + composite == θ_off: < 厳密なので close しない
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.1}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    assert strat.on_bar(_bar(5), _long_snapshot(entry_time)) == []


def test_exit_short_above_neg_theta_off() -> None:
    # short 保有 + -composite < θ_off → close
    # composite = 0.0 だと -composite = 0.0 < 0.1 → close
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.0}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(5), _short_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_exit_at_theta_off_equal_short_no_close() -> None:
    # short 保有 + -composite == θ_off: < 厳密なので close しない
    # -composite = 0.1 なので composite = -0.1
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": -0.1}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    assert strat.on_bar(_bar(5), _short_snapshot(entry_time)) == []


# ---- time_stop ----


def test_time_stop_forces_close() -> None:
    # time_stop_min=60、entry_time から 60 分経過で close
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1, time_stop_min=60)
    # composite=0.5 (普段なら hold) だが time_stop で close される
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # _bar(60) は entry_time + 60 分
    result = strat.on_bar(_bar(60), _long_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_time_stop_just_before_no_close() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1, time_stop_min=60)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # 59 分経過: time_stop 未発火
    result = strat.on_bar(_bar(59), _long_snapshot(entry_time))
    assert result == []


def test_time_stop_disabled_when_zero() -> None:
    # time_stop_min=0 なら経過時間で close しない
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1, time_stop_min=0)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    result = strat.on_bar(_bar(1000), _long_snapshot(entry_time))
    assert result == []


# ---- session close ----


def test_session_close_forces_close() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator, session_close_utc=time(21, 0))
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # bar_time.time() が 21:00 以降になるよう minute=21*60
    bar = make_bar(21 * 60, bid_close="154.0", ask_close="154.01")
    result = strat.on_bar(bar, _long_snapshot(entry_time))
    assert len(result) == 1
    assert result[0].kind == "close_position"


def test_session_close_none_no_force() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator, session_close_utc=None)
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    bar = make_bar(21 * 60, bid_close="154.0", ask_close="154.01")
    # session_close=None なので自発 close しない（engine EOD に委譲）
    assert strat.on_bar(bar, _long_snapshot(entry_time)) == []


def test_session_close_before_time_no_force() -> None:
    g = _mk_genome(entry_threshold=0.3, exit_threshold=0.1)
    evaluator = ScriptedEvaluator({0: {"F1": 0.5}})
    strat = DslStrategy(g, evaluator, session_close_utc=time(21, 0))
    entry_time = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    # 20:59
    bar = make_bar(20 * 60 + 59, bid_close="154.0", ask_close="154.01")
    assert strat.on_bar(bar, _long_snapshot(entry_time)) == []
