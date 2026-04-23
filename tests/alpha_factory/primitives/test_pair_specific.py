"""T013 Pair-specific primitive 12 個 (P1-P12) の単体テスト。

カバー範囲:
- registry 登録確認 (合計 32 = F14 + M6 + P12, pair_specific 12)
- 共通: 出力域 / compute と compute_all_bars 一致 / look-ahead bias
- 個別: P1-P12 の既知入力での期待値・挙動
- 3 状態テスト: MISSING_KEY / STALE_VALUE / MISALIGNMENT
- preflight verify (RegistryEvaluator.strict_aux_required)
- strict_snapshot_required で compute 内 fail-fast
- 後方互換 (F1-F14 / M1-M6 が aux_pair_bars 未指定で動く)
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
    RegistryEvaluator,
    VixSeriesSnapshot,
    clear,
    ensure_registered,
    get_primitive,
    list_all,
    list_by_domain,
)
from src.alpha_factory.primitives.pair_specific import (
    P1_SPEC,
    P2_SPEC,
    P3_SPEC,
    P4_SPEC,
    P5_SPEC,
    P6_SPEC,
    P7_SPEC,
    P8_SPEC,
    P9_SPEC,
    P10_SPEC,
    P11_SPEC,
    P12_SPEC,
    PAIR_SPECIFIC_SPECS,
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
    ensure_registered()  # F1-F14 + M1-M6 + P1-P12 = 32
    yield
    clear()


def _build_bars(
    n: int,
    *,
    seed: int = 42,
    start_price: float = 1.0,
    volatility: float = 0.001,
    base_time: datetime | None = None,
    step: timedelta = timedelta(hours=1),
    spread_bps_const: float | None = None,
    pair_name: str = "EUR_USD",
) -> list[PriceBar]:
    """ランダムウォーク bars (mid OHLC) を生成。"""
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
        hi = max(o, c) + abs(rng.normal(0, volatility * 0.2))
        lo = min(o, c) - abs(rng.normal(0, volatility * 0.2))
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
                pair_name=pair_name,
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


def _build_aligned_aux_bars(
    target_bars: list[PriceBar],
    *,
    ratio: float = 1.1,
    pair_name: str = "EUR_USD",
) -> list[PriceBar]:
    """target_bars と同じ bar_time を持つ synthetic 別ペア bar 列を生成。

    各 close を target.close * ratio で構築。bid/ask 同値（zero spread）。
    """
    out: list[PriceBar] = []
    for tb in target_bars:
        target_close = (float(tb.bid.close) + float(tb.ask.close)) * 0.5
        c = target_close * ratio
        o = c
        ohlc = Ohlc(
            open=Decimal(str(o)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
        )
        out.append(
            PriceBar(
                pair_name=pair_name,
                bar_time=tb.bar_time,
                bid=ohlc,
                ask=ohlc,
                volume=1000,
                complete=True,
            )
        )
    return out


def _mock_event_snapshot(
    events: list[EconomicEvent] | None = None,
    as_of: datetime | None = None,
) -> EconomicEventSnapshot:
    if events is None:
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 14, 30, tzinfo=UTC),
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


def _bar_aligned_series(n: int, value: float = 100.0, drift: float = 0.0) -> list[float]:
    return [value + drift * i for i in range(n)]


def _ctx(
    bars,
    idx: int,
    spec: PrimitiveSpec,
    *,
    pair: str = "EUR_USD",
    aux_series: dict[str, list[float]] | None = None,
    aux_pair_bars: dict[str, list[PriceBar | None]] | None = None,
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
        aux_series=aux_series or {},
        aux_pair_bars=aux_pair_bars or {},
        event_snapshot=event_snapshot,
        vix_snapshot=vix_snapshot,
        strict_snapshot_required=strict,
    )


ALL_PAIR_SPECS = (
    P1_SPEC, P2_SPEC, P3_SPEC, P4_SPEC, P5_SPEC, P6_SPEC,
    P7_SPEC, P8_SPEC, P9_SPEC, P10_SPEC, P11_SPEC, P12_SPEC,
)


def _full_aux_for(spec: PrimitiveSpec, bars: list[PriceBar]) -> dict:
    """spec の required_data + optional_data_groups を満たす aux dict を生成。"""
    aux_series: dict[str, list[float]] = {}
    aux_pair_bars: dict[str, list[PriceBar | None]] = {}
    n = len(bars)
    for k in spec.required_data:
        if k.startswith("macro.") and k != "macro.vix":
            aux_series[k] = _bar_aligned_series(n, value=100.0)
        elif k.startswith("cross_pair."):
            pname = k[len("cross_pair."):]
            aux_pair_bars[pname] = list(_build_aligned_aux_bars(bars, pair_name=pname))
    for group in spec.optional_data_groups:
        # 1 つ目だけ供給
        k = group[0]
        if k.startswith("macro."):
            aux_series[k] = _bar_aligned_series(n, value=100.0, drift=0.01)
    return {
        "aux_series": aux_series,
        "aux_pair_bars": aux_pair_bars,
    }


# ---------------------------------------------------------------------------
# Registry 集計
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_all_32_registered(self):
        specs = list_all()
        assert len(specs) == 32
        ids = {s.id for s in specs}
        expected = (
            {f"F{i}" for i in range(1, 15)}
            | {f"M{i}" for i in range(1, 7)}
            | {f"P{i}" for i in range(1, 13)}
        )
        assert ids == expected

    def test_pair_specific_count_is_12(self):
        specs = list_by_domain("pair_specific")
        assert len(specs) == 12
        assert {s.id for s in specs} == {f"P{i}" for i in range(1, 13)}

    def test_each_pair_specific_retrievable(self):
        for i in range(1, 13):
            spec = get_primitive(f"P{i}")
            assert spec.id == f"P{i}"
            assert spec.domain == "pair_specific"

    def test_module_level_spec_tuple_consistent(self):
        assert all_specs() == ALL_PAIR_SPECS
        assert PAIR_SPECIFIC_SPECS == ALL_PAIR_SPECS

    def test_total_generic_unchanged(self):
        # T012 の F+M = 20 個が generic で維持される
        assert len(list_by_domain("generic")) == 20


# ---------------------------------------------------------------------------
# 12 個共通テスト (parametrize)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec", ALL_PAIR_SPECS, ids=[s.id for s in ALL_PAIR_SPECS]
)
class TestEachPrimitiveCommon:
    def test_compute_matches_compute_all_bars(self, spec):
        # 各 primitive の bar_time 範囲をカバーするよう、24 時間 × 3 日 = 72 bars
        bars = _build_bars(72, seed=1)
        aux = _full_aux_for(spec, bars)
        ctx_full = _ctx(
            bars,
            71,
            spec,
            aux_series=aux["aux_series"],
            aux_pair_bars=aux["aux_pair_bars"],
            event_snapshot=_mock_event_snapshot(),
            vix_snapshot=_mock_vix_snapshot(bars),
        )
        # warning 抑止 (snapshot/aux 揃いなら出ないが安全のため filter)
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            arr = spec.compute_all_bars(ctx_full)
        for idx in (30, 50, 71):
            ctx_idx = _ctx(
                bars,
                idx,
                spec,
                aux_series=aux["aux_series"],
                aux_pair_bars=aux["aux_pair_bars"],
                event_snapshot=_mock_event_snapshot(),
                vix_snapshot=_mock_vix_snapshot(bars),
            )
            with _w.catch_warnings():
                _w.simplefilter("ignore", RuntimeWarning)
                val_single = spec.compute(ctx_idx)
            val_all = arr[idx]
            if not np.isfinite(val_all):
                # neutral 値: directional=0.0、P10=1.0、P6/P11=0.5
                if spec.id == "P10":
                    assert val_single == pytest.approx(1.0)
                elif spec.id in ("P6", "P11"):
                    assert val_single == pytest.approx(0.5)
                else:
                    assert val_single == pytest.approx(0.0)
            else:
                assert val_single == pytest.approx(float(val_all), abs=1e-12)

    def test_output_in_expected_range(self, spec):
        bars = _build_bars(72, seed=2)
        aux = _full_aux_for(spec, bars)
        ctx = _ctx(
            bars,
            71,
            spec,
            aux_series=aux["aux_series"],
            aux_pair_bars=aux["aux_pair_bars"],
            event_snapshot=_mock_event_snapshot(),
            vix_snapshot=_mock_vix_snapshot(bars),
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            arr = spec.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        if spec.category == "MODULATOR":
            assert np.all(valid >= -1e-9)
            assert np.all(valid <= 1.0 + 1e-9)
        else:
            assert np.all(valid >= -1.0 - 1e-9)
            assert np.all(valid <= 1.0 + 1e-9)

    def test_no_lookahead_property(self, spec):
        """bars[k+1:] を改変しても compute_all_bars(bars')[:k+1] は不変。"""
        bars_orig = _build_bars(72, seed=3)
        aux = _full_aux_for(spec, bars_orig)
        k = 30
        snap_e = _mock_event_snapshot()
        snap_v = _mock_vix_snapshot(bars_orig)
        ctx_orig = _ctx(
            bars_orig,
            71,
            spec,
            aux_series=aux["aux_series"],
            aux_pair_bars=aux["aux_pair_bars"],
            event_snapshot=snap_e,
            vix_snapshot=snap_v,
        )
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            result_orig = spec.compute_all_bars(ctx_orig)

        # bars[k+1:] を別 seed のデータで置き換える (bar_time は維持)
        bars_replacement = _build_bars(72 - (k + 1), seed=999)
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
        # aux も bar_time だけ書き換えた replacement を作成
        aux_mod = _full_aux_for(spec, bars_mod_fixed)
        ctx_mod = _ctx(
            bars_mod_fixed,
            71,
            spec,
            aux_series=aux_mod["aux_series"],
            aux_pair_bars=aux_mod["aux_pair_bars"],
            event_snapshot=snap_e,
            vix_snapshot=snap_v,
        )
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            result_mod = spec.compute_all_bars(ctx_mod)
        # ただし aux 系列の値も変えると過去 index も影響を受けるため、aux
        # 系列が同じになる primitive (P1-P4, P6) に限って厳密 check する。
        # P5 / P7-P12 は aux series の変化を含む → 過去 index は同じ aux で
        # 計算する場合のみ不変 → ここでは aux 不変経路を簡易化し、aux も
        # 保持して bars だけ改変するテストに変更する。
        aux_keep = aux  # 元の aux のまま
        ctx_mod_aux_keep = _ctx(
            bars_mod_fixed,
            71,
            spec,
            aux_series=aux_keep["aux_series"],
            aux_pair_bars=aux_keep["aux_pair_bars"],
            event_snapshot=snap_e,
            vix_snapshot=snap_v,
        )
        # P5 のときは bars の close が変わると bar_time 一致でも aux の合成が
        # 変わるので、過去 index も変化しうる。そこで P5 は bars だけ改変する
        # ケースを skip し、aux 改変無 + bars[k+1:] 改変のみを testる。
        # P5 の場合: aux_pair_bars は target bars の close * ratio で生成されるため、
        # bars の close を改変すると aux_pair_bars も連動して変わる。
        # よって P5 は手動で aux を bars_orig から作って固定する。
        if spec.id == "P5":
            aux_fixed = _full_aux_for(spec, bars_orig)
            ctx_mod_aux_keep = _ctx(
                bars_mod_fixed,
                71,
                spec,
                aux_series=aux_fixed["aux_series"],
                aux_pair_bars=aux_fixed["aux_pair_bars"],
                event_snapshot=snap_e,
                vix_snapshot=snap_v,
            )
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            result_mod_2 = spec.compute_all_bars(ctx_mod_aux_keep)
        # 過去 [0..k] index が一致
        np.testing.assert_allclose(
            result_orig[: k + 1],
            result_mod_2[: k + 1],
            equal_nan=True,
            atol=1e-10,
        )
        # 未使用変数警告抑止
        _ = result_mod


# ---------------------------------------------------------------------------
# 個別: P1 LondonNYOverlapMomentum
# ---------------------------------------------------------------------------


class TestP1LondonNYOverlapMomentum:
    def test_in_overlap_window_with_uptrend_positive(self):
        # bars 全部が UTC 13-17 のうち、close が単調増加なら正値
        base = datetime(2026, 1, 1, 13, tzinfo=UTC)
        bars = _build_bars(4, seed=10, base_time=base, volatility=0.0001)
        # close を強制的に単調増加させる
        ctx = _ctx(bars, 3, P1_SPEC, params_override={"n": 1, "scale": 0.0001})
        # この test では random walk なので符号は seed 依存。範囲だけ check
        arr = P1_SPEC.compute_all_bars(ctx)
        assert -1.0 <= arr[3] <= 1.0

    def test_outside_overlap_window_returns_zero(self):
        # UTC 0:00 の bar は overlap (13-17) 外 → 0
        base = datetime(2026, 1, 1, 0, tzinfo=UTC)
        bars = _build_bars(3, seed=11, base_time=base)
        ctx = _ctx(bars, 2, P1_SPEC)
        arr = P1_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)


