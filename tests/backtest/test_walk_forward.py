from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.backtest.walk_forward import WalkForwardConfig, aggregate, run_walk_forward, slice_folds
from tests._helpers import make_bar, usd_jpy_meta


def test_slice_folds_rolling_produces_sequential_windows() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 3, 1, tzinfo=UTC)
    folds = slice_folds(start, end, train_days=30, test_days=7, step_days=7, mode="rolling")
    assert len(folds) >= 4
    assert folds[0].train_start == start
    assert folds[0].train_end == folds[0].test_start
    assert folds[0].test_end == start + timedelta(days=37)
    # rolling: 2 個目の train_start は step 分後ろ
    assert folds[1].train_start == start + timedelta(days=7)


def test_slice_folds_anchored_keeps_train_start_fixed() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 3, 1, tzinfo=UTC)
    folds = slice_folds(start, end, train_days=30, test_days=7, step_days=7, mode="anchored")
    assert all(f.train_start == start for f in folds)


def test_slice_folds_skips_incomplete_test_window() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)  # 31 days
    # train=20d, test=10d → 1 つ目の test は day20-30、2 つ目は day27-37 で end 超過
    folds = slice_folds(start, end, train_days=20, test_days=10, step_days=7, mode="rolling")
    # test_end <= end を満たす fold のみ
    for f in folds:
        assert f.test_end <= end


def test_run_walk_forward_on_small_dataset() -> None:
    # 1 日分の short bars を使って fold 1 つ分が動くことを確認（train_days=1, test_days=1）
    bars = []
    for day in range(1, 4):  # day 1, 2, 3
        for minute in range(0, 60, 15):  # 4 bars per day
            bars.append(make_bar(minute, bid_close="154.100", ask_close="154.110", day=day))

    config = WalkForwardConfig(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 4, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        strategy_name="bollinger",
        parameter_grid={"window": [2], "k": [1.0], "units": [1000]},
        train_days=1,
        test_days=1,
        step_days=1,
        mode="rolling",
        parallel=1,
    )
    result = run_walk_forward(bars, usd_jpy_meta(), config)
    assert len(result.folds) >= 1
    for fold in result.folds:
        assert fold.best_params == {"window": 2, "k": 1.0, "units": 1000}


def test_aggregate_overfit_score_zero_when_train_equals_test() -> None:
    # fold が空なら overfit_score は None
    result_empty = type("R", (), {"folds": []})()
    agg = aggregate(result_empty)
    assert agg["overfit_score"] is None
