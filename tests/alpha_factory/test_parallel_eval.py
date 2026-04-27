"""``src/alpha_factory/parallel_eval.py`` のテスト (T052).

設計根拠:
- devnotes/20260427-1114-ga-parallel-workers/conceptual-design.md
- devnotes/20260427-1114-ga-parallel-workers/detailed-design.md

テスト戦略:
- 評価関数 ``evaluate_genome`` は monkeypatch で
  ``evaluate_stage_a/b/c`` を差し替え、純粋関数としての契約を検証
- ``GenomeEvaluator(max_workers=1)`` の in-process 経路は単純ループで検証
- ``multiprocessing.Pool`` 起動を伴うテストは spawn 経由で時間がかかるため
  最小本数に絞る (``test_genome_evaluator_pool_runs_population_in_order``)
"""

from __future__ import annotations

import logging
import pickle
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.alpha_factory.cross_pair import CrossPairConfig
from src.alpha_factory.parallel_eval import (
    CrossPairLaneInputs,
    GenomeEvaluator,
    GenomeStageResult,
    LaneEvalContext,
    PreflightPayload,
    _classify_exception,
    _to_error_result,
    evaluate_genome,
    measure_peak_rss_mb,
)
from src.alpha_factory.stage_gate import StageGateConfig, StageResult
from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_genome(name: str = "g0") -> Genome:
    sig = SignalConfig(name="ConstSignal", weight=1.0, params={})
    clause = ClauseConfig(directional=(sig,), local_gate=(), weight=1.0)
    return Genome(
        name=name,
        units=10000,
        clauses=(clause,),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.1, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=2.0),
    )


def _make_meta(pair: str = "EUR_JPY") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name=pair,
        base_currency=pair.split("_")[0],
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def _make_bars(n: int = 4, pair: str = "EUR_JPY") -> list[PriceBar]:
    bid = Decimal("154.00")
    ask = Decimal("154.01")
    return [
        PriceBar(
            pair_name=pair,
            bar_time=datetime(2026, 1, (i % 28) + 1, 12, 0, tzinfo=UTC),
            bid=Ohlc(bid, bid, bid, bid),
            ask=Ohlc(ask, ask, ask, ask),
            volume=10,
            complete=True,
        )
        for i in range(n)
    ]


def _make_bt_cfg(instrument: str = "EUR_JPY") -> BacktestConfig:
    return BacktestConfig(
        instrument=instrument,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 5, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=25,
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )


def _make_ctx(
    *,
    preflight_underfilled: bool = False,
    preflight_payload: PreflightPayload | None = None,
    cp_inputs: CrossPairLaneInputs | None = None,
) -> LaneEvalContext:
    return LaneEvalContext(
        lane_id="tier1_EUR_JPY",
        bars_a=tuple(_make_bars(4)),
        bars_b=tuple(_make_bars(8)),
        bars_holdout=tuple(_make_bars(4)),
        meta=_make_meta(),
        bt_cfg=_make_bt_cfg(),
        cp_inputs=cp_inputs,
        preflight_underfilled=preflight_underfilled,
        preflight_payload=preflight_payload,
    )


def _stage_result(
    stage: str, passed: bool, *, payload: Mapping[str, Any] | None = None
) -> StageResult:
    return StageResult(
        stage=stage,  # type: ignore[arg-type]
        passed=passed,
        metrics={
            "stage": stage,
            "genome_name": "g0",
            "n_bars": 4,
            "wall_time_seconds": 0.001,
            "payload": dict(payload or {}),
        },
        reason_codes=() if passed else ("test_fail",),
    )


# ---------------------------------------------------------------------------
# LaneEvalContext / CrossPairLaneInputs / PreflightPayload (深い不変性)
# ---------------------------------------------------------------------------


