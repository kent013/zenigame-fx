"""primitives-registry 契約テスト（T010 骨格）。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import (
    EvaluationContext,
    ParamSpec,
    PrimitiveSpec,
    RegistryEvaluator,
    clear,
    ensure_registered,
    get_primitive,
    is_valid_required_data,
    list_all,
    list_by_category,
    list_by_domain,
    register,
    slot_from_category,
)
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy


@pytest.fixture(autouse=True)
def _isolate_registry():
    clear()
    yield
    clear()


def _dummy_bar(ts: datetime) -> PriceBar:
    o = Ohlc(
        open=Decimal("1.0"),
        high=Decimal("1.0"),
        low=Decimal("1.0"),
        close=Decimal("1.0"),
    )
    return PriceBar(
        pair_name="EUR_USD",
        bar_time=ts,
        bid=o,
        ask=o,
        volume=0,
        complete=True,
    )


def _dummy_compute(ctx: EvaluationContext) -> float:
    return float(ctx.params.get("value", 0.0))


def _dummy_compute_all_bars(ctx: EvaluationContext) -> np.ndarray:
    return np.full(len(ctx.bars), float(ctx.params.get("value", 0.0)))


def _make_spec(
    *,
    id: str = "X1",
    name: str = "DummyPrimitive",
    category: str = "TREND_FOLLOW",
    domain: str = "generic",
) -> PrimitiveSpec:
    return PrimitiveSpec(
        id=id,
        name=name,
        category=category,  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        param_schema=(ParamSpec(name="value", low=0.0, high=1.0),),
        required_data=("ohlc",),
        compute=_dummy_compute,
        compute_all_bars=_dummy_compute_all_bars,
    )


class TestRegistryBasics:
    def test_register_then_get(self):
        spec = _make_spec()
        register(spec)
        assert get_primitive("X1") is spec

    def test_duplicate_register_raises(self):
        register(_make_spec())
        with pytest.raises(ValueError, match="already registered"):
            register(_make_spec())

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="not in registry"):
            get_primitive("UNKNOWN")

    def test_list_all_returns_registration_order(self):
        s1 = _make_spec(id="A1")
        s2 = _make_spec(id="A2")
        register(s1)
        register(s2)
        assert list_all() == (s1, s2)

    def test_list_by_category(self):
        s_trend = _make_spec(id="T1", category="TREND_FOLLOW")
        s_mod = _make_spec(id="M1", category="MODULATOR")
        register(s_trend)
        register(s_mod)
        assert list_by_category("TREND_FOLLOW") == (s_trend,)
        assert list_by_category("MODULATOR") == (s_mod,)
        assert list_by_category("MEAN_REVERT") == ()

    def test_list_by_domain(self):
        s_g = _make_spec(id="G1", domain="generic")
        s_p = _make_spec(id="P1", domain="pair_specific")
        register(s_g)
        register(s_p)
        assert list_by_domain("generic") == (s_g,)
        assert list_by_domain("pair_specific") == (s_p,)

    def test_clear_empties_registry(self):
        register(_make_spec())
        clear()
        assert list_all() == ()


class TestSlotFromCategory:
    @pytest.mark.parametrize(
        "category,expected",
        [
            ("TREND_FOLLOW", "directional"),
            ("MEAN_REVERT", "directional"),
            ("NEUTRAL", "directional"),
            ("MODULATOR", "local_gate"),
        ],
    )
    def test_slot_from_category(self, category, expected):
        assert slot_from_category(category) == expected

    def test_slot_from_category_rejects_unknown(self):
        with pytest.raises(ValueError, match="unknown PrimitiveCategory"):
            slot_from_category("BOGUS")  # type: ignore[arg-type]


class TestRequiredDataNaming:
    @pytest.mark.parametrize(
        "key,ok",
        [
            ("ohlc", True),
            ("atr", True),
            ("spread", True),
            ("swap", True),
            ("calendar.session", True),
            ("calendar.economic_event", True),
            ("macro.vix", True),
            ("macro.dxy", True),
            ("macro.dgs10", True),
            ("macro.dgs2", True),
            ("macro.t10yie", True),
            ("macro.spx500", True),
            ("cross_pair.EUR_USD", True),
            ("cross_pair.", False),
            ("cross_pair", False),
            ("unknown", False),
            ("macro.unknown", False),
            ("", False),
        ],
    )
    def test_is_valid_required_data(self, key, ok):
        assert is_valid_required_data(key) is ok


class TestRegistryEvaluator:
    def test_evaluate_returns_compute_value(self):
        register(_make_spec(id="X1"))
        ev = RegistryEvaluator(pair="EUR_USD")
        bars = [_dummy_bar(datetime(2026, 1, 1, 9, tzinfo=UTC))]
        sig = SignalConfig(name="X1", weight=1.0, params={"value": 0.42})
        assert ev.evaluate(bars, 0, sig) == pytest.approx(0.42)

    def test_evaluate_unknown_primitive_raises(self):
        ev = RegistryEvaluator(pair="EUR_USD")
        bars = [_dummy_bar(datetime(2026, 1, 1, 9, tzinfo=UTC))]
        sig = SignalConfig(name="NOT_REGISTERED", weight=1.0)
        with pytest.raises(KeyError):
            ev.evaluate(bars, 0, sig)

    def test_aux_series_none_defaults_to_empty_mapping(self):
        register(_make_spec(id="X1"))
        ev = RegistryEvaluator(pair="EUR_USD", aux_series=None)
        bars = [_dummy_bar(datetime(2026, 1, 1, 9, tzinfo=UTC))]
        sig = SignalConfig(name="X1", weight=1.0, params={"value": 1.5})
        # aux_series が空でも compute は呼べる
        assert ev.evaluate(bars, 0, sig) == pytest.approx(1.5)

    def test_context_receives_pair_and_params(self):
        captured: dict[str, object] = {}

        def _capture_compute(ctx: EvaluationContext) -> float:
            captured["pair"] = ctx.pair
            captured["params"] = dict(ctx.params)
            captured["idx"] = ctx.idx
            return 0.0

        spec = PrimitiveSpec(
            id="C1",
            name="Capture",
            category="NEUTRAL",
            domain="generic",
            param_schema=(),
            required_data=("ohlc",),
            compute=_capture_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        register(spec)
        ev = RegistryEvaluator(pair="USD_JPY")
        bars = [
            _dummy_bar(datetime(2026, 1, 1, 9, tzinfo=UTC)),
            _dummy_bar(datetime(2026, 1, 1, 10, tzinfo=UTC)),
        ]
        sig = SignalConfig(name="C1", weight=1.0, params={"k": 7})
        ev.evaluate(bars, 1, sig)
        assert captured["pair"] == "USD_JPY"
        assert captured["params"] == {"k": 7}
        assert captured["idx"] == 1


class TestEnsureRegistered:
    def test_ensure_registered_registers_directional_and_modulator_generic(self):
        # T011 で directional_generic 14 (F1-F14)、T012 で modulator_generic 6
        # (M1-M6)。合計 20 が登録される。
        ensure_registered()
        specs = list_all()
        ids = {s.id for s in specs}
        assert len(specs) == 20
        expected = {f"F{i}" for i in range(1, 15)} | {
            f"M{i}" for i in range(1, 7)
        }
        assert ids == expected

    def test_ensure_registered_is_idempotent(self):
        ensure_registered()
        ensure_registered()
        # エラー無しで 2 回呼べる。件数は 20 で不変。
        assert len(list_all()) == 20


class TestSpecValidation:
    """register() 時の PrimitiveSpec 不変条件検証（R1/R2 対応）。"""

    def test_register_rejects_empty_id(self):
        spec = PrimitiveSpec(
            id="",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="id must be non-empty"):
            register(spec)

    def test_register_rejects_empty_name(self):
        spec = PrimitiveSpec(
            id="X1",
            name="",
            category="NEUTRAL",
            domain="generic",
            param_schema=(),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="name must be non-empty"):
            register(spec)

    def test_register_rejects_duplicate_param_names(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(
                ParamSpec(name="n", low=1, high=10, is_int=True),
                ParamSpec(name="n", low=5, high=20, is_int=True),
            ),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="duplicate param name"):
            register(spec)

    def test_register_rejects_low_greater_than_high(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(ParamSpec(name="n", low=10.0, high=5.0),),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match=r"low .* > high"):
            register(spec)

    def test_register_rejects_default_out_of_range(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(
                ParamSpec(name="n", low=0.0, high=1.0, default=2.0),
            ),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="out of"):
            register(spec)

    def test_register_rejects_is_int_with_float_bounds(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(
                ParamSpec(name="n", low=1.5, high=10.0, is_int=True),
            ),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="is_int but low/high"):
            register(spec)

    def test_register_rejects_is_int_with_float_default(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(
                ParamSpec(
                    name="n", low=1, high=10, is_int=True, default=5.5
                ),
            ),
            required_data=("ohlc",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="is_int but default"):
            register(spec)

    def test_register_rejects_invalid_required_data(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="generic",
            param_schema=(),
            required_data=("bogus_key",),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        with pytest.raises(ValueError, match="invalid required_data key"):
            register(spec)

    def test_register_accepts_cross_pair_required_data(self):
        spec = PrimitiveSpec(
            id="X1",
            name="X",
            category="NEUTRAL",
            domain="pair_specific",
            param_schema=(),
            required_data=("ohlc", "cross_pair.EUR_JPY"),
            compute=_dummy_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        register(spec)  # should not raise


class TestConcurrency:
    """register / clear の並行呼び出しに対する安全性（R3 対応）。

    bootstrap 時の並行 register でレース条件が発生せず、重複 id は
    必ずちょうど 1 回成功・1 回 ValueError になることを検証する。
    """

    def test_parallel_register_same_id_has_exactly_one_success(self):
        import threading

        errors: list[Exception] = []
        successes: list[bool] = []
        barrier = threading.Barrier(8)

        def worker() -> None:
            barrier.wait()  # start all threads simultaneously
            try:
                register(_make_spec(id="SHARED"))
                successes.append(True)
            except ValueError as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 1, (
            f"expected 1 success, got {len(successes)}"
        )
        assert len(errors) == 7, (
            f"expected 7 ValueError, got {len(errors)}"
        )
        assert list_all()[0].id == "SHARED"


class TestDslStrategyIntegration:
    """RegistryEvaluator が DslStrategy.PrimitiveEvaluator Protocol を
    structural に満たし、DslStrategy に直接注入可能であることを検証する。
    互換性回帰（Protocol シグネチャ変更や import 破壊）の早期検知用。"""

    def test_registry_evaluator_fits_protocol(self):
        register(_make_spec(id="DIR1", category="TREND_FOLLOW"))
        genome = Genome(
            name="test",
            units=1000,
            clauses=(
                ClauseConfig(
                    directional=(
                        SignalConfig(
                            name="DIR1", weight=1.0, params={"value": 0.5}
                        ),
                    ),
                    local_gate=(),
                    weight=1.0,
                ),
            ),
            position=PositionConfig(
                entry_threshold=0.3,
                exit_threshold=0.1,
                max_pos=1,
                time_stop_min=0,
            ),
            risk=RiskConfig(stop_atr=2.0, take_atr=2.0),
        )
        evaluator = RegistryEvaluator(pair="EUR_USD")
        strategy = DslStrategy(genome=genome, evaluator=evaluator)
        assert strategy.genome is genome
        assert strategy.warmup_bars() == 0
