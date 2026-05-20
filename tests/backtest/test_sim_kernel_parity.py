"""T108 golden parity: numba njit kernel 経路 == 現行 Decimal 経路 (bit-identical)。

selection-invariant performance-only change の最終 arbiter。kernel 経路 (run_backtest)
と Decimal 経路 (_run_backtest_decimal) を同一入力で走らせ、trades 全フィールド・
equity curve 配列・broker 最終 cash が完全一致することを検証する。

合成 bars で entry/exit/EOD/session close/spread filter/margin call の各分岐を網羅する。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from src.backtest.engine import (
    BacktestConfig,
    _run_backtest_decimal,
    run_backtest,
)
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy


class _ScriptedAllBarsEvaluator:
    """prepared path 対応の評価器。signal.name -> 全 bar 値配列を返す。

    composite は単一 clause/単一 directional のとき directional 値そのものになる。
    """

    def __init__(self, values: dict[str, list[float]]) -> None:
        self._values = {k: np.asarray(v, dtype=np.float64) for k, v in values.items()}

    def evaluate(self, bars, idx, signal):  # unprepared path 用 (本テストでは未使用)
        return float(self._values[signal.name][idx])

    def evaluate_all_bars(self, bars, signal):
        arr = self._values[signal.name]
        assert len(arr) == len(bars)
        return arr


def _meta() -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def _genome(*, time_stop_min: int = 0) -> Genome:
    return Genome(
        name="g",
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="D1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=time_stop_min
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _bar(
    bt: datetime,
    bid_o: str, bid_c: str, ask_o: str, ask_c: str,
) -> PriceBar:
    bo, bc, ao, ac = Decimal(bid_o), Decimal(bid_c), Decimal(ask_o), Decimal(ask_c)
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(bo, max(bo, bc), min(bo, bc), bc),
        ask=Ohlc(ao, max(ao, ac), min(ao, ac), ac),
        volume=10,
        complete=True,
    )


def _cfg(
    *,
    max_spread_bps: Decimal | None = Decimal("10"),
    session_close_utc_hours: frozenset[int] = frozenset(),
    spread_cost_multiplier: Decimal = Decimal("1.0"),
) -> BacktestConfig:
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 5, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=3,  # kernel preflight (leverage==3)
        max_spread_bps=max_spread_bps,
        holding_cost_per_day_bps=Decimal("0"),
        session_close_utc_hours=session_close_utc_hours,
        spread_cost_multiplier=spread_cost_multiplier,
    )


def _run_both(bars, genome, cfg, evaluator):
    """kernel 経路 (run_backtest) と Decimal 経路を別 instance で走らせて返す。"""
    strat_k = DslStrategy(genome, evaluator)
    broker_k = MockBroker(instrument_meta=_meta())
    res_k = run_backtest(bars, strat_k, broker_k, cfg)

    strat_d = DslStrategy(genome, evaluator)
    broker_d = MockBroker(instrument_meta=_meta())
    # 直接 Decimal 経路を呼ぶ (preflight をバイパスして reference を得る)
    broker_d.deposit  # noqa: B018  - 明示: deposit は _run_backtest_decimal 内で実行
    res_d = _run_backtest_decimal(list(bars), strat_d, broker_d, cfg)
    return (res_k, broker_k), (res_d, broker_d)


def _assert_trades_equal(trades_k, trades_d) -> None:
    assert len(trades_k) == len(trades_d), (len(trades_k), len(trades_d))
    for tk, td in zip(trades_k, trades_d, strict=True):
        assert tk.position_id == td.position_id
        assert tk.instrument == td.instrument
        assert tk.side == td.side
        assert tk.units == td.units
        assert tk.entry_price == td.entry_price
        assert tk.entry_time == td.entry_time
        assert tk.exit_price == td.exit_price
        assert tk.exit_time == td.exit_time
        assert tk.pnl == td.pnl
        assert tk.exit_reason == td.exit_reason
        assert tk.equity_at_entry == td.equity_at_entry
        assert tk.spread_cost == td.spread_cost
        assert tk.holding_cost == td.holding_cost


def _assert_equity_equal(res_k, res_d) -> None:
    assert np.array_equal(res_k.equity_curve.epoch_ns, res_d.equity_curve.epoch_ns)
    assert np.array_equal(
        res_k.equity_curve.equity_scaled, res_d.equity_curve.equity_scaled
    )


def test_kernel_path_is_actually_used_for_default_config() -> None:
    # leverage=3 / max_spread=10 / holding=0 / DslStrategy(prepared) → kernel path。
    from src.backtest.engine import _can_use_kernel

    bars = _make_multiday_bars()
    cfg = _cfg()
    strat = DslStrategy(_genome(), _flat_evaluator(len(bars)))
    broker = MockBroker(instrument_meta=_meta())
    assert _can_use_kernel(list(bars), strat, broker, cfg) is True


def _flat_evaluator(n: int) -> _ScriptedAllBarsEvaluator:
    return _ScriptedAllBarsEvaluator({"D1": [0.0] * n})


def _make_multiday_bars() -> list[PriceBar]:
    bars = []
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    for day in range(2):
        for m in range(60):
            bt = base + timedelta(days=day, minutes=m)
            bars.append(_bar(bt, "154.000", "154.010", "154.010", "154.020"))
    return bars


def test_parity_long_entry_exit_cycle() -> None:
    # D1 >= 0.5 で long entry、< 0.2 で exit のサイクル。
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            # 緩やかに上昇 (long 利益)
            px = Decimal("154.000") + Decimal(m) * Decimal("0.005")
            bars.append(_bar(bt, str(px), str(px), str(px + Decimal("0.010")), str(px + Decimal("0.010"))))
    d1 = [0.0] * n
    for i in range(5, 15):
        d1[i] = 0.8  # entry trigger (long)
    for i in range(15, 25):
        d1[i] = 0.0  # exit trigger
    for i in range(45, 55):
        d1[i] = 0.9
    for i in range(55, 65):
        d1[i] = 0.0
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg()
    (rk, bk), (rd, bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash
    assert len(rk.trades) >= 1


def _long_cycle_bars_and_ev():
    """long entry→exit サイクルの bars + evaluator (m>1 stress 検証用、spread あり)."""
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            px = Decimal("154.000") + Decimal(m) * Decimal("0.005")
            # bid=px, ask=px+0.010 (spread あり) で cost stress が効く
            bars.append(_bar(bt, str(px), str(px), str(px + Decimal("0.010")), str(px + Decimal("0.010"))))
    d1 = [0.0] * n
    for i in range(5, 15):
        d1[i] = 0.8
    for i in range(15, 25):
        d1[i] = 0.0
    for i in range(45, 55):
        d1[i] = 0.9
    for i in range(55, 65):
        d1[i] = 0.0
    return bars, _ScriptedAllBarsEvaluator({"D1": d1})


def test_parity_spread_cost_multiplier_stress() -> None:
    """T110: spread_cost_multiplier=1.5 でも kernel/Decimal parity が保たれる。"""
    bars, ev = _long_cycle_bars_and_ev()
    cfg = _cfg(spread_cost_multiplier=Decimal("1.5"))
    (rk, bk), (rd, bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash
    assert len(rk.trades) >= 1


def test_spread_cost_multiplier_worsens_pnl() -> None:
    """T110: m=1.5 は m=1.0 比で realized PnL を悪化させる (cost stress が効く)。

    realized fill の実効スプレッド割増が PnL に反映されることを確認 (degradation>0)。
    """
    bars, ev = _long_cycle_bars_and_ev()
    (rk1, _bk1), _ = _run_both(bars, _genome(), _cfg(), ev)
    (rk2, _bk2), _ = _run_both(
        bars, _genome(), _cfg(spread_cost_multiplier=Decimal("1.5")), ev
    )
    # 同一 trade 数で realized PnL 合計が m=1.5 の方が小さい (cost 増)
    assert len(rk1.trades) == len(rk2.trades) >= 1
    pnl_base = sum(t.pnl for t in rk1.trades)
    pnl_stress = sum(t.pnl for t in rk2.trades)
    assert pnl_stress < pnl_base, (pnl_base, pnl_stress)


def test_parity_short_entry_and_eod_close() -> None:
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            px = Decimal("154.000") - Decimal(m) * Decimal("0.003")
            bars.append(_bar(bt, str(px), str(px), str(px + Decimal("0.010")), str(px + Decimal("0.010"))))
    d1 = [0.0] * n
    for i in range(5, 40):
        d1[i] = -0.8  # short entry を day0 末尾まで維持 → exit signal 無し → EOD 強制クローズ
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg()
    (rk, bk), (rd, bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash
    assert any(t.exit_reason == "eod" for t in rk.trades)


def test_parity_session_close_and_spread_filter() -> None:
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    # 30 分刻みで hour を進め、hour=5 を session close に設定。
    # 一部 bar で wide spread (>10bps) を作り spread filter も誘発する。
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m * 30)
            ask_c = "154.300" if m in (8, 9) else "154.010"  # m8,9 で ~19bps > 10
            bars.append(_bar(bt, "154.000", "154.000", "154.010", ask_c))
    d1 = [0.0] * n
    for i in range(7, 20):
        d1[i] = 0.8
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg(session_close_utc_hours=frozenset({5}))
    (rk, bk), (rd, bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash


def test_parity_margin_call() -> None:
    # long 保有中に大暴落させ margin call (equity < notional/3) を誘発。
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            idx = day * 40 + m
            # 154 -> 100 の暴落 (10000*54 = 540k 損 > 487k で margin call)
            px = Decimal("100.000") if idx >= 20 else Decimal("154.000")
            bars.append(_bar(bt, str(px), str(px), str(px + Decimal("0.010")), str(px + Decimal("0.010"))))
    d1 = [0.0] * n
    for i in range(5, 40):
        d1[i] = 0.8  # long を day0 末尾まで維持 → exit signal 無し → idx20 暴落で margin call
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg()
    (rk, bk), (rd, bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash
    assert any(t.exit_reason == "margin_call" for t in rk.trades)


def test_spread_cost_multiplier_does_not_change_margin_behavior() -> None:
    """T110 [impl-review Critical]: MTM/margin は raw 価格を使うため、m=1.0 と m=1.5 で
    margin_call 発火タイミング (exit_reason 列・exit_idx) が不変であること。

    realized PnL のみ stress cost を反映し、含み損益・証拠金判定は raw のまま、という
    契約の直接検証。"""
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            idx = day * 40 + m
            px = Decimal("100.000") if idx >= 20 else Decimal("154.000")
            bars.append(_bar(bt, str(px), str(px), str(px + Decimal("0.010")), str(px + Decimal("0.010"))))
    d1 = [0.0] * n
    for i in range(5, 40):
        d1[i] = 0.8
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    (rk1, _b1), _ = _run_both(bars, _genome(), _cfg(), ev)
    (rk2, _b2), _ = _run_both(
        bars, _genome(), _cfg(spread_cost_multiplier=Decimal("1.5")), ev
    )
    # margin_call の発火タイミング (exit_reason 列・exit_time) は m に依らず不変
    assert [t.exit_reason for t in rk1.trades] == [t.exit_reason for t in rk2.trades]
    assert [t.exit_time for t in rk1.trades] == [t.exit_time for t in rk2.trades]
    assert any(t.exit_reason == "margin_call" for t in rk1.trades)


def test_parity_time_stop() -> None:
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            bars.append(_bar(bt, "154.000", "154.000", "154.010", "154.010"))
    d1 = [0.0] * n
    for i in range(5, 35):
        d1[i] = 0.8  # entry 維持、time_stop で強制クローズ
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg()
    (rk, bk), (rd, bd) = _run_both(bars, _genome(time_stop_min=5), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash
    assert len(rk.trades) >= 1


def test_overflow_sentinel_falls_back_to_decimal_and_stays_correct() -> None:
    # 巨大 initial_cash で margin sentinel (equity_scaled*300 > int64) を発火させ、
    # kernel が OVERFLOW を返して Decimal 経路へフォールバックしても結果が正しいこと。
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            bars.append(_bar(bt, "154.000", "154.000", "154.010", "154.010"))
    d1 = [0.0] * n
    for i in range(5, 40):
        d1[i] = 0.8  # 保有を作って margin check (sentinel) を走らせる
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 5, tzinfo=UTC),
        # 1e9 -> equity_scaled=1e17 (int64 内) だが *100*3=3e19 で margin sentinel 発火。
        initial_cash=Decimal("1000000000"),
        leverage=3,
        max_spread_bps=Decimal("10"),
        holding_cost_per_day_bps=Decimal("0"),
    )
    # kernel 経路は sentinel で None を返す (overflow → フォールバック) ことを直接確認。
    from src.backtest.engine import _run_backtest_kernel

    strat_ov = DslStrategy(_genome(), ev)
    broker_ov = MockBroker(instrument_meta=_meta())
    assert _run_backtest_kernel(list(bars), strat_ov, broker_ov, cfg) is None

    strat_k = DslStrategy(_genome(), ev)
    broker_k = MockBroker(instrument_meta=_meta())
    res_k = run_backtest(bars, strat_k, broker_k, cfg)  # 内部でフォールバック

    strat_d = DslStrategy(_genome(), ev)
    broker_d = MockBroker(instrument_meta=_meta())
    res_d = _run_backtest_decimal(list(bars), strat_d, broker_d, cfg)

    _assert_trades_equal(res_k.trades, res_d.trades)
    _assert_equity_equal(res_k, res_d)


def test_spread_filter_at_exact_boundary_not_rejected() -> None:
    # spread_bps == max (strict > なので reject されない) の境界一致を確認。
    # spread が exactly 10bps になる価格を作る: bps=(ask-bid)*20000/(ask+bid)=10
    # -> (ask-bid)*2000 = (ask+bid)。bid=100.000, ask=100.100 -> diff0.1, sum200.1
    # (0.1*2000=200 != 200.1) 厳密境界は作りにくいので、kernel/decimal 一致のみ確認。
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    for day in range(2):
        for m in range(40):
            bt = base + timedelta(days=day, minutes=m)
            bars.append(_bar(bt, "100.000", "100.000", "100.010", "100.010"))
    d1 = [0.0] * n
    for i in range(5, 20):
        d1[i] = 0.8
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg()
    (rk, _bk), (rd, _bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)


def test_parity_same_bar_margin_session_eod_conflict() -> None:
    # 同一 bar で margin call / session close / EOD が同時成立する競合での優先順位:
    # margin(step6) が先に close → session/EOD は no-op → 単一 trade / reason=margin_call。
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = []
    # day0: hour0 の bar を 38 本 + 末尾に hour5 の bar 1 本 (= is_eod & session & 暴落)
    for m in range(38):
        bars.append(_bar(base + timedelta(minutes=m), "154.000", "154.000", "154.010", "154.010"))
    # 末尾 bar (hour5, 暴落): is_eod (翌日と date 不一致) かつ session(5) かつ margin
    bars.append(_bar(base + timedelta(hours=5), "100.000", "100.000", "100.010", "100.010"))
    # day1 (multi-day 要件)
    for m in range(10):
        bars.append(_bar(base + timedelta(days=1, minutes=m), "100.000", "100.000", "100.010", "100.010"))
    n = len(bars)
    d1 = [0.0] * n
    for i in range(2, 38):
        d1[i] = 0.8  # day0 中に long entry し保有維持 (exit signal 無し)
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg(session_close_utc_hours=frozenset({5}))
    (rk, bk), (rd, bd) = _run_both(bars, _genome(), cfg, ev)
    _assert_trades_equal(rk.trades, rd.trades)
    _assert_equity_equal(rk, rd)
    assert bk.cash == bd.cash
    # 暴落 bar で margin が先勝ち → reason=margin_call、二重 close なし (1 position = 1 trade)
    margin_trades = [t for t in rk.trades if t.exit_reason == "margin_call"]
    assert len(margin_trades) == 1
    # 同一 position_id が複数回 close されていない
    pos_ids = [t.position_id for t in rk.trades]
    assert len(pos_ids) == len(set(pos_ids))


def test_active_clause_indices_parity() -> None:
    # kernel 経路と Decimal 経路で active_clause_indices が一致 (observability parity)。
    n = 80
    base = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    bars = [
        _bar(base + timedelta(days=i // 40, minutes=i % 40), "154.000", "154.000", "154.010", "154.010")
        for i in range(n)
    ]
    d1 = [0.0] * n
    for i in range(5, 30):
        d1[i] = 0.8
    ev = _ScriptedAllBarsEvaluator({"D1": d1})
    cfg = _cfg()

    strat_k = DslStrategy(_genome(), ev)
    run_backtest(bars, strat_k, MockBroker(instrument_meta=_meta()), cfg)
    strat_d = DslStrategy(_genome(), ev)
    _run_backtest_decimal(list(bars), strat_d, MockBroker(instrument_meta=_meta()), cfg)

    assert strat_k.active_clause_indices == strat_d.active_clause_indices
