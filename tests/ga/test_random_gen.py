"""T007: 旧フラット Genome 前提の random_gen テスト。Clause 対応は後続 TODO で。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="T007: legacy flat random_gen; awaiting clause-ga-operators TODO"
)


def test_legacy_random_gen_placeholder() -> None:
    """Visible skip marker for pytest report."""
    raise AssertionError("placeholder — should be skipped")
