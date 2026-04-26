"""``src/alpha_factory/swim_lane.py`` のテスト (T017).

設計根拠:
- devnotes/20260423-2112-swim-lane-manager/conceptual-design.md
- devnotes/20260423-2112-swim-lane-manager/detailed-design.md §5
- devnotes/20260423-2112-swim-lane-manager/design-review-r2.md

テスト戦略:
- Stage A/B/C の内部実装は既存 T014 テストで担保済のため、本テストでは
  ``evaluate_stage_a/b/c`` を ``monkeypatch`` で module-level 差し替え、
  orchestration の順序・短絡・graduation 判定のみを検証する。
- ``GenomeArchive`` は ``MagicMock(spec=GenomeArchive)`` で置き換え、
  ``collect_stage_a/b/c`` / ``mark_graduated`` の呼び出し位置を検証する。
- cross-pair adapter は Stage C の ``cross_pair_evaluator`` 引数経由で
  渡される設計を尊重し、stub Stage C 結果 (CrossPairResult embedded) を
  構築して graduation_criteria の挙動を検証する。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from src.alpha_factory.archive import GenomeArchive
from src.alpha_factory.cross_pair import CrossPairConfig
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    StageResult,
)
from src.alpha_factory.swim_lane import (
    GRADUATION_INSTRUMENT_SENTINEL,
    GRADUATION_LANE_ID,
    GraduationLane,
    LaneManager,
    SwimLane,
    Tier1Lane,
)
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
from src.dsl.strategy import PrimitiveEvaluator
from tests.dsl.conftest import ConstantPrimitiveEvaluator

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _stub_genome(name: str = "g0_i0") -> Genome:
    sig = SignalConfig(name="ConstSignal", weight=1.0, params={})
    clause = ClauseConfig(directional=(sig,), local_gate=(), weight=1.0)
    pos = PositionConfig(
        entry_threshold=0.5,
        exit_threshold=0.1,
        max_pos=1,
        time_stop_min=0,
    )
    risk = RiskConfig(stop_atr=2.0, take_atr=2.0)
    return Genome(
        name=name,
        units=10000,
        clauses=(clause,),
        position=pos,
        risk=risk,
    )


def _stub_meta(pair: str = "EUR_JPY") -> InstrumentMeta:
    base = pair.split("_")[0]
    return InstrumentMeta(
        oanda_name=pair,
        base_currency=base,
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def _stub_bars(pair: str = "EUR_JPY", n: int = 10) -> list[PriceBar]:
    bars: list[PriceBar] = []
    base_bid = Decimal("154.00")
    base_ask = Decimal("154.01")
    for i in range(n):
        bt = datetime(2026, 1, (i % 28) + 1, 12, 0, tzinfo=UTC)
        bars.append(
            PriceBar(
                pair_name=pair,
                bar_time=bt,
                bid=Ohlc(base_bid, base_bid, base_bid, base_bid),
                ask=Ohlc(base_ask, base_ask, base_ask, base_ask),
                volume=10,
                complete=True,
            )
        )
    return bars


def _stub_bt_config(instrument: str = "EUR_JPY") -> BacktestConfig:
    return BacktestConfig(
        instrument=instrument,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 5, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=25,
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )


def _stub_bt_factory_intraday() -> Callable[[str], BacktestConfig]:
    def factory(instrument: str) -> BacktestConfig:
        return _stub_bt_config(instrument)

    return factory


def _stub_bt_factory_violating_hours() -> Callable[[str], BacktestConfig]:
    def factory(instrument: str) -> BacktestConfig:
        return BacktestConfig(
            instrument=instrument,
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 5, tzinfo=UTC),
            initial_cash=Decimal("1000000"),
            leverage=25,
            session_close_utc_hours=frozenset(),  # 空 → intraday 違反
            bar_minutes=1,
        )

    return factory


def _stub_bt_factory_returns_str() -> Callable[[str], BacktestConfig]:
    def factory(instrument: str) -> BacktestConfig:
        return cast(BacktestConfig, "not a config")

    return factory


def _make_tier1_lane(
    instrument: str = "EUR_JPY",
    pop_size: int = 2,
    *,
    state: str = "active",
) -> Tier1Lane:
    lane_id = f"tier1_{instrument}"
    population = [_stub_genome(f"g0_i{i}") for i in range(pop_size)]
    return Tier1Lane(
        lane_id=lane_id,
        population=population,
        instrument=instrument,
        bars_60d=_stub_bars(instrument, n=4),
        bars_18m=_stub_bars(instrument, n=8),
        bars_holdout=_stub_bars(instrument, n=4),
        meta=_stub_meta(instrument),
        state=cast(Any, state),
    )


def _make_graduation_lane(
    with_pair_data: bool = False,
    pairs: tuple[str, ...] = ("EUR_JPY", "USD_JPY"),
) -> GraduationLane:
    pair_bars: dict[str, list[PriceBar]] = {}
    pair_meta: dict[str, InstrumentMeta] = {}
    if with_pair_data:
        pair_bars = {p: _stub_bars(p, n=4) for p in pairs}
        pair_meta = {p: _stub_meta(p) for p in pairs}
    return GraduationLane(
        lane_id=GRADUATION_LANE_ID,
        pair_bars=pair_bars,
        pair_meta=pair_meta,
    )


def _make_lane_manager(
    *,
    tier1: dict[str, Tier1Lane] | None = None,
    graduation: GraduationLane | None = None,
    archive: Any | None = None,
    factory: Callable[[str], BacktestConfig] | None = None,
    deferred_promotion: bool = False,
    stage_gate_config: StageGateConfig | None = None,
) -> LaneManager:
    if tier1 is None:
        tier1 = {"tier1_EUR_JPY": _make_tier1_lane("EUR_JPY")}
    if graduation is None:
        graduation = _make_graduation_lane()
    if archive is None:
        archive = MagicMock(spec=GenomeArchive)
    if factory is None:
        factory = _stub_bt_factory_intraday()
    if stage_gate_config is None:
        # T035: 既存 fixture は bars_18m=8 unique dates で十分な観測日数を持たない
        # ため、デフォルトの wf_train_days=120/test=20/embargo=1 (sum=141) では
        # skip-path 発動。既存テストの期待を維持するため小さい wf 値を与える。
        stage_gate_config = StageGateConfig(
            wf_train_days=2,
            wf_test_days=1,
            wf_step_days=1,
            wf_embargo_days=0,
        )
    return LaneManager(
        tier1=tier1,
        graduation=graduation,
        stage_gate_config=stage_gate_config,
        cross_pair_config=CrossPairConfig(),
        primitive_evaluator=cast(PrimitiveEvaluator, ConstantPrimitiveEvaluator(0.0)),
        archive=archive,
        backtest_config_factory=factory,
        deferred_promotion=deferred_promotion,
    )


# Stage result stubs -------------------------------------------------------


def _stage_a_result(*, passed: bool, name: str = "g0_i0") -> StageResult:
    return StageResult(
        stage="A",
        passed=passed,
        metrics={
            "stage": "A",
            "genome_name": name,
            "n_bars": 4,
            "wall_time_seconds": 0.01,
            "payload": {
                "fitness_raw": 0.5 if passed else -0.1,
                "size_norm": 0.2,
                "fitness_pen": 0.44 if passed else -0.11,
                "alpha_a": 0.03,
                "threshold": 0.0,
                "trade_count": 10 if passed else 0,
                "sharpe_raw": 0.5 if passed else -0.1,
            },
        },
        reason_codes=() if passed else ("below_threshold",),
    )


def _stage_b_result(*, passed: bool, name: str = "g0_i0") -> StageResult:
    return StageResult(
        stage="B",
        passed=passed,
        metrics={
            "stage": "B",
            "genome_name": name,
            "n_bars": 8,
            "wall_time_seconds": 0.01,
            "payload": {
                "n_fold": 3,
                "n_fold_unavailable": 0,
                "oos_sharpes": (0.3, 0.4, 0.5) if passed else (0.0, 0.0, 0.0),
                "median_oos_sharpe": 0.4 if passed else 0.0,
                "positive_fold_ratio": 1.0 if passed else 0.0,
                "dsr": None,
                "is_full_sharpe": 0.6 if passed else 0.0,
                "is_full_total_pnl": 10000.0,
                "is_full_trade_count": 30,
            },
        },
        reason_codes=() if passed else ("median_oos_sharpe<min",),
    )


def _stage_c_result(
    *,
    passed: bool,
    cp_skipped: bool = True,
    cp_passed: bool | None = None,
    name: str = "g0_i0",
    target_pair: str = "EUR_JPY",
) -> StageResult:
    cp: dict[str, Any] = {"skipped": cp_skipped, "result": None, "error_type": None}
    if not cp_skipped:
        cp["result"] = CrossPairResult(
            target_pair=target_pair,
            anchor_pairs=("USD_JPY", "EUR_USD"),
            aggregator_name="mean_min_and",
            window=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 2, 1, tzinfo=UTC),
            ),
            passed=bool(cp_passed),
            metrics={"skipped": False},
            reason_codes=(),
        )
    payload = {
        "sharpe": 1.2,
        "total_pnl": 60000.0,
        "max_drawdown_frac": 0.15,
        "trade_count": 80,
        "live_criteria_pass": {},
        "intraday_compliant": True,
        "overnight_violations": 0,
        "stress": {"skipped": False},
        "cross_pair": cp,
    }
    return StageResult(
        stage="C",
        passed=passed,
        metrics={
            "stage": "C",
            "genome_name": name,
            "n_bars": 4,
            "wall_time_seconds": 0.01,
            "payload": payload,
        },
        reason_codes=() if passed else ("live_criteria.sharpe<min",),
    )


# ---------------------------------------------------------------------------
# dataclass / 型検証 (4)
# ---------------------------------------------------------------------------


def test_swim_lane_dataclass_fields() -> None:
    lane = SwimLane(lane_id="x", population=[_stub_genome("g")])
    assert lane.lane_id == "x"
    assert len(lane.population) == 1
    assert lane.generation_count == 0
    assert lane.state == "active"


def test_tier1_lane_inheritance() -> None:
    t = Tier1Lane(
        lane_id="tier1_EUR_JPY",
        population=[],
        instrument="EUR_JPY",
        bars_60d=_stub_bars(n=2),
        bars_18m=[],
        bars_holdout=[],
        meta=_stub_meta("EUR_JPY"),
    )
    assert isinstance(t, SwimLane)
    assert t.instrument == "EUR_JPY"
    assert t.meta is not None
    assert len(t.bars_60d) == 2


def test_graduation_lane_inheritance() -> None:
    g = GraduationLane(lane_id=GRADUATION_LANE_ID)
    assert isinstance(g, SwimLane)
    assert g.seed_graduates == []
    assert g.pair_bars == {}
    assert g.pair_meta == {}


def test_graduation_instrument_sentinel_constant() -> None:
    # sentinel は "multi"、archive row の instrument カラム用予約値
    assert GRADUATION_INSTRUMENT_SENTINEL == "multi"
    assert GRADUATION_LANE_ID == "graduation"


# ---------------------------------------------------------------------------
# LaneManager 初期化 (5)
# ---------------------------------------------------------------------------


def test_lane_manager_init_basic() -> None:
    mgr = _make_lane_manager()
    lanes = mgr.get_all_lanes()
    assert len(lanes) == 2
    assert isinstance(lanes[0], Tier1Lane)
    assert isinstance(lanes[1], GraduationLane)


def test_lane_manager_init_empty_tier1_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _make_lane_manager(tier1={})


def test_lane_manager_init_instrument_key_mismatch() -> None:
    # lane_id は "tier1_EUR_JPY" だが内部 instrument は "USD_JPY" → suffix 不一致
    bad_lane = Tier1Lane(
        lane_id="tier1_EUR_JPY",
        population=[],
        instrument="USD_JPY",  # mismatch
        bars_60d=[],
        bars_18m=[],
        bars_holdout=[],
        meta=_stub_meta("USD_JPY"),
    )
    with pytest.raises(ValueError, match="must match suffix"):
        _make_lane_manager(tier1={"tier1_EUR_JPY": bad_lane})


def test_lane_manager_init_graduation_lane_id_mismatch() -> None:
    bad_grad = GraduationLane(lane_id="not_graduation")
    with pytest.raises(ValueError, match=r"graduation\.lane_id"):
        _make_lane_manager(graduation=bad_grad)


def test_lane_manager_init_meta_none_raises() -> None:
    lane = Tier1Lane(
        lane_id="tier1_EUR_JPY",
        population=[],
        instrument="EUR_JPY",
        bars_60d=[],
        bars_18m=[],
        bars_holdout=[],
        meta=None,  # invalid
    )
    with pytest.raises(ValueError, match="meta must be non-None"):
        _make_lane_manager(tier1={"tier1_EUR_JPY": lane})


# ---------------------------------------------------------------------------
# get_all_lanes (1)
# ---------------------------------------------------------------------------


def test_get_all_lanes_order() -> None:
    tier1 = {
        "tier1_EUR_JPY": _make_tier1_lane("EUR_JPY"),
        "tier1_USD_JPY": _make_tier1_lane("USD_JPY"),
    }
    mgr = _make_lane_manager(tier1=tier1)
    lanes = mgr.get_all_lanes()
    assert [lane.lane_id for lane in lanes] == [
        "tier1_EUR_JPY",
        "tier1_USD_JPY",
        GRADUATION_LANE_ID,
    ]


# ---------------------------------------------------------------------------
# run_generation - Tier1 lane (8)
# ---------------------------------------------------------------------------


def test_run_generation_unknown_lane_id_keyerror() -> None:
    mgr = _make_lane_manager()
    with pytest.raises(KeyError, match="unknown lane_id"):
        mgr.run_generation("tier1_DOES_NOT_EXIST")


def test_run_generation_graduation_not_implemented() -> None:
    mgr = _make_lane_manager()
    with pytest.raises(NotImplementedError, match="GraduationLane"):
        mgr.run_generation(GRADUATION_LANE_ID)


def _patch_stage_funcs(
    monkeypatch: pytest.MonkeyPatch,
    a_result: Callable[[Genome], StageResult]
    | StageResult = None,  # type: ignore[assignment]
    b_result: Callable[[Genome], StageResult] | StageResult | None = None,
    c_result: Callable[..., StageResult] | StageResult | None = None,
) -> dict[str, int]:
    """``evaluate_stage_a/b/c`` を module-level で差し替え、呼び出し回数を記録する。"""
    counts = {"a": 0, "b": 0, "c": 0, "c_with_cp": 0}

    def _fake_a(*args: Any, **kwargs: Any) -> StageResult:
        counts["a"] += 1
        genome = args[0]
        if callable(a_result):
            return a_result(genome)
        assert a_result is not None
        return a_result

    def _fake_b(*args: Any, **kwargs: Any) -> StageResult:
        counts["b"] += 1
        genome = args[0]
        if callable(b_result):
            return b_result(genome)
        assert b_result is not None
        return b_result

    def _fake_c(*args: Any, **kwargs: Any) -> StageResult:
        counts["c"] += 1
        if kwargs.get("cross_pair_evaluator") is not None:
            counts["c_with_cp"] += 1
        genome = args[0]
        if callable(c_result):
            return c_result(genome, **kwargs)
        assert c_result is not None
        return c_result

    monkeypatch.setattr(
        "src.alpha_factory.swim_lane.evaluate_stage_a", _fake_a
    )
    monkeypatch.setattr(
        "src.alpha_factory.swim_lane.evaluate_stage_b", _fake_b
    )
    monkeypatch.setattr(
        "src.alpha_factory.swim_lane.evaluate_stage_c", _fake_c
    )
    return counts


def test_run_generation_stage_a_fail_short_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    mgr = _make_lane_manager(archive=archive)
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert counts["a"] == 2  # 2 個体
    assert counts["b"] == 0
    assert counts["c"] == 0
    assert summary["stage_a_pass"] == 0
    assert summary["graduation_count"] == 0
    assert archive.collect_stage_a.call_count == 2
    assert archive.collect_stage_b.call_count == 0
    assert archive.collect_stage_c.call_count == 0
    assert archive.mark_graduated.call_count == 0


def test_run_generation_propagates_provenance_to_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T018: Tier1Lane.provenance が collect_stage_a の parent_a/parent_b に
    伝搬されることを検証."""
    _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    tier1 = _make_tier1_lane("EUR_JPY", pop_size=2)
    tier1.provenance = {
        tier1.population[0].name: ("parent_a0", "parent_b0"),
        tier1.population[1].name: ("parent_a1", None),
    }
    mgr = _make_lane_manager(
        tier1={"tier1_EUR_JPY": tier1},
        archive=archive,
    )
    mgr.run_generation("tier1_EUR_JPY")
    # collect_stage_a の kwargs を検証
    call_args = archive.collect_stage_a.call_args_list
    assert len(call_args) == 2
    # 第1個体
    ka0 = call_args[0].kwargs
    assert ka0["parent_a"] == "parent_a0"
    assert ka0["parent_b"] == "parent_b0"
    # 第2個体
    ka1 = call_args[1].kwargs
    assert ka1["parent_a"] == "parent_a1"
    assert ka1["parent_b"] is None


