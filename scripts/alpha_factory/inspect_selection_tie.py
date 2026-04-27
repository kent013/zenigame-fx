"""T050: selection_score tie drift / 多様性測定 CLI.

archive Parquet から世代ごとの:
- 同 fitness_pen 集団のサイズ分布
- primitive 利用頻度の Herfindahl-Hirschman Index (HHI)
- elite として retain された個体の重複度
を出力し、winner-take-all / tie drift を quantitative に観察する。

Usage:
    uv run python scripts/alpha_factory/inspect_selection_tie.py \\
        --parquet .cache/alpha_factory/runs/genomes_run_*.parquet

詳細: devnotes/20260427-0100-investigate-selection-tie-drift/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_archive_rows(parquet_path: Path) -> list[dict[str, Any]]:
    return list(pq.read_table(parquet_path).to_pylist())


def compute_hhi(counts: Iterable[int]) -> float:
    """Herfindahl-Hirschman Index = sum(share^2)。

    範囲 [1/N, 1]。N = unique items 数。1.0 = 1 種に完全集中、1/N = 完全分散。
    空入力 0.0。
    """
    counts_list = [c for c in counts if c > 0]
    total = sum(counts_list)
    if total == 0:
        return 0.0
    return sum((c / total) ** 2 for c in counts_list)


def primitive_usage_per_generation(
    rows: list[dict[str, Any]],
) -> dict[int, Counter]:
    """generation → primitive name の利用頻度 Counter."""
    by_gen: dict[int, Counter] = defaultdict(Counter)
    for r in rows:
        gen = int(r.get("generation", 0))
        gj = r.get("genome_json")
        if not gj:
            continue
        try:
            g = json.loads(gj)
        except (TypeError, ValueError):
            continue
        for clause in g.get("clauses", []) or []:
            for sig in clause.get("directional", []) or []:
                if sig.get("name"):
                    by_gen[gen][sig["name"]] += 1
            for sig in clause.get("local_gate", []) or []:
                if sig.get("name"):
                    by_gen[gen][sig["name"]] += 1
    return by_gen


def fitness_pen_tie_ratio_per_generation(
    rows: list[dict[str, Any]],
) -> dict[int, float]:
    """generation ごとの「同 fitness_pen 重複比率」 = 1 - unique/total."""
    by_gen: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        gen = int(r.get("generation", 0))
        fp = r.get("fitness_pen")
        if fp is not None:
            by_gen[gen].append(float(fp))
    out: dict[int, float] = {}
    for gen, fps in by_gen.items():
        if not fps:
            out[gen] = 0.0
            continue
        # 浮動小数点 strict 同値で集計 (Run report の typical 状況)
        unique = len(set(fps))
        total = len(fps)
        tie_ratio = 1.0 - (unique / total)
        out[gen] = tie_ratio
    return out


def _format_report(
    rows: list[dict[str, Any]],
    *,
    parquet_path: Path,
) -> str:
    by_gen = primitive_usage_per_generation(rows)
    tie_per_gen = fitness_pen_tie_ratio_per_generation(rows)
    if not by_gen:
        return "(no genome data)"

    lines = [f"# Selection Tie / Diversity Inspection — {parquet_path.name}", ""]
    lines.append(
        "| gen | n_individuals | n_unique_primitives | hhi | tie_ratio | top primitive (share) |"
    )
    lines.append(
        "|----:|--------------:|-------------------:|----:|----------:|----------------------|"
    )
    for gen in sorted(by_gen.keys()):
        cnt = by_gen[gen]
        n_ind = sum(1 for r in rows if int(r.get("generation", -1)) == gen)
        n_unique = len(cnt)
        hhi = compute_hhi(cnt.values())
        total = sum(cnt.values())
        top_name, top_count = (
            cnt.most_common(1)[0] if cnt else ("-", 0)
        )
        top_share = top_count / total if total > 0 else 0.0
        tie = tie_per_gen.get(gen, 0.0)
        lines.append(
            f"| {gen} | {n_ind} | {n_unique} | {hhi:.4f} | {tie:.3f} | "
            f"{top_name} ({top_share:.1%}) |"
        )
    lines.append("")
    lines.append(
        "> HHI 範囲: 1/N (完全分散) 〜 1.0 (1 primitive に完全集中)。"
        "tie_ratio = 1 - unique_fitness/total。両方が高い = winner-take-all 兆候。"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="T050: selection tie drift / HHI inspection",
    )
    parser.add_argument("--parquet", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.parquet.exists():
        print(f"[error] parquet not found: {args.parquet}", file=sys.stderr)
        return 2

    rows = _load_archive_rows(args.parquet)
    print(_format_report(rows, parquet_path=args.parquet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