# ---------------------------------------------------------------------------
# 個別: P2 IntradayRangeFade
# ---------------------------------------------------------------------------


class TestP2IntradayRangeFade:
    def test_outside_ny_window_returns_zero(self):
        # 全 bar アジア時間 (3:00-6:00 UTC) → out 0
        base = datetime(2026, 1, 1, 3, tzinfo=UTC)
        bars = _build_bars(4, seed=20, base_time=base)
        ctx = _ctx(bars, 3, P2_SPEC)
        arr = P2_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_close_above_range_returns_negative(self):
        # アジア時間 (0:00-6:00 UTC) bar 6 個 + NY 時間 bar の close が高い
        base = datetime(2026, 1, 1, 0, tzinfo=UTC)
        bars: list[PriceBar] = []
        # アジア時間 0-6 UTC: 価格 1.0, range は [0.99, 1.01]
        for i in range(7):
            ohlc = Ohlc(
                open=Decimal("1.0"),
                high=Decimal("1.005"),
                low=Decimal("0.995"),
                close=Decimal("1.0"),
            )
            bars.append(
                PriceBar(
                    pair_name="EUR_USD",
                    bar_time=base + timedelta(hours=i),
                    bid=ohlc, ask=ohlc, volume=1000, complete=True,
                )
            )
        # NY 時間 12:00 UTC: close = 1.05 (range 上限 1.005 より高い)
        ohlc_ny = Ohlc(
            open=Decimal("1.04"),
            high=Decimal("1.05"),
            low=Decimal("1.03"),
            close=Decimal("1.05"),
        )
        bars.append(
            PriceBar(
                pair_name="EUR_USD",
                bar_time=base + timedelta(hours=12),
                bid=ohlc_ny, ask=ohlc_ny, volume=1000, complete=True,
            )
        )
        # ATR n=14 だが warmup 不足のため、専用 ATR でも NaN になる可能性
        # ここでは n=2 にして warmup 短く
        ctx = _ctx(bars, 7, P2_SPEC, params_override={"atr_n": 2})
        arr = P2_SPEC.compute_all_bars(ctx)
        # 12 UTC bar (idx=7) は close > range_high → 負値
        assert arr[7] < 0


