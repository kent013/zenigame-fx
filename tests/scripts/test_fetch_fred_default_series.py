"""T057 Gate B: scripts/fetch_fred.py DEFAULT_SERIES 拡張の assert tests.

回帰防止: DEFAULT_SERIES に Phase 2 で追加した 5 series が含まれることを確認。
"""

from __future__ import annotations

from scripts.fetch_fred import DEFAULT_SERIES


def test_default_series_includes_existing_baseline() -> None:
    """既存 5 series (VIXCLS / DTWEXBGS / DGS10 / DGS2 / T10YIE) が残ること."""
    expected_existing = {"VIXCLS", "DTWEXBGS", "DGS10", "DGS2", "T10YIE"}
    assert expected_existing.issubset(set(DEFAULT_SERIES))


def test_default_series_includes_phase2_additions() -> None:
    """T057 Phase 2 で追加された 4 series が含まれること.

    GOLDPMGBD228NLBM は FRED で discontinued (2024-) のため除外。
    後継は Yahoo Finance GC=F (scripts/fetch_gold_daily.py 経由)。
    """
    expected_new = {
        "DCOILWTICO",        # P9 WTI
        "PCOPPUSDM",         # P8 Copper
        "PALLFNFINDEXM",     # P8 commodity index
        "SP500",             # P7 SPX500
    }
    assert expected_new.issubset(set(DEFAULT_SERIES))


def test_default_series_excludes_discontinued_gold() -> None:
    """FRED で discontinued された GOLDPMGBD228NLBM は含まれないこと."""
    assert "GOLDPMGBD228NLBM" not in set(DEFAULT_SERIES)


def test_default_series_count_is_nine() -> None:
    """総数 9 であること (FRED 廃止 GOLD を除外したため拡張漏れ早期検出)."""
    assert len(DEFAULT_SERIES) == 9


def test_default_series_no_duplicates() -> None:
    assert len(DEFAULT_SERIES) == len(set(DEFAULT_SERIES))
