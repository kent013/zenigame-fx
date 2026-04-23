"""T012 MODULATOR primitive 6 個の単体テスト。

カバー範囲:
- registry 登録確認 (合計 20 = F14 + M6, MODULATOR 6)
- 共通: 出力 [0, 1] bounded / compute と compute_all_bars 一致 / look-ahead bias
- 個別: M1-M6 の既知入力での期待値・挙動
- snapshot 欠損時の warning + safe default
- strict mode: snapshot=None で RuntimeError
- VixSeriesSnapshot の tz-aware 検証 + 昇順検証
- F1-F14 後方互換 (snapshot 未指定で動作)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import (
    EconomicEventSnapshot,
    EvaluationContext,
    PrimitiveSpec,
    VixSeriesSnapshot,
    clear,
    ensure_registered,
    get_primitive,
    list_all,
    list_by_category,
    list_by_domain,
)
from src.alpha_factory.primitives.modulator_generic import (
    M1_SPEC,
    M2_SPEC,
    M3_SPEC,
    M4_SPEC,
    M5_SPEC,
    M6_SPEC,
    MODULATOR_SPECS,
    all_specs,
)
from src.domain.price import Ohlc, PriceBar
from src.events.calendar import EconomicCalendar, EconomicEvent

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _registry_isolation():
    clear()
    ensure_registered()  # F1-F14 + M1-M6
    yield
    clear()


def _build_bars(
    n: int,
    *,
    seed: int = 42,
    start_price: float = 100.0,
    volatility: float = 0.5,
    base_time: datetime | None = None,
    step: timedelta = timedelta(hours=1),
    spread_bps_const: float | None = None,
) -> list[PriceBar]:
    """ランダムウォーク bars (mid OHLC) を生成。

    spread_bps_const を指定すると bid/ask に対称スプレッドを付与
    （ask = mid * (1 + s/2), bid = mid * (1 - s/2), s = spread_bps_const/10000）。
    None なら bid = ask = mid (zero spread)。
    """
    rng = np.random.default_rng(seed)
    if base_time is None:
        base_time = datetime(2026, 1, 1, 0, tzinfo=UTC)
    prices = [start_price]
    for _ in range(n):
        prices.append(prices[-1] + rng.normal(0, volatility))
    bars: list[PriceBar] = []
    half_s = (spread_bps_const or 0.0) / 2.0 / 10000.0
    for i in range(n):
        o = prices[i]
        c = prices[i + 1]
        hi = max(o, c) + abs(rng.normal(0, 0.1))
        lo = min(o, c) - abs(rng.normal(0, 0.1))
        if spread_bps_const is None:
            bid_ohlc = ask_ohlc = Ohlc(
                open=Decimal(str(o)),
                high=Decimal(str(hi)),
                low=Decimal(str(lo)),
                close=Decimal(str(c)),
            )
        else:
            bid_ohlc = Ohlc(
                open=Decimal(str(o * (1 - half_s))),
                high=Decimal(str(hi * (1 - half_s))),
                low=Decimal(str(lo * (1 - half_s))),
                close=Decimal(str(c * (1 - half_s))),
            )
            ask_ohlc = Ohlc(
                open=Decimal(str(o * (1 + half_s))),
                high=Decimal(str(hi * (1 + half_s))),
                low=Decimal(str(lo * (1 + half_s))),
                close=Decimal(str(c * (1 + half_s))),
            )
        bars.append(
            PriceBar(
                pair_name="EUR_USD",
                bar_time=base_time + step * i,
                bid=bid_ohlc,
                ask=ask_ohlc,
                volume=1000,
                complete=True,
            )
        )
    return bars


def _default_params(spec: PrimitiveSpec) -> dict:
    params: dict = {}
    for p in spec.param_schema:
        if p.default is not None:
            params[p.name] = int(p.default) if p.is_int else float(p.default)
        else:
            params[p.name] = int(p.low) if p.is_int else float(p.low)
    return params


def _mock_event_snapshot(
    events: list[EconomicEvent] | None = None,
    as_of: datetime | None = None,
) -> EconomicEventSnapshot:
    if events is None:
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
                currency="USD",
                name="NFP",
                impact=3,
            ),
        ]
    return EconomicEventSnapshot(
        calendar=EconomicCalendar(events),
        as_of=as_of or datetime(2099, 1, 1, tzinfo=UTC),
    )


def _mock_vix_snapshot(
    bars: list[PriceBar], level: float = 20.0
) -> VixSeriesSnapshot:
    """bars 区間をカバーする daily VIX publication を生成 (level 一定)。"""
    start = bars[0].bar_time.date()
    end = bars[-1].bar_time.date()
    obs: list[tuple[datetime, float]] = []
    cur = start - timedelta(days=5)
    while cur <= end:
        pub_ts = datetime.combine(cur, datetime.min.time()).replace(
            hour=21, minute=15, tzinfo=UTC
        )
        obs.append((pub_ts, level))
        cur += timedelta(days=1)
    return VixSeriesSnapshot(observations=tuple(obs))


def _ctx(
    bars,
    idx: int,
    spec: PrimitiveSpec,
    *,
    pair: str = "EUR_USD",
    event_snapshot: EconomicEventSnapshot | None = None,
    vix_snapshot: VixSeriesSnapshot | None = None,
    strict: bool = False,
    params_override: dict | None = None,
) -> EvaluationContext:
    return EvaluationContext(
        bars=bars,
        idx=idx,
        pair=pair,
        params=params_override or _default_params(spec),
        event_snapshot=event_snapshot,
        vix_snapshot=vix_snapshot,
        strict_snapshot_required=strict,
    )


ALL_MODULATOR_SPECS = (M1_SPEC, M2_SPEC, M3_SPEC, M4_SPEC, M5_SPEC, M6_SPEC)


# ---------------------------------------------------------------------------
# Registry 集計
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_all_required_registered(self):
        # T013 で P1-P12 も登録される (合計 32) ため、ID 集合で subset 検証
        specs = list_all()
        ids = {s.id for s in specs}
        expected_subset = {f"F{i}" for i in range(1, 15)} | {
            f"M{i}" for i in range(1, 7)
        }
        assert expected_subset.issubset(ids)

    def test_modulator_count_includes_m1_to_m6(self):
        # M1-M6 が MODULATOR として存在 (T013 で P6/P10/P11 も MODULATOR 追加)
        mods = list_by_category("MODULATOR")
        mod_ids = {s.id for s in mods}
        assert {f"M{i}" for i in range(1, 7)}.issubset(mod_ids)

    def test_each_modulator_retrievable(self):
        for i in range(1, 7):
            spec = get_primitive(f"M{i}")
            assert spec.category == "MODULATOR"
            assert spec.domain == "generic"

    def test_module_level_spec_tuple_consistent(self):
        assert all_specs() == ALL_MODULATOR_SPECS
        assert MODULATOR_SPECS == ALL_MODULATOR_SPECS

    def test_generic_domain_contains_all_f_and_m(self):
        # T013 で pair_specific 12 も追加されるが、generic は依然 F1-F14 + M1-M6
        generic_ids = {s.id for s in list_by_domain("generic")}
        expected_generic = {f"F{i}" for i in range(1, 15)} | {
            f"M{i}" for i in range(1, 7)
        }
        assert generic_ids == expected_generic


# ---------------------------------------------------------------------------
# 6 個共通テスト（parametrize）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec", ALL_MODULATOR_SPECS, ids=[s.id for s in ALL_MODULATOR_SPECS]
)
class TestEachModulatorCommon:
    def test_compute_matches_compute_all_bars(self, spec):
        bars = _build_bars(120, seed=1, spread_bps_const=2.0)
        ctx_full = _ctx(
            bars,
            100,
            spec,
            event_snapshot=_mock_event_snapshot(),
            vix_snapshot=_mock_vix_snapshot(bars),
        )
        arr = spec.compute_all_bars(ctx_full)
        for idx in (50, 80, 119):
            ctx_idx = _ctx(
                bars,
                idx,
                spec,
                event_snapshot=_mock_event_snapshot(),
                vix_snapshot=_mock_vix_snapshot(bars),
            )
            val_single = spec.compute(ctx_idx)
            val_all = arr[idx]
            if np.isnan(val_all):
                # compute は nan を neutral 値に吸収
                # M4 は neutral=1.0, M5 は neutral=0.5, それ以外は 0.5
                if spec.id == "M4":
                    assert val_single == pytest.approx(1.0)
                else:
                    assert val_single == pytest.approx(0.5)
            else:
                assert val_single == pytest.approx(float(val_all), abs=1e-12)

    def test_output_bounded_0_to_1(self, spec):
        bars = _build_bars(150, seed=2, spread_bps_const=2.0)
        ctx = _ctx(
            bars,
            149,
            spec,
            event_snapshot=_mock_event_snapshot(),
            vix_snapshot=_mock_vix_snapshot(bars),
        )
        arr = spec.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert np.all(valid >= -1e-9)
        assert np.all(valid <= 1.0 + 1e-9)

    def test_no_lookahead_property(self, spec):
        """bars[k+1:] を改変しても compute_all_bars(bars')[:k+1] は不変。"""
        bars_orig = _build_bars(120, seed=3, spread_bps_const=2.0)
        k = 60
        snap_e = _mock_event_snapshot()
        snap_v = _mock_vix_snapshot(bars_orig)
        ctx_orig = _ctx(
            bars_orig,
            119,
            spec,
            event_snapshot=snap_e,
            vix_snapshot=snap_v,
        )
        result_orig = spec.compute_all_bars(ctx_orig)

        bars_replacement = _build_bars(
            120 - (k + 1), seed=999, spread_bps_const=2.0
        )
        bars_mod = list(bars_orig[: k + 1]) + list(bars_replacement)
        bars_mod_fixed: list[PriceBar] = []
        for i, b in enumerate(bars_mod):
            bars_mod_fixed.append(
                PriceBar(
                    pair_name=b.pair_name,
                    bar_time=bars_orig[i].bar_time,
                    bid=b.bid,
                    ask=b.ask,
                    volume=b.volume,
                    complete=b.complete,
                )
            )
        ctx_mod = _ctx(
            bars_mod_fixed,
            119,
            spec,
            event_snapshot=snap_e,
            vix_snapshot=snap_v,
        )
        result_mod = spec.compute_all_bars(ctx_mod)

        np.testing.assert_allclose(
            result_orig[: k + 1],
            result_mod[: k + 1],
            equal_nan=True,
            atol=1e-10,
        )


# ---------------------------------------------------------------------------
# M1 ATRRegimeGate
# ---------------------------------------------------------------------------


class TestM1ATRRegime:
    def test_high_vol_with_prefer_high_close_to_one(self):
        # 大きな volatility → ATR_rel 大 → prefer_high=1 で 1 寄り
        bars = _build_bars(80, seed=10, volatility=2.0)
        ctx = _ctx(bars, 79, M1_SPEC)
        arr = M1_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        # 後半 (warmup 後) の中央値が 0.5 より上
        assert np.median(valid[-30:]) > 0.5

    def test_low_vol_with_prefer_high_close_to_zero(self):
        bars = _build_bars(80, seed=11, volatility=0.05)
        ctx = _ctx(bars, 79, M1_SPEC)
        arr = M1_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert np.median(valid[-30:]) < 0.5

    def test_prefer_low_inverts_response(self):
        bars = _build_bars(80, seed=12, volatility=2.0)
        params_high = _default_params(M1_SPEC)
        params_low = dict(params_high, prefer_high=0)
        ctx_high = _ctx(bars, 79, M1_SPEC, params_override=params_high)
        ctx_low = _ctx(bars, 79, M1_SPEC, params_override=params_low)
        arr_high = M1_SPEC.compute_all_bars(ctx_high)
        arr_low = M1_SPEC.compute_all_bars(ctx_low)
        # prefer_high=1 と 0 は sigmoid の符号が反転 → 和 ~ 1.0
        idx = ~np.isnan(arr_high) & ~np.isnan(arr_low)
        assert np.allclose(arr_high[idx] + arr_low[idx], 1.0, atol=1e-9)


# ---------------------------------------------------------------------------
# M2 SessionGate
# ---------------------------------------------------------------------------


class TestM2SessionGate:
    def test_outside_tokyo_is_zero(self):
        # UTC 10:00 開始 → 全 bar tokyo (0-9 UTC) 外
        base = datetime(2026, 1, 1, 10, tzinfo=UTC)
        bars = _build_bars(8, seed=20, base_time=base)
        ctx = _ctx(
            bars, 7, M2_SPEC,
            params_override={"session": 0, "soft_edge_min": 0.0},
        )
        arr = M2_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_inside_tokyo_is_one_step(self):
        base = datetime(2026, 1, 1, 3, tzinfo=UTC)
        bars = _build_bars(5, seed=21, base_time=base)
        ctx = _ctx(
            bars, 4, M2_SPEC,
            params_override={"session": 0, "soft_edge_min": 0.0},
        )
        arr = M2_SPEC.compute_all_bars(ctx)
        # UTC 03:00 - 07:00 → 全 tokyo session 内
        assert np.allclose(arr, 1.0)

    def test_soft_edge_blends_at_boundary(self):
        # London (7-16 UTC) 開始 30 分前から
        base = datetime(2026, 1, 1, 6, 30, tzinfo=UTC)
        bars = _build_bars(4, seed=22, base_time=base, step=timedelta(minutes=15))
        ctx = _ctx(
            bars, 3, M2_SPEC,
            params_override={"session": 1, "soft_edge_min": 30.0},
        )
        arr = M2_SPEC.compute_all_bars(ctx)
        # 0 < val < 1 の値が境界近辺で発生
        assert np.all(arr > 0.0)
        assert np.all(arr < 1.0)


# ---------------------------------------------------------------------------
# M3 SpreadConditionGate
# ---------------------------------------------------------------------------


class TestM3SpreadCondition:
    def test_low_spread_close_to_one(self):
        # spread_bps=1.0 < threshold=2.0 → close to 1
        bars = _build_bars(40, seed=30, spread_bps_const=1.0)
        ctx = _ctx(bars, 39, M3_SPEC)
        arr = M3_SPEC.compute_all_bars(ctx)
        # k=1.0 で sigmoid(-(1 - 2)) = sigmoid(1) ≈ 0.731
        valid = arr[~np.isnan(arr)]
        assert np.all(valid > 0.5)
        assert valid.mean() == pytest.approx(0.7310, abs=0.01)

    def test_high_spread_close_to_zero(self):
        # spread_bps=10.0 >> threshold=2.0 → close to 0
        bars = _build_bars(40, seed=31, spread_bps_const=10.0)
        ctx = _ctx(bars, 39, M3_SPEC)
        arr = M3_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        # sigmoid(-(10 - 2)) = sigmoid(-8) ≈ 0.000335
        assert np.all(valid < 0.01)


# ---------------------------------------------------------------------------
# M4 EconomicEventGate
# ---------------------------------------------------------------------------


class TestM4EconomicEventGate:
    def test_no_snapshot_returns_one_with_warning(self):
        bars = _build_bars(20, seed=40)
        ctx = _ctx(bars, 19, M4_SPEC)
        with pytest.warns(RuntimeWarning, match="event_snapshot is None"):
            arr = M4_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 1.0)

    def test_event_at_bar_time_suppresses(self):
        # bar_time = 12:30 UTC で event_time = 12:30 UTC → diff_min = 0
        # raw = (window_min - 0) / scale_min = 30 / 5 = 6, sigmoid(6) ≈ 0.9975
        # out = 1 - 0.9975 = 0.0025
        base = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
        bars = _build_bars(1, seed=41, base_time=base)
        snap = _mock_event_snapshot()  # NFP at 12:30 UTC
        ctx = _ctx(bars, 0, M4_SPEC, event_snapshot=snap)
        arr = M4_SPEC.compute_all_bars(ctx)
        assert arr[0] < 0.01

    def test_far_from_event_close_to_one(self):
        # bar_time = 18:00 UTC, event 12:30 UTC → diff = 330 min >> window=30
        base = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)
        bars = _build_bars(1, seed=42, base_time=base)
        snap = _mock_event_snapshot()
        ctx = _ctx(bars, 0, M4_SPEC, event_snapshot=snap)
        arr = M4_SPEC.compute_all_bars(ctx)
        assert arr[0] > 0.99

    def test_min_impact_filters_low_impact_events(self):
        # impact=2 (Medium) のイベントは min_impact=3 で無視 → gate 開放
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
                currency="USD",
                name="MediumEvent",
                impact=2,
            ),
        ]
        snap = EconomicEventSnapshot(
            calendar=EconomicCalendar(events),
            as_of=datetime(2099, 1, 1, tzinfo=UTC),
        )
        bars = _build_bars(1, seed=43, base_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC))
        ctx = _ctx(bars, 0, M4_SPEC, event_snapshot=snap)
        arr = M4_SPEC.compute_all_bars(ctx)
        assert arr[0] == pytest.approx(1.0)

    def test_as_of_excludes_future_event(self):
        # as_of = 2026-01-01 11:00 (event 12:30 より前) → event は未知扱いで無視
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
                currency="USD",
                name="NFP",
                impact=3,
            ),
        ]
        snap = EconomicEventSnapshot(
            calendar=EconomicCalendar(events),
            as_of=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        )
        bars = _build_bars(1, seed=44, base_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC))
        ctx = _ctx(bars, 0, M4_SPEC, event_snapshot=snap)
        arr = M4_SPEC.compute_all_bars(ctx)
        # as_of で除外 → event なし → gate 全開 1.0
        assert arr[0] == pytest.approx(1.0)

    def test_currency_filter_includes_base_or_quote(self):
        # EUR_USD で USD event は含まれる、JPY event は除外
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
                currency="JPY",
                name="JPY_NFP",
                impact=3,
            ),
        ]
        snap = EconomicEventSnapshot(
            calendar=EconomicCalendar(events),
            as_of=datetime(2099, 1, 1, tzinfo=UTC),
        )
        bars = _build_bars(1, seed=45, base_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC))
        ctx = _ctx(bars, 0, M4_SPEC, event_snapshot=snap)  # pair=EUR_USD
        arr = M4_SPEC.compute_all_bars(ctx)
        # JPY は EUR/USD どちらにも該当しない → gate 開放
        assert arr[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# M5 VIXRegimeGate
# ---------------------------------------------------------------------------


class TestM5VIXRegimeGate:
    def test_no_snapshot_returns_neutral_with_warning(self):
        bars = _build_bars(20, seed=50)
        ctx = _ctx(bars, 19, M5_SPEC)
        with pytest.warns(RuntimeWarning, match="vix_snapshot missing"):
            arr = M5_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.5)

    def test_low_vix_close_to_one(self):
        bars = _build_bars(40, seed=51)
        snap = _mock_vix_snapshot(bars, level=10.0)
        ctx = _ctx(bars, 39, M5_SPEC, vix_snapshot=snap)
        arr = M5_SPEC.compute_all_bars(ctx)
        # threshold=20, scale=5 → sigmoid((20-10)/5) = sigmoid(2) ≈ 0.881
        valid = arr[arr != 0.5]  # 前半 neutral 区間を除外
        if valid.size > 0:
            assert valid.mean() > 0.7

    def test_high_vix_close_to_zero(self):
        bars = _build_bars(40, seed=52)
        snap = _mock_vix_snapshot(bars, level=35.0)
        ctx = _ctx(bars, 39, M5_SPEC, vix_snapshot=snap)
        arr = M5_SPEC.compute_all_bars(ctx)
        # sigmoid((20-35)/5) = sigmoid(-3) ≈ 0.047
        valid = arr[arr != 0.5]
        if valid.size > 0:
            assert valid.mean() < 0.2

    def test_strict_less_than_publication(self):
        """publication_ts == bar_time のとき strict less than で除外。"""
        # publication 1 件、bar_time = publication ts ちょうど
        pub_ts = datetime(2026, 1, 1, 21, 15, tzinfo=UTC)
        snap = VixSeriesSnapshot(observations=((pub_ts, 15.0),))
        bars = _build_bars(1, seed=53, base_time=pub_ts)  # bar_time = pub_ts
        ctx = _ctx(bars, 0, M5_SPEC, vix_snapshot=snap)
        arr = M5_SPEC.compute_all_bars(ctx)
        # bisect_left で index 0 → 該当 publication なし → neutral 0.5
        assert arr[0] == pytest.approx(0.5)

        # bar_time = pub_ts + 1 us → 該当 publication あり
        bars2 = _build_bars(
            1, seed=54, base_time=pub_ts + timedelta(microseconds=1)
        )
        ctx2 = _ctx(bars2, 0, M5_SPEC, vix_snapshot=snap)
        arr2 = M5_SPEC.compute_all_bars(ctx2)
        assert arr2[0] != 0.5


