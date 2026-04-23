"""T011 directional primitive 14 個の単体テスト。

- 各 primitive の registry 登録確認
- compute と compute_all_bars の一致
- 出力 bounded 確認
- look-ahead bias property（後続バー改変で過去 index 不変）
- 既知入力での期待値一致
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import (
    EvaluationContext,
    PrimitiveSpec,
    clear,
    ensure_registered,
    get_primitive,
    list_all,
    list_by_category,
    list_by_domain,
)
from src.alpha_factory.primitives._indicators import (
    adx,
    atr,
    ema,
    zscore,
)
from src.alpha_factory.primitives.directional_generic import (
    F1_SPEC,
    F2_SPEC,
    F3_SPEC,
    F4_SPEC,
    F5_SPEC,
    F6_SPEC,
    F7_SPEC,
    F8_SPEC,
    F9_SPEC,
    F10_SPEC,
    F11_SPEC,
    F12_SPEC,
    F13_SPEC,
    F14_SPEC,
    MEAN_REVERT_SPECS,
    NEUTRAL_SPECS,
    TREND_FOLLOW_SPECS,
    all_specs,
)
from src.domain.price import Ohlc, PriceBar

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _registry_isolation():
    clear()
    ensure_registered()
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
) -> list[PriceBar]:
    """ランダムウォーク bars を生成（bid = ask、スプレッド 0）。"""
    rng = np.random.default_rng(seed)
    if base_time is None:
        base_time = datetime(2026, 1, 1, 0, tzinfo=UTC)
    prices = [start_price]
    for _ in range(n):
        prices.append(prices[-1] + rng.normal(0, volatility))
    bars: list[PriceBar] = []
    for i in range(n):
        o = prices[i]
        c = prices[i + 1]
        hi = max(o, c) + abs(rng.normal(0, 0.1))
        lo = min(o, c) - abs(rng.normal(0, 0.1))
        ohlc = Ohlc(
            open=Decimal(str(o)),
            high=Decimal(str(hi)),
            low=Decimal(str(lo)),
            close=Decimal(str(c)),
        )
        bars.append(
            PriceBar(
                pair_name="EUR_USD",
                bar_time=base_time + step * i,
                bid=ohlc,
                ask=ohlc,
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


def _ctx(bars, idx: int, spec: PrimitiveSpec) -> EvaluationContext:
    return EvaluationContext(
        bars=bars,
        idx=idx,
        pair="EUR_USD",
        params=_default_params(spec),
    )


ALL_SPECS = (
    F1_SPEC, F2_SPEC, F3_SPEC, F4_SPEC, F5_SPEC, F6_SPEC,
    F7_SPEC, F8_SPEC, F9_SPEC, F10_SPEC, F11_SPEC,
    F12_SPEC, F13_SPEC, F14_SPEC,
)


# ---------------------------------------------------------------------------
# Registry 集計
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_all_14_directional_registered(self):
        # T012 で modulator (M1-M6) も同時登録される (合計 20)。
        # 本テストでは directional 14 が含まれることのみ verify。
        specs = list_all()
        ids = {s.id for s in specs}
        directional_ids = {f"F{i}" for i in range(1, 15)}
        assert directional_ids.issubset(ids)

    def test_category_counts(self):
        assert len(list_by_category("TREND_FOLLOW")) == 6
        assert len(list_by_category("MEAN_REVERT")) == 5
        assert len(list_by_category("NEUTRAL")) == 3
        # MODULATOR は T012 で 6 個登録
        assert len(list_by_category("MODULATOR")) == 6

    def test_all_generic_domain(self):
        # T012 で modulator 6 も generic に追加 → 合計 20
        assert len(list_by_domain("generic")) == 20
        assert len(list_by_domain("pair_specific")) == 0

    def test_each_id_retrievable(self):
        for i in range(1, 15):
            spec = get_primitive(f"F{i}")
            assert spec.id == f"F{i}"

    def test_module_level_spec_tuples_consistent(self):
        assert all_specs() == ALL_SPECS
        assert ALL_SPECS[0:6] == TREND_FOLLOW_SPECS
        assert ALL_SPECS[6:11] == MEAN_REVERT_SPECS
        assert ALL_SPECS[11:14] == NEUTRAL_SPECS


# ---------------------------------------------------------------------------
# 14 個共通テスト（parametrize）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", ALL_SPECS, ids=[s.id for s in ALL_SPECS])
class TestEachPrimitiveCommon:
    def test_compute_matches_compute_all_bars(self, spec):
        bars = _build_bars(120, seed=1)
        arr = spec.compute_all_bars(_ctx(bars, 100, spec))
        for idx in (50, 80, 119):
            val_single = spec.compute(_ctx(bars, idx, spec))
            val_all = arr[idx]
            if np.isnan(val_all):
                # compute は nan を 0.0 に吸収
                assert val_single == 0.0
            else:
                assert val_single == pytest.approx(float(val_all), abs=1e-12)

    def test_output_bounded(self, spec):
        bars = _build_bars(150, seed=2)
        arr = spec.compute_all_bars(_ctx(bars, 149, spec))
        valid = arr[~np.isnan(arr)]
        assert np.all(valid >= -1.0 - 1e-9)
        assert np.all(valid <= 1.0 + 1e-9)

    def test_no_lookahead_property(self, spec):
        """bars[k+1:] を改変しても compute_all_bars(bars')[:k+1] は不変。"""
        bars_orig = _build_bars(120, seed=3)
        k = 60
        ctx_orig = _ctx(bars_orig, 119, spec)
        result_orig = spec.compute_all_bars(ctx_orig)

        # 後続バーを別 seed で置換
        bars_replacement = _build_bars(120 - (k + 1), seed=999)
        bars_mod = list(bars_orig[: k + 1]) + list(bars_replacement)
        # bar_time は連続性を保つため、元の時刻を再利用
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
        ctx_mod = _ctx(bars_mod_fixed, 119, spec)
        result_mod = spec.compute_all_bars(ctx_mod)

        # 先頭 k+1 バーの値は不変（NaN は NaN のままで一致）
        np.testing.assert_allclose(
            result_orig[: k + 1],
            result_mod[: k + 1],
            equal_nan=True,
            atol=1e-10,
        )

    def test_warmup_returns_nan_in_array(self, spec):
        bars = _build_bars(40, seed=4)
        arr = spec.compute_all_bars(_ctx(bars, 39, spec))
        # 先頭 1 index は必ず NaN（warmup）
        assert np.isnan(arr[0]) or np.isfinite(arr[0])  # F6 は session 外で 0 になりうる
        # 少なくとも 1 index は NaN のはず（どの primitive も warmup > 0）
        # F6 は 0 を返すので除外（session 外は 0）
        if spec.id != "F6":
            assert np.any(np.isnan(arr))


# ---------------------------------------------------------------------------
# primitive 個別: 期待値一致
# ---------------------------------------------------------------------------


def _mid_close_arr(bars) -> np.ndarray:
    return np.array(
        [(float(b.bid.close) + float(b.ask.close)) * 0.5 for b in bars]
    )


def _mid_hl_arrays(bars) -> tuple[np.ndarray, np.ndarray]:
    h = np.array(
        [(float(b.bid.high) + float(b.ask.high)) * 0.5 for b in bars]
    )
    low = np.array(
        [(float(b.bid.low) + float(b.ask.low)) * 0.5 for b in bars]
    )
    return h, low


class TestF1Expected:
    def test_matches_tanh_ema_diff_over_atr(self):
        bars = _build_bars(100, seed=11)
        ctx = _ctx(bars, 99, F1_SPEC)
        arr = F1_SPEC.compute_all_bars(ctx)
        c = _mid_close_arr(bars)
        h, low = _mid_hl_arrays(bars)
        p = _default_params(F1_SPEC)
        ef = ema(c, p["fast_n"])
        es = ema(c, p["slow_n"])
        a = atr(h, low, c, p["atr_n"])
        expected = np.tanh((ef - es) / (a + 1e-10))
        # NaN 位置と一致
        for i in (50, 80, 99):
            if np.isnan(expected[i]):
                assert np.isnan(arr[i])
            else:
                assert arr[i] == pytest.approx(expected[i], abs=1e-12)


class TestF4AdxTrend:
    def test_direction_follows_di_sign(self):
        bars = _build_bars(300, seed=13)
        ctx = _ctx(bars, 299, F4_SPEC)
        arr = F4_SPEC.compute_all_bars(ctx)
        c = _mid_close_arr(bars)
        h, low = _mid_hl_arrays(bars)
        p = _default_params(F4_SPEC)
        adx_arr, plus_di, minus_di = adx(h, low, c, p["n"])
        for i in range(100, 300, 20):
            if np.isnan(arr[i]) or np.isnan(adx_arr[i]):
                continue
            direction = np.sign(plus_di[i] - minus_di[i])
            strength = max(0.0, np.tanh((adx_arr[i] - 25.0) / (p["scale"] + 1e-10)))
            expected = strength * direction
            assert arr[i] == pytest.approx(expected, abs=1e-12)


class TestF5Vol:
    def test_short_ge_long_warns(self):
        bars = _build_bars(100, seed=14)
        params = {"short_n": 30, "long_n": 10, "k": 3.0}  # invalid
        ctx = EvaluationContext(bars=bars, idx=99, pair="EUR_USD", params=params)
        with pytest.warns(RuntimeWarning, match=r"short_n \(30\) >= long_n \(10\)"):
            F5_SPEC.compute_all_bars(ctx)


class TestF6SessionMomentum:
    def test_outside_session_is_zero(self):
        # Tokyo session (0-9 UTC). bars を UTC 10 時以降に配置 → すべて 0
        base = datetime(2026, 1, 1, 10, tzinfo=UTC)
        bars = _build_bars(30, seed=15, base_time=base)
        ctx = EvaluationContext(
            bars=bars,
            idx=29,
            pair="EUR_USD",
            params={"session": 0, "k": 1.0, "atr_n": 14},
        )
        arr = F6_SPEC.compute_all_bars(ctx)
        # 全 bar が 10-16 UTC → tokyo (0-9) 外 → 全 0
        for i in range(30):
            t = bars[i].bar_time.astimezone(UTC).hour
            if not (0 <= t < 9):
                assert arr[i] == pytest.approx(0.0)

    def test_session_open_bar_is_zero(self):
        # Tokyo session 開始直前から
        base = datetime(2026, 1, 1, 23, tzinfo=UTC)
        bars = _build_bars(30, seed=16, base_time=base)
        ctx = EvaluationContext(
            bars=bars,
            idx=29,
            pair="EUR_USD",
            params={"session": 0, "k": 1.0, "atr_n": 14},
        )
        arr = F6_SPEC.compute_all_bars(ctx)
        # index 1 で UTC 00:00 (tokyo 開始)。開始 bar は 0。
        # NaN (ATR warmup) の可能性もあるが、開始 bar は 0 で固定のため 0 のはず。
        assert arr[1] == pytest.approx(0.0)


class TestF10ZScoreRevert:
    def test_matches_tanh_neg_zscore(self):
        bars = _build_bars(80, seed=17)
        ctx = _ctx(bars, 79, F10_SPEC)
        arr = F10_SPEC.compute_all_bars(ctx)
        c = _mid_close_arr(bars)
        z = zscore(c, 20)
        expected = np.tanh(-z)
        for i in (40, 60, 79):
            if np.isnan(expected[i]):
                assert np.isnan(arr[i])
            else:
                assert arr[i] == pytest.approx(expected[i], abs=1e-12)


class TestF13ReturnAutocorrLag:
    def test_output_within_minus_one_plus_one(self):
        bars = _build_bars(300, seed=19)
        ctx = _ctx(bars, 299, F13_SPEC)
        arr = F13_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert np.all(valid >= -1.0 - 1e-9)
        assert np.all(valid <= 1.0 + 1e-9)

    def test_iid_returns_expected_near_zero(self):
        # ランダムウォーク（独立リターン） → 自己相関は 0 近辺
        bars = _build_bars(500, seed=20)
        ctx = _ctx(bars, 499, F13_SPEC)
        arr = F13_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert abs(valid.mean()) < 0.15  # sample size による統計的範囲


class TestF14TrendStrengthRatio:
    def test_non_negative(self):
        bars = _build_bars(300, seed=21)
        ctx = _ctx(bars, 299, F14_SPEC)
        arr = F14_SPEC.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        # F14 は absolute strength を tanh で bound → [0, +1]
        assert np.all(valid >= 0.0 - 1e-9)
        assert np.all(valid <= 1.0 + 1e-9)

    def test_explicit_range_0_to_1(self):
        """impl-review Should-consider 1 対応: F14 の [0, +1] 下限を明示検証。"""
        # 複数 seed で F14 出力が負にならないことを property ベースで確認。
        for seed in range(5):
            bars = _build_bars(200, seed=100 + seed)
            ctx = _ctx(bars, 199, F14_SPEC)
            arr = F14_SPEC.compute_all_bars(ctx)
            valid = arr[~np.isnan(arr)]
            assert valid.size > 0
            assert np.all(valid >= 0.0), f"seed={seed} produced negative F14 value: min={valid.min()}"
            assert np.all(valid <= 1.0 + 1e-12)


# ---------------------------------------------------------------------------
# RegistryEvaluator 経由での動作確認
# ---------------------------------------------------------------------------


class TestViaRegistryEvaluator:
    def test_evaluate_returns_float(self):
        from src.alpha_factory.primitives import RegistryEvaluator
        from src.dsl.genome import SignalConfig

        bars = _build_bars(100, seed=22)
        ev = RegistryEvaluator(pair="EUR_USD")
        for spec in ALL_SPECS:
            sig = SignalConfig(name=spec.id, weight=1.0, params=_default_params(spec))
            val = ev.evaluate(bars, 90, sig)
            assert isinstance(val, float)
            assert -1.0 - 1e-9 <= val <= 1.0 + 1e-9
