"""T047: aux_loader unit tests (CSV → snapshot/aux_series 経路)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.alpha_factory.aux_loader import (
    AuxBundle,
    build_aux_bundle,
    load_aux_series,
    load_dxy_series,
    load_event_calendar,
    load_event_snapshot,
    load_vix_snapshot,
)


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(header + "\n")
        for r in rows:
            f.write(r + "\n")


class TestLoadDxySeries:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_dxy_series(tmp_path) is None

    def test_loads_close_column(self, tmp_path: Path) -> None:
        _write_csv(
            tmp_path / "DXY.csv",
            "date,close",
            ["2026-01-01,100.5", "2026-01-02,101.0", "2026-01-03,102.3"],
        )
        out = load_dxy_series(tmp_path)
        assert out == [100.5, 101.0, 102.3]

    def test_skips_invalid_rows(self, tmp_path: Path) -> None:
        _write_csv(
            tmp_path / "DXY.csv",
            "date,close",
            ["2026-01-01,100.5", "2026-01-02,not_a_number", "2026-01-03,101.0"],
        )
        out = load_dxy_series(tmp_path)
        assert out == [100.5, 101.0]


class TestLoadVixSnapshot:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_vix_snapshot(tmp_path) is None

    def test_loads_with_publication_ts(self, tmp_path: Path) -> None:
        _write_csv(
            tmp_path / "VIX.csv",
            "publication_ts_utc,close",
            [
                "2026-01-01T21:15:00,15.5",
                "2026-01-02T21:15:00,16.2",
            ],
        )
        snap = load_vix_snapshot(tmp_path)
        assert snap is not None
        assert len(snap.observations) == 2
        assert snap.observations[0][1] == pytest.approx(15.5)

    def test_loads_with_date_fallback(self, tmp_path: Path) -> None:
        """publication_ts_utc が無くても date があれば動く."""
        _write_csv(
            tmp_path / "VIX.csv",
            "date,close",
            ["2026-01-01,15.5", "2026-01-02,16.2"],
        )
        snap = load_vix_snapshot(tmp_path)
        assert snap is not None
        assert len(snap.observations) == 2


class TestLoadEventCalendar:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_event_calendar(tmp_path / "events.csv") is None

    def test_loads_events(self, tmp_path: Path) -> None:
        path = tmp_path / "events.csv"
        _write_csv(
            path,
            "event_time_utc,currency,name,impact",
            [
                "2026-01-01T13:30:00,USD,NFP,3",
                "2026-01-02T08:00:00,EUR,ECB,3",
            ],
        )
        cal = load_event_calendar(path)
        assert cal is not None
        assert len(cal.events) == 2
        assert cal.events[0].currency == "USD"
        assert cal.events[1].name == "ECB"

    def test_skips_invalid_rows(self, tmp_path: Path) -> None:
        path = tmp_path / "events.csv"
        _write_csv(
            path,
            "event_time_utc,currency,name,impact",
            [
                "invalid,USD,X,3",
                "2026-01-01T13:30:00,USD,NFP,3",
                "2026-01-02T08:00:00,EUR,ECB,not_int",
            ],
        )
        cal = load_event_calendar(path)
        assert cal is not None
        assert len(cal.events) == 1


class TestLoadEventSnapshot:
    def test_returns_none_when_no_events(self, tmp_path: Path) -> None:
        snap = load_event_snapshot(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            calendar_path=tmp_path / "missing.csv",
        )
        assert snap is None

    def test_returns_snapshot_with_strict_flag(self, tmp_path: Path) -> None:
        path = tmp_path / "events.csv"
        _write_csv(
            path,
            "event_time_utc,currency,name,impact",
            ["2026-01-01T13:30:00,USD,NFP,3"],
        )
        snap = load_event_snapshot(
            as_of=datetime(2026, 1, 5, tzinfo=UTC),
            as_of_strict=True,
            calendar_path=path,
        )
        assert snap is not None
        assert snap.as_of_strict is True

    def test_naive_as_of_normalized_to_utc(self, tmp_path: Path) -> None:
        """naive datetime は UTC に正規化される (snapshot 側 tz-aware 強制)."""
        path = tmp_path / "events.csv"
        _write_csv(
            path,
            "event_time_utc,currency,name,impact",
            ["2026-01-01T13:30:00,USD,NFP,3"],
        )
        snap = load_event_snapshot(
            as_of=datetime(2026, 1, 5),  # naive
            calendar_path=path,
        )
        assert snap is not None
        assert snap.as_of.tzinfo is not None


class TestLoadAuxSeries:
    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_aux_series(tmp_path) == {}

    def test_loads_macro_keys(self, tmp_path: Path) -> None:
        _write_csv(tmp_path / "DXY.csv", "date,close", ["2026-01-01,100.0"])
        _write_csv(tmp_path / "copper.csv", "date,close", ["2026-01-01,4.0"])
        out = load_aux_series(tmp_path)
        assert "macro.dxy" in out
        assert "macro.copper" in out
        assert out["macro.dxy"] == [100.0]
        assert out["macro.copper"] == [4.0]


class TestBuildAuxBundle:
    def test_all_missing_returns_empty_bundle(self, tmp_path: Path) -> None:
        bundle = build_aux_bundle(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            fred_data_dir=tmp_path / "fred",
            calendar_path=tmp_path / "events.csv",
        )
        assert isinstance(bundle, AuxBundle)
        assert bundle.event_snapshot is None
        assert bundle.vix_snapshot is None
        assert bundle.aux_series == {}
        assert bundle.aux_pair_bars == {}

    def test_full_bundle(self, tmp_path: Path) -> None:
        fred = tmp_path / "fred"
        _write_csv(fred / "DXY.csv", "date,close", ["2026-01-01,100.0"])
        _write_csv(
            fred / "VIX.csv",
            "date,close",
            ["2026-01-01,15.0"],
        )
        cal_path = tmp_path / "events.csv"
        _write_csv(
            cal_path,
            "event_time_utc,currency,name,impact",
            ["2026-01-01T13:30:00,USD,NFP,3"],
        )
        bundle = build_aux_bundle(
            as_of=datetime(2026, 1, 5, tzinfo=UTC),
            as_of_strict=True,
            fred_data_dir=fred,
            calendar_path=cal_path,
        )
        assert bundle.event_snapshot is not None
        assert bundle.event_snapshot.as_of_strict is True
        assert bundle.vix_snapshot is not None
        assert "macro.dxy" in bundle.aux_series
