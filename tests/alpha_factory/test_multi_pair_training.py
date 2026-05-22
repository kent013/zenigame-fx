"""T117: multi-pair training (Stage A fitness min 集約) のユニットテスト。

- config default OFF / fail-closed / aggregate 検証
- _aggregate_multi_pair_stage_a の min 集約 (anchor 取引枯渇個体を淘汰)
- default (mp_train_inputs=None) は単一ペア現挙動 (bit-exact は run_ga_parallel が担保)
"""

from __future__ import annotations

import numpy as np
import pytest

from src.alpha_factory.config import MultiPairTrainingConfig
from src.alpha_factory.primitives import RegistryEvaluator
from src.alpha_factory.stage_gate import StageResult


class TestMultiPairTrainingConfig:
    def test_default_off(self) -> None:
        c = MultiPairTrainingConfig()
        assert c.enable is False
        assert c.pairs == ()
        assert c.aggregate == "min"
        assert c.scope == "stage_a"

    def test_enable_requires_two_pairs(self) -> None:
        with pytest.raises(ValueError, match="requires >=2 pairs"):
            MultiPairTrainingConfig(enable=True, pairs=("EUR_JPY",))

    def test_valid_enable(self) -> None:
        c = MultiPairTrainingConfig(enable=True, pairs=("EUR_JPY", "USD_JPY"))
        assert c.enable is True

    def test_pairs_must_be_unique(self) -> None:
        with pytest.raises(ValueError, match="pairs must be unique"):
            MultiPairTrainingConfig(pairs=("EUR_JPY", "USD_JPY", "USD_JPY"))

    def test_aggregate_validation(self) -> None:
        with pytest.raises(ValueError, match="aggregate must be"):
            MultiPairTrainingConfig(aggregate="median")

    def test_scope_validation(self) -> None:
        with pytest.raises(ValueError, match="scope must be stage_a"):
            MultiPairTrainingConfig(scope="stage_b")


class TestRegistryEvaluatorWithPair:
    def test_with_pair_replaces_pair_only(self) -> None:
        arr = np.array([1.0, 2.0], dtype=np.float64)
        ev = RegistryEvaluator(
            pair="EUR_JPY",
            aux_series={"macro.vix": [10.0, 11.0]},
            aux_pair_mid_close={"USD_JPY": arr},
            strict_snapshot_required=True,
            strict_aux_required=False,
        )
        out = ev.with_pair("USD_JPY")

        assert out is not ev
        assert out._pair == "USD_JPY"
        assert ev._pair == "EUR_JPY"
        assert out._aux_series == ev._aux_series
        assert out._aux_pair_mid_close == ev._aux_pair_mid_close
        assert out._strict_snapshot_required is True


def _stage_a_result(fitness_pen: float, *, passed: bool = True) -> StageResult:
    return StageResult(
        stage="A",
        passed=passed,
        metrics={"payload": {"fitness_pen": fitness_pen, "fitness_raw": 1.0}},
    )