def test_run_generation_default_provenance_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T018 後方互換: provenance 未設定 (default 空 dict) は parent_a/b=None で
    collect_stage_a が呼ばれること."""
    _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    tier1 = _make_tier1_lane("EUR_JPY", pop_size=1)
    assert tier1.provenance == {}  # default
    mgr = _make_lane_manager(
        tier1={"tier1_EUR_JPY": tier1},
        archive=archive,
    )
    mgr.run_generation("tier1_EUR_JPY")
    ka = archive.collect_stage_a.call_args_list[0].kwargs
    assert ka["parent_a"] is None
    assert ka["parent_b"] is None


def test_run_generation_stage_b_fail_short_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    mgr = _make_lane_manager(archive=archive)
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert counts["a"] == 2
    assert counts["b"] == 2
    assert counts["c"] == 0
    assert summary["stage_a_pass"] == 2
    assert summary["stage_b_pass"] == 0
    assert summary["graduation_count"] == 0
    assert archive.collect_stage_a.call_count == 2
    assert archive.collect_stage_b.call_count == 2
    assert archive.collect_stage_c.call_count == 0
    assert archive.mark_graduated.call_count == 0


def test_run_generation_stage_c_fail_no_graduation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=_stage_c_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    mgr = _make_lane_manager(archive=archive)
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert counts["c"] == 2
    assert summary["stage_a_pass"] == 2
    assert summary["stage_b_pass"] == 2
    assert summary["stage_c_pass"] == 0
    assert summary["graduation_count"] == 0
    assert archive.collect_stage_c.call_count == 2
    assert archive.mark_graduated.call_count == 0


def test_run_generation_stage_c_pass_with_cp_pass_graduates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c_res = _stage_c_result(passed=True, cp_skipped=False, cp_passed=True)
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=c_res,
    )
    archive = MagicMock(spec=GenomeArchive)
    graduation = _make_graduation_lane(with_pair_data=True)
    mgr = _make_lane_manager(
        archive=archive,
        graduation=graduation,
    )
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert counts["c"] == 2
    # cross-pair adapter は pair_bars 注入済なので Stage C 呼び出し時に渡される
    assert counts["c_with_cp"] == 2
    assert summary["stage_c_pass"] == 2
    assert summary["graduation_count"] == 2
    assert archive.mark_graduated.call_count == 2
    assert len(graduation.seed_graduates) == 2


def test_run_generation_stage_c_pass_with_cp_fail_no_graduation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c_res = _stage_c_result(passed=True, cp_skipped=False, cp_passed=False)
    _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=c_res,
    )
    archive = MagicMock(spec=GenomeArchive)
    graduation = _make_graduation_lane(with_pair_data=True)
    mgr = _make_lane_manager(archive=archive, graduation=graduation)
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert summary["stage_c_pass"] == 2
    assert summary["graduation_count"] == 0
    assert archive.mark_graduated.call_count == 0
    assert len(graduation.seed_graduates) == 0


def test_run_generation_stage_c_pass_with_cp_skipped_no_graduation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cp_skipped=True で cross_pair.result が None → graduation 保守的 False
    c_res = _stage_c_result(passed=True, cp_skipped=True)
    _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=c_res,
    )
    archive = MagicMock(spec=GenomeArchive)
    graduation = _make_graduation_lane(with_pair_data=False)
    mgr = _make_lane_manager(archive=archive, graduation=graduation)
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert summary["stage_c_pass"] == 2
    assert summary["graduation_count"] == 0
    assert archive.mark_graduated.call_count == 0
    assert len(graduation.seed_graduates) == 0


# ---------------------------------------------------------------------------
# run_generation - state / 計数 (3)
# ---------------------------------------------------------------------------


def test_run_generation_increments_generation_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=False),
    )
    mgr = _make_lane_manager()
    lane = mgr.tier1["tier1_EUR_JPY"]
    assert lane.generation_count == 0
    mgr.run_generation("tier1_EUR_JPY")
    assert lane.generation_count == 1
    mgr.run_generation("tier1_EUR_JPY")
    assert lane.generation_count == 2
    mgr.run_generation("tier1_EUR_JPY")
    assert lane.generation_count == 3


def test_run_generation_converged_state_noop() -> None:
    # converged state → NoOp summary、generation_count 不変、archive 未更新
    lane = _make_tier1_lane("EUR_JPY", state="converged")
    archive = MagicMock(spec=GenomeArchive)
    mgr = _make_lane_manager(
        tier1={"tier1_EUR_JPY": lane},
        archive=archive,
    )
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert summary["state"] == "converged"
    assert summary["n_evaluated"] == 0
    assert summary["stage_a_pass"] == 0
    assert summary["graduation_count"] == 0
    assert "wall_time_seconds" in summary
    assert lane.generation_count == 0
    assert archive.collect_stage_a.call_count == 0
    assert archive.collect_stage_b.call_count == 0
    assert archive.collect_stage_c.call_count == 0
    assert archive.mark_graduated.call_count == 0


def test_run_generation_paused_state_noop() -> None:
    lane = _make_tier1_lane("EUR_JPY", state="paused")
    archive = MagicMock(spec=GenomeArchive)
    mgr = _make_lane_manager(
        tier1={"tier1_EUR_JPY": lane},
        archive=archive,
    )
    summary = mgr.run_generation("tier1_EUR_JPY")
    assert summary["state"] == "paused"
    assert summary["n_evaluated"] == 0
    assert lane.generation_count == 0
    assert archive.collect_stage_a.call_count == 0


# ---------------------------------------------------------------------------
# graduation_criteria (4)
# ---------------------------------------------------------------------------


def test_graduation_criteria_stage_c_fail() -> None:
    mgr = _make_lane_manager()
    c_res = _stage_c_result(passed=False)
    assert mgr.graduation_criteria(_stub_genome(), c_res, None) is False


def test_graduation_criteria_cross_pair_none() -> None:
    mgr = _make_lane_manager()
    c_res = _stage_c_result(passed=True)
    # cp=None → 保守的 False
    assert mgr.graduation_criteria(_stub_genome(), c_res, None) is False


def test_graduation_criteria_cross_pair_fail() -> None:
    mgr = _make_lane_manager()
    c_res = _stage_c_result(passed=True)
    cp = CrossPairResult(
        target_pair="EUR_JPY",
        anchor_pairs=("USD_JPY", "EUR_USD"),
        aggregator_name="mean_min_and",
        window=(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
        ),
        passed=False,
        metrics={"skipped": False},
        reason_codes=("mean_sharpe<min",),
    )
    assert mgr.graduation_criteria(_stub_genome(), c_res, cp) is False


def test_graduation_criteria_both_pass() -> None:
    mgr = _make_lane_manager()
    c_res = _stage_c_result(passed=True)
    cp = CrossPairResult(
        target_pair="EUR_JPY",
        anchor_pairs=("USD_JPY", "EUR_USD"),
        aggregator_name="mean_min_and",
        window=(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
        ),
        passed=True,
        metrics={"skipped": False},
        reason_codes=(),
    )
    assert mgr.graduation_criteria(_stub_genome(), c_res, cp) is True


# ---------------------------------------------------------------------------
# promote_graduates / 冪等性 (2)
# ---------------------------------------------------------------------------


def test_promote_graduates_returns_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 0 → full-pass 世代後に 2
    c_res = _stage_c_result(passed=True, cp_skipped=False, cp_passed=True)
    _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=c_res,
    )
    graduation = _make_graduation_lane(with_pair_data=True)
    mgr = _make_lane_manager(
        archive=MagicMock(spec=GenomeArchive),
        graduation=graduation,
    )
    assert mgr.promote_graduates() == 0
    mgr.run_generation("tier1_EUR_JPY")
    assert mgr.promote_graduates() == 2


def test_promote_graduates_deferred_mode_raises() -> None:
    mgr = _make_lane_manager(deferred_promotion=True)
    with pytest.raises(NotImplementedError, match="deferred_promotion"):
        mgr.promote_graduates()


def test_mark_for_graduation_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 同一 (lane, gen, name) で 2 回 mark でも seed_graduates は 1 件、
    # archive.mark_graduated は 1 回
    archive = MagicMock(spec=GenomeArchive)
    graduation = _make_graduation_lane(with_pair_data=True)
    mgr = _make_lane_manager(archive=archive, graduation=graduation)
    lane = mgr.tier1["tier1_EUR_JPY"]
    genome = _stub_genome("g0_dup")
    # 1 回目
    promoted1 = mgr._mark_for_graduation(lane, genome)
    # 2 回目 (同一 lane.generation_count で同名)
    promoted2 = mgr._mark_for_graduation(lane, genome)
    assert promoted1 is True
    assert promoted2 is False
    assert len(graduation.seed_graduates) == 1
    assert archive.mark_graduated.call_count == 1


# ---------------------------------------------------------------------------
# cross-pair adapter / 健全性 (1)
# ---------------------------------------------------------------------------


def test_lane_manager_init_intraday_violation_raises() -> None:
    with pytest.raises(ValueError, match="session_close_utc_hours"):
        _make_lane_manager(factory=_stub_bt_factory_violating_hours())


def test_lane_manager_init_factory_non_config_raises() -> None:
    with pytest.raises(TypeError, match="BacktestConfig"):
        _make_lane_manager(factory=_stub_bt_factory_returns_str())


# ---------------------------------------------------------------------------
# cross-pair adapter 構築 (1) — pair_bars 注入で Stage C に evaluator が渡ること
# ---------------------------------------------------------------------------


def test_run_generation_passes_cp_evaluator_when_pair_data_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cross-pair adapter が Stage C に渡される (cp_with_cp > 0)
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=_stage_c_result(passed=True, cp_skipped=False, cp_passed=True),
    )
    graduation = _make_graduation_lane(with_pair_data=True)
    mgr = _make_lane_manager(graduation=graduation)
    mgr.run_generation("tier1_EUR_JPY")
    assert counts["c_with_cp"] == 2


def test_run_generation_skips_cp_evaluator_when_pair_data_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=True),
        c_result=_stage_c_result(passed=True, cp_skipped=True),
    )
    graduation = _make_graduation_lane(with_pair_data=False)
    mgr = _make_lane_manager(graduation=graduation)
    mgr.run_generation("tier1_EUR_JPY")
    # pair_bars 未注入なら cp_evaluator=None → counts["c_with_cp"] 増えない
    assert counts["c_with_cp"] == 0
    assert counts["c"] == 2


# T035 / T044: Stage B skip-path ==============================================


def test_stage_b_skipped_when_unique_dates_below_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bars_18m の unique dates < wf_min_unique_dates → T044 pre-flight が先取りし
    reason_codes=('stage_b_pre_flight_underfilled',) で記録される (T035 wf_min_unique_dates 単独経路は dead)."""
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    # default _make_lane_manager が小さい wf cfg を渡すので、それを大きい cfg で
    # 上書きして underfilled を再現する (bars_18m=8 unique dates < 141)
    big_cfg = StageGateConfig()  # wf_train=120 + embargo=1 + test=20 = 141
    mgr = _make_lane_manager(archive=archive, stage_gate_config=big_cfg)
    mgr.run_generation("tier1_EUR_JPY")
    # Stage A は通常通り 2 回呼ばれる
    assert counts["a"] == 2
    # Stage B は skip-path で 0 回呼ばれる
    assert counts["b"] == 0
    assert archive.collect_stage_b.call_count == 2
    for call in archive.collect_stage_b.call_args_list:
        sr = call.kwargs.get("stage_result") or call.args[3]
        # T044: pre_flight が wf_min_folds_required (default 2) で先取り
        assert sr.reason_codes == ("stage_b_pre_flight_underfilled",)
        assert sr.passed is False
        payload = sr.metrics["payload"]
        assert payload["n_unique_dates"] == 8
        assert payload["wf_min_unique_dates"] == 141
        assert payload["max_folds"] == 0
        assert payload["wf_min_folds_required"] == 2
        assert payload["n_fold"] == 0