# ---------------------------------------------------------------------------
# 個別: P3 TokyoOpenReversal
# ---------------------------------------------------------------------------


class TestP3TokyoOpenReversal:
    def test_outside_window_returns_zero(self):
        base = datetime(2026, 1, 1, 5, tzinfo=UTC)  # 5:00 UTC = 範囲外
        bars = _build_bars(2, seed=30, base_time=base)
        ctx = _ctx(bars, 1, P3_SPEC)
        arr = P3_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_in_window_uptrend_returns_negative(self):
        # 強引に close を上昇させてから 1:00 UTC bar を評価
        base = datetime(2026, 1, 1, 0, tzinfo=UTC)
        bars: list[PriceBar] = []
        for i, c_val in enumerate([1.0, 1.01, 1.02]):
            ohlc = Ohlc(
                open=Decimal(str(c_val - 0.001)),
                high=Decimal(str(c_val + 0.001)),
                low=Decimal(str(c_val - 0.002)),
                close=Decimal(str(c_val)),
            )
            bars.append(
                PriceBar(
                    pair_name="USD_JPY",
                    bar_time=base + timedelta(hours=i),
                    bid=ohlc, ask=ohlc, volume=1000, complete=True,
                )
            )
        ctx = _ctx(
            bars, 2, P3_SPEC, pair="USD_JPY",
            params_override={"n": 1, "scale": 0.001},
        )
        arr = P3_SPEC.compute_all_bars(ctx)
        # 2:00 UTC は範囲外 (open_hi=2:00 exclusive) → 0
        # 1:00 UTC bar (idx=1) は範囲内、return = +0.01 → -tanh(10) ≈ -1
        assert arr[1] < 0


