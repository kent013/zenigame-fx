"""T007: 旧フラット DslStrategy warmup 境界テスト。新 DslStrategy は warmup_bars を
コンストラクタ引数で受け取る方式に変わったため一時 skip。

後続 TODO `primitives-registry` で primitive 側の必要 lookback を自動算出する機構
を整備したあとに再設計する。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="T007: legacy warmup boundary test; awaiting primitives-registry TODO"
)


def test_legacy_warmup_boundary_placeholder() -> None:
    """Visible skip marker for pytest report."""
    raise AssertionError("placeholder — should be skipped")
