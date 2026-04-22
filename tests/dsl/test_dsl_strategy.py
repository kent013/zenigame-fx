"""T007: 旧フラット DslStrategy のテスト。Clause 構造への置き換えにより一時 skip。

後続 TODO `clause-backtest-integration` で Clause 版 DslStrategy 統合テストを整備する。
新 DslStrategy の単体ヒステリシス・time_stop・session close テストは `test_strategy.py` にある。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="T007: legacy flat DslStrategy tests; awaiting clause-backtest-integration TODO"
)


def test_legacy_flat_dsl_strategy_placeholder() -> None:
    """Visible skip marker for pytest report."""
    raise AssertionError("placeholder — should be skipped")