# ---------------------------------------------------------------------------
# M6 TrendStrengthGate
# ---------------------------------------------------------------------------


class TestM6TrendStrength:
    def test_strong_trend_close_to_one(self):
        # 強いドリフト = ADX 高
        rng = np.random.default_rng(60)
        prices = np.cumsum(rng.normal(0.5, 0.1, 200)) + 100.0  # strong drift
        bars: list[PriceBar] = []
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(200):
            o = float(prices[i])
            c = float(prices[i] + 0.1)
            ohlc = Ohlc(
                open=Decimal(str(o)),
                high=Decimal(str(c + 0.1)),
                low=Decimal(str(o - 0.1)),
                close=Decimal(str(c)),
            )
            bars.append(
                PriceBar(
                    pair_name="EUR_USD",
                    bar_time=base + timedelta(hours=i),
                    bid=ohlc, ask=ohlc, volume=1000, complete=True,
                )
            )
        ctx = _ctx(bars, 199, M6_SPEC)
        arr = M6_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert np.median(valid[-50:]) > 0.5  # ADX > 25 想定

    def test_random_walk_low_adx_ratio(self):
        """純粋ランダムウォークでも ADX は揺らぐので、強トレンド入力との差を見る。"""
        # ランダムウォーク
        bars_rw = _build_bars(300, seed=61, volatility=0.5)
        ctx_rw = _ctx(bars_rw, 299, M6_SPEC)
        arr_rw = M6_SPEC.compute_all_bars(ctx_rw)
        valid_rw = arr_rw[~np.isnan(arr_rw)]
        # 強トレンド入力 (drift = 0.5)
        rng = np.random.default_rng(62)
        prices = np.cumsum(rng.normal(0.5, 0.1, 300)) + 100.0
        bars_tr: list[PriceBar] = []
        base = datetime(2026, 1, 1, tzinfo=UTC)
        for i in range(300):
            o = float(prices[i])
            c = float(prices[i] + 0.1)
            ohlc = Ohlc(
                open=Decimal(str(o)),
                high=Decimal(str(c + 0.1)),
                low=Decimal(str(o - 0.1)),
                close=Decimal(str(c)),
            )
            bars_tr.append(
                PriceBar(
                    pair_name="EUR_USD",
                    bar_time=base + timedelta(hours=i),
                    bid=ohlc, ask=ohlc, volume=1000, complete=True,
                )
            )
        ctx_tr = _ctx(bars_tr, 299, M6_SPEC)
        arr_tr = M6_SPEC.compute_all_bars(ctx_tr)
        valid_tr = arr_tr[~np.isnan(arr_tr)]
        # 強トレンドのほうが平均値が大きい
        assert valid_tr[-100:].mean() > valid_rw[-100:].mean()


