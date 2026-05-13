"""cycle 23 C3: 過去 RUN の archive Parquet を annualized sharpe で再評価し、
live_criteria.all_pass を満たす mission 候補数を集計する retroactive audit script。

cycle 23 C1 修正 (= _check_live_criteria を annualize 経路に統一) の効果検証用。
過去 19 RUN (Run 57-75) を再評価することで、 trade-level vs annualized 単位不整合
bug 由来で過小評価されていた mission 達成個体数を verify する。

設計判断: 過去 RUN の retroactive 整合性のため、 各 run の `summary.json` 内に
保存された `live_criteria` 閾値を使用する (= 現行 yaml ではない、 Codex Round 1
Warning 反映)。

出力:
- markdown: reports/audit-live-criteria-retroactive.md
- カラム: run_id / run_number / stage_c_pass / mission_candidates / top annualized sharpe

実行例:
    uv run python scripts/alpha_factory/audit_live_criteria_retroactive.py \
      --run-ids run_20260507_011702 run_20260513_120619 \
      --output reports/audit-live-criteria-retroactive.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.alpha_factory.stage_gate import _annualize_trade_sharpe

# script location based repo root
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _row_passes_live_criteria(
    row: dict[str, Any],
    *,
    sharpe_min: float,
    pnl_min: float,
    dd_max_pct: float,
    tc_min: int,
    tc_max: int,
    holdout_days: int,
    stage_a_window_days: int,
) -> tuple[bool, float | None]:
    """1 行が live_criteria all_pass か判定し、 annualized sharpe を返す。

    sharpe は trade_sharpe_stage_c 第一優先、 fallback で trade_sharpe_raw。
    Codex Round 1 Warning 反映: raw fallback は stage_a_window_days で annualize。
    """
    stage_c_val = _safe_float(row.get("trade_sharpe_stage_c"))
    if stage_c_val is not None:
        sharpe_trade = stage_c_val
        win = holdout_days
    else:
        raw_val = _safe_float(row.get("trade_sharpe_raw"))
        if raw_val is None:
            return (False, None)
        sharpe_trade = raw_val
        win = stage_a_window_days
    tc = int(row.get("trade_count", 0) or 0)
    sa = _annualize_trade_sharpe(sharpe_trade, tc, win)
    if sa is None or sa < sharpe_min:
        return (False, sa)
    pnl = _safe_float(row.get("total_pnl")) or 0.0
    if pnl < pnl_min:
        return (False, sa)
    dd = _safe_float(row.get("max_drawdown_pct")) or 0.0
    if dd > dd_max_pct:
        return (False, sa)
    if not (tc_min <= tc <= tc_max):
        return (False, sa)
    return (True, sa)


def audit_run(
    run_id: str,
    *,
    archive_dir: Path,
    summary_dir: Path,
) -> dict[str, Any]:
    """1 つの run_id について retroactive audit を実行。"""
    parquet_path = archive_dir / f"genomes_{run_id}.parquet"
    if not parquet_path.exists():
        return {"run_id": run_id, "error": "archive_not_found"}

    # summary.json から run_number と live_criteria 閾値を取得
    summary_path: Path | None = None
    for d in summary_dir.glob("run-*"):
        s = d / "summary.json"
        if not s.exists():
            continue
        try:
            data = json.loads(s.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("run_id") == run_id:
            summary_path = s
            break

    if summary_path is None:
        return {"run_id": run_id, "error": "summary_not_found"}
    summary = json.loads(summary_path.read_text())
    run_number = summary.get("run_number")

    lc_summary = summary.get("live_criteria") or {}
    lc_checks = lc_summary.get("checks") or {}
    sharpe_min = float(lc_checks.get("sharpe", {}).get("threshold", 1.0))
    pnl_min = float(lc_checks.get("total_pnl", {}).get("threshold", 50000.0))
    dd_max_pct = float(
        lc_checks.get("max_drawdown_pct", {}).get("threshold", 20.0)
    )
    tc_min = int(lc_checks.get("trade_count", {}).get("threshold_min", 50))
    tc_max = int(lc_checks.get("trade_count", {}).get("threshold_max", 5000))

    sg_cfg = summary.get("stage_gate_config") or {}
    holdout_days = int(sg_cfg.get("stage_c_holdout_days", 60))
    stage_a_window_days = int(sg_cfg.get("stage_a_window_days", 60))

    df = pq.read_table(parquet_path).to_pandas()
    sc_pass_count = int(df["stage_c_pass"].fillna(False).astype(bool).sum())
    sc_df = df[df["stage_c_pass"].fillna(False).astype(bool)]

    mission_candidates = 0
    examples: list[dict[str, Any]] = []
    for _, row in sc_df.iterrows():
        passed, sa = _row_passes_live_criteria(
            row.to_dict(),
            sharpe_min=sharpe_min,
            pnl_min=pnl_min,
            dd_max_pct=dd_max_pct,
            tc_min=tc_min,
            tc_max=tc_max,
            holdout_days=holdout_days,
            stage_a_window_days=stage_a_window_days,
        )
        if passed:
            mission_candidates += 1
            examples.append({
                "name": row.get("individual_name"),
                "annualized_sharpe": sa,
                "trade_count": int(row.get("trade_count", 0) or 0),
                "total_pnl": float(row.get("total_pnl", 0.0) or 0.0),
            })

    top_examples = sorted(
        examples,
        key=lambda x: -(x["annualized_sharpe"] or 0.0),
    )[:5]

    return {
        "run_id": run_id,
        "run_number": run_number,
        "stage_c_pass": sc_pass_count,
        "mission_candidates": mission_candidates,
        "top_examples": top_examples,
        "thresholds": {
            "sharpe_min": sharpe_min,
            "pnl_min": pnl_min,
            "dd_max_pct": dd_max_pct,
            "tc_min": tc_min,
            "tc_max": tc_max,
            "holdout_days": holdout_days,
            "stage_a_window_days": stage_a_window_days,
        },
    }


def _format_markdown(results: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    lines.append(
        "# Live Criteria Retroactive Audit (cycle 23 C1 修正検証)"
    )
    lines.append("")
    lines.append(
        "本 audit は archive Parquet を再評価し、 cycle 23 C1 修正 "
        "(`_check_live_criteria` の annualize 経路統一) 後の真の mission "
        "達成個体数を集計する。"
    )
    lines.append("")
    lines.append(
        "**閾値の出所**: 各 run の `summary.json` 内に保存された `live_criteria` "
        "閾値を使用 (現行 yaml ではない)。 retroactive contamination 防止のため。"
    )
    lines.append("")
    lines.append("## サマリー")
    lines.append("")
    lines.append(
        "| run_id | run_number | stage_c_pass | mission_candidates | top annualized sharpe |"
    )
    lines.append(
        "|--------|-----------:|-------------:|-------------------:|----------------------:|"
    )
    for r in results:
        if "error" in r:
            lines.append(
                f"| {r['run_id']} | — | — | — | (error: {r['error']}) |"
            )
            continue
        top_sa = (
            f"{r['top_examples'][0]['annualized_sharpe']:.4f}"
            if r["top_examples"]
            else "—"
        )
        lines.append(
            f"| {r['run_id']} | {r['run_number']} | "
            f"{r['stage_c_pass']} | {r['mission_candidates']} | {top_sa} |"
        )

    lines.append("")
    lines.append("## Top examples (annualized sharpe 降順、 run ごと最大 5 件)")
    lines.append("")
    for r in results:
        if r.get("error") or not r.get("top_examples"):
            continue
        lines.append(f"### {r['run_id']} (run-{r['run_number']})")
        lines.append("")
        lines.append("| name | annualized sharpe | trade_count | total_pnl |")
        lines.append("|------|------------------:|------------:|----------:|")
        for ex in r["top_examples"]:
            sa = ex["annualized_sharpe"]
            sa_str = f"{sa:.4f}" if sa is not None else "—"
            lines.append(
                f"| {ex['name']} | {sa_str} | {ex['trade_count']} | "
                f"{ex['total_pnl']:.1f} |"
            )
        lines.append("")
    return lines


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--run-ids", nargs="+", required=True,
        help="audit 対象の run_id 列",
    )
    p.add_argument(
        "--output", type=Path,
        default=REPO_ROOT / "reports" / "audit-live-criteria-retroactive.md",
    )
    p.add_argument(
        "--archive-dir", type=Path,
        default=REPO_ROOT / ".cache" / "alpha_factory" / "runs",
    )
    p.add_argument(
        "--summary-dir", type=Path,
        default=REPO_ROOT / "reports" / "run-reports",
    )
    args = p.parse_args()

    results: list[dict[str, Any]] = []
    for run_id in args.run_ids:
        r = audit_run(
            run_id,
            archive_dir=args.archive_dir,
            summary_dir=args.summary_dir,
        )
        results.append(r)
        if "error" in r:
            print(f"{run_id}: ERROR {r['error']}")
        else:
            print(
                f"{run_id} (run-{r['run_number']}): "
                f"stage_c_pass={r['stage_c_pass']}, "
                f"mission_candidates={r['mission_candidates']}"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(_format_markdown(results)) + "\n")
    print(f"[done] report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