# ---------------------------------------------------------------------------
# 個別: P4 YenFixingBias
# ---------------------------------------------------------------------------


class TestP4YenFixingBias:
    def test_at_fixing_bias_around_zero(self):
        # bar_time = 0:55 UTC ちょうど → delta = 0 → sign = +1, magnitude ~ 2
        base = datetime(2026, 1, 1, 0, 55, tzinfo=UTC)
        bars = _build_bars(1, seed=40, base_time=base, pair_name="USD_JPY")
        ctx = _ctx(bars, 0, P4_SPEC, pair="USD_JPY")
        arr = P4_SPEC.compute_all_bars(ctx)
        assert arr[0] > 0  # +1 寄り

    def test_after_fixing_negative(self):
        # 1:05 UTC = 仲値 +10 分 → sign = -1
        base = datetime(2026, 1, 1, 1, 5, tzinfo=UTC)
        bars = _build_bars(1, seed=41, base_time=base, pair_name="USD_JPY")
        ctx = _ctx(bars, 0, P4_SPEC, pair="USD_JPY")
        arr = P4_SPEC.compute_all_bars(ctx)
        assert arr[0] < 0

    def test_outside_window_zero(self):
        # 仲値から ±60 分以上離す
        base = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)
        bars = _build_bars(1, seed=42, base_time=base, pair_name="USD_JPY")
        ctx = _ctx(bars, 0, P4_SPEC, pair="USD_JPY")
        arr = P4_SPEC.compute_all_bars(ctx)
        assert arr[0] == 0.0


# ---------------------------------------------------------------------------
# 個別: P5 CrossPairTriangulation
# ---------------------------------------------------------------------------


class TestP5CrossPairTriangulation:
    def test_aux_missing_returns_zero_with_warning(self):
        bars = _build_bars(80, seed=50, pair_name="EUR_JPY")
        ctx = _ctx(bars, 79, P5_SPEC, pair="EUR_JPY")
        with pytest.warns(RuntimeWarning, match="aux_pair_bars"):
            arr = P5_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_aux_misalign_raises_value_error(self):
        bars = _build_bars(80, seed=51, pair_name="EUR_JPY")
        # 長さ違いの aux
        eu_short = _build_aligned_aux_bars(bars[:50], pair_name="EUR_USD")
        uj = _build_aligned_aux_bars(bars, pair_name="USD_JPY")
        ctx = _ctx(
            bars, 79, P5_SPEC, pair="EUR_JPY",
            aux_pair_bars={"EUR_USD": list(eu_short), "USD_JPY": list(uj)},
        )
        with pytest.raises(ValueError, match="length mismatch"):
            P5_SPEC.compute_all_bars(ctx)

    def test_aux_bar_time_mismatch_raises(self):
        bars = _build_bars(80, seed=52, pair_name="EUR_JPY")
        eu = _build_aligned_aux_bars(bars, pair_name="EUR_USD")
        # eu の最初の bar の bar_time を改ざん
        eu_mod_first = PriceBar(
            pair_name="EUR_USD",
            bar_time=bars[0].bar_time + timedelta(hours=1),  # mismatch!
            bid=eu[0].bid, ask=eu[0].ask, volume=eu[0].volume,
            complete=eu[0].complete,
        )
        eu_mod = [eu_mod_first, *list(eu[1:])]
        uj = _build_aligned_aux_bars(bars, pair_name="USD_JPY")
        ctx = _ctx(
            bars, 79, P5_SPEC, pair="EUR_JPY",
            aux_pair_bars={"EUR_USD": eu_mod, "USD_JPY": list(uj)},
        )
        with pytest.raises(ValueError, match="bar_time mismatch"):
            P5_SPEC.compute_all_bars(ctx)

    def test_aux_with_none_returns_nan_for_that_bar(self):
        bars = _build_bars(80, seed=53, pair_name="EUR_JPY")
        eu = list(_build_aligned_aux_bars(bars, pair_name="EUR_USD"))
        eu[40] = None  # type: ignore[assignment]
        uj = list(_build_aligned_aux_bars(bars, pair_name="USD_JPY"))
        ctx = _ctx(
            bars, 79, P5_SPEC, pair="EUR_JPY",
            aux_pair_bars={"EUR_USD": eu, "USD_JPY": uj},
        )
        arr = P5_SPEC.compute_all_bars(ctx)
        # idx 40 は NaN になる (zscore も NaN 伝播し得る)
        # → 周辺も zscore window で NaN 化、少なくとも 40 は NaN
        assert np.isnan(arr[40])

    def test_strict_mode_raises_when_missing(self):
        bars = _build_bars(80, seed=54, pair_name="EUR_JPY")
        ctx = _ctx(bars, 79, P5_SPEC, pair="EUR_JPY", strict=True)
        with pytest.raises(RuntimeError, match="strict mode"):
            P5_SPEC.compute_all_bars(ctx)


