"""Per-Run lightweight metrics extraction for batch GA.

zenigame-fx-batch-ga skill の Phase 1-4 で各 Run 完了後に呼び出される。
summary.json + archive Parquet から、クロスラン集計に必要な数値だけを
軽量に切り出して JSON / 短い Markdown レポートに書き出す。

正式な run-{N}.md は generate_run_report.py が生成する。本スクリプトは
batch ベースライン分布計算用の数値抽出専任で、深掘りは行わない。

入力:
- 位置引数 run_id (例: run_20260425_004002) または --run-number N

出力:
- --output PATH  : JSON metrics (compare_batch_runs.py が集計)
- --report PATH  : 短い Markdown サマリー (任意)

run_id 解決は reports/run-reports/run-*/summary.json を走査して
summary["run_id"] と突き合わせる。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"

logger = logging.getLogger(__name__)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _resolve_run_dir(run_id: str | None, run_number: int | None) -> tuple[Path, int, str]:
    """run_id または run_number から (run_dir, run_number, run_id) を返す。"""
    if run_number is not None:
        run_dir = RUN_REPORTS_DIR / f"run-{run_number}"
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"summary not found: {summary_path}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return run_dir, run_number, summary.get("run_id", "")

    if run_id is None:
        raise ValueError("run_id or --run-number must be provided")

    if not RUN_REPORTS_DIR.exists():
        raise FileNotFoundError(f"run-reports dir not found: {RUN_REPORTS_DIR}")

    for entry in sorted(RUN_REPORTS_DIR.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("run-"):
            continue
        summary_path = entry / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summary.get("run_id") == run_id:
            n = summary.get("run_number")
            if not isinstance(n, int):
                try:
                    n = int(entry.name.removeprefix("run-"))
                except ValueError:
                    n = -1
            return entry, n, run_id
    raise FileNotFoundError(f"run_id not found in any summary.json: {run_id}")


def _load_archive(parquet_path_str: str | None) -> list[dict[str, Any]] | None:
    if not parquet_path_str:
        return None
    p = Path(parquet_path_str)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        logger.warning("archive parquet missing: %s", p)
        return None
    try:
        import pyarrow.parquet as pq

        return pq.read_table(p).to_pylist()
    except Exception as exc:
        logger.warning("archive parquet load failed (%s): %s", p, exc)
        return None


def _stage_pass_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "stage_a_pass": sum(1 for r in rows if r.get("stage_a_pass")),
        "stage_b_pass": sum(1 for r in rows if r.get("stage_b_pass")),
        "stage_c_pass": sum(1 for r in rows if r.get("stage_c_pass")),
        "total": len(rows),
    }


def _best_b_sharpe(rows: list[dict[str, Any]]) -> float | None:
    sharpes = [
        _to_float(r.get("sharpe"))
        for r in rows
        if r.get("stage_b_pass")
    ]
    finite = [s for s in sharpes if s is not None]
    return max(finite) if finite else None


def _best_c_sharpe(rows: list[dict[str, Any]]) -> float | None:
    sharpes = [
        _to_float(r.get("sharpe"))
        for r in rows
        if r.get("stage_c_pass")
    ]
    finite = [s for s in sharpes if s is not None]
    return max(finite) if finite else None


def extract(run_id: str | None, run_number: int | None) -> dict[str, Any]:
    run_dir, n, resolved_run_id = _resolve_run_dir(run_id, run_number)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    best = summary.get("best") or {}
    best_metrics = best.get("metrics") or {}
    lc = summary.get("live_criteria") or {}
    ga = summary.get("ga_config") or {}
    ds = summary.get("dataset") or {}

    archive_rows = _load_archive(summary.get("archive_parquet"))
    if archive_rows is None:
        stage_pass = {"stage_a_pass": None, "stage_b_pass": None, "stage_c_pass": None, "total": None}
        best_b_sharpe = None
        best_c_sharpe = None
    else:
        stage_pass = _stage_pass_counts(archive_rows)
        best_b_sharpe = _best_b_sharpe(archive_rows)
        best_c_sharpe = _best_c_sharpe(archive_rows)

    metrics = {
        "run_id": resolved_run_id,
        "run_number": n,
        "generated_at": summary.get("generated_at"),
        "dataset": {
            "instrument": ds.get("instrument"),
            "start": ds.get("start"),
            "end": ds.get("end"),
            "bars": ds.get("bars"),
        },
        "ga_config": {
            "population_size": ga.get("population_size"),
            "generations": ga.get("generations"),
            "mutation_rate": ga.get("mutation_rate"),
            "crossover_rate": ga.get("crossover_rate"),
            "fitness_metric": ga.get("fitness_metric"),
            "seed": ga.get("seed"),
        },
        "best": {
            "name": best.get("name"),
            "generation": best.get("generation"),
            "fitness": _to_float(best.get("fitness")),
            "stage_a_pass": best.get("stage_a_pass"),
            "stage_b_pass": best.get("stage_b_pass"),
            "stage_c_pass": best.get("stage_c_pass"),
            "sharpe": _to_float(best_metrics.get("sharpe")),
            "trade_count": best_metrics.get("trade_count"),
            "total_pnl": _to_float(best_metrics.get("total_pnl")),
            "max_drawdown_pct": _to_float(best_metrics.get("max_drawdown_pct")),
            "win_rate": _to_float(best_metrics.get("win_rate")),
            "profit_factor": _to_float(best_metrics.get("profit_factor")),
        },
        "stage_pass": stage_pass,
        "best_b_sharpe": best_b_sharpe,
        "best_c_sharpe": best_c_sharpe,
        "live_criteria_all_pass": bool(lc.get("all_pass")) if lc else None,
        "live_criteria_failed": [
            name for name, chk in (lc.get("checks") or {}).items()
            if isinstance(chk, dict) and not chk.get("pass")
        ],
        "graduation_count": summary.get("graduation_count"),
        "archive_parquet": summary.get("archive_parquet"),
        "archive_loaded": archive_rows is not None,
    }
    return metrics


def _format_value(v: Any, ndigits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✅" if v else "❌"
    if isinstance(v, float):
        return f"{v:.{ndigits}f}"
    return str(v)


def render_markdown(m: dict[str, Any]) -> str:
    best = m["best"]
    sp = m["stage_pass"]
    lines = [
        f"# Batch metrics — Run {m['run_number']} ({m['run_id']})",
        "",
        f"**Generated**: {m.get('generated_at', '—')}",
        f"**Dataset**: {m['dataset'].get('instrument', '—')} "
        f"`{m['dataset'].get('start', '—')}` → `{m['dataset'].get('end', '—')}` "
        f"(bars={m['dataset'].get('bars', '—')})",
        "",
        "## Best 個体",
        "",
        f"- name: `{best.get('name', '—')}` (gen {best.get('generation', '—')})",
        f"- fitness: {_format_value(best.get('fitness'))}",
        f"- sharpe: {_format_value(best.get('sharpe'))}",
        f"- trade_count: {best.get('trade_count', '—')}",
        f"- total_pnl: {_format_value(best.get('total_pnl'), 2)}",
        f"- max_drawdown_pct: {_format_value(best.get('max_drawdown_pct'))}",
        f"- A/B/C: {_format_value(best.get('stage_a_pass'))}/"
        f"{_format_value(best.get('stage_b_pass'))}/"
        f"{_format_value(best.get('stage_c_pass'))}",
        "",
        "## Stage 通過数 (archive)",
        "",
        f"- total: {sp.get('total') if sp.get('total') is not None else '—'}",
        f"- A: {sp.get('stage_a_pass') if sp.get('stage_a_pass') is not None else '—'}",
        f"- B: {sp.get('stage_b_pass') if sp.get('stage_b_pass') is not None else '—'}",
        f"- C: {sp.get('stage_c_pass') if sp.get('stage_c_pass') is not None else '—'}",
        f"- best_b_sharpe: {_format_value(m.get('best_b_sharpe'))}",
        f"- best_c_sharpe: {_format_value(m.get('best_c_sharpe'))}",
        "",
        "## 使命判定",
        "",
        f"- all_pass: {_format_value(m.get('live_criteria_all_pass'))}",
        f"- failed: {', '.join(m.get('live_criteria_failed') or []) or '—'}",
        f"- graduation_count: {m.get('graduation_count', '—')}",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    p = argparse.ArgumentParser(description="Extract per-run batch metrics (lightweight)")
    p.add_argument("run_id", nargs="?", default=None,
                   help="run_id (e.g. run_20260425_004002). 省略時は --run-number 必須")
    p.add_argument("--run-number", type=int, default=None,
                   help="run_id の代わりに run-{N} 番号で指定")
    p.add_argument("--output", type=Path, required=True,
                   help="metrics JSON 出力先")
    p.add_argument("--report", type=Path, default=None,
                   help="軽量 Markdown レポート出力先 (省略可)")
    args = p.parse_args(argv)

    try:
        metrics = extract(args.run_id, args.run_number)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[done] metrics written to {args.output}")

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(metrics), encoding="utf-8")
        print(f"[done] report written to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
