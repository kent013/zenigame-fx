"""Cross-run aggregation for batch GA.

zenigame-fx-batch-ga skill の Phase 2 で呼び出される。
{batch_dir}/metrics/*.json を集約し、{batch_dir}/comparison_report.md と
{batch_dir}/batch_summary.json を生成する。

モード:
1. 単一バッチ集計  : --batch-dir DIR
2. Before/After 比較: --baseline DIR --treatment DIR

集計対象（数値が None / NaN の Run は除外して n を別計算）:
- best_fitness, best_sharpe, best_trade_count, best_total_pnl, best_max_drawdown_pct
- stage_a_pass, stage_b_pass, stage_c_pass
- best_b_sharpe, best_c_sharpe
- live_criteria_all_pass rate
- graduation_count
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

logger = logging.getLogger(__name__)


METRIC_PATHS: list[tuple[str, tuple[str, ...]]] = [
    ("best_fitness", ("best", "fitness")),
    ("best_sharpe", ("best", "sharpe")),
    ("best_trade_count", ("best", "trade_count")),
    ("best_total_pnl", ("best", "total_pnl")),
    ("best_max_drawdown_pct", ("best", "max_drawdown_pct")),
    ("best_win_rate", ("best", "win_rate")),
    ("best_profit_factor", ("best", "profit_factor")),
    ("stage_a_pass", ("stage_pass", "stage_a_pass")),
    ("stage_b_pass", ("stage_pass", "stage_b_pass")),
    ("stage_c_pass", ("stage_pass", "stage_c_pass")),
    ("archive_total", ("stage_pass", "total")),
    ("best_b_sharpe", ("best_b_sharpe",)),
    ("best_c_sharpe", ("best_c_sharpe",)),
    ("graduation_count", ("graduation_count",)),
]


def _dig(d: Any, keys: tuple[str, ...]) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _to_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _stats(values: list[float | None]) -> dict[str, Any]:
    nums = [v for v in values if v is not None]
    if not nums:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    return {
        "n": len(nums),
        "mean": mean(nums),
        "median": median(nums),
        "std": pstdev(nums) if len(nums) > 1 else 0.0,
        "min": min(nums),
        "max": max(nums),
    }


def _load_metrics(batch_dir: Path) -> list[dict[str, Any]]:
    metrics_dir = batch_dir / "metrics"
    if not metrics_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(metrics_dir.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("metrics load failed (%s): %s", p, exc)
    return out


def _aggregate(metrics_list: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"n_runs": len(metrics_list), "metrics": {}}
    for label, path in METRIC_PATHS:
        vals = [_to_float(_dig(m, path)) for m in metrics_list]
        summary["metrics"][label] = _stats(vals)

    pass_flags = [m.get("live_criteria_all_pass") for m in metrics_list]
    n_known = sum(1 for v in pass_flags if v is not None)
    n_pass = sum(1 for v in pass_flags if v is True)
    summary["live_criteria_all_pass"] = {
        "n_known": n_known,
        "n_pass": n_pass,
        "rate": (n_pass / n_known) if n_known > 0 else None,
    }
    return summary


def _format_value(v: Any, ndigits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✅" if v else "❌"
    if isinstance(v, float):
        return f"{v:.{ndigits}f}"
    return str(v)


def _stats_row(label: str, s: dict[str, Any]) -> str:
    return (
        f"| {label} | {s['n']} | "
        f"{_format_value(s['mean'])} | {_format_value(s['median'])} | "
        f"{_format_value(s['std'])} | {_format_value(s['min'])} | "
        f"{_format_value(s['max'])} |"
    )


def _render_single(batch_id: str, label: str | None, summary: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    lines = [
        f"# Batch comparison — `{batch_id}`",
        "",
    ]
    if label:
        lines.append(f"**Label**: {label}")
    lines += [
        f"**n_runs**: {summary['n_runs']}",
        "",
        "## クロスラン集計",
        "",
        "| metric | n | mean | median | std | min | max |",
        "|--------|--:|-----:|-------:|----:|----:|----:|",
    ]
    for label_name, _ in METRIC_PATHS:
        lines.append(_stats_row(label_name, summary["metrics"][label_name]))
    lines.append("")

    lc = summary["live_criteria_all_pass"]
    lines += [
        "## 使命判定",
        "",
        f"- all_pass: {lc['n_pass']}/{lc['n_known']} "
        f"(rate={_format_value(lc['rate'])})",
        "",
    ]

    lines += [
        "## Per-run 一覧",
        "",
        "| run_number | run_id | best_fit | best_sharpe | A | B | C | best_b_sharpe | best_c_sharpe | all_pass |",
        "|----------:|--------|---------:|------------:|--:|--:|--:|--------------:|--------------:|:--------:|",
    ]
    for m in runs:
        sp = m.get("stage_pass") or {}
        best = m.get("best") or {}
        lines.append(
            f"| {m.get('run_number', '—')} | `{m.get('run_id', '—')}` | "
            f"{_format_value(_to_float(best.get('fitness')))} | "
            f"{_format_value(_to_float(best.get('sharpe')))} | "
            f"{sp.get('stage_a_pass', '—')} | {sp.get('stage_b_pass', '—')} | "
            f"{sp.get('stage_c_pass', '—')} | "
            f"{_format_value(_to_float(m.get('best_b_sharpe')))} | "
            f"{_format_value(_to_float(m.get('best_c_sharpe')))} | "
            f"{_format_value(m.get('live_criteria_all_pass'))} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _render_compare(
    baseline_id: str, treatment_id: str,
    baseline: dict[str, Any], treatment: dict[str, Any],
) -> str:
    lines = [
        f"# Batch before/after comparison",
        "",
        f"- baseline: `{baseline_id}` (n={baseline['n_runs']})",
        f"- treatment: `{treatment_id}` (n={treatment['n_runs']})",
        "",
        "## 平均値の差分",
        "",
        "| metric | baseline mean | treatment mean | Δmean | baseline median | treatment median | Δmedian |",
        "|--------|--------------:|---------------:|------:|----------------:|-----------------:|--------:|",
    ]
    for label_name, _ in METRIC_PATHS:
        b = baseline["metrics"][label_name]
        t = treatment["metrics"][label_name]
        d_mean = (
            t["mean"] - b["mean"] if b["mean"] is not None and t["mean"] is not None else None
        )
        d_median = (
            t["median"] - b["median"] if b["median"] is not None and t["median"] is not None else None
        )
        lines.append(
            f"| {label_name} | {_format_value(b['mean'])} | {_format_value(t['mean'])} | "
            f"{_format_value(d_mean)} | {_format_value(b['median'])} | "
            f"{_format_value(t['median'])} | {_format_value(d_median)} |"
        )
    lines.append("")

    lb = baseline["live_criteria_all_pass"]
    lt = treatment["live_criteria_all_pass"]
    lines += [
        "## 使命判定 rate",
        "",
        f"- baseline: {lb['n_pass']}/{lb['n_known']} (rate={_format_value(lb['rate'])})",
        f"- treatment: {lt['n_pass']}/{lt['n_known']} (rate={_format_value(lt['rate'])})",
        "",
        "> 統計的有意性検定は本スクリプトでは実施しない。"
        "n=10 程度では分布形状の確認 (min/max/std) を併読すること。",
        "",
    ]
    return "\n".join(lines) + "\n"


def _read_label(batch_dir: Path) -> str | None:
    state = batch_dir / "batch_state.json"
    if not state.exists():
        return None
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("label")
    except Exception:
        return None


def _run_single(batch_dir: Path) -> int:
    runs = _load_metrics(batch_dir)
    if not runs:
        print(f"[error] no metrics under {batch_dir / 'metrics'}", file=sys.stderr)
        return 1
    summary = _aggregate(runs)
    label = _read_label(batch_dir)
    batch_id = batch_dir.name

    summary_out = {"batch_id": batch_id, "label": label, **summary}
    (batch_dir / "batch_summary.json").write_text(
        json.dumps(summary_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = _render_single(batch_id, label, summary, runs)
    (batch_dir / "comparison_report.md").write_text(md, encoding="utf-8")
    print(f"[done] {batch_dir / 'batch_summary.json'}")
    print(f"[done] {batch_dir / 'comparison_report.md'}")
    return 0


def _run_compare(baseline: Path, treatment: Path, output: Path | None) -> int:
    b_runs = _load_metrics(baseline)
    t_runs = _load_metrics(treatment)
    if not b_runs:
        print(f"[error] no baseline metrics under {baseline / 'metrics'}", file=sys.stderr)
        return 1
    if not t_runs:
        print(f"[error] no treatment metrics under {treatment / 'metrics'}", file=sys.stderr)
        return 1
    b_sum = _aggregate(b_runs)
    t_sum = _aggregate(t_runs)
    md = _render_compare(baseline.name, treatment.name, b_sum, t_sum)
    if output is None:
        print(md)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(md, encoding="utf-8")
        print(f"[done] {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    p = argparse.ArgumentParser(description="Aggregate batch GA metrics across runs")
    p.add_argument("--batch-dir", type=Path, default=None,
                   help="単一バッチ集計モード: {batch_dir}/metrics/ を集約")
    p.add_argument("--baseline", type=Path, default=None,
                   help="Before/After 比較モード: baseline batch dir")
    p.add_argument("--treatment", type=Path, default=None,
                   help="Before/After 比較モード: treatment batch dir")
    p.add_argument("--output", type=Path, default=None,
                   help="比較モードの Markdown 出力先 (省略時は stdout)")
    args = p.parse_args(argv)

    if args.batch_dir is not None and (args.baseline or args.treatment):
        print("[error] --batch-dir と --baseline/--treatment は併用不可", file=sys.stderr)
        return 2
    if args.batch_dir is not None:
        return _run_single(args.batch_dir)
    if args.baseline is not None and args.treatment is not None:
        return _run_compare(args.baseline, args.treatment, args.output)

    print("[error] --batch-dir または (--baseline + --treatment) を指定してください", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