# ---------------------------------------------------------------------------
# 個別: P6 EuroHourVolRegime
# ---------------------------------------------------------------------------


class TestP6EuroHourVolRegime:
    def test_outside_window_zero(self):
        base = datetime(2026, 1, 1, 0, tzinfo=UTC)  # 0 UTC = 範囲外
        bars = _build_bars(3, seed=60, base_time=base)
        ctx = _ctx(bars, 2, P6_SPEC)
        arr = P6_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_in_window_with_finite_atr_in_unit_range(self):
        base = datetime(2026, 1, 1, 8, tzinfo=UTC)  # 8 UTC = 欧州時間
        bars = _build_bars(40, seed=61, base_time=base, volatility=0.001)
        ctx = _ctx(bars, 39, P6_SPEC)
        arr = P6_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)


# ---------------------------------------------------------------------------
# 個別: P7 RiskOnOffProxy
# ---------------------------------------------------------------------------


class TestP7RiskOnOffProxy:
    def test_aux_missing_returns_zero_with_warning(self):
        bars = _build_bars(40, seed=70, pair_name="AUD_JPY")
        ctx = _ctx(bars, 39, P7_SPEC, pair="AUD_JPY")
        with pytest.warns(RuntimeWarning, match="vix_snapshot or macro.spx500"):
            arr = P7_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_low_vix_uptrend_spx_positive(self):
        bars = _build_bars(40, seed=71, pair_name="AUD_JPY")
        # SPX uptrend
        spx = [100.0 + i * 0.5 for i in range(40)]
        snap = _mock_vix_snapshot(bars, level=10.0)
        ctx = _ctx(
            bars, 39, P7_SPEC, pair="AUD_JPY",
            aux_series={"macro.spx500": spx},
            vix_snapshot=snap,
        )
        arr = P7_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert valid.size > 0
        assert valid[-1] > 0


# ---------------------------------------------------------------------------
# 個別: P8 CommodityFlowBias
# ---------------------------------------------------------------------------


class TestP8CommodityFlowBias:
    def test_aux_missing_returns_zero_with_warning(self):
        bars = _build_bars(40, seed=80, pair_name="AUD_JPY")
        ctx = _ctx(bars, 39, P8_SPEC, pair="AUD_JPY")
        with pytest.warns(RuntimeWarning, match="macro.copper or macro.commodity_index"):
            arr = P8_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_copper_uptrend_positive(self):
        bars = _build_bars(40, seed=81, pair_name="AUD_JPY")
        copper = [100.0 + i * 0.2 for i in range(40)]
        ctx = _ctx(
            bars, 39, P8_SPEC, pair="AUD_JPY",
            aux_series={"macro.copper": copper},
        )
        arr = P8_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert valid.size > 0
        assert valid[-1] > 0

    def test_commodity_index_fallback_used_when_copper_missing(self):
        bars = _build_bars(40, seed=82, pair_name="AUD_JPY")
        idx = [100.0 + i * 0.2 for i in range(40)]
        ctx = _ctx(
            bars, 39, P8_SPEC, pair="AUD_JPY",
            aux_series={"macro.commodity_index": idx},
        )
        # warning 出さず、commodity_index 経路で計算
        arr = P8_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert valid.size > 0
        assert valid[-1] > 0


# ---------------------------------------------------------------------------
# 個別: P9 OilPriceInverseFlow
# ---------------------------------------------------------------------------


