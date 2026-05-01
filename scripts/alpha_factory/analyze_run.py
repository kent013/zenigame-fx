"""Alpha Factory Run の簡易分析。

対象 Run の summary.json / history.json を読み、直前 Run との差分を踏まえた
分析 Markdown を指定 tmp_dir に書き出す。

出力:
- {tmp_dir}/analysis-claude.md  — 観察事実と解釈

Alpha Factory の正式な analyze-run はより広範な Codex 合議と深層分析を行うが、
zenigame-fx ではまず Claude 単独の簡易分析のみを実装する。
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.alpha_factory.schema_contract import (
    assert_epoch_id_present_for_display,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"


def _load_run(run_number: int) -> dict[str, Any] | None:
    run_dir = RUN_REPORTS_DIR / f"run-{run_number}"
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return None
    return {
        "dir": run_dir,
        "summary": json.loads(summary_path.read_text(encoding="utf-8")),
        "history": json.loads((run_dir / "history.json").read_text(encoding="utf-8"))
        if (run_dir / "history.json").exists()
        else [],
    }


def _fitness_progression(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"plateau": False, "generations": 0}
    fitness = [Decimal(h["best_fitness"]) for h in history]
    plateau = len(fitness) >= 3 and fitness[-1] == fitness[-3]
    first, last = fitness[0], fitness[-1]
    return {
        "first": str(first),
        "last": str(last),
        "delta": str(last - first),
        "plateau": plateau,
        "generations": len(fitness),
    }


def _criteria_status(summary: dict[str, Any]) -> list[str]:
    lc = summary.get("live_criteria", {}).get("checks", {})
    if not lc:
        return ["- live_criteria 判定データなし"]
    lines = []
    for name, chk in lc.items():
        mark = "✅" if chk.get("pass") else "❌"
        if name == "trade_count":
            lines.append(
                f"- {mark} {name}: {chk['value']} (許容 {chk['threshold_min']}〜{chk['threshold_max']})"
            )
        else:
            lines.append(
                f"- {mark} {name}: {chk['value']} / 閾値 {chk.get('threshold', '?')}"
            )
    return lines


def _compare(prev: dict[str, Any] | None, curr: dict[str, Any]) -> list[str]:
    if prev is None:
        return ["- 前回 Run なし — 初回サイクル"]
    prev_fit = Decimal(prev["summary"]["best"]["fitness"])
    curr_fit = Decimal(curr["summary"]["best"]["fitness"])
    diff = curr_fit - prev_fit
    arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
    lines = [
        f"- best_fitness: {prev_fit} {arrow} {curr_fit} (Δ={diff})",
    ]
    prev_tc = prev["summary"]["best"]["metrics"].get("trade_count", 0)
    curr_tc = curr["summary"]["best"]["metrics"].get("trade_count", 0)
    lines.append(f"- trade_count: {prev_tc} → {curr_tc}")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Analyze Alpha Factory FX run")
    p.add_argument("--run-number", type=int, required=True)
    p.add_argument("--tmp-dir", type=Path, required=True)
    args = p.parse_args(argv)

    curr = _load_run(args.run_number)
    if curr is None:
        print(f"[error] run-{args.run_number} not found", file=sys.stderr)
        return 1
    prev = _load_run(args.run_number - 1)

    summary = curr["summary"]
    prog = _fitness_progression(curr["history"])

    lines: list[str] = [
        f"# Run {args.run_number} 分析",
        "",
        f"**run_id**: `{summary['run_id']}`",
        f"**dataset_epoch_id**: `{summary.get('dataset_epoch_id') or '—'}`",
        f"**generated_at**: {summary['generated_at']}",
        "",
        "## 観察事実",
        "",
        "### 使命判定 (live_criteria)",
        "",
        *_criteria_status(summary),
        "",
        "### Best 個体",
        "",
        f"- name: `{summary['best']['name']}`",
        f"- fitness ({summary['ga_config']['fitness_metric']}): {summary['best']['fitness']}",
        f"- trade_count: {summary['best']['metrics'].get('trade_count')}",
        f"- total_pnl: {summary['best']['metrics'].get('total_pnl')}",
        f"- sharpe: {summary['best']['metrics'].get('sharpe')}",
        f"- max_drawdown_pct: {summary['best']['metrics'].get('max_drawdown_pct')}",
        f"- win_rate: {summary['best']['metrics'].get('win_rate')}",
        "",
        "### 収束状況",
        "",
        f"- 世代数: {prog['generations']}",
        f"- 初世代 best_fitness: {prog.get('first')}",
        f"- 最終世代 best_fitness: {prog.get('last')}",
        f"- Δfitness: {prog.get('delta')}",
        f"- plateau: {prog['plateau']}",
        "",
        "### 前回 Run との比較",
        "",
        *_compare(prev, curr),
        "",
        "## 解釈",
        "",
    ]

    if summary["live_criteria"]["all_pass"]:
        lines.append("- **🎯 使命達成**: live_criteria を全て満たす個体が出現。次 Run では閾値を引き上げて次の目標を設定すべき。")
    else:
        failed = [
            name for name, chk in summary["live_criteria"]["checks"].items() if not chk["pass"]
        ]
        lines.append(
            f"- 未達: {', '.join(failed)}。これらが次サイクルの改善ターゲット。"
        )

    if prog["plateau"]:
        lines.append(
            "- plateau 検出: 最終 3 世代で best_fitness が変化なし。mutation_rate 増加 or 初期集団多様化を検討。"
        )

    if prev is not None:
        prev_fit = Decimal(prev["summary"]["best"]["fitness"])
        curr_fit = Decimal(summary["best"]["fitness"])
        if curr_fit < prev_fit:
            lines.append(
                "- 前回より後退。seed のばらつきの可能性もあるので、即座に閾値を弄らず複数 Run の傾向で判断する。"
            )
        elif curr_fit > prev_fit:
            lines.append("- 前回より改善。方向性は正しい可能性。")

    # T058 PR 6: Tier 2 軽量ガード — analysis-claude.md 書込前に
    # dataset_epoch_id 引用漏れ検知 (詳細設計 § 施策 11、 fail-open)
    assert_epoch_id_present_for_display(
        summary, artifact="analyze_run.analysis-claude.md"
    )

    args.tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.tmp_dir / "analysis-claude.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] analysis written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