class TestLaneEvalContextInvariants:
    def test_rejects_list_bars_a(self) -> None:
        with pytest.raises(TypeError, match="bars_a must be tuple"):
            LaneEvalContext(
                lane_id="x",
                bars_a=[],  # type: ignore[arg-type]
                bars_b=tuple(),
                bars_holdout=tuple(),
                meta=_make_meta(),
                bt_cfg=_make_bt_cfg(),
            )

    def test_rejects_list_bars_b(self) -> None:
        with pytest.raises(TypeError, match="bars_b must be tuple"):
            LaneEvalContext(
                lane_id="x",
                bars_a=tuple(),
                bars_b=[],  # type: ignore[arg-type]
                bars_holdout=tuple(),
                meta=_make_meta(),
                bt_cfg=_make_bt_cfg(),
            )

    def test_rejects_dict_cp_inputs(self) -> None:
        with pytest.raises(TypeError, match="cp_inputs must be CrossPairLaneInputs"):
            LaneEvalContext(
                lane_id="x",
                bars_a=tuple(),
                bars_b=tuple(),
                bars_holdout=tuple(),
                meta=_make_meta(),
                bt_cfg=_make_bt_cfg(),
                cp_inputs={"target_pair": "EUR_JPY"},  # type: ignore[arg-type]
            )

    def test_preflight_payload_required_when_underfilled(self) -> None:
        with pytest.raises(ValueError, match="preflight_payload must be set"):
            LaneEvalContext(
                lane_id="x",
                bars_a=tuple(),
                bars_b=tuple(),
                bars_holdout=tuple(),
                meta=_make_meta(),
                bt_cfg=_make_bt_cfg(),
                preflight_underfilled=True,
            )


class TestCrossPairLaneInputsImmutability:
    def test_immutable_against_external_dict_mutation(self) -> None:
        bar = _make_bars(1)[0]
        src_pair_bars: dict[str, list[PriceBar]] = {"USD_JPY": list(_make_bars(2))}
        src_meta: dict[str, InstrumentMeta] = {"USD_JPY": _make_meta("USD_JPY")}
        cp = CrossPairLaneInputs(
            target_pair="EUR_JPY",
            pair_bars_map=src_pair_bars,
            meta_map=src_meta,
        )
        # 外部 dict を変更
        src_pair_bars["EUR_USD"] = []
        src_pair_bars["USD_JPY"].append(bar)
        src_meta["NEW"] = _make_meta("NEW_XX")
        # cp は影響を受けない
        assert "EUR_USD" not in cp.pair_bars_map
        assert len(cp.pair_bars_map["USD_JPY"]) == 2
        assert "NEW" not in cp.meta_map

    def test_pair_bars_map_is_mappingproxy(self) -> None:
        cp = CrossPairLaneInputs(
            target_pair="EUR_JPY",
            pair_bars_map={"USD_JPY": (_make_bars(1)[0],)},
            meta_map={"USD_JPY": _make_meta("USD_JPY")},
        )
        with pytest.raises(TypeError):
            cp.pair_bars_map["XXX"] = ()  # type: ignore[index]
        with pytest.raises(TypeError):
            cp.meta_map["XXX"] = _make_meta()  # type: ignore[index]

    def test_picklable_directly(self) -> None:
        cp = CrossPairLaneInputs(
            target_pair="EUR_JPY",
            pair_bars_map={"USD_JPY": (_make_bars(1)[0],)},
            meta_map={"USD_JPY": _make_meta("USD_JPY")},
        )
        restored = pickle.loads(pickle.dumps(cp))
        assert restored == cp

    def test_pickle_round_trip_preserves_immutability(self) -> None:
        cp = CrossPairLaneInputs(
            target_pair="EUR_JPY",
            pair_bars_map={"USD_JPY": (_make_bars(1)[0],)},
            meta_map={"USD_JPY": _make_meta("USD_JPY")},
        )
        ctx = _make_ctx(cp_inputs=cp)
        restored = pickle.loads(pickle.dumps(ctx))
        assert restored == ctx
        from types import MappingProxyType

        assert isinstance(restored.cp_inputs.pair_bars_map, MappingProxyType)
        assert isinstance(restored.cp_inputs.meta_map, MappingProxyType)
        with pytest.raises(TypeError):
            restored.cp_inputs.pair_bars_map["X"] = ()  # type: ignore[index]


