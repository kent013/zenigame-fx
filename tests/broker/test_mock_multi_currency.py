"""MockBroker 非 JPY-quote 通貨ペア対応テスト (T019)。

設計根拠:
- devnotes/20260424-0517-mock-broker-multi-currency/conceptual-design.md
- devnotes/20260424-0517-mock-broker-multi-currency/detailed-design.md

テスト戦略:
1. EUR_USD / USD_CAD の P&L 符号サニティ
2. home_currency 明示指定 (JPY keeps, USD matches quote) / mismatch fail-fast
3. pip_size / display_precision validation
4. Scale 不変性 (S2: initial_cash × units 同時スケール → Sharpe 不変、
   S3: 同時スケール → equity returns 要素一致)
5. Cross-pair shadow が非 JPY anchor でも pair_failure を起こさない
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.alpha_factory.cross_pair import (
    CrossPairConfig,
    evaluate_cross_pair,
)
from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import compute_metrics
from src.broker import InstrumentMeta, MockBroker, OrderSignal
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy
from tests._helpers import (
    eur_jpy_meta,
    eur_usd_meta,
    make_bar,
    usd_cad_meta,
    usd_jpy_meta,
)
from tests.dsl.conftest import ConstantPrimitiveEvaluator, ScriptedPrimitiveEvaluator

# ---------------------------------------------------------------------------
# 1. EUR_USD / USD_CAD P&L sign sanity
# ---------------------------------------------------------------------------


def _make_eur_usd_bar(
    minute: int,
    bid_close: str,
    ask_close: str,
    *,
    day: int = 1,
    bid_open: str | None = None,
    ask_open: str | None = None,
) -> PriceBar:
    return make_bar(
        minute,
        bid_close,
        ask_close,
        day=day,
        pair_name="EUR_USD",
        bid_open=bid_open,
        ask_open=ask_open,
    )


def _make_usd_cad_bar(
    minute: int,
    bid_close: str,
    ask_close: str,
    *,
    day: int = 1,
    bid_open: str | None = None,
    ask_open: str | None = None,
) -> PriceBar:
    return make_bar(
        minute,
        bid_close,
        ask_close,
        day=day,
        pair_name="USD_CAD",
        bid_open=bid_open,
        ask_open=ask_open,
    )


def test_eur_usd_long_close_pnl_sign_positive_on_rally() -> None:
    broker = MockBroker(instrument_meta=eur_usd_meta())
    broker.deposit(Decimal("1000000"))
    bar_open = _make_eur_usd_bar(0, bid_close="1.08000", ask_close="1.08010")
    bar_next = _make_eur_usd_bar(1, bid_close="1.08500", ask_close="1.08510")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)
    trade = broker.trades[0]
    assert trade.entry_price == Decimal("1.08010")  # long entry at ask.open
    assert trade.exit_price == Decimal("1.08500")  # long exit at bid.open
    assert trade.pnl > 0
    assert trade.pnl == Decimal("10000") * (Decimal("1.08500") - Decimal("1.08010"))


def test_eur_usd_short_close_pnl_sign_positive_on_decline() -> None:
    broker = MockBroker(instrument_meta=eur_usd_meta())
    broker.deposit(Decimal("1000000"))
    bar_open = _make_eur_usd_bar(0, bid_close="1.08000", ask_close="1.08010")
    bar_next = _make_eur_usd_bar(1, bid_close="1.07500", ask_close="1.07510")
    broker.submit(OrderSignal(kind="open_short", units=10000), leverage=1)
    broker.fill_pending(bar_open)  # short entry at bid.open=1.08000
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)  # short exit at ask.open=1.07510
    trade = broker.trades[0]
    assert trade.entry_price == Decimal("1.08000")
    assert trade.exit_price == Decimal("1.07510")
    assert trade.pnl > 0
    assert trade.pnl == Decimal("10000") * (Decimal("1.08000") - Decimal("1.07510"))


def test_usd_cad_long_roundtrip_cash_matches_pnl() -> None:
    broker = MockBroker(instrument_meta=usd_cad_meta())
    broker.deposit(Decimal("1000000"))
    bar_open = _make_usd_cad_bar(0, bid_close="1.35000", ask_close="1.35010")
    bar_next = _make_usd_cad_bar(1, bid_close="1.35500", ask_close="1.35510")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)
    trade = broker.trades[0]
    expected_pnl = Decimal("10000") * (Decimal("1.35500") - Decimal("1.35010"))
    assert trade.pnl == expected_pnl
    assert broker.cash == Decimal("1000000") + expected_pnl


# ---------------------------------------------------------------------------
# 2. home_currency explicit / mismatch
# ---------------------------------------------------------------------------


def test_explicit_home_currency_jpy_keeps_usd_jpy_behavior() -> None:
    """明示 home_currency="JPY" 指定 + USD_JPY meta で旧挙動維持。"""
    broker = MockBroker(instrument_meta=usd_jpy_meta(), home_currency="JPY")
    broker.deposit(Decimal("1000000"))
    assert broker.cash == Decimal("1000000")
    # 簡単なトレードで P&L を確認
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_next = make_bar(1, bid_close="154.500", ask_close="154.510")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)
    assert len(broker.trades) == 1
    assert broker.trades[0].pnl > 0


def test_explicit_home_currency_matches_quote_for_eur_usd() -> None:
    """明示 home_currency="USD" + EUR_USD meta は受理される (quote==home)。"""
    broker = MockBroker(instrument_meta=eur_usd_meta(), home_currency="USD")
    broker.deposit(Decimal("1000000"))
    assert broker.cash == Decimal("1000000")


def test_mismatched_home_quote_raises_not_implemented_with_phase4_hint() -> None:
    """home != quote は NotImplementedError + Phase 4 / fx_rate_provider のヒント。"""
    with pytest.raises(NotImplementedError) as excinfo:
        MockBroker(instrument_meta=eur_usd_meta(), home_currency="JPY")
    msg = str(excinfo.value)
    assert "Phase 4" in msg
    assert "fx_rate_provider" in msg


def test_default_home_currency_uses_quote_currency_per_pair() -> None:
    """引数無指定では meta.quote_currency を自動採用 (per-pair home)。"""
    # USD_JPY: home 自動=JPY
    MockBroker(instrument_meta=usd_jpy_meta())
    # EUR_USD: home 自動=USD (新規対応)
    MockBroker(instrument_meta=eur_usd_meta())
    # USD_CAD: home 自動=CAD (新規対応)
    MockBroker(instrument_meta=usd_cad_meta())
    # エラーが出ないことだけ確認


# ---------------------------------------------------------------------------
# 3. pip_size / display_precision validation
# ---------------------------------------------------------------------------


def test_instrument_meta_default_pip_size_for_quote() -> None:
    assert InstrumentMeta.default_pip_size_for_quote("JPY") == Decimal("0.01")
    assert InstrumentMeta.default_pip_size_for_quote("jpy") == Decimal("0.01")
    assert InstrumentMeta.default_pip_size_for_quote("USD") == Decimal("0.0001")
    assert InstrumentMeta.default_pip_size_for_quote("CAD") == Decimal("0.0001")


def test_instrument_meta_default_display_precision_for_quote() -> None:
    assert InstrumentMeta.default_display_precision_for_quote("JPY") == 3
    assert InstrumentMeta.default_display_precision_for_quote("jpy") == 3
    assert InstrumentMeta.default_display_precision_for_quote("USD") == 5
    assert InstrumentMeta.default_display_precision_for_quote("CAD") == 5


def test_instrument_meta_pip_size_default_is_usd_quote() -> None:
    """default は USD-quote (0.0001 / 5)。"""
    m = InstrumentMeta(
        oanda_name="EUR_USD",
        base_currency="EUR",
        quote_currency="USD",
        margin_rate=Decimal("0.03"),
    )
    assert m.pip_size == Decimal("0.0001")
    assert m.display_precision == 5


def test_instrument_meta_rejects_zero_or_negative_pip_size() -> None:
    with pytest.raises(ValueError, match="pip_size"):
        InstrumentMeta(
            oanda_name="USD_JPY",
            base_currency="USD",
            quote_currency="JPY",
            margin_rate=Decimal("0.04"),
            pip_size=Decimal("0"),
        )
    with pytest.raises(ValueError, match="pip_size"):
        InstrumentMeta(
            oanda_name="USD_JPY",
            base_currency="USD",
            quote_currency="JPY",
            margin_rate=Decimal("0.04"),
            pip_size=Decimal("-0.01"),
        )


def test_instrument_meta_rejects_negative_display_precision() -> None:
    with pytest.raises(ValueError, match="display_precision"):
        InstrumentMeta(
            oanda_name="USD_JPY",
            base_currency="USD",
            quote_currency="JPY",
            margin_rate=Decimal("0.04"),
            display_precision=-1,
        )


# ---------------------------------------------------------------------------
# 4. Scale invariance (S2: Sharpe 不変 / S3: equity returns 一致)
# ---------------------------------------------------------------------------


def _build_trending_genome() -> Genome:
    """長期上昇で long エントリー → 直後 close の単純 genome (scripted evaluator で制御)。"""
    sig_long = SignalConfig(name="always_long", weight=1.5, params={})
    clause = ClauseConfig(directional=(sig_long,), local_gate=(), weight=1.0)
    pos = PositionConfig(
        entry_threshold=0.5,
        exit_threshold=0.0,
        max_pos=1,
        time_stop_min=0,
    )
    risk = RiskConfig(stop_atr=2.0, take_atr=2.0)
    return Genome(
        name="scale_invariance_genome",
        units=10000,
        clauses=(clause,),
        position=pos,
        risk=risk,
    )


def _make_trending_bars(
    *,
    pair_name: str,
    base_bid: Decimal,
    pip_step: Decimal,
    n_per_day: int = 5,
    n_days: int = 3,
) -> list[PriceBar]:
    """複数日の単純上昇→下降→上昇サイクル bars を生成する (イントラデイ制約対応)。"""
    bars: list[PriceBar] = []
    bid = base_bid
    spread = Decimal("0.00010") if pip_step < Decimal("0.01") else Decimal("0.010")
    for day in range(1, n_days + 1):
        # 日中は上昇、日をまたぐと少し引く
        direction = Decimal("1") if day % 2 == 1 else Decimal("-1")
        for minute in range(n_per_day):
            bid += pip_step * direction
            ask = bid + spread
            bt = datetime(2026, 4, day, 12, minute, 0, tzinfo=UTC)
            bars.append(
                PriceBar(
                    pair_name=pair_name,
                    bar_time=bt,
                    bid=Ohlc(open=bid, high=bid, low=bid, close=bid),
                    ask=Ohlc(open=ask, high=ask, low=ask, close=ask),
                    volume=10,
                    complete=True,
                )
            )
    return bars


def _run_scaled_backtest(
    *,
    meta: InstrumentMeta,
    bars: list[PriceBar],
    cash_scale: int,
    units_scale: int,
    base_cash: Decimal = Decimal("1000000"),
    base_units: int = 10000,
    leverage: int = 5,
):
    """scale=k で (base_cash * k, base_units * k) で backtest を回す。"""
    # 強制的に毎 bar 開閉するゲノム signal (scripted: 奇数 bar 0.8, 偶数 bar -0.8)
    script: dict[int, dict[str, float]] = {}
    for i in range(len(bars)):
        script[i] = {"always_long": 0.8 if i % 3 != 0 else -0.3}
    evaluator = ScriptedPrimitiveEvaluator(script)
    genome = _build_trending_genome()
    # genome.units は config から来るが、ここは broker に直接 signal を送る方が簡単。
    # DslStrategy は genome.units を OrderSignal.units に流すので、unit scale は
    # genome.units の上書きで実現する。
    scaled_genome = Genome(
        name=genome.name,
        units=base_units * units_scale,
        clauses=genome.clauses,
        position=genome.position,
        risk=genome.risk,
    )
    strategy = DslStrategy(scaled_genome, evaluator)
    broker = MockBroker(instrument_meta=meta)
    config = BacktestConfig(
        instrument=meta.oanda_name,
        start=bars[0].bar_time,
        end=bars[-1].bar_time + timedelta(minutes=1),
        initial_cash=base_cash * cash_scale,
        leverage=leverage,
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )
    result = run_backtest(bars, strategy, broker, config)
    metrics = compute_metrics(result.trades, result.equity_curve)
    return result, metrics


@pytest.mark.parametrize(
    "pair_name, meta_factory, base_bid, pip_step",
    [
        ("USD_JPY", usd_jpy_meta, Decimal("154.000"), Decimal("0.010")),
        ("EUR_USD", eur_usd_meta, Decimal("1.08000"), Decimal("0.00010")),
    ],
)
def test_scale_invariance_sharpe_s2(
    pair_name: str, meta_factory, base_bid: Decimal, pip_step: Decimal
) -> None:
    """S2: initial_cash と units を同倍率 k でスケール → Sharpe 不変。"""
    meta = meta_factory()
    bars = _make_trending_bars(
        pair_name=pair_name, base_bid=base_bid, pip_step=pip_step, n_per_day=5, n_days=3
    )
    result_1, metrics_1 = _run_scaled_backtest(
        meta=meta, bars=bars, cash_scale=1, units_scale=1
    )
    result_10, metrics_10 = _run_scaled_backtest(
        meta=meta, bars=bars, cash_scale=10, units_scale=10
    )
    # margin_call は起こってはいけない (S2 は非拘束条件下で検証)
    assert all(t.exit_reason != "margin_call" for t in result_1.trades)
    assert all(t.exit_reason != "margin_call" for t in result_10.trades)
    # trade が発生していること
    assert len(result_1.trades) > 0, f"{pair_name}: no trades in scale=1"
    assert len(result_10.trades) > 0, f"{pair_name}: no trades in scale=10"
    # Sharpe が両ケースとも算出されていること
    assert metrics_1.sharpe is not None, f"{pair_name}: sharpe None at scale=1"
    assert metrics_10.sharpe is not None, f"{pair_name}: sharpe None at scale=10"
    # 不変性: 差 < 1e-6
    diff = abs(float(metrics_1.sharpe) - float(metrics_10.sharpe))
    assert diff < 1e-6, (
        f"{pair_name}: sharpe scale invariance violated: "
        f"scale=1 {metrics_1.sharpe} vs scale=10 {metrics_10.sharpe} diff={diff}"
    )


@pytest.mark.parametrize(
    "pair_name, meta_factory, base_bid, pip_step",
    [
        ("USD_JPY", usd_jpy_meta, Decimal("154.000"), Decimal("0.010")),
        ("EUR_USD", eur_usd_meta, Decimal("1.08000"), Decimal("0.00010")),
    ],
)
def test_scale_invariance_equity_returns_s3(
    pair_name: str, meta_factory, base_bid: Decimal, pip_step: Decimal
) -> None:
    """S3: 同時スケール下で equity returns 系列が要素ごとに一致。"""
    meta = meta_factory()
    bars = _make_trending_bars(
        pair_name=pair_name, base_bid=base_bid, pip_step=pip_step, n_per_day=5, n_days=3
    )
    result_1, _ = _run_scaled_backtest(
        meta=meta, bars=bars, cash_scale=1, units_scale=1
    )
    result_10, _ = _run_scaled_backtest(
        meta=meta, bars=bars, cash_scale=10, units_scale=10
    )

    def _returns(eq_curve: list[tuple[datetime, Decimal]]) -> list[float]:
        rets: list[float] = []
        prev: Decimal | None = None
        for _, eq in eq_curve:
            if prev is not None and prev > 0:
                rets.append(float((eq - prev) / prev))
            prev = eq
        return rets

    # S3 も margin 非拘束条件下で検証することを明示 (S2 と揃える)
    assert all(t.exit_reason != "margin_call" for t in result_1.trades)
    assert all(t.exit_reason != "margin_call" for t in result_10.trades)

    r1 = _returns(result_1.equity_curve)
    r10 = _returns(result_10.equity_curve)
    assert len(r1) == len(r10)
    for i, (a, b) in enumerate(zip(r1, r10, strict=True)):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), (
            f"{pair_name}: equity returns diverge at idx={i}: scale1={a} scale10={b}"
        )


# ---------------------------------------------------------------------------
# 5. Cross-pair shadow with non-JPY anchor (backtest 完走、pair_failure なし)
# ---------------------------------------------------------------------------


def _simple_cross_genome() -> Genome:
    sig = SignalConfig(name="const", weight=1.2, params={})
    clause = ClauseConfig(directional=(sig,), local_gate=(), weight=1.0)
    pos = PositionConfig(
        entry_threshold=0.5,
        exit_threshold=0.0,
        max_pos=1,
        time_stop_min=0,
    )
    risk = RiskConfig(stop_atr=2.0, take_atr=2.0)
    return Genome(
        name="cross_pair_smoke",
        units=10000,
        clauses=(clause,),
        position=pos,
        risk=risk,
    )


def _multi_day_bars(
    *, pair_name: str, base_bid: Decimal, pip_step: Decimal
) -> list[PriceBar]:
    """cross-pair shadow backtest 用の複数日 bars (session_close hit 保証)。"""
    return _make_trending_bars(
        pair_name=pair_name,
        base_bid=base_bid,
        pip_step=pip_step,
        n_per_day=5,
        n_days=3,
    )


def test_cross_pair_multi_currency_shadow_no_pair_failure_not_implemented() -> None:
    """target=EUR_JPY + anchors (EUR_USD, USD_JPY) を実 backtest で走らせ、
    NotImplementedError 由来の pair_failure が消えていることを確認 (T019 の核心)。
    """
    bars_map = {
        "EUR_JPY": _multi_day_bars(
            pair_name="EUR_JPY", base_bid=Decimal("168.000"), pip_step=Decimal("0.010")
        ),
        "EUR_USD": _multi_day_bars(
            pair_name="EUR_USD", base_bid=Decimal("1.08000"), pip_step=Decimal("0.00010")
        ),
        "USD_JPY": _multi_day_bars(
            pair_name="USD_JPY", base_bid=Decimal("154.000"), pip_step=Decimal("0.010")
        ),
    }
    meta_map = {
        "EUR_JPY": eur_jpy_meta(),
        "EUR_USD": eur_usd_meta(),
        "USD_JPY": usd_jpy_meta(),
    }
    bt_config = BacktestConfig(
        instrument="EUR_JPY",
        start=bars_map["EUR_JPY"][0].bar_time,
        end=bars_map["EUR_JPY"][-1].bar_time + timedelta(minutes=1),
        initial_cash=Decimal("1000000"),
        leverage=5,
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )
    # anchors override: ANCHOR_PAIRS default (EUR_JPY → EUR_USD, USD_JPY) を再利用
    anchor_override = {"EUR_JPY": ("EUR_USD", "USD_JPY")}
    result = evaluate_cross_pair(
        genome=_simple_cross_genome(),
        target="EUR_JPY",
        pair_bars=bars_map,
        pair_meta=meta_map,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.8),
        cross_pair_config=CrossPairConfig(),
        anchor_pairs=anchor_override,
    )
    # 構造的 pair_failure (NotImplementedError) が完全に消えていること
    ni_failures = [rc for rc in result.reason_codes if "NotImplementedError" in rc]
    assert ni_failures == [], (
        f"NotImplementedError pair_failure still present: {result.reason_codes}"
    )
    # 全 3 pair に対して sharpe_per_pair が記録されていること (値は None でも 0.0 でも可)
    sharpes_obj = result.metrics["sharpe_per_pair"]
    assert isinstance(sharpes_obj, dict)
    sharpes: dict[str, float] = sharpes_obj
    assert set(sharpes.keys()) == {"EUR_JPY", "EUR_USD", "USD_JPY"}
    # Sharpe 値は finite（pair_failure 時の dummy 0.0 も finite）
    for pair, sh in sharpes.items():
        assert math.isfinite(sh), f"{pair} sharpe not finite: {sh}"
    # mean_sharpe も finite
    mean_sharpe = result.metrics["mean_sharpe"]
    assert mean_sharpe is not None
    assert isinstance(mean_sharpe, float)
    assert math.isfinite(mean_sharpe)
