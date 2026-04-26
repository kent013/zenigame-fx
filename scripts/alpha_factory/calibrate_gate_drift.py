"""T040: calibrate-gate drift monitor CLI.

直近 N Run の calibrate-gate decision を ``reports/calibrate-gate/history.jsonl``
から読み、Markdown テーブル + drift 警告を stdout に出力する。

判断主体は人間。本機構は記録・集計のみ (C3 collider bias 回避)。

Usage:
    uv run python scripts/alpha_factory/calibrate_gate_drift.py --last 5
    uv run python scripts/alpha_factory/calibrate_gate_drift.py --last 10 \\
        --history reports/calibrate-gate/history.jsonl

Exit codes:
    0  drift なし (アラート 0 件)
    10 drift あり (1 件以上のアラート発火 = warning)
    2  invalid arg
    3  history 不在
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.alpha_factory.calibrate_gate_history import (  # noqa: E402
    DEFAULT_HISTORY_PATH,
    DriftAnalysis,
    HistoryRecord,
    compute_drift,
    read_history,
)

EXIT_OK = 0
EXIT_INVALID_ARG = 2
EXIT_NO_HISTORY = 3
EXIT_DRIFT_DETECTED = 10


def _format_table(records: list[HistoryRecord]) -> str:
    """Markdown テーブルで直近 N record を整形."""
    if not records:
        return "(no records)"
    lines = [
        "| run_id | decision | prev_t | new_t | actual | target | gap | clamped |",
        "|--------|---------|-------|------|--------|--------|-----|---------|",
    ]
    for r in records:
        gap = r.actual_pass_rate - r.target_pass_rate
        clamp = "✓" if r.clamped_by_floor_or_ceiling else ""
        lines.append(
            f"| {r.run_id} | {r.decision} | "
            f"{r.prev_threshold:.4f} | {r.new_threshold:.4f} | "
            f"{r.actual_pass_rate:.3f} | {r.target_pass_rate:.3f} | "
            f"{gap:+.3f} | {clamp} |"
        )
    return "\n".join(lines)


def _format_alerts(analysis: DriftAnalysis, last_n: int) -> str:
    """drift アラート行を整形."""
    a = analysis.alerts
    lines = [
        "Alerts:",
        f"- monotone tighten: {analysis.n_tighten}/{last_n} "
        f"{'(ALERT)' if a.monotone_tighten else ''}",
        f"- monotone loosen: {analysis.n_loosen}/{last_n} "
        f"{'(ALERT)' if a.monotone_loosen else ''}",
        f"- threshold clamp: {analysis.n_clamped_floor_ceiling}/{last_n} "
        f"{'(ALERT)' if a.threshold_clamp else ''}",
        f"- pass_rate band excess (max |gap|={analysis.max_abs_gap:.3f}) "
        f"{'(ALERT)' if a.pass_rate_band_excess else ''}",
    ]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="T040: calibrate-gate threshold drift monitor",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=5,
        help="末尾 N record を集計対象とする (default: 5)",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=REPO_ROOT / DEFAULT_HISTORY_PATH,
        help="history JSONL path (default: reports/calibrate-gate/history.jsonl)",
    )
    parser.add_argument(
        "--monotone-threshold",
        type=int,
        default=4,
        help="N record 中 K 回以上 tighten/loosen でアラート (default: 4)",
    )
    parser.add_argument(
        "--clamp-threshold",
        type=int,
        default=3,
        help="N record 中 clamp が K 回以上でアラート (default: 3)",
    )
    parser.add_argument(
        "--band-multiplier",
        type=float,
        default=2.0,
        help="|actual-target| > band_multiplier * tol でアラート (default: 2.0)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.last < 1:
        print(
            f"[error] --last must be >= 1: got {args.last}",
            file=sys.stderr,
        )
        return EXIT_INVALID_ARG
    if not args.history.exists():
        print(
            f"[error] history file not found: {args.history}",
            file=sys.stderr,
        )
        return EXIT_NO_HISTORY

    records = read_history(args.history, last_n=args.last)
    if not records:
        print("(history is empty)")
        return EXIT_OK

    analysis = compute_drift(
        records,
        monotone_threshold=args.monotone_threshold,
        clamp_threshold=args.clamp_threshold,
        band_multiplier=args.band_multiplier,
    )
    last_n = len(records)
    print(f"## Calibrate Gate Drift (last {last_n} runs)")
    print()
    print(_format_table(records))
    print()
    print(_format_alerts(analysis, last_n))
    print()
    return EXIT_DRIFT_DETECTED if analysis.alerts.any_alert else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