# ---------------------------------------------------------------------------
# _classify_exception 決定表
# ---------------------------------------------------------------------------


class TestClassifyException:
    def test_maps_linalg_to_fixed_code(self) -> None:
        err = _classify_exception(np.linalg.LinAlgError("foo"), "A")
        assert err.error_code == "BACKTEST_LINALG_ERROR"
        assert err.fixed_message == "linalg numerical error"
        assert err.stage == "A"

    def test_maps_memory_error_to_oom(self) -> None:
        err = _classify_exception(MemoryError(), "C")
        assert err.error_code == "WORKER_OOM"

    def test_maps_runtime_primitive_to_lookup_fail(self) -> None:
        err = _classify_exception(RuntimeError("primitive xyz not found"), "A")
        assert err.error_code == "PRIMITIVE_LOOKUP_FAIL"

    def test_maps_value_stage_b_to_fold_invalid(self) -> None:
        err = _classify_exception(ValueError("stage_b fold issue"), "B")
        assert err.error_code == "STAGE_B_FOLD_INVALID"

    def test_maps_value_wf_to_fold_invalid(self) -> None:
        err = _classify_exception(ValueError("wf train days too small"), "B")
        assert err.error_code == "STAGE_B_FOLD_INVALID"

    def test_unclassified_default_for_typeerror(self) -> None:
        err = _classify_exception(TypeError("random"), "A")
        assert err.error_code == "WORKER_UNCLASSIFIED"

    def test_unclassified_for_arrow_invalid_fallback(self) -> None:
        try:
            from pyarrow.lib import ArrowInvalid  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip("pyarrow not installed")
        err = _classify_exception(ArrowInvalid("test"), "A")
        assert err.error_code == "WORKER_UNCLASSIFIED"

    def test_unclassified_for_pandas_empty_data(self) -> None:
        from pandas.errors import EmptyDataError

        err = _classify_exception(EmptyDataError("test"), "B")
        assert err.error_code == "WORKER_UNCLASSIFIED"

    def test_does_not_swallow_keyboard_interrupt(self) -> None:
        with pytest.raises(KeyboardInterrupt):
            _classify_exception(KeyboardInterrupt(), "A")

    def test_does_not_swallow_system_exit(self) -> None:
        with pytest.raises(SystemExit):
            _classify_exception(SystemExit(1), "A")