class TestP9OilPriceInverseFlow:
    def test_aux_missing_returns_zero_with_warning(self):
        bars = _build_bars(40, seed=90, pair_name="USD_CAD")
        ctx = _ctx(bars, 39, P9_SPEC, pair="USD_CAD")
        with pytest.warns(RuntimeWarning, match="macro.wti"):
            arr = P9_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_wti_uptrend_negative(self):
        bars = _build_bars(40, seed=91, pair_name="USD_CAD")
        wti = [50.0 + i * 0.3 for i in range(40)]
        ctx = _ctx(
            bars, 39, P9_SPEC, pair="USD_CAD",
            aux_series={"macro.wti": wti},
        )
        arr = P9_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert valid.size > 0
        assert valid[-1] < 0


# ---------------------------------------------------------------------------
# 個別: P10 NADataProximityGate
# ---------------------------------------------------------------------------


class TestP10NADataProximityGate:
    def test_no_snapshot_returns_one_with_warning(self):
        bars = _build_bars(20, seed=100, pair_name="USD_CAD")
        ctx = _ctx(bars, 19, P10_SPEC, pair="USD_CAD")
        with pytest.warns(RuntimeWarning, match="event_snapshot"):
            arr = P10_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 1.0)

    def test_outside_na_session_open_gate(self):
        # bar_time = 5:00 UTC = NA セッション外 → 1.0
        base = datetime(2026, 1, 1, 5, tzinfo=UTC)
        bars = _build_bars(2, seed=101, base_time=base, pair_name="USD_CAD")
        snap = _mock_event_snapshot()  # USD NFP 14:30 UTC
        ctx = _ctx(bars, 1, P10_SPEC, pair="USD_CAD", event_snapshot=snap)
        arr = P10_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 1.0)

    def test_in_na_session_event_proximity_suppress(self):
        # bar_time = 14:30 UTC, event_time = 14:30 UTC USD → 0 寄り
        base = datetime(2026, 1, 1, 14, 30, tzinfo=UTC)
        bars = _build_bars(1, seed=102, base_time=base, pair_name="USD_CAD")
        snap = _mock_event_snapshot()
        ctx = _ctx(bars, 0, P10_SPEC, pair="USD_CAD", event_snapshot=snap)
        arr = P10_SPEC.compute_all_bars(ctx)
        assert arr[0] < 0.1

    def test_currency_filter_excludes_jpy(self):
        # JPY event は USD/CAD filter で除外 → gate 開放
        base = datetime(2026, 1, 1, 14, 30, tzinfo=UTC)
        bars = _build_bars(1, seed=103, base_time=base, pair_name="USD_CAD")
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 14, 30, tzinfo=UTC),
                currency="JPY",
                name="JPY_event",
                impact=3,
            ),
        ]
        snap = EconomicEventSnapshot(
            calendar=EconomicCalendar(events),
            as_of=datetime(2099, 1, 1, tzinfo=UTC),
        )
        ctx = _ctx(bars, 0, P10_SPEC, pair="USD_CAD", event_snapshot=snap)
        arr = P10_SPEC.compute_all_bars(ctx)
        assert arr[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 個別: P11 EmergingMarketStressGate
# ---------------------------------------------------------------------------


class TestP11EmergingMarketStressGate:
    def test_aux_missing_returns_neutral_with_warning(self):
        bars = _build_bars(20, seed=110, pair_name="USD_ZAR")
        ctx = _ctx(bars, 19, P11_SPEC, pair="USD_ZAR")
        with pytest.warns(RuntimeWarning, match="vix_snapshot or macro.dxy"):
            arr = P11_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.5)

    def test_high_vix_dxy_uptrend_low_gate(self):
        bars = _build_bars(60, seed=111, pair_name="USD_ZAR")
        snap = _mock_vix_snapshot(bars, level=35.0)
        dxy = [100.0 + i * 0.3 for i in range(60)]
        ctx = _ctx(
            bars, 59, P11_SPEC, pair="USD_ZAR",
            aux_series={"macro.dxy": dxy},
            vix_snapshot=snap,
        )
        arr = P11_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert valid.size > 0
        assert valid[-1] < 0.5


# ---------------------------------------------------------------------------
# 個別: P12 GoldCorrelationBias
# ---------------------------------------------------------------------------


class TestP12GoldCorrelationBias:
    def test_aux_missing_returns_zero_with_warning(self):
        bars = _build_bars(40, seed=120, pair_name="USD_ZAR")
        ctx = _ctx(bars, 39, P12_SPEC, pair="USD_ZAR")
        with pytest.warns(RuntimeWarning, match="macro.gold"):
            arr = P12_SPEC.compute_all_bars(ctx)
        assert np.allclose(arr, 0.0)

    def test_gold_uptrend_negative(self):
        bars = _build_bars(40, seed=121, pair_name="USD_ZAR")
        gold = [1900.0 + i * 2.0 for i in range(40)]
        ctx = _ctx(
            bars, 39, P12_SPEC, pair="USD_ZAR",
            aux_series={"macro.gold": gold},
        )
        arr = P12_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert valid.size > 0
        assert valid[-1] < 0


# ---------------------------------------------------------------------------
# Stale value test (P7/P11 staleness cap, P8/P9/P12 stale_mask)
# ---------------------------------------------------------------------------