# ---------------------------------------------------------------------------
# strict mode
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_m4_raises_when_strict_and_no_snapshot(self):
        bars = _build_bars(30, seed=70)
        ctx = _ctx(bars, 29, M4_SPEC, strict=True)
        with pytest.raises(RuntimeError, match="event_snapshot is None"):
            M4_SPEC.compute_all_bars(ctx)

    def test_m5_raises_when_strict_and_no_snapshot(self):
        bars = _build_bars(30, seed=71)
        ctx = _ctx(bars, 29, M5_SPEC, strict=True)
        with pytest.raises(RuntimeError, match="vix_snapshot missing"):
            M5_SPEC.compute_all_bars(ctx)

    def test_m5_raises_when_strict_and_empty_observations(self):
        bars = _build_bars(30, seed=72)
        empty = VixSeriesSnapshot(observations=())
        ctx = _ctx(bars, 29, M5_SPEC, strict=True, vix_snapshot=empty)
        with pytest.raises(RuntimeError, match="vix_snapshot missing"):
            M5_SPEC.compute_all_bars(ctx)


# ---------------------------------------------------------------------------
# VixSeriesSnapshot バリデーション
# ---------------------------------------------------------------------------


class TestVixSnapshotValidation:
    def test_naive_datetime_raises(self):
        with pytest.raises(ValueError, match="tz-aware"):
            VixSeriesSnapshot(
                observations=((datetime(2026, 1, 1, 21, 15), 20.0),)
            )

    def test_descending_order_raises(self):
        ts1 = datetime(2026, 1, 2, 21, 15, tzinfo=UTC)
        ts2 = datetime(2026, 1, 1, 21, 15, tzinfo=UTC)
        with pytest.raises(ValueError, match="ascending"):
            VixSeriesSnapshot(observations=((ts1, 20.0), (ts2, 21.0)))

    def test_lookup_returns_none_for_empty(self):
        snap = VixSeriesSnapshot(observations=())
        assert snap.lookup(datetime(2026, 1, 1, tzinfo=UTC)) is None

    def test_lookup_strict_less_than(self):
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        snap = VixSeriesSnapshot(observations=((ts, 20.0),))
        # bar_time == publication → strict less than → None
        assert snap.lookup(ts) is None
        # bar_time > publication → 値を返す
        assert snap.lookup(ts + timedelta(microseconds=1)) == 20.0


