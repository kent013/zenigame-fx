"""tests for IndividualCacheEntry.fold_robust (cycle 4 improve-cycle)."""

from __future__ import annotations

import math

from scripts.alpha_factory.run_ga import IndividualCacheEntry


def test_selection_score_9_tuple_default_fold_robust_false():
    """default で fold_robust=False、 selection_score 9 要素、 8 要素目 = 0."""
    entry = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
    )
    score = entry.selection_score
    assert len(score) == 10  # cycle 5: 10-tuple
    assert score[8] == 0  # fold_robust default False (位置 9)
    assert score[9] == 0.5  # fitness_pen (位置 10)


def test_selection_score_9_tuple_fold_robust_true():
    """fold_robust=True で 9 要素目が 1 (cycle 5 で位置がシフト)."""
    entry = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=True,
    )
    score = entry.selection_score
    assert len(score) == 10  # cycle 5: 10-tuple
    assert score[8] == 1  # fold_robust 位置 9
    assert score[9] == 0.5  # fitness_pen


def test_selection_score_stage_b_pass_and_feasible_top_priority():
    """cycle 5: stage_b_pass AND feasible が要素 3 に昇格、 stage_b_pass のみより上位."""
    sb_and_feasible = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.0,
        stage_a_pass=True,
        stage_b_pass=True,
        stage_c_pass=False,
        feasible=True,  # entry_count >= 50
    )
    sb_only_no_feasible = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,  # higher
        stage_a_pass=True,
        stage_b_pass=True,
        stage_c_pass=False,
        feasible=False,  # entry_count < 50
    )
    # cycle 5: stage_b_pass_and_feasible=1 が要素 3 で勝つ (要素 1 feasible は 0 でも要素 3 で先勝)
    # 注: feasible=False で 要素 1 が 0、 sb_and_feasible が 要素 1 = 1 で勝つ
    assert sb_and_feasible.selection_score > sb_only_no_feasible.selection_score


def test_selection_score_v3_3_top_3_elements_when_full_pass():
    """cycle 5: feasible + stage_b_pass + AND の 3 要素が揃った個体が最優先."""
    full_pass = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.1,
        stage_a_pass=True,
        stage_b_pass=True,
        stage_c_pass=False,
        feasible=True,
    )
    score = full_pass.selection_score
    assert score[0] == 1  # feasible
    assert score[2] == 1  # stage_b_pass_and_feasible
    assert score[3] == 1  # stage_b_pass


def test_selection_score_lexicographic_fold_robust_priority():
    """同じ fitness_pen でも fold_robust=1 が fold_robust=0 より上位 (lex 比較)."""
    fold_robust_high = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.3,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=True,
    )
    fold_robust_low = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,  # fitness_pen は high
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=False,
    )
    # fold_robust が上位なので、 fitness_pen が低くても fold_robust=1 が勝つ
    assert fold_robust_high.selection_score > fold_robust_low.selection_score


def test_selection_score_fitness_pen_tiebreak_when_fold_robust_equal():
    """同 fold_robust なら fitness_pen で tiebreak."""
    high_fp = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=True,
    )
    low_fp = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.3,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=True,
    )
    assert high_fp.selection_score > low_fp.selection_score


def test_selection_score_stage_b_pass_above_fold_robust():
    """stage_b_pass=True (3 要素目) は fold_robust より上位."""
    stage_b_pass_no_fold = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.0,
        stage_a_pass=True,
        stage_b_pass=True,
        stage_c_pass=False,
        fold_robust=False,
    )
    stage_b_fail_high_fold = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=True,
    )
    # stage_b_pass=True が常に勝つ (lex 順序の上位)
    assert stage_b_pass_no_fold.selection_score > stage_b_fail_high_fold.selection_score


def test_selection_score_legacy_4tuple_unchanged():
    """legacy_selection_score (fallback 用) は 4 要素のまま、 fold_robust 含まない."""
    entry = IndividualCacheEntry(
        generation=0,
        fitness_pen=0.5,
        stage_a_pass=True,
        stage_b_pass=False,
        stage_c_pass=False,
        fold_robust=True,  # 設定しても legacy には影響しない
    )
    legacy = entry._legacy_selection_score
    assert len(legacy) == 4  # 4-tuple 不変
    assert legacy == (0, 0, 1, 0.5)  # (C_pass, B_pass, A_pass, fitness_pen)


def test_selection_score_finite_guard_fitness_pen_inf():
    """fitness_pen が -inf でも 10 要素 tuple、 10 要素目が -inf (cycle 5)."""
    entry = IndividualCacheEntry(
        generation=0,
        fitness_pen=-math.inf,
        stage_a_pass=False,
        stage_b_pass=False,
        stage_c_pass=False,
    )
    score = entry.selection_score
    assert len(score) == 10  # cycle 5: 10-tuple
    assert score[9] == -math.inf  # fitness_pen 位置 10


# ---------------------------------------------------------------------------
# T091 cycle_phase1 段階 2: _coerce_optional_int helper + trade_count_full_dataset
# ---------------------------------------------------------------------------


class TestT091CoerceOptionalInt:
    """T091 段階 2: _coerce_optional_int helper の入力正規化。"""

    def test_returns_none_for_none(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(None) is None

    def test_returns_none_for_nan(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(float("nan")) is None

    def test_returns_none_for_inf(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(float("inf")) is None
        assert _coerce_optional_int(float("-inf")) is None

    def test_returns_none_for_list_dict_tuple(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int([1, 2]) is None
        assert _coerce_optional_int((1,)) is None
        assert _coerce_optional_int({"k": 1}) is None
        assert _coerce_optional_int("100") is None  # has __len__

    def test_returns_none_for_python_bool(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(True) is None
        assert _coerce_optional_int(False) is None

    def test_returns_none_for_numpy_bool(self) -> None:
        import numpy as np

        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(np.bool_(True)) is None
        assert _coerce_optional_int(np.bool_(False)) is None

    def test_returns_none_for_non_integer_float(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(100.5) is None
        assert _coerce_optional_int(0.1) is None

    def test_returns_none_for_negative(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(-1) is None
        assert _coerce_optional_int(-100.0) is None

    def test_returns_int_for_positive_int(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(0) == 0
        assert _coerce_optional_int(100) == 100
        assert _coerce_optional_int(2**30) == 2**30

    def test_returns_int_for_integer_valued_float(self) -> None:
        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(100.0) == 100
        assert _coerce_optional_int(0.0) == 0

    def test_returns_int_for_numpy_int64(self) -> None:
        import numpy as np

        from scripts.alpha_factory.run_ga import _coerce_optional_int

        assert _coerce_optional_int(np.int64(100)) == 100


class TestT091IndividualCacheEntryFullDataset:
    """T091 段階 2: IndividualCacheEntry に trade_count_full_dataset field 追加。"""

    def test_default_none(self) -> None:
        entry = IndividualCacheEntry(
            generation=0,
            fitness_pen=0.5,
            stage_a_pass=True,
            stage_b_pass=False,
            stage_c_pass=False,
        )
        assert entry.trade_count_full_dataset is None

    def test_explicit_value(self) -> None:
        entry = IndividualCacheEntry(
            generation=0,
            fitness_pen=0.5,
            stage_a_pass=True,
            stage_b_pass=False,
            stage_c_pass=False,
            trade_count_full_dataset=200,
        )
        assert entry.trade_count_full_dataset == 200
