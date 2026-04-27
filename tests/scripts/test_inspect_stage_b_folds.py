"""T045: inspect_stage_b_folds CLI テスト (helper の単体検証)."""

from __future__ import annotations

import json
from typing import Any

from scripts.alpha_factory.inspect_stage_b_folds import _pick_individuals


def _row(
    *,
    name: str,
    fitness_pen: float | None = 0.05,
    stage_b_pass: bool = True,
    has_genome: bool = True,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "individual_name": name,
        "fitness_pen": fitness_pen,
        "stage_b_pass": stage_b_pass,
    }
    if has_genome:
        r["genome_json"] = json.dumps({"name": name, "clauses": []})
    return r


class TestPickIndividuals:
    def test_filters_b_pass_only(self) -> None:
        rows = [
            _row(name="a", stage_b_pass=True, fitness_pen=0.1),
            _row(name="b", stage_b_pass=False, fitness_pen=0.2),
            _row(name="c", stage_b_pass=True, fitness_pen=0.05),
        ]
        picked = _pick_individuals(rows, top=10, only_b_pass=True)
        names = [r["individual_name"] for r in picked]
        assert "b" not in names
        assert names == ["a", "c"]  # fitness_pen 降順

    def test_include_non_b_pass(self) -> None:
        rows = [
            _row(name="a", stage_b_pass=True, fitness_pen=0.1),
            _row(name="b", stage_b_pass=False, fitness_pen=0.5),
        ]
        picked = _pick_individuals(rows, top=10, only_b_pass=False)
        names = [r["individual_name"] for r in picked]
        assert names == ["b", "a"]  # fitness_pen 降順 (b が高い)

    def test_top_n_limits_count(self) -> None:
        rows = [
            _row(name=f"i{i}", fitness_pen=float(i), stage_b_pass=True)
            for i in range(10)
        ]
        picked = _pick_individuals(rows, top=3, only_b_pass=True)
        assert len(picked) == 3
        assert [r["individual_name"] for r in picked] == ["i9", "i8", "i7"]

    def test_skips_rows_without_genome_json(self) -> None:
        rows = [
            _row(name="a", has_genome=True),
            _row(name="b", has_genome=False),
        ]
        picked = _pick_individuals(rows, top=10, only_b_pass=True)
        assert [r["individual_name"] for r in picked] == ["a"]

    def test_handles_none_fitness_pen(self) -> None:
        rows = [
            _row(name="a", fitness_pen=None),
            _row(name="b", fitness_pen=0.1),
        ]
        picked = _pick_individuals(rows, top=10, only_b_pass=True)
        # None は -inf に正規化されるので b が先
        assert picked[0]["individual_name"] == "b"