class TestAggregateMultiPairStageA:
    def test_min_aggregation_picks_worst_pair(self, monkeypatch) -> None:
        """anchor が低 fitness_pen なら min がそれを選び selection fitness を下げる。"""
        from src.alpha_factory import parallel_eval as pe

        # anchor の Stage A 評価を fitness_pen=-5.0 (低=取引枯渇相当) に固定
        def fake_eval(genome, bars, meta, bt, ev, cfg):
            return _stage_a_result(-5.0)

        monkeypatch.setattr(pe, "evaluate_stage_a", fake_eval)

        mp = pe.MultiPairTrainInputs(
            anchor_pairs=("USD_JPY",),
            bars_a_map={"USD_JPY": ()},
            meta_map={"USD_JPY": object()},
            bt_cfg_map={"USD_JPY": object()},
            aggregate="min",
        )
        ctx = _make_ctx(mp)
        target = _stage_a_result(2.0)  # target は高い
        out = pe._aggregate_multi_pair_stage_a(
            object(), ctx, mp, object(), _StubEval(), target
        )
        payload = out.metrics["payload"]
        # min(2.0, -5.0) = -5.0 が selection fitness_pen
        assert payload["fitness_pen"] == -5.0
        assert payload["mp_fitness_pen_min"] == -5.0
        assert payload["mp_fitness_pen_mean"] == pytest.approx((2.0 + -5.0) / 2)

    def test_min_aggregation_keeps_high_when_all_good(self, monkeypatch) -> None:
        from src.alpha_factory import parallel_eval as pe

        def fake_eval(genome, bars, meta, bt, ev, cfg):
            return _stage_a_result(3.0)

        monkeypatch.setattr(pe, "evaluate_stage_a", fake_eval)
        mp = pe.MultiPairTrainInputs(
            anchor_pairs=("USD_JPY",),
            bars_a_map={"USD_JPY": ()},
            meta_map={"USD_JPY": object()},
            bt_cfg_map={"USD_JPY": object()},
            aggregate="min",
        )
        ctx = _make_ctx(mp)
        target = _stage_a_result(2.0)
        out = pe._aggregate_multi_pair_stage_a(
            object(), ctx, mp, object(), _StubEval(), target
        )
        # min(2.0, 3.0) = 2.0
        assert out.metrics["payload"]["fitness_pen"] == 2.0

    def test_anchor_exception_uses_sentinel(self, monkeypatch) -> None:
        from src.alpha_factory import parallel_eval as pe
        from src.alpha_factory.stage_gate import SYSTEM_FAILURE_FITNESS

        def fake_eval(genome, bars, meta, bt, ev, cfg):
            raise RuntimeError("anchor eval boom")

        monkeypatch.setattr(pe, "evaluate_stage_a", fake_eval)
        mp = pe.MultiPairTrainInputs(
            anchor_pairs=("USD_JPY",),
            bars_a_map={"USD_JPY": ()},
            meta_map={"USD_JPY": object()},
            bt_cfg_map={"USD_JPY": object()},
            aggregate="min",
        )
        ctx = _make_ctx(mp)
        target = _stage_a_result(2.0)
        out = pe._aggregate_multi_pair_stage_a(
            object(), ctx, mp, object(), _StubEval(), target
        )
        # anchor 例外 → SYSTEM_FAILURE_FITNESS が min
        assert out.metrics["payload"]["fitness_pen"] == SYSTEM_FAILURE_FITNESS

    def test_no_payload_returns_unchanged(self) -> None:
        from src.alpha_factory import parallel_eval as pe

        mp = pe.MultiPairTrainInputs(
            anchor_pairs=("USD_JPY",),
            bars_a_map={"USD_JPY": ()},
            meta_map={"USD_JPY": object()},
            bt_cfg_map={"USD_JPY": object()},
            aggregate="min",
        )
        ctx = _make_ctx(mp)
        # payload 不在 (sentinel 経路) → そのまま返す
        target = StageResult(stage="A", passed=False, metrics={})
        out = pe._aggregate_multi_pair_stage_a(
            object(), ctx, mp, object(), _StubEval(), target
        )
        assert out is target


class _StubEval:
    """primitive_evaluator stub。with_pair は self を返す (evaluate_stage_a は monkeypatch)。"""

    def with_pair(self, pair: str) -> _StubEval:
        return self


def _make_ctx(mp):
    """_evaluator_for_stage が aux なし base を返すよう最小 ctx を作る。"""

    # _aggregate は _evaluator_for_stage(ctx, bars).with_pair(pair) を呼ぶ。
    # aux_bundle=None なら base evaluator (=渡した _StubEval) を返す。
    class _Ctx:
        lane_id = "L0"
        aux_bundle = None
        mp_train_inputs = mp

    return _Ctx()
