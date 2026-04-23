"""``src/alpha_factory/walk_forward.py`` のテスト (T014)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from src.alpha_factory.walk_forward import make_wf_folds
from src.domain.price import Ohlc, PriceBar


def _bar(dt: datetime, minute: int = 0) -> PriceBar:
    o = Ohlc(
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
    )
    return PriceBar(
        pair_name="EUR_JPY",
        bar_time=dt + timedelta(minutes=minute),
        bid=o,
        ask=o,
        volume=1,
        complete=True,
    )


def _continuous_bars(n_days: int, bars_per_day: int = 1) -> list[PriceBar]:
    """連続 n_days 日 × bars_per_day bar の bars。"""
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    bars: list[PriceBar] = []
    for d in range(n_days):
        day_start = base + timedelta(days=d)
        for m in range(bars_per_day):
            bars.append(_bar(day_start, minute=m))
    return bars


# ---------------------------------------------------------------------------
# 引数バリデーション
# ---------------------------------------------------------------------------


def test_make_wf_folds_invalid_train_days() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        make_wf_folds(_continuous_bars(10), train_days=0, test_days=2, step_days=1, embargo_days=0)


def test_make_wf_folds_invalid_test_days() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        make_wf_folds(_continuous_bars(10), train_days=2, test_days=0, step_days=1, embargo_days=0)


def test_make_wf_folds_invalid_step_days() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        make_wf_folds(_continuous_bars(10), train_days=2, test_days=2, step_days=0, embargo_days=0)


def test_make_wf_folds_invalid_embargo_days() -> None:
    with pytest.raises(ValueError, match="embargo_days must be >= 0"):
        make_wf_folds(_continuous_bars(10), train_days=2, test_days=2, step_days=1, embargo_days=-1)


# ---------------------------------------------------------------------------
# 空 / 短すぎ
# ---------------------------------------------------------------------------


def test_make_wf_folds_empty_input() -> None:
    assert make_wf_folds([], train_days=2, test_days=2, step_days=1, embargo_days=0) == []


def test_make_wf_folds_too_short() -> None:
    """fold_len > n_unique_dates のとき空 list."""
    bars = _continuous_bars(50)
    folds = make_wf_folds(bars, train_days=120, test_days=20, step_days=20, embargo_days=1)
    assert folds == []


def test_make_wf_folds_exactly_one_fold() -> None:
    """fold_len == n_days のとき 1 fold."""
    bars = _continuous_bars(141)  # 120 + 1 + 20
    folds = make_wf_folds(bars, train_days=120, test_days=20, step_days=20, embargo_days=1)
    assert len(folds) == 1


# ---------------------------------------------------------------------------
# 通常動作
# ---------------------------------------------------------------------------


def test_make_wf_folds_simple_count_and_sizes() -> None:
    """200 日連続 bars、train=120/test=20/step=20/embargo=1 → 3 fold。

    fold k: train_start_idx=20k, train_end_idx=20k+120, embargo_end=20k+121,
    test_end=20k+141 <= 200 → k in {0,1,2,3} だが k=3 は test_end=141+60=… 計算:
    expected fold count = floor((200 - 120 - 1 - 20) / 20) + 1 = floor(59/20) + 1 = 2 + 1 = 3
    """
    bars = _continuous_bars(200)
    folds = make_wf_folds(bars, train_days=120, test_days=20, step_days=20, embargo_days=1)
    assert len(folds) == 3
    for train_bars, test_bars in folds:
        train_dates = {b.bar_time.date() for b in train_bars}
        test_dates = {b.bar_time.date() for b in test_bars}
        assert len(train_dates) == 120
        assert len(test_dates) == 20
        # train と test は重ならない
        assert train_dates.isdisjoint(test_dates)


def test_make_wf_folds_embargo_zero() -> None:
    """embargo=0 → test_start_idx == train_end_idx_exclusive.

    test の最初の date が train の最後の date の翌観測日になることを確認。
    """
    bars = _continuous_bars(100)
    folds = make_wf_folds(bars, train_days=50, test_days=20, step_days=10, embargo_days=0)
    assert folds, "should generate at least one fold"
    train_bars, test_bars = folds[0]
    train_last_date = max(b.bar_time.date() for b in train_bars)
    test_first_date = min(b.bar_time.date() for b in test_bars)
    # test_start_idx = train_end_idx_exclusive (== train_start + train_days)
    assert test_first_date == train_last_date + timedelta(days=1)


def test_make_wf_folds_embargo_5() -> None:
    """embargo=5 → train と test の間に 5 観測日 gap."""
    bars = _continuous_bars(100)
    folds = make_wf_folds(bars, train_days=50, test_days=20, step_days=10, embargo_days=5)
    assert folds
    train_bars, test_bars = folds[0]
    train_dates = sorted({b.bar_time.date() for b in train_bars})
    test_dates = sorted({b.bar_time.date() for b in test_bars})
    # 5 日 gap → test_first - train_last == 6 日
    assert (test_dates[0] - train_dates[-1]).days == 6


# ---------------------------------------------------------------------------
# 観測日 (祝日・gap)
# ---------------------------------------------------------------------------


def test_make_wf_folds_holiday_gap() -> None:
    """暦日 130 日に対し観測日 100 日（30 日抜け）。観測日 index で fold される."""
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    bars: list[PriceBar] = []
    skipped = 0
    for d in range(130):
        if d % 4 == 3 and skipped < 30:  # 4 日に 1 日休 (30 日まで)
            skipped += 1
            continue
        bars.append(_bar(base + timedelta(days=d)))
    n_unique = len({b.bar_time.date() for b in bars})
    assert n_unique == 100
    folds = make_wf_folds(bars, train_days=50, test_days=20, step_days=10, embargo_days=1)
    # n_days=100, fold_len=71 → fold 数 = floor((100-71)/10) + 1 = 3
    assert len(folds) == 3
    for train_bars, test_bars in folds:
        assert len({b.bar_time.date() for b in train_bars}) == 50
        assert len({b.bar_time.date() for b in test_bars}) == 20


def test_make_wf_folds_multiple_bars_per_day() -> None:
    """1 日複数 bar が train または test に正しく振り分けられる."""
    bars = _continuous_bars(40, bars_per_day=5)
    folds = make_wf_folds(bars, train_days=20, test_days=10, step_days=5, embargo_days=1)
    assert folds
    for train_bars, test_bars in folds:
        train_dates = {b.bar_time.date() for b in train_bars}
        test_dates = {b.bar_time.date() for b in test_bars}
        assert len(train_dates) == 20
        assert len(test_dates) == 10
        # bars_per_day=5 → train_bars は 100 個
        assert len(train_bars) == 20 * 5
        assert len(test_bars) == 10 * 5


# ---------------------------------------------------------------------------
# 入力順序
# ---------------------------------------------------------------------------


def test_make_wf_folds_non_ascending_bars() -> None:
    bars = _continuous_bars(20)
    bars[0], bars[1] = bars[1], bars[0]
    with pytest.raises(ValueError, match="ascending"):
        make_wf_folds(bars, train_days=5, test_days=3, step_days=2, embargo_days=1)


def test_make_wf_folds_dates_are_chronological() -> None:
    """fold 内の train_dates / test_dates が時系列昇順."""
    bars = _continuous_bars(100)
    folds = make_wf_folds(bars, train_days=50, test_days=20, step_days=10, embargo_days=1)
    for train_bars, test_bars in folds:
        train_dates = [b.bar_time.date() for b in train_bars]
        test_dates = [b.bar_time.date() for b in test_bars]
        assert train_dates == sorted(train_dates)
        assert test_dates == sorted(test_dates)
        # train の最後 < test の最初
        assert max(train_dates) < min(test_dates)


def test_make_wf_folds_step_progression() -> None:
    """連続 fold の train_start_idx が step_days 分進む."""
    bars = _continuous_bars(100)
    folds = make_wf_folds(bars, train_days=50, test_days=20, step_days=5, embargo_days=1)
    assert len(folds) >= 2
    train_starts: list[date] = []
    for train_bars, _ in folds:
        train_starts.append(min(b.bar_time.date() for b in train_bars))
    diffs = [(train_starts[i + 1] - train_starts[i]).days for i in range(len(train_starts) - 1)]
    assert all(d == 5 for d in diffs)
