"""T007: 旧 Expr serialize (expr_to_dict/from_dict) のテスト。本 TODO で serialize 側が
Clause 構造に置き換わり、旧 API が削除されたため一時 skip。

新 Genome の serialize round-trip テストは `test_genome_clause.py` の
`test_genome_roundtrip_through_dict` にある。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="T007: legacy Expr serialize tests; new clause round-trip in test_genome_clause.py"
)


def test_legacy_expr_serialize_placeholder() -> None:
    """Visible skip marker for pytest report."""
    raise AssertionError("placeholder — should be skipped")
