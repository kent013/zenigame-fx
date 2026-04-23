"""Alpha Factory Run レポート生成。

reports/run-reports/run-{N}/ にある summary.json / history.json / analysis-claude.md を
集約して reports/run-reports/run-{N}.md を生成する（ブロック配下ではなくフラット配置）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate Alpha Factory FX run report")
    p.add_argument("--run-number", type=int, required=True)
    p.add_argument("--analysis-md", type=Path, default=None, help="分析 md のパス（省略時は含めない）")
    args = p.parse_args(argv)

    run_dir = RUN_REPORTS_DIR / f"run-{args.run_number}"
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        print(f"[error] summary not found: {summary_path}", file=sys.stderr)
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = summary["best"]["metrics"]
    lc = summary["live_criteria"]

    lines: list[str] = [
        f"# Run {args.run_number} — {summary['run_id']}",
        "",
        f"**Generated**: {summary['generated_at']}",
        f"**Dataset**: {summary['dataset']['instrument']} "
        f"`{summary['dataset']['start']}` → `{summary['dataset']['end']}` "
        f"(bars={summary['dataset']['bars']})",
        "",
        "## 使命判定",
        "",
        ("🎯 **使命達成**" if lc["all_pass"] else "未達"),
        "",
    ]
    for name, chk in lc["checks"].items():
        mark = "✅" if chk["pass"] else "❌"
        if name == "trade_count":
            lines.append(
                f"- {mark} **{name}**: {chk['value']} (range {chk['threshold_min']}〜{chk['threshold_max']})"
            )
        else:
            lines.append(
                f"- {mark} **{name}**: {chk['value']} / threshold {chk.get('threshold', '?')}"
            )

    lines.extend(
        [
            "",
            "## GA 設定",
            "",
            f"- population_size: {summary['ga_config']['population_size']}",
            f"- generations: {summary['ga_config']['generations']}",
            f"- mutation_rate: {summary['ga_config']['mutation_rate']}",
            f"- crossover_rate: {summary['ga_config']['crossover_rate']}",
            f"- tournament_size: {summary['ga_config']['tournament_size']}",
            f"- elite_count: {summary['ga_config']['elite_count']}",
            f"- max_depth: {summary['ga_config']['max_depth']}",
            f"- fitness_metric: {summary['ga_config']['fitness_metric']}",
            f"- seed: {summary['ga_config']['seed']}",
            "",
            "## Best 個体",
            "",
            f"- name: `{summary['best']['name']}`",
            f"- fitness: **{summary['best']['fitness']}**",
            f"- trade_count: {metrics.get('trade_count')}",
            f"- total_pnl: {metrics.get('total_pnl')}",
            f"- win_rate: {metrics.get('win_rate')}",
            f"- profit_factor: {metrics.get('profit_factor')}",
            f"- sharpe: {metrics.get('sharpe')}",
            f"- sortino: {metrics.get('sortino')}",
            f"- calmar: {metrics.get('calmar')}",
            f"- max_drawdown_pct: {metrics.get('max_drawdown_pct')}",
            f"- final_equity: {metrics.get('final_equity')}",
            "",
            "## 収束履歴",
            "",
        ]
    )

    history_path = run_dir / "history.json"
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
        lines.append("| gen | best_fitness |")
        lines.append("|-----|--------------|")
        for h in history:
            lines.append(f"| {h['generation']} | {h['best_fitness']} |")
        lines.append("")

    if args.analysis_md and args.analysis_md.exists():
        lines.extend(
            [
                "## 分析",
                "",
                args.analysis_md.read_text(encoding="utf-8").strip(),
                "",
            ]
        )

    out_path = RUN_REPORTS_DIR / f"run-{args.run_number}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
