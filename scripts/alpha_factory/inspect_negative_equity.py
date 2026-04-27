"""T049 Phase 1: negative equity warnings 調査 CLI.

Run log (`*.log`) から `trade_return.invalid_equity_at_entry` warning を抽出し
集計する。Run 19 で 10k+ 件発生した負 equity 状態の物理的説明を切り分け、
ストップアウト logic 整備の必要性を判定する根拠を取得する。

Phase 1 scope: ログ抽出 + 集計のみ。stop-out logic 追加は調査結果を踏まえ
別 TODO で起票する。

Usage:
    uv run python scripts/alpha_factory/inspect_negative_equity.py \\
        --log .cache/alpha_factory/runs/run_*.log

詳細: devnotes/20260427-0100-investigate-negative-equity/
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# warning フォーマット例 (1 行に折りたたみ):
# `trade_return.invalid_equity_at_entry equity_at_entry=-3083770.000000 trade_position_id=14107`
WARNING_RE = re.compile(
    r"trade_return\.invalid_equity_at_entry\s+"
    r"equity_at_entry=(?P<equity>[-\d.]+)\s+"
    r"trade_position_id=(?P<pid>\d+)"
)


def parse_log(lines: Iterable[str]) -> list[dict[str, Any]]:
    """log から negative equity warning を抽出する."""
    out: list[dict[str, Any]] = []
    for line in lines:
        m = WARNING_RE.search(line)
        if m:
            try:
                out.append(
                    {
                        "equity": float(m.group("equity")),
                        "position_id": int(m.group("pid")),
                    }
                )
            except (ValueError, TypeError):
                continue
    return out


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """抽出した warning 集計 (件数 / equity 分布 / position 重複)."""
    if not records:
        return {
            "n_warnings": 0,
            "n_unique_positions": 0,
            "equity_min": None,
            "equity_max": None,
            "equity_median": None,
        }
    equities = [r["equity"] for r in records]
    pids = {r["position_id"] for r in records}
    sorted_eq = sorted(equities)
    return {
        "n_warnings": len(records),
        "n_unique_positions": len(pids),
        "equity_min": min(equities),
        "equity_max": max(equities),
        "equity_median": sorted_eq[len(sorted_eq) // 2],
    }


def _format_summary(summary: dict[str, Any]) -> str:
    lines = ["# Negative Equity Warning 集計", ""]
    lines.append(f"- warning 件数: {summary['n_warnings']}")
    lines.append(f"- ユニーク position_id 数: {summary['n_unique_positions']}")
    if summary["n_warnings"] > 0:
        lines.append(f"- equity_at_entry min: {summary['equity_min']:,.2f}")
        lines.append(f"- equity_at_entry max: {summary['equity_max']:,.2f}")
        lines.append(f"- equity_at_entry median: {summary['equity_median']:,.2f}")
    lines.append("")
    if summary["n_warnings"] > 0:
        lines.append(
            "→ 上記 warning は backtest engine の equity 計算で entry 時点の "
            "equity が negative になった件数。typical 原因: leverage 25x + "
            "units 10000 で同時保有過多 → margin 完全壊滅。production "
            "GA で再発防止には MockBroker / backtest engine への stop-out "
            "logic 追加が必要 (別 TODO)。"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="T049 Phase 1: negative equity log inspection",
    )
    parser.add_argument(
        "--log", type=Path, required=True, help="Run log file path"
    )
    args = parser.parse_args(argv)

    if not args.log.exists():
        print(f"[error] log not found: {args.log}", file=sys.stderr)
        return 2

    with args.log.open(encoding="utf-8", errors="replace") as f:
        records = parse_log(f)

    summary = summarize(records)
    print(_format_summary(summary))
    return 0 if summary["n_warnings"] == 0 else 10


if __name__ == "__main__":
    sys.exit(main())