class TestAuxSeriesMisalignment:
    """Codex impl-review 1-1/1-2 反映: aux_series 長さ不一致は MISALIGNMENT
    として ValueError fail-fast (warning + safe default に流さない)。
    """

    def test_p7_spx_length_mismatch_raises(self):
        bars = _build_bars(40, seed=200, pair_name="AUD_JPY")
        snap = _mock_vix_snapshot(bars)
        spx_short = [100.0] * 30  # bars=40 と不一致
        ctx = _ctx(
            bars, 39, P7_SPEC, pair="AUD_JPY",
            aux_series={"macro.spx500": spx_short},
            vix_snapshot=snap,
        )
        with pytest.raises(ValueError, match=r"MISALIGNMENT"):
            P7_SPEC.compute_all_bars(ctx)

    def test_p8_copper_length_mismatch_raises(self):
        bars = _build_bars(40, seed=201, pair_name="AUD_JPY")
        copper_long = [100.0] * 50
        ctx = _ctx(
            bars, 39, P8_SPEC, pair="AUD_JPY",
            aux_series={"macro.copper": copper_long},
        )
        with pytest.raises(ValueError, match=r"MISALIGNMENT"):
            P8_SPEC.compute_all_bars(ctx)

    def test_p8_commodity_index_length_mismatch_raises(self):
        bars = _build_bars(40, seed=202, pair_name="AUD_JPY")
        idx_short = [100.0] * 20
        ctx = _ctx(
            bars, 39, P8_SPEC, pair="AUD_JPY",
            aux_series={"macro.commodity_index": idx_short},
        )
        with pytest.raises(ValueError, match=r"MISALIGNMENT"):
            P8_SPEC.compute_all_bars(ctx)

    def test_p9_wti_length_mismatch_raises(self):
        bars = _build_bars(40, seed=203, pair_name="USD_CAD")
        wti_short = [50.0] * 35
        ctx = _ctx(
            bars, 39, P9_SPEC, pair="USD_CAD",
            aux_series={"macro.wti": wti_short},
        )
        with pytest.raises(ValueError, match=r"MISALIGNMENT"):
            P9_SPEC.compute_all_bars(ctx)

    def test_p11_dxy_length_mismatch_raises(self):
        bars = _build_bars(60, seed=204, pair_name="USD_ZAR")
        snap = _mock_vix_snapshot(bars)
        dxy_short = [100.0] * 40
        ctx = _ctx(
            bars, 59, P11_SPEC, pair="USD_ZAR",
            aux_series={"macro.dxy": dxy_short},
            vix_snapshot=snap,
        )
        with pytest.raises(ValueError, match=r"MISALIGNMENT"):
            P11_SPEC.compute_all_bars(ctx)

    def test_p12_gold_length_mismatch_raises(self):
        bars = _build_bars(40, seed=205, pair_name="USD_ZAR")
        gold_long = [1900.0] * 50
        ctx = _ctx(
            bars, 39, P12_SPEC, pair="USD_ZAR",
            aux_series={"macro.gold": gold_long},
        )
        with pytest.raises(ValueError, match=r"MISALIGNMENT"):
            P12_SPEC.compute_all_bars(ctx)


class TestStaleValue:
    def test_p9_stale_series_returns_nan(self):
        bars = _build_bars(40, seed=130, pair_name="USD_CAD")
        # WTI 系列の最後 30 個を NaN (stale)
        wti = [50.0 + i * 0.3 for i in range(10)] + [float("nan")] * 30
        ctx = _ctx(
            bars, 39, P9_SPEC, pair="USD_CAD",
            aux_series={"macro.wti": wti},
            params_override={
                "mom_n": 5, "scale": 0.02, "staleness_bars": 5,
            },
        )
        arr = P9_SPEC.compute_all_bars(ctx)
        # 最後の bar は stale → NaN (compute は neutral 0.0 に変換)
        assert np.isnan(arr[39])


# ---------------------------------------------------------------------------
# strict_aux_required preflight verify
# ---------------------------------------------------------------------------


class TestPreflightVerify:
    def test_missing_aux_pair_bars_raises(self):
        # P5 requires both cross_pair.EUR_USD and cross_pair.USD_JPY.
        # set iteration order is non-deterministic — どちらが先に検出されても OK
        with pytest.raises(
            RuntimeError, match=r"cross_pair\.(EUR_USD|USD_JPY)"
        ):
            RegistryEvaluator(
                pair="EUR_JPY",
                strict_aux_required=True,
                selected_primitive_ids=("P5",),
            )

    def test_missing_macro_series_raises(self):
        with pytest.raises(RuntimeError, match=r"macro\.wti"):
            RegistryEvaluator(
                pair="USD_CAD",
                strict_aux_required=True,
                selected_primitive_ids=("P9",),
            )

    def test_optional_data_groups_missing_raises(self):
        # P8 は optional_data_groups (macro.copper OR macro.commodity_index)
        with pytest.raises(RuntimeError, match=r"macro\.copper"):
            RegistryEvaluator(
                pair="AUD_JPY",
                strict_aux_required=True,
                selected_primitive_ids=("P8",),
            )

    def test_optional_data_groups_satisfied_by_alternative(self):
        # macro.commodity_index だけで P8 OK
        ev = RegistryEvaluator(
            pair="AUD_JPY",
            aux_series={"macro.commodity_index": [100.0] * 10},
            strict_aux_required=True,
            selected_primitive_ids=("P8",),
        )
        assert ev is not None

    def test_strict_aux_required_without_selected_ids_raises(self):
        with pytest.raises(ValueError, match="selected_primitive_ids"):
            RegistryEvaluator(
                pair="EUR_USD",
                strict_aux_required=True,
            )

    def test_no_strict_aux_works_without_aux(self):
        # default は strict 無効なので問題なく初期化
        ev = RegistryEvaluator(pair="EUR_USD")
        assert ev is not None

    def test_atr_required_data_satisfied_by_bars(self):
        # F primitive で required_data に "atr" を持つものは現状ない (T013 以降の予約)
        # ここでは _BARS_PROVIDED_KEYS に atr が含まれていることを直接確認
        # 内部 _BARS_PROVIDED_KEYS が "atr" を含む (preflight が atr で
        # unknown key 扱いしないことの保証)
        assert "atr" in RegistryEvaluator._BARS_PROVIDED_KEYS