class TestToErrorResult:
    def test_to_error_result_logs_warning_and_returns_error_result(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            res = _to_error_result("g0", "A", RuntimeError("primitive missing"))
        assert isinstance(res, GenomeStageResult)
        assert res.error is not None
        assert res.error.error_code == "PRIMITIVE_LOOKUP_FAIL"
        assert res.stage_a is None
        assert res.stage_b is None
        assert res.stage_c is None
        assert "parallel_eval.worker_exception" in caplog.text


# ---------------------------------------------------------------------------
# evaluate_genome (純粋関数)
# ---------------------------------------------------------------------------


class TestEvaluateGenomeShortCircuits:
    """Stage A fail / preflight_underfilled / Stage B fail での短絡経路."""

    def _setup_evaluators(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        a: StageResult,
        b: StageResult | None = None,
        c: StageResult | None = None,
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        spy_a = MagicMock(return_value=a)
        spy_b = MagicMock(return_value=b)
        spy_c = MagicMock(return_value=c)
        monkeypatch.setattr(
            "src.alpha_factory.parallel_eval.evaluate_stage_a", spy_a
        )
        monkeypatch.setattr(
            "src.alpha_factory.parallel_eval.evaluate_stage_b", spy_b
        )
        monkeypatch.setattr(
            "src.alpha_factory.parallel_eval.evaluate_stage_c", spy_c
        )
        return spy_a, spy_b, spy_c

    def test_short_circuits_when_stage_a_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy_a, spy_b, spy_c = self._setup_evaluators(
            monkeypatch, a=_stage_result("A", passed=False)
        )
        ctx = _make_ctx()
        result = evaluate_genome(
            _make_genome(),
            ctx,
            StageGateConfig(),
            CrossPairConfig(),
            MagicMock(),
        )
        spy_a.assert_called_once()
        spy_b.assert_not_called()
        spy_c.assert_not_called()
        assert result.stage_a is not None and not result.stage_a.passed
        assert result.stage_b is None
        assert result.stage_c is None

    def test_does_not_call_stage_b_when_preflight_underfilled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy_a, spy_b, spy_c = self._setup_evaluators(
            monkeypatch, a=_stage_result("A", passed=True)
        )
        ctx = _make_ctx(
            preflight_underfilled=True,
            preflight_payload=PreflightPayload(
                n_unique_dates=5,
                wf_min_unique_dates=120,
                max_folds=0,
                wf_min_folds_required=2,
                n_bars=8,
            ),
        )
        result = evaluate_genome(
            _make_genome(),
            ctx,
            StageGateConfig(),
            CrossPairConfig(),
            MagicMock(),
        )
        spy_a.assert_called_once()
        spy_b.assert_not_called()
        spy_c.assert_not_called()
        assert result.stage_a is not None and result.stage_a.passed
        assert result.stage_b is None  # main 側で偽結果生成
        assert result.stage_c is None

    def test_short_circuits_when_stage_b_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy_a, spy_b, spy_c = self._setup_evaluators(
            monkeypatch,
            a=_stage_result("A", passed=True),
            b=_stage_result("B", passed=False),
        )
        ctx = _make_ctx()
        result = evaluate_genome(
            _make_genome(),
            ctx,
            StageGateConfig(),
            CrossPairConfig(),
            MagicMock(),
        )
        spy_a.assert_called_once()
        spy_b.assert_called_once()
        spy_c.assert_not_called()
        assert result.stage_b is not None and not result.stage_b.passed

    def test_runs_all_three_stages_on_full_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy_a, spy_b, spy_c = self._setup_evaluators(
            monkeypatch,
            a=_stage_result("A", passed=True),
            b=_stage_result("B", passed=True),
            c=_stage_result("C", passed=True),
        )
        ctx = _make_ctx()
        result = evaluate_genome(
            _make_genome(),
            ctx,
            StageGateConfig(),
            CrossPairConfig(),
            MagicMock(),
        )
        spy_a.assert_called_once()
        spy_b.assert_called_once()
        spy_c.assert_called_once()
        assert result.stage_c is not None and result.stage_c.passed

    def test_normalizes_stage_a_exception_to_genome_eval_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*args: Any, **kwargs: Any) -> StageResult:
            raise RuntimeError("primitive missing")

        monkeypatch.setattr(
            "src.alpha_factory.parallel_eval.evaluate_stage_a", boom
        )
        ctx = _make_ctx()
        result = evaluate_genome(
            _make_genome(),
            ctx,
            StageGateConfig(),
            CrossPairConfig(),
            MagicMock(),
        )
        assert result.error is not None
        assert result.error.error_code == "PRIMITIVE_LOOKUP_FAIL"
        assert result.error.stage == "A"


# ---------------------------------------------------------------------------
# GenomeEvaluator
# ---------------------------------------------------------------------------


class TestGenomeEvaluatorInProcess:
    """max_workers=1: Pool は起動しない (in-process 経路)."""

    def test_max_workers_1_does_not_create_pool(self) -> None:
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={"tier1_EUR_JPY": _make_ctx()},
        )
        assert ev._pool is None
        assert ev.pool_pids == set()
        ev.close()

    def test_max_workers_below_one_raises(self) -> None:
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            GenomeEvaluator(
                max_workers=0,
                stage_gate_cfg=StageGateConfig(),
                cross_pair_cfg=CrossPairConfig(),
                prim_evaluator=MagicMock(),
                lane_contexts={},
            )

    def test_evaluate_population_returns_results_in_population_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "src.alpha_factory.parallel_eval.evaluate_stage_a",
            lambda g, *args, **kw: _stage_result("A", passed=False),
        )
        ctx = _make_ctx()
        population = [_make_genome(f"g{i}") for i in range(5)]
        with GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={ctx.lane_id: ctx},
        ) as ev:
            results = ev.evaluate_population(ctx.lane_id, 0, population)
        assert [r.genome_name for r in results] == [g.name for g in population]

    def test_close_is_idempotent(self) -> None:
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={},
        )
        ev.close()
        ev.close()  # 二度呼んでも例外なし

    def test_evaluate_after_close_raises(self) -> None:
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={"tier1_EUR_JPY": _make_ctx()},
        )
        ev.close()
        with pytest.raises(RuntimeError, match="already closed"):
            ev.evaluate_population("tier1_EUR_JPY", 0, [])

    def test_context_manager_normal_exit_closes_pool(self) -> None:
        mock_pool = MagicMock()
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={},
        )
        ev._pool = mock_pool  # 注入
        with ev:
            pass
        mock_pool.close.assert_called_once()
        mock_pool.terminate.assert_not_called()
        mock_pool.join.assert_called_once()

    def test_context_manager_exception_terminates_pool(self) -> None:
        mock_pool = MagicMock()
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={},
        )
        ev._pool = mock_pool
        with pytest.raises(ValueError), ev:
            raise ValueError("boom")
        mock_pool.terminate.assert_called_once()
        mock_pool.close.assert_not_called()
        mock_pool.join.assert_called_once()


