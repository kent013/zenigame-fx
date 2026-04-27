"""T049: inspect_negative_equity unit tests."""

from __future__ import annotations

from scripts.alpha_factory.inspect_negative_equity import (
    parse_log,
    summarize,
)

_W = "trade_return.invalid_equity_at_entry"
SAMPLE_LINES = [
    f"2026-04-26 22:03:24 [warning  ] {_W} "
    f"equity_at_entry=-3082830.000000 trade_position_id=14101",
    f"2026-04-26 22:03:24 [warning  ] {_W} "
    f"equity_at_entry=-3082980.000000 trade_position_id=14102",
    f"2026-04-26 22:03:24 [warning  ] {_W} "
    f"equity_at_entry=-3083200.000000 trade_position_id=14103",
    "2026-04-26 22:03:25 [info     ] backtest.finished bars=8",  # 関係ない行
    "garbage line",
]


class TestParseLog:
    def test_extracts_warnings(self) -> None:
        records = parse_log(SAMPLE_LINES)
        assert len(records) == 3
        assert records[0]["equity"] == -3082830.0
        assert records[0]["position_id"] == 14101

    def test_skips_non_matching_lines(self) -> None:
        records = parse_log(["completely irrelevant line", "another one"])
        assert records == []

    def test_skips_malformed_warning(self) -> None:
        bad = [
            "trade_return.invalid_equity_at_entry equity_at_entry=NOT_NUM trade_position_id=1",
        ]
        # NOT_NUM は regex match しないので 0 件
        assert parse_log(bad) == []


class TestSummarize:
    def test_empty_records(self) -> None:
        s = summarize([])
        assert s["n_warnings"] == 0
        assert s["n_unique_positions"] == 0

    def test_unique_positions(self) -> None:
        records = parse_log(SAMPLE_LINES)
        s = summarize(records)
        assert s["n_warnings"] == 3
        assert s["n_unique_positions"] == 3

    def test_equity_min_max_median(self) -> None:
        records = parse_log(SAMPLE_LINES)
        s = summarize(records)
        assert s["equity_min"] == -3083200.0
        assert s["equity_max"] == -3082830.0
        # median of 3 sorted values [-3083200, -3082980, -3082830] → -3082980
        assert s["equity_median"] == -3082980.0

    def test_duplicate_position_ids(self) -> None:
        lines = [
            "trade_return.invalid_equity_at_entry equity_at_entry=-100.0 trade_position_id=1",
            "trade_return.invalid_equity_at_entry equity_at_entry=-200.0 trade_position_id=1",
            "trade_return.invalid_equity_at_entry equity_at_entry=-300.0 trade_position_id=2",
        ]
        records = parse_log(lines)
        s = summarize(records)
        assert s["n_warnings"] == 3
        assert s["n_unique_positions"] == 2  # pid=1 重複あり
