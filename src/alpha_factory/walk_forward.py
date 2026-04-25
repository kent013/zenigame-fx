"""Walk-Forward fold 分割 (T014)。

observed-day index ベースで (train_bars, test_bars) tuple のリストを返す。
暦日加算は使わず、実際に観測された UTC date のインデックスのみで切る。
祝日 / 週末 / 休場 gap に対して robust。

仕様根拠:
- docs/alpha_factory/stage-gates.md
- devnotes/20260423-1540-stage-gate-implementation/detailed-design.md §2.4
- López de Prado, M. (2018). Advances in Financial Machine Learning, Ch.7.
"""

from __future__ import annotations

from datetime import date

from src.domain.price import PriceBar

__all__ = ["make_wf_folds", "n_unique_dates", "wf_min_unique_dates"]


def wf_min_unique_dates(
    train_days: int, embargo_days: int, test_days: int
) -> int:
    """``make_wf_folds`` の sufficiency 最小観測日数 (1 fold ぶん).

    ``make_wf_folds`` は ``train_days + embargo_days + test_days > n_unique_dates``
    のとき空 list を返す。本関数はその閾値を上位レイヤから参照するための
    SSOT 共有 helper (T035)。``make_wf_folds`` 内部の ``fold_len`` 計算も
    本関数を使うため二重化を避ける。
    """
    return int(train_days) + int(embargo_days) + int(test_days)


def n_unique_dates(bars: list[PriceBar]) -> int:
    """``bars`` の bar_time から UTC date を抽出した unique 日数を返す (T035)."""
    seen: set[date] = set()
    for b in bars:
        seen.add(b.bar_time.date())
    return len(seen)


def make_wf_folds(
    bars: list[PriceBar],
    train_days: int,
    test_days: int,
    step_days: int,
    embargo_days: int,
) -> list[tuple[list[PriceBar], list[PriceBar]]]:
    """observed-day index ベースで (train_bars, test_bars) のリストを返す。

    各 fold は連続 ``train_days`` 観測日 + ``embargo_days`` 観測日隔離 +
    ``test_days`` 観測日テストの構造を持つ。``step_days`` ごとに前進。

    Args:
        bars: 評価対象 bars (bar_time 昇順前提、関数内 assert)。
        train_days: train 区間の観測日数 (>= 1)。
        test_days:  test 区間の観測日数 (>= 1)。
        step_days:  fold 間の観測日数 step (>= 1)。
        embargo_days: train と test の間の隔離観測日数 (>= 0)。

    Returns:
        各 fold の (train_bars, test_bars) tuple のリスト。
        以下のケースで空 list を返す（ValueError は raise しない）:
        - bars が空
        - ``train_days + embargo_days + test_days > n_unique_dates``

    Raises:
        ValueError:
            - ``train_days``, ``test_days``, ``step_days`` が 1 未満
            - ``embargo_days`` が 0 未満
            - bars が ``bar_time`` 昇順でない

    Notes:
        embargo 区間の bars はどちらにも含めない（leak 防止、
        López de Prado 2018 Ch.7）。
    """
    if train_days < 1 or test_days < 1 or step_days < 1:
        raise ValueError(
            f"train_days/test_days/step_days must be >= 1: "
            f"got train={train_days}, test={test_days}, step={step_days}"
        )
    if embargo_days < 0:
        raise ValueError(f"embargo_days must be >= 0: got {embargo_days}")

    if not bars:
        return []

    # 時系列昇順 assert
    for i in range(1, len(bars)):
        if bars[i].bar_time < bars[i - 1].bar_time:
            raise ValueError(
                "bars must be ascending by bar_time "
                f"(violation at index {i}: {bars[i - 1].bar_time} -> {bars[i].bar_time})"
            )

    # ユニーク UTC date 列 (出現順 = 時系列昇順)
    seen: set[date] = set()
    sorted_dates: list[date] = []
    for b in bars:
        d = b.bar_time.date()
        if d not in seen:
            seen.add(d)
            sorted_dates.append(d)

    n_days = len(sorted_dates)
    fold_len = wf_min_unique_dates(train_days, embargo_days, test_days)
    if fold_len > n_days:
        return []

    # 各 date → bars 列を一度だけ index
    bars_by_date: dict[date, list[PriceBar]] = {}
    for b in bars:
        bars_by_date.setdefault(b.bar_time.date(), []).append(b)

    folds: list[tuple[list[PriceBar], list[PriceBar]]] = []
    k = 0
    while True:
        train_start = step_days * k
        train_end_excl = train_start + train_days
        test_start = train_end_excl + embargo_days
        test_end_excl = test_start + test_days
        if test_end_excl > n_days:
            break
        train_dates = sorted_dates[train_start:train_end_excl]
        test_dates = sorted_dates[test_start:test_end_excl]
        train_bars: list[PriceBar] = []
        for d in train_dates:
            train_bars.extend(bars_by_date[d])
        test_bars: list[PriceBar] = []
        for d in test_dates:
            test_bars.extend(bars_by_date[d])
        folds.append((train_bars, test_bars))
        k += 1
    return folds