class TestGenomeEvaluatorPoolPidsFallback:
    def test_pool_pids_returns_empty_set_when_no_pool(self) -> None:
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={},
        )
        assert ev.pool_pids == set()
        ev.close()

    def test_pool_pids_fallbacks_when_internal_attr_missing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ev = GenomeEvaluator(
            max_workers=1,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=MagicMock(),
            lane_contexts={},
        )
        # attribute-free pool stub を注入 (AttributeError 経路を強制)
        class _StubPool:
            pass

        ev._pool = _StubPool()  # type: ignore[assignment]
        with caplog.at_level(logging.WARNING):
            pids = ev.pool_pids
        assert pids == set()
        assert "pool_pids_unavailable" in caplog.text
        ev._pool = None  # close で触らないように
        ev.close()


# ---------------------------------------------------------------------------
# multiprocessing.Pool 経路 (実 spawn を伴う最小ケース)
# ---------------------------------------------------------------------------


def _stage_a_const_pass(*args: Any, **kwargs: Any) -> StageResult:
    """worker process でも import されるためモジュールトップに置く。"""
    genome = args[0]
    return StageResult(
        stage="A",
        passed=False,  # Stage B/C を呼ばずに済むよう fail
        metrics={
            "stage": "A",
            "genome_name": genome.name,
            "n_bars": 4,
            "wall_time_seconds": 0.0,
            "payload": {"fitness_pen": 0.0},
        },
        reason_codes=("test_const_fail",),
    )


@pytest.fixture
def _patch_stage_a_for_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.alpha_factory.parallel_eval.evaluate_stage_a",
        _stage_a_const_pass,
    )


