"""T115: cross-pair in-loop selection pressure の selection_key / resolve helper tests。

R88(multi-pair run)で汎化改善を A/B 検証する前に、default OFF bit-exact と ON 時の
tie-break 挿入順序、effective 判定 helper を固める。
"""

from __future__ import annotations

from types import SimpleNamespace

from scripts.alpha_factory.run_ga import (
    IndividualCacheEntry,
    _resolve_cross_pair_selection_pressure,
    _selection_key,
)


def _entry(*, fitness_pen: float, cross_pair_margin: float | None,
           fold_robust: bool = True, stage_b_pass: bool = True,
           stage_c_pass: bool = True) -> IndividualCacheEntry:
    return IndividualCacheEntry(
        generation=1, fitness_pen=fitness_pen,
        stage_a_pass=True, stage_b_pass=stage_b_pass, stage_c_pass=stage_c_pass,
        feasible=True, fold_robust=fold_robust,
        cross_pair_margin=cross_pair_margin,
    )


class TestSelectionKeyBitExact:
    def test_off_returns_current_10_tuple(self) -> None:
        """selection_pressure=False (default) で現行 10-tuple をそのまま返す。"""
        e = _entry(fitness_pen=0.5, cross_pair_margin=0.9)
        key = _selection_key(e, False)
        assert key == e.selection_score
        assert len(key) == 10

    def test_off_invariant_to_cross_pair_margin(self) -> None:
        """OFF では cross_pair_margin の有無に依らず key 完全一致 (bit-exact)。"""
        e_none = _entry(fitness_pen=0.5, cross_pair_margin=None)
        e_pos = _entry(fitness_pen=0.5, cross_pair_margin=5.0)
        assert _selection_key(e_none, False) == _selection_key(e_pos, False)


class TestSelectionKeyPressureOn:
    def test_on_returns_11_tuple_with_tiebreak(self) -> None:
        """ON で fold_robust(8) と fitness_pen(9) の間に tie-break 挿入 → 11-tuple。"""
        e = _entry(fitness_pen=0.5, cross_pair_margin=0.9)
        key = _selection_key(e, False, selection_pressure=True, margin_threshold=0.0)
        assert len(key) == 11
        # index 9 が cross-pair tie-break (margin 0.9 > 0.0 → 1)
        assert key[9] == 1
        # 末尾は fitness_pen、index 8 は fold_robust (元 score と整合)
        assert key[10] == e.selection_score[9]
        assert key[8] == e.selection_score[8]

    def test_on_positive_margin_ranks_above_negative(self) -> None:
        """同 fold_robust なら margin>threshold 個体が低 margin 個体より上位。"""
        hi = _entry(fitness_pen=0.5, cross_pair_margin=0.9)
        lo = _entry(fitness_pen=0.5, cross_pair_margin=-2.0)
        k_hi = _selection_key(hi, False, selection_pressure=True)
        k_lo = _selection_key(lo, False, selection_pressure=True)
        assert k_hi > k_lo  # cross-pair 寄与ある個体が selection 上位

    def test_on_none_margin_treated_as_no_contribution(self) -> None:
        none_e = _entry(fitness_pen=0.9, cross_pair_margin=None)
        k = _selection_key(none_e, False, selection_pressure=True)
        assert k[9] == 0  # None → tie-break 0 (無圧)

    def test_on_threshold_respected(self) -> None:
        e = _entry(fitness_pen=0.5, cross_pair_margin=0.3)
        # threshold 0.5 → 0.3 は不満 → 0
        k = _selection_key(e, False, selection_pressure=True, margin_threshold=0.5)
        assert k[9] == 0


class TestResolveSelectionPressure:
    def _cfg(self, *, sel_pressure: bool, enable: bool, nsga2: bool = False):
        cross_pair = SimpleNamespace(
            selection_pressure=sel_pressure, enable=enable,
        )
        ga = SimpleNamespace(nsga2_selection_enabled=nsga2)
        return SimpleNamespace(cross_pair=cross_pair, ga=ga)

    def test_off_when_pressure_false(self) -> None:
        eff, reason = _resolve_cross_pair_selection_pressure(
            self._cfg(sel_pressure=False, enable=True))
        assert eff is False
        assert "selection_pressure=False" in reason

    def test_off_when_enable_false(self) -> None:
        eff, reason = _resolve_cross_pair_selection_pressure(
            self._cfg(sel_pressure=True, enable=False))
        assert eff is False
        assert "enable=False" in reason

    def test_off_when_nsga2(self) -> None:
        eff, reason = _resolve_cross_pair_selection_pressure(
            self._cfg(sel_pressure=True, enable=True, nsga2=True))
        assert eff is False
        assert "nsga2" in reason

    def test_on_when_all_satisfied(self) -> None:
        eff, reason = _resolve_cross_pair_selection_pressure(
            self._cfg(sel_pressure=True, enable=True))
        assert eff is True
        assert reason == "enabled"
