"""T111: ParetoFeaturesLite (NSGA-II selection 用 Stage B 完結軸) のテスト。

pooling は fold artifact を直消費 (period 再フィルタ・再 backtest なし)、
no-raise 隔離、source_stage=B、軸方向 invariant を検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.alpha_factory import pareto_features
from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBucket,
    TradeRecord,
)
from src.alpha_factory.pareto_features import (
    FoldCanonicalArtifact,
    ParetoFeaturesLite,
    build_stage_b_pooled_cf_from_fold_artifacts,
    try_build_pareto_lite_from_stage_b_fold_artifacts,
)

_LC = {
    "sharpe_min": 1.0,
    "total_pnl_min": 50000.0,
    "max_drawdown_max": 0.2,
    "trade_count_min": 50,
    "trade_count_max": 5000,
    "win_rate_min": 0.5,
}


def _make_cf(
    *, is_feasible: bool = True, max_dd: float = 0.1, net_pnl: float = 60000.0
) -> CanonicalFiveResult:
    codes: frozenset[InfeasibleReasonCode] = (
        frozenset()
        if is_feasible
        else frozenset({InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST})
    )
    return CanonicalFiveResult(
        sr_session_worst_block_scale=0.1,
        sr_session_worst_annual_estimate=2.5,
        net_pnl_after_cost=net_pnl,
        max_dd=max_dd,
        trade_count=100,
        session_block_win_rate_worst=0.5,
        per_bucket_sr={b: 0.1 for b in SessionBucket},
        per_bucket_wr={b: 0.5 for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=0.5,
        slack_pnl=0.5,
        slack_dd=0.5,
        slack_tc=0.5,
        slack_wr=0.5,
        gate_worst_gap=0.0,
        gate_pass=is_feasible,
        log_pf_clip=0.0,
        bucket_validator_version="unvalidated",
        invariants=InvariantFlags(
            session_close_drop_count=0,
            negative_equity_drop_open_count=0,
            infeasible_reason_codes=codes,
        ),
    )


def _make_trade(ts: datetime) -> TradeRecord:
    return TradeRecord(
        entry_time_utc=ts,
        exit_time_utc=ts + timedelta(hours=1),
        pnl_net=10.0,
        session_bucket=SessionBucket.TOKYO,
        business_day_index=0,
        is_session_close_drop=False,
        is_negative_equity_drop_open=False,
    )


def _make_artifact(
    fold_index: int,
    start: datetime,
    *,
    is_feasible: bool = True,
    max_dd: float = 0.1,
    n_trades: int = 2,
) -> FoldCanonicalArtifact:
    points = tuple(
        BarEquityPoint(timestamp_utc=start + timedelta(days=d), equity=100.0 + d)
        for d in range(5)
    )
    trades = tuple(_make_trade(start + timedelta(days=d)) for d in range(n_trades))
    return FoldCanonicalArtifact(
        fold_index=fold_index,
        period_start=points[0].timestamp_utc,
        period_end=points[-1].timestamp_utc,
        canonical_trades=trades,
        canonical_bars=BarEquitySeries(points=points),
        canonical_universe={b: frozenset({fold_index}) for b in SessionBucket},
        cf_result=_make_cf(is_feasible=is_feasible, max_dd=max_dd),
    )


def _five_artifacts(**kw) -> list[FoldCanonicalArtifact]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        _make_artifact(i, base + timedelta(days=10 * i), **kw) for i in range(5)
    ]


class TestPoolingLogic:
    def test_returns_none_when_any_fold_infeasible(self) -> None:
        arts = _five_artifacts()
        arts[2] = _make_artifact(
            2, arts[2].period_start - timedelta(days=0), is_feasible=False
        )
        cf, dd, feasible = build_stage_b_pooled_cf_from_fold_artifacts(
            arts, thresholds=pareto_features.derive_stage_b_thresholds(_LC)
        )
        assert cf is None and dd is None and feasible is False

    def test_raises_on_wrong_fold_count(self) -> None:
        with pytest.raises(ValueError):
            build_stage_b_pooled_cf_from_fold_artifacts(
                _five_artifacts()[:4],
                thresholds=pareto_features.derive_stage_b_thresholds(_LC),
            )

    def test_raises_on_non_chronological_order(self) -> None:
        arts = _five_artifacts()
        arts[1], arts[2] = arts[2], arts[1]  # break ordering, keep fold_index seq
        arts = [
            FoldCanonicalArtifact(
                fold_index=i,
                period_start=a.period_start,
                period_end=a.period_end,
                canonical_trades=a.canonical_trades,
                canonical_bars=a.canonical_bars,
                canonical_universe=a.canonical_universe,
                cf_result=a.cf_result,
            )
            for i, a in enumerate(arts)
        ]
        with pytest.raises(ValueError):
            build_stage_b_pooled_cf_from_fold_artifacts(
                arts, thresholds=pareto_features.derive_stage_b_thresholds(_LC)
            )

    def test_raises_on_boundary_touch_overlap(self) -> None:
        """period_end == next period_start (同一 bar 二重所属) を overlap として弾く."""
        base = datetime(2026, 1, 1, tzinfo=UTC)
        arts = _five_artifacts()
        # fold0 の period_end を fold1 の period_start に一致させる
        touch = arts[1].period_start
        arts[0] = FoldCanonicalArtifact(
            fold_index=0,
            period_start=base - timedelta(days=5),
            period_end=touch,  # == arts[1].period_start
            canonical_trades=arts[0].canonical_trades,
            canonical_bars=arts[0].canonical_bars,
            canonical_universe=arts[0].canonical_universe,
            cf_result=arts[0].cf_result,
        )
        with pytest.raises(ValueError):
            build_stage_b_pooled_cf_from_fold_artifacts(
                arts, thresholds=pareto_features.derive_stage_b_thresholds(_LC)
            )

    def test_pooled_consumes_fold_artifacts_no_refilter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """pooled は fold artifact を直 concat する (period 再フィルタしない)。

        evaluate_canonical_five を捕捉し、 渡される trades 数が per-fold trades の
        総和、 bars 数が per-fold bars の総和であることを確認 (= 落ちも再フィルタもなし)。
        """
        arts = _five_artifacts(n_trades=2)
        captured: dict = {}

        def _fake_eval(trades, bars, thresholds, universe):
            captured["n_trades"] = len(trades)
            captured["n_bars"] = len(bars.points)
            return _make_cf(max_dd=0.05)

        monkeypatch.setattr(pareto_features, "evaluate_canonical_five", _fake_eval)
        cf, _dd, feasible = build_stage_b_pooled_cf_from_fold_artifacts(
            arts, thresholds=pareto_features.derive_stage_b_thresholds(_LC)
        )
        assert feasible is True and cf is not None
        assert captured["n_trades"] == 5 * 2  # 全 fold trades の総和
        assert captured["n_bars"] == 5 * 5  # 全 fold bars の総和

    def test_pooled_dd_is_max_of_per_fold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        dds = [0.1, 0.3, 0.2, 0.05, 0.25]
        arts = [
            _make_artifact(i, base + timedelta(days=10 * i), max_dd=dds[i])
            for i in range(5)
        ]
        monkeypatch.setattr(
            pareto_features, "evaluate_canonical_five",
            lambda *a, **k: _make_cf(),
        )
        _, dd, _ = build_stage_b_pooled_cf_from_fold_artifacts(
            arts, thresholds=pareto_features.derive_stage_b_thresholds(_LC)
        )
        assert dd == max(dds)


class TestTryBuildNoRaise:
    def test_unusable_on_wrong_fold_count(self) -> None:
        lite = try_build_pareto_lite_from_stage_b_fold_artifacts(
            _five_artifacts()[:3], live_criteria=_LC
        )
        assert lite.pareto_axis_usable is False
        assert lite.source_stage is None

    def test_unusable_when_infeasible(self) -> None:
        arts = _five_artifacts()
        arts[0] = _make_artifact(0, arts[0].period_start, is_feasible=False)
        lite = try_build_pareto_lite_from_stage_b_fold_artifacts(
            arts, live_criteria=_LC
        )
        assert lite.pareto_axis_usable is False

    def test_noraise_on_internal_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*a, **k):
            raise RuntimeError("canonical exploded")

        monkeypatch.setattr(pareto_features, "evaluate_canonical_five", _boom)
        # 例外を投げず unusable に落ちる (LOG_ONLY 隔離)
        lite = try_build_pareto_lite_from_stage_b_fold_artifacts(
            _five_artifacts(), live_criteria=_LC
        )
        assert lite.pareto_axis_usable is False
        assert lite.source_stage is None

    def test_usable_sets_source_stage_b_and_finite_axes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            pareto_features, "evaluate_canonical_five",
            lambda *a, **k: _make_cf(max_dd=0.07, net_pnl=61000.0),
        )
        lite = try_build_pareto_lite_from_stage_b_fold_artifacts(
            _five_artifacts(max_dd=0.07), live_criteria=_LC
        )
        assert lite.pareto_axis_usable is True
        assert lite.source_stage == "B"
        assert lite.net_pnl_after_cost == 61000.0
        assert lite.pooled_dd_per_fold_max == 0.07
        assert lite.mission_inf_gap is not None

    def test_usable_with_production_like_live_criteria_missing_win_rate_min(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """production default.yaml は win_rate_min を持たない。

        derive_stage_b_thresholds は必須要求するが、helper が 0.45 fallback を補い
        usable になること (Codex impl-review Round 2 Critical の回帰)。
        """
        prod_lc = {
            "sharpe_min": 1.0,
            "total_pnl_min": 50000.0,
            "max_drawdown_max": 0.2,
            "trade_count_min": 50,
            "trade_count_max": 5000,
            # win_rate_min 無し (= production default.yaml と同形)
        }
        monkeypatch.setattr(
            pareto_features, "evaluate_canonical_five",
            lambda *a, **k: _make_cf(max_dd=0.07, net_pnl=61000.0),
        )
        lite = try_build_pareto_lite_from_stage_b_fold_artifacts(
            _five_artifacts(max_dd=0.07), live_criteria=prod_lc
        )
        assert lite.pareto_axis_usable is True
        assert lite.source_stage == "B"

    def test_negative_pooled_dd_is_unusable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        arts = [
            _make_artifact(i, base + timedelta(days=10 * i), max_dd=-0.5)
            for i in range(5)
        ]
        monkeypatch.setattr(
            pareto_features, "evaluate_canonical_five",
            lambda *a, **k: _make_cf(),
        )
        lite = try_build_pareto_lite_from_stage_b_fold_artifacts(
            arts, live_criteria=_LC
        )
        assert lite.pareto_axis_usable is False


def test_unusable_sentinel_shape() -> None:
    lite = ParetoFeaturesLite.unusable()
    assert lite.pareto_axis_usable is False
    assert lite.source_stage is None
    assert lite.net_pnl_after_cost is None