# ---------------------------------------------------------------------------
# 後方互換 (T011 既存挙動を壊さないこと)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_existing_f_primitives_work_without_snapshots(self):
        """F1-F14 は event_snapshot/vix_snapshot なしで動くこと。"""
        bars = _build_bars(100, seed=80)
        for fid in [f"F{i}" for i in range(1, 15)]:
            spec = get_primitive(fid)
            params = _default_params(spec)
            # F5 は short_n < long_n を必要とするので default のまま
            ctx = EvaluationContext(
                bars=bars, idx=99, pair="EUR_USD", params=params
            )
            val = spec.compute(ctx)
            assert isinstance(val, float)

    def test_evaluation_context_field_addition_keeps_default(self):
        """新フィールド未指定でも EvaluationContext が構築できる。"""
        bars = _build_bars(10, seed=81)
        ctx = EvaluationContext(
            bars=bars, idx=9, pair="EUR_USD", params={"n": 14}
        )
        assert ctx.event_snapshot is None
        assert ctx.vix_snapshot is None
        assert ctx.strict_snapshot_required is False

    def test_f6_session_output_consistent_after_indicator_move(self):
        """F6 の _SESSION_RANGES_UTC を _indicators.py に移動しても出力が変わらない。"""
        from src.alpha_factory.primitives.directional_generic import F6_SPEC

        base = datetime(2026, 1, 1, 0, tzinfo=UTC)
        bars = _build_bars(48, seed=82, base_time=base)
        ctx = EvaluationContext(
            bars=bars,
            idx=47,
            pair="EUR_USD",
            params={"session": 0, "k": 1.0, "atr_n": 14},
        )
        arr = F6_SPEC.compute_all_bars(ctx)
        assert arr.shape == (48,)
        # session 外 (UTC 9:00 以降) は 0 のまま
        for i in range(48):
            t = bars[i].bar_time.astimezone(UTC).hour
            if not (0 <= t < 9):
                assert arr[i] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# RegistryEvaluator 経由
# ---------------------------------------------------------------------------


class TestViaRegistryEvaluator:
    def test_evaluate_modulator_returns_float_in_0_1(self):
        from src.alpha_factory.primitives import RegistryEvaluator
        from src.dsl.genome import SignalConfig

        bars = _build_bars(100, seed=90, spread_bps_const=2.0)
        ev = RegistryEvaluator(pair="EUR_USD")
        for spec in ALL_MODULATOR_SPECS:
            sig = SignalConfig(
                name=spec.id, weight=1.0, params=_default_params(spec)
            )
            # M4/M5 は snapshot 無しでも warn + safe default で動くはず
            with pytest.warns() if spec.id in ("M4", "M5") else _no_warn_context():
                val = ev.evaluate(bars, 90, sig)
            assert isinstance(val, float)
            assert -1e-9 <= val <= 1.0 + 1e-9


class _NoWarnContext:
    """no-op context manager (M1-M3, M6 用)。"""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _no_warn_context():
    return _NoWarnContext()