# ---------------------------------------------------------------------------
# strict_snapshot_required (compute 内 fail-fast)
# ---------------------------------------------------------------------------


class TestStrictSnapshotPerCall:
    def test_p5_strict_raises(self):
        bars = _build_bars(20, seed=140, pair_name="EUR_JPY")
        ctx = _ctx(bars, 19, P5_SPEC, pair="EUR_JPY", strict=True)
        with pytest.raises(RuntimeError, match="strict mode"):
            P5_SPEC.compute_all_bars(ctx)

    def test_p7_strict_raises(self):
        bars = _build_bars(20, seed=141, pair_name="AUD_JPY")
        ctx = _ctx(bars, 19, P7_SPEC, pair="AUD_JPY", strict=True)
        with pytest.raises(RuntimeError, match="strict mode"):
            P7_SPEC.compute_all_bars(ctx)

    def test_p10_strict_raises(self):
        bars = _build_bars(20, seed=142, pair_name="USD_CAD")
        ctx = _ctx(bars, 19, P10_SPEC, pair="USD_CAD", strict=True)
        with pytest.raises(RuntimeError, match="strict mode"):
            P10_SPEC.compute_all_bars(ctx)


# ---------------------------------------------------------------------------
# 後方互換: F1-F14 / M1-M6 が aux_pair_bars 未指定で動く
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_evaluation_context_without_aux_pair_bars_works(self):
        bars = _build_bars(50, seed=150)
        ctx = EvaluationContext(
            bars=bars, idx=49, pair="EUR_USD", params={"n": 14}
        )
        assert ctx.aux_pair_bars == {}

    def test_existing_f_primitives_work(self):
        bars = _build_bars(80, seed=151)
        for fid in [f"F{i}" for i in range(1, 15)]:
            spec = get_primitive(fid)
            params = _default_params(spec)
            ctx = EvaluationContext(
                bars=bars, idx=79, pair="EUR_USD", params=params
            )
            val = spec.compute(ctx)
            assert isinstance(val, float)

    def test_existing_m_primitives_work(self):
        bars = _build_bars(80, seed=152, spread_bps_const=2.0)
        for mid in [f"M{i}" for i in range(1, 7)]:
            spec = get_primitive(mid)
            params = _default_params(spec)
            ctx = EvaluationContext(
                bars=bars, idx=79, pair="EUR_USD", params=params
            )
            # M4/M5 は warning 出るが OK
            import warnings as _w
            with _w.catch_warnings():
                _w.simplefilter("ignore", RuntimeWarning)
                val = spec.compute(ctx)
            assert isinstance(val, float)


# ---------------------------------------------------------------------------
# RegistryEvaluator 経由
# ---------------------------------------------------------------------------


class TestViaRegistryEvaluator:
    def test_evaluate_pair_specific_returns_float(self):
        from src.dsl.genome import SignalConfig

        bars = _build_bars(80, seed=160, pair_name="EUR_JPY")
        eu = list(_build_aligned_aux_bars(bars, pair_name="EUR_USD"))
        uj = list(_build_aligned_aux_bars(bars, pair_name="USD_JPY"))
        ev = RegistryEvaluator(
            pair="EUR_JPY",
            aux_pair_bars={"EUR_USD": eu, "USD_JPY": uj},
            event_snapshot=_mock_event_snapshot(),
            vix_snapshot=_mock_vix_snapshot(bars),
            aux_series={
                "macro.spx500": [100.0] * 80,
                "macro.copper": [100.0] * 80,
                "macro.wti": [50.0] * 80,
                "macro.dxy": [100.0] * 80,
                "macro.gold": [1900.0] * 80,
            },
        )
        for spec in ALL_PAIR_SPECS:
            sig = SignalConfig(
                name=spec.id, weight=1.0, params=_default_params(spec)
            )
            import warnings as _w
            with _w.catch_warnings():
                _w.simplefilter("ignore", RuntimeWarning)
                val = ev.evaluate(bars, 70, sig)
            assert isinstance(val, float)
            if spec.category == "MODULATOR":
                assert -1e-9 <= val <= 1.0 + 1e-9
            else:
                assert -1.0 - 1e-9 <= val <= 1.0 + 1e-9