class TestGenomeEvaluatorMultiprocessing:
    """spawn を伴う実テスト (slow)."""

    def test_pool_runs_population_in_order(self) -> None:
        # NOTE: spawn では module-global を pickle 経由で再構築するため、
        # monkeypatch で差し替えた evaluate_stage_a は worker に届かない。
        # ここでは「pool が起動し、population 順 list が返る」契約のみ確認。
        ctx = _make_ctx()
        # Stage A 関数は worker 内で実 evaluate_stage_a が走るが、bars 4 本
        # では即座に system_failure 等になり Stage A の結果が返ってくる
        # (passed=False)。順序保証だけ確認すれば十分。
        from src.alpha_factory.primitives import (
            RegistryEvaluator,
            ensure_registered,
        )

        ensure_registered()
        prim = RegistryEvaluator(pair="EUR_JPY")
        population = [_make_genome(f"g{i}") for i in range(3)]
        with GenomeEvaluator(
            max_workers=2,
            stage_gate_cfg=StageGateConfig(),
            cross_pair_cfg=CrossPairConfig(),
            prim_evaluator=prim,
            lane_contexts={ctx.lane_id: ctx},
        ) as ev:
            results = ev.evaluate_population(ctx.lane_id, 0, population)
        assert [r.genome_name for r in results] == [g.name for g in population]


# ---------------------------------------------------------------------------
# RegistryEvaluator picklability
# ---------------------------------------------------------------------------


class TestRegistryEvaluatorPicklability:
    def test_picklable_with_empty_aux(self) -> None:
        from src.alpha_factory.primitives import RegistryEvaluator

        ev = RegistryEvaluator(pair="EUR_JPY")
        restored = pickle.loads(pickle.dumps(ev))
        assert restored._pair == "EUR_JPY"

    def test_picklable_with_aux_pair_bars(self) -> None:
        from src.alpha_factory.primitives import RegistryEvaluator

        aux = {"USD_JPY": [_make_bars(2)[0]]}
        ev = RegistryEvaluator(pair="EUR_JPY", aux_pair_bars=aux)
        restored = pickle.loads(pickle.dumps(ev))
        assert "USD_JPY" in restored._aux_pair_bars


class TestStageGateConfigPicklability:
    """T052: multiprocessing.Pool initargs 経路のため pickle round-trip 必須."""

    def test_stage_gate_config_picklable_directly(self) -> None:
        from types import MappingProxyType

        cfg = StageGateConfig()
        restored = pickle.loads(pickle.dumps(cfg))
        # 数値フィールドが復元される
        assert restored.stage_a_window_days == cfg.stage_a_window_days
        # live_criteria が MappingProxyType に再 wrap される (深い不変性復元)
        assert isinstance(restored.live_criteria, MappingProxyType)
        assert dict(restored.live_criteria) == dict(cfg.live_criteria)


class TestSignalConfigPicklability:
    """T052: Genome 内の SignalConfig も pickle round-trip が必要 (worker 配布)."""

    def test_signal_config_picklable_directly(self) -> None:
        from types import MappingProxyType

        sig = SignalConfig(name="X", weight=1.0, params={"a": 1, "b": 2})
        restored = pickle.loads(pickle.dumps(sig))
        assert restored.name == "X"
        assert restored.weight == 1.0
        assert isinstance(restored.params, MappingProxyType)
        assert dict(restored.params) == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# measure_peak_rss_mb
# ---------------------------------------------------------------------------


class TestMeasurePeakRss:
    def test_returns_main_and_children_keys(self) -> None:
        result = measure_peak_rss_mb()
        assert "main_rss_mb" in result
        assert "ga_worker_max_rss_mb" in result
        assert "all_children_max_rss_mb" in result
        assert result["main_rss_mb"] > 0

    def test_pool_pids_specified_uses_ga_worker_buckets(self) -> None:
        # pool_pids=set() (空) を渡すと all_children も ga_worker も 0 に
        # (空 set は「指定あり」扱いで all_children 経路は走らない)
        result = measure_peak_rss_mb(pool_pids=set())
        assert result["n_ga_workers"] == 0.0
        assert result["n_all_children"] == 0.0