def test_stage_b_evaluated_when_unique_dates_meet_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bars_18m unique dates >= wf_min_unique_dates → 通常 evaluate_stage_b 発火."""
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    # default fixture は小さい wf (2+0+1=3) で bars_18m=8 だから skip-path 不発動
    mgr = _make_lane_manager(archive=archive)
    mgr.run_generation("tier1_EUR_JPY")
    assert counts["a"] == 2
    # Stage B は通常通り評価される
    assert counts["b"] == 2


# T044: Stage B pre-flight =================================================


def test_stage_b_skipped_pre_flight_when_max_folds_below_min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bars_18m が max_folds<min_folds_required → pre-flight skip-path."""
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    # train=120, test=20, embargo=1, step=20 → fold_len=141。bars_18m=8 → max_folds=0 < min=2
    big_cfg = StageGateConfig(wf_min_folds_required=2)
    mgr = _make_lane_manager(archive=archive, stage_gate_config=big_cfg)
    mgr.run_generation("tier1_EUR_JPY")
    # Stage A は通常通り 2 回呼ばれる
    assert counts["a"] == 2
    # Stage B は pre-flight で skip → 0 回
    assert counts["b"] == 0
    # archive に pre-flight reason で記録
    assert archive.collect_stage_b.call_count == 2
    for call in archive.collect_stage_b.call_args_list:
        sr = call.kwargs.get("stage_result") or call.args[3]
        assert sr.reason_codes == ("stage_b_pre_flight_underfilled",)
        assert sr.passed is False
        payload = sr.metrics["payload"]
        assert "max_folds" in payload
        assert "wf_min_folds_required" in payload
        assert payload["wf_min_folds_required"] == 2


def test_stage_b_evaluated_when_max_folds_meets_min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max_folds >= min_folds_required → 通常 evaluate_stage_b."""
    counts = _patch_stage_funcs(
        monkeypatch,
        a_result=_stage_a_result(passed=True),
        b_result=_stage_b_result(passed=False),
    )
    archive = MagicMock(spec=GenomeArchive)
    # default _make_lane_manager は train=2/test=1/embargo=0/step=1, bars=8 → max_folds=6 >= 2
    mgr = _make_lane_manager(archive=archive)
    mgr.run_generation("tier1_EUR_JPY")
    assert counts["a"] == 2
    assert counts["b"] == 2
