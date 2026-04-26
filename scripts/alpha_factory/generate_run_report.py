"""Alpha Factory Run レポート生成 (T021 拡張版)。

reports/run-reports/run-{N}/ にある summary.json / history.json と
.cache/alpha_factory/runs/genomes_{run_id}.parquet を集約して
reports/run-reports/run-{N}.md を生成する。

セクション粒度で defensive 化: summary.json 不在は exit 1 だが、それ以外の
拡張キー欠落 / archive 不在 / archive 読取失敗は warning + 部分生成。
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"

logger = logging.getLogger(__name__)


def _as_int_safe(v: Any) -> int:
    """``trade_count`` 等を安全に int 化 (NaN / None / 文字列パース失敗で 0)."""
    if v is None:
        return 0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(f):
        return 0
    return int(f)


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _format_value(v: Any, ndigits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✅" if v else "❌"
    if isinstance(v, float):
        if v != v:  # NaN
            return "—"
        return f"{v:.{ndigits}f}"
    return str(v)


def _load_archive(parquet_path: Path | None) -> list[dict[str, Any]] | None:
    """Parquet を pylist として読み込み。失敗時 None。"""
    if parquet_path is None or not parquet_path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(parquet_path)
        return table.to_pylist()
    except Exception as exc:
        logger.warning("archive load failed: %s (%s)", parquet_path, exc)
        return None


def _format_live_criteria(lc: Any) -> list[str]:
    """summary["live_criteria"] の表示。新形式 (criteria + all_pass + checks) と旧形式どちらにも対応。"""
    if not isinstance(lc, dict):
        return ["- 使命判定: 未記録"]
    lines: list[str] = []
    overall = lc.get("all_pass")
    if overall is True:
        lines.append("🎯 **使命達成**")
    elif overall is False:
        lines.append("未達")
    lines.append("")
    checks = lc.get("checks") or {}
    if not checks:
        lines.append("- live_criteria: 未記録（拡張キー欠落）")
        return lines
    for name, chk in checks.items():
        if not isinstance(chk, dict):
            continue
        mark = "✅" if chk.get("pass") else "❌"
        if name == "trade_count":
            lines.append(
                f"- {mark} **{name}**: {chk.get('value')} "
                f"(range {chk.get('threshold_min')}〜{chk.get('threshold_max')})"
            )
        else:
            lines.append(
                f"- {mark} **{name}**: {chk.get('value')} / "
                f"threshold {chk.get('threshold', '?')}"
            )
    return lines


def _format_ga_config(ga: Any) -> list[str]:
    if not isinstance(ga, dict):
        return ["- GA 設定: 未記録"]
    keys = [
        "population_size", "generations", "mutation_rate", "crossover_rate",
        "tournament_size", "elite_count", "max_depth", "fitness_metric", "seed",
    ]
    lines = []
    for k in keys:
        if k in ga:
            lines.append(f"- {k}: {ga[k]}")
    return lines or ["- GA 設定: 未記録"]


def _format_best(best: Any, archive_rows: list[dict[str, Any]] | None) -> list[str]:
    if not isinstance(best, dict):
        return ["- Best 個体: 未記録"]
    lines = [
        f"- name: `{best.get('name', '—')}`",
        f"- generation: {best.get('generation', '—')}",
        f"- fitness: **{_format_value(best.get('fitness'))}**",
        f"- fitness_finite: {_format_value(best.get('fitness_finite'))}",
    ]
    for stage in ("a", "b", "c"):
        key = f"stage_{stage}_pass"
        if key in best:
            lines.append(f"- {key}: {_format_value(best[key])}")
    metrics = best.get("metrics") or {}
    if isinstance(metrics, dict):
        for k in ("trade_count", "total_pnl", "win_rate", "profit_factor",
                   "sharpe", "sortino", "calmar", "max_drawdown_pct", "final_equity"):
            if k in metrics:
                lines.append(f"- {k}: {_format_value(metrics[k])}")
    # archive 補足
    if archive_rows is not None:
        match = next(
            (r for r in archive_rows
             if r.get("individual_name") == best.get("name")
             and r.get("generation") == best.get("generation")),
            None,
        )
        if match is not None:
            lines.append("")
            lines.append("**Archive 補足情報**:")
            for k in ("lane_id", "instrument", "fold_sign_ratio", "dsr",
                       "ii_lite_pass", "n_nodes", "active_clause"):
                if k in match:
                    lines.append(f"- {k}: {_format_value(match[k])}")
        else:
            lines.append("- archive 該当行なし（lane 不一致等、設計通り）")
    return lines


def _stage_pass_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "stage_a_pass": sum(1 for r in rows if r.get("stage_a_pass")),
        "stage_b_pass": sum(1 for r in rows if r.get("stage_b_pass")),
        "stage_c_pass": sum(1 for r in rows if r.get("stage_c_pass")),
        "total": len(rows),
    }


def _lane_pass_distribution(rows: list[dict[str, Any]]) -> list[tuple[str, dict[str, int]]]:
    by_lane: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_lane.setdefault(r.get("lane_id", "unknown"), []).append(r)
    out = [(lane, _stage_pass_counts(rs)) for lane, rs in by_lane.items()]
    out.sort(key=lambda x: x[0])
    return out


def _pair_distribution(rows: list[dict[str, Any]]) -> list[tuple[str, dict[str, int]]]:
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_pair.setdefault(r.get("instrument", "unknown"), []).append(r)
    out = [(pair, _stage_pass_counts(rs)) for pair, rs in by_pair.items()]
    out.sort(key=lambda x: x[0])
    return out


def _basic_stats(values: list[float | None]) -> dict[str, float | None]:
    nums = [v for v in values if v is not None and isinstance(v, (int, float)) and v == v]
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


def _fmt_stats(stats: dict[str, Any]) -> str:
    if stats["n"] == 0:
        return "n=0"
    return (
        f"n={stats['n']}, mean={_format_value(stats['mean'])}, "
        f"median={_format_value(stats['median'])}, std={_format_value(stats['std'])}, "
        f"min={_format_value(stats['min'])}, max={_format_value(stats['max'])}"
    )


def _ii_lite_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for r in rows:
        v = r.get("ii_lite_pass")
        if v is True:
            c["True"] += 1
        elif v is False:
            c["False"] += 1
        else:
            c["None"] += 1
    return dict(c)


def _archive_top_n(rows: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    sortable = [r for r in rows if r.get("fitness_pen") is not None]
    sortable.sort(key=lambda r: r.get("fitness_pen", float("-inf")), reverse=True)
    return sortable[:n]


def _per_generation_table(
    summary: dict[str, Any], history: list[dict[str, Any]] | None
) -> list[str]:
    pg = summary.get("per_generation")
    if isinstance(pg, list) and pg:
        lines = ["| gen | best_fitness |", "|-----|--------------|"]
        for entry in pg:
            gen = entry.get("generation", "—")
            bf = entry.get("best_fitness", entry.get("best_fitness_pen", "—"))
            lines.append(f"| {gen} | {bf} |")
        return lines
    if history:
        lines = ["| gen | best_fitness |", "|-----|--------------|"]
        for h in history:
            lines.append(f"| {h.get('generation', '—')} | {h.get('best_fitness', '—')} |")
        return lines
    return ["- 収束履歴: 未記録"]


def _collect_analysis_md(
    explicit_paths: list[Path], analysis_dirs: list[Path]
) -> list[Path]:
    """指定 path + dir 内の analysis-*.md を集めて dedup (Path.resolve)。"""
    seen: dict[str, Path] = {}
    for p in explicit_paths or []:
        try:
            r = p.resolve()
        except Exception:
            continue
        if r.exists() and r.is_file():
            seen[str(r)] = r
        else:
            logger.warning("analysis-md not found: %s", p)
    for d in analysis_dirs or []:
        try:
            r = d.resolve()
        except Exception:
            continue
        if not r.exists() or not r.is_dir():
            logger.warning("analysis-dir not found: %s", d)
            continue
        for f in sorted(r.glob("analysis-*.md")):
            seen[str(f.resolve())] = f.resolve()
    return list(seen.values())


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    p = argparse.ArgumentParser(description="Generate Alpha Factory FX run report (T021)")
    p.add_argument("--run-number", type=int, required=True)
    p.add_argument(
        "--analysis-md",
        type=Path,
        action="append",
        default=[],
        help="分析 md ファイルパス（複数回指定可）",
    )
    p.add_argument(
        "--analysis-dir",
        type=Path,
        action="append",
        default=[],
        help="ディレクトリ内の analysis-*.md を自動収集（複数回指定可）",
    )
    args = p.parse_args(argv)

    run_dir = RUN_REPORTS_DIR / f"run-{args.run_number}"
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        print(f"[error] summary not found: {summary_path}", file=sys.stderr)
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # archive load (defensive)
    archive_path_str = summary.get("archive_parquet")
    archive_path = Path(archive_path_str) if archive_path_str else None
    if archive_path and not archive_path.is_absolute():
        archive_path = REPO_ROOT / archive_path
    archive_rows = _load_archive(archive_path)
    if archive_rows is None:
        if archive_path_str:
            logger.warning("archive Parquet 読取失敗 or 不在: %s", archive_path)
        else:
            logger.warning("summary に archive_parquet キーなし")

    # history fallback
    history_path = run_dir / "history.json"
    history: list[dict[str, Any]] | None = None
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("history.json 読取失敗: %s", exc)

    # === レポート組み立て ===
    lines: list[str] = []
    lines.append(f"# Run {args.run_number} — {summary.get('run_id', '—')}")
    lines.append("")
    lines.append(f"**Generated**: {summary.get('generated_at', '—')}")
    ds = summary.get("dataset", {})
    if isinstance(ds, dict):
        lines.append(
            f"**Dataset**: {ds.get('instrument', '—')} "
            f"`{ds.get('start', '—')}` → `{ds.get('end', '—')}` "
            f"(bars={ds.get('bars', '—')})"
        )
        for bk in ("bars_stage_a", "bars_stage_b", "bars_holdout"):
            if bk in ds:
                lines.append(f"  - {bk}: {ds[bk]}")
    lines.append("")

    # 使命判定
    lines.append("## 使命判定")
    lines.append("")
    lines.extend(_format_live_criteria(summary.get("live_criteria")))
    lines.append("")

    # GA 設定
    lines.append("## GA 設定")
    lines.append("")
    lines.extend(_format_ga_config(summary.get("ga_config")))
    lines.append("")

    # Best 個体
    lines.append("## Best 個体")
    lines.append("")
    lines.extend(_format_best(summary.get("best"), archive_rows))
    lines.append("")

    # Stage 通過数 (archive 依存)
    lines.append("## Stage 通過数")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        sp = _stage_pass_counts(archive_rows)
        lines.append(f"- 全 archive 行数: {sp['total']}")
        lines.append(f"- Stage A pass: {sp['stage_a_pass']}")
        lines.append(f"- Stage B pass: {sp['stage_b_pass']}")
        lines.append(f"- Stage C pass: {sp['stage_c_pass']}")
    lines.append("")

    # Lane 別落下分布
    lines.append("## Lane 別落下分布")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        dist = _lane_pass_distribution(archive_rows)
        lines.append("| lane_id | total | A | B | C |")
        lines.append("|---------|-------|---|---|---|")
        for lane, sp in dist:
            lines.append(
                f"| {lane} | {sp['total']} | {sp['stage_a_pass']} | "
                f"{sp['stage_b_pass']} | {sp['stage_c_pass']} |"
            )
    lines.append("")

    # Pair 別落下分布
    lines.append("## Pair 別落下分布")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        dist = _pair_distribution(archive_rows)
        lines.append("| instrument | total | A | B | C |")
        lines.append("|------------|-------|---|---|---|")
        for pair, sp in dist:
            lines.append(
                f"| {pair} | {sp['total']} | {sp['stage_a_pass']} | "
                f"{sp['stage_b_pass']} | {sp['stage_c_pass']} |"
            )
    lines.append("")

    # active_clause / n_nodes 分布
    lines.append("## active_clause / n_nodes 分布")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        ac = _basic_stats([r.get("active_clause") for r in archive_rows])
        nn = _basic_stats([r.get("n_nodes") for r in archive_rows])
        lines.append(f"- active_clause: {_fmt_stats(ac)}")
        lines.append(f"- n_nodes: {_fmt_stats(nn)}")
    lines.append("")

    # T043: mission_score 分布 (Stage C 評価された個体のみ)
    lines.append("## mission_score 分布 (T043 / observation only)")
    lines.append("")
    lines.append(
        "> live_criteria 4 軸 (sharpe/total_pnl/max_drawdown/trade_count) の "
        "soft 合算スコア (幾何平均、[0.1, 1.0])。GA fitness や stage_c.passed には "
        "影響しない (詳細: docs/alpha_factory/mission-score.md)。"
    )
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        ms_values = [r.get("mission_score") for r in archive_rows]
        ms_present = [v for v in ms_values if v is not None]
        if not ms_present:
            lines.append(
                "- mission_score=計測対象 0 件 (Stage C base 評価で Sharpe を出した "
                "個体が無いため未計測)"
            )
        else:
            ms_stats = _basic_stats(ms_values)
            lines.append(f"- mission_score: {_fmt_stats(ms_stats)}")
            best_ms = max(ms_present)
            best_row = next(
                r for r in archive_rows
                if r.get("mission_score") == best_ms
            )
            lines.append(
                f"- best mission_score: **{best_ms:.4f}** "
                f"(`{best_row.get('individual_name', '?')}`, "
                f"gen={best_row.get('generation', '?')}, "
                f"instrument={best_row.get('instrument', '?')})"
            )
    lines.append("")

    # fold_sign_ratio / dsr 分布
    lines.append("## fold_sign_ratio / dsr 分布")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        fs = _basic_stats([r.get("fold_sign_ratio") for r in archive_rows])
        ds_st = _basic_stats([r.get("dsr") for r in archive_rows])
        lines.append(f"- fold_sign_ratio: {_fmt_stats(fs)}")
        lines.append(f"- dsr: {_fmt_stats(ds_st)}")
        # T035: n_fold_effective / positive_fold_ratio_effective 分布
        sa_rows = [r for r in archive_rows if r.get("stage_a_pass")]
        fe = _basic_stats([r.get("n_fold_effective") for r in sa_rows])
        prfe = _basic_stats(
            [r.get("positive_fold_ratio_effective") for r in sa_rows]
        )
        lines.append(f"- n_fold_effective (Stage A pass): {_fmt_stats(fe)}")
        lines.append(
            f"- positive_fold_ratio_effective (Stage A pass): {_fmt_stats(prfe)}"
        )
    lines.append("")

    # T035: Stage B failure reason 集計 (primary_reason + any_reason incidence)
    lines.append("## Stage B failure reason 集計")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        sa_rows = [r for r in archive_rows if r.get("stage_a_pass")]
        n_evaluated = len(sa_rows)
        n_pass = sum(1 for r in sa_rows if r.get("stage_b_pass"))
        known_codes = (
            "no_folds",
            "insufficient_folds",
            "all_folds_unavailable",
            "stage_b_window_underfilled",
            # T035 fix (cycle 5): 旧実装で漏れていた stage_gate.py の reason
            # を known_codes に追加。これらが Stage B 全滅 reason に隠蔽されていた。
            "median_oos_sharpe<min",
            "positive_fold_ratio<min",
            # T044: pre-flight feasibility skip-path
            "stage_b_pre_flight_underfilled",
        )
        # Primary reason: ;-split の先頭のみで集計、合計 = failures
        primary_counts: dict[str, int] = {c: 0 for c in known_codes}
        primary_counts["other"] = 0
        primary_counts["unknown_reason"] = 0
        # Any reason incidence: 全 reason をカウント (合計 >= failures)
        any_counts: dict[str, int] = {c: 0 for c in known_codes}
        any_counts["other"] = 0
        for r in sa_rows:
            if r.get("stage_b_pass"):
                continue
            rc_raw = r.get("stage_b_reason_codes")
            if rc_raw is None or rc_raw == "":
                primary_counts["unknown_reason"] += 1
                continue
            rc_list = [c.strip() for c in str(rc_raw).split(";") if c.strip()]
            if not rc_list:
                primary_counts["unknown_reason"] += 1
                continue
            primary = rc_list[0]
            if primary in primary_counts:
                primary_counts[primary] += 1
            else:
                primary_counts["other"] += 1
            for c in rc_list:
                if c in any_counts:
                    any_counts[c] += 1
                else:
                    any_counts["other"] += 1
        total_failures = n_evaluated - n_pass
        primary_sum = sum(primary_counts.values())
        lines.append(
            f"- Stage A pass = {n_evaluated}, Stage B pass = {n_pass}, "
            f"failures = {total_failures} (primary_sum = {primary_sum})"
        )
        lines.append("")
        lines.append("### Primary reason (先頭 reason、合計 = failures)")
        lines.append("")
        lines.append(
            "| reason | count |"
        )
        lines.append("|--------|------:|")
        for c in (*known_codes, "unknown_reason", "other"):
            lines.append(f"| `{c}` | {primary_counts[c]} |")
        lines.append("")
        lines.append("### Any reason incidence (全 reason、合計 >= failures)")
        lines.append("")
        lines.append("| reason | count |")
        lines.append("|--------|------:|")
        for c in (*known_codes, "other"):
            lines.append(f"| `{c}` | {any_counts[c]} |")
    lines.append("")

    # cross-pair shadow 集計
    lines.append("## Cross-pair shadow 集計")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        cp_mode = summary.get("cross_pair_runtime_mode", "—")
        lines.append(f"- runtime mode: {cp_mode}")
        ii = _ii_lite_counts(archive_rows)
        lines.append(
            f"- ii_lite_pass: True={ii.get('True', 0)}, "
            f"False={ii.get('False', 0)}, None={ii.get('None', 0)}"
        )
    lines.append("")

    # graduated 件数
    lines.append("## Graduation")
    lines.append("")
    if archive_rows is None:
        lines.append(
            f"- summary.graduation_count: {summary.get('graduation_count', '—')}"
        )
    else:
        graduated = sum(1 for r in archive_rows if r.get("graduated"))
        lines.append(f"- archive graduated: {graduated}")
        lines.append(
            f"- summary.graduation_count: {summary.get('graduation_count', '—')}"
        )
    lines.append("")

    # T031 Feasibility 集計 (selection_score_schema = v2_feasibility 時に出力)
    best = summary.get("best") or {}
    schema = best.get("selection_score_schema", "v1_legacy")
    lines.append("## Feasibility 集計")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        no_trade_count = sum(
            1 for r in archive_rows
            if _as_int_safe(r.get("trade_count")) == 0
        )
        total_rows = max(1, len(archive_rows))
        no_trade_ratio = no_trade_count / total_rows
        best_trade_count = _as_int_safe(
            (best.get("metrics") or {}).get("trade_count")
        )
        best_feasible = bool(best.get("feasible", True))
        lines.append(
            f"- selection_score schema: `{schema}`"
        )
        lines.append(
            f"- trade_count=0 個体比率: {no_trade_ratio:.1%} "
            f"({no_trade_count}/{total_rows})"
        )
        lines.append(f"- best 個体 trade_count: {best_trade_count}")
        lines.append(
            f"- best 個体 feasibility: "
            f"{'✅' if best_feasible else '❌'}"
        )
    lines.append("")

    # archive Top-5 個体一覧 (Best とは別物)
    lines.append("## Archive Top-5 個体一覧")
    lines.append("")
    if schema == "v2_feasibility":
        note = (
            "Best は "
            "(feasible, -violation, stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) "
            "の辞書式 (v2_feasibility)。"
        )
    else:
        note = (
            "Best は (stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen) "
            "の辞書式 (v1_legacy)。"
        )
    lines.append(f"> Best とは別物です。`fitness_pen` 単独降順。{note}")
    lines.append("")
    if archive_rows is None:
        lines.append("- archive Parquet なし、計算スキップ")
    else:
        top = _archive_top_n(archive_rows, 5)
        if not top:
            lines.append("- 該当行なし")
        else:
            lines.append(
                "| rank | name | gen | lane | instrument | fitness_pen "
                "| fitness_raw | A | B | C | trade_count | sharpe |"
            )
            lines.append(
                "|-----:|------|----:|------|------------|------------:"
                "|------------:|---|---|---|----:|-------:|"
            )
            for i, r in enumerate(top, 1):
                lines.append(
                    f"| {i} | `{r.get('individual_name', '—')}` | {r.get('generation', '—')} | "
                    f"{r.get('lane_id', '—')} | {r.get('instrument', '—')} | "
                    f"{_format_value(r.get('fitness_pen'))} | {_format_value(r.get('fitness_raw'))} | "
                    f"{_format_value(r.get('stage_a_pass'))} | {_format_value(r.get('stage_b_pass'))} | "
                    f"{_format_value(r.get('stage_c_pass'))} | {r.get('trade_count', '—')} | "
                    f"{_format_value(r.get('sharpe'))} |"
                )
    lines.append("")

    # 収束履歴
    lines.append("## 収束履歴")
    lines.append("")
    lines.extend(_per_generation_table(summary, history))
    lines.append("")

    # 分析 md
    analysis_files = _collect_analysis_md(
        list(args.analysis_md), list(args.analysis_dir)
    )
    if analysis_files:
        lines.append("## 分析")
        lines.append("")
        for af in analysis_files:
            try:
                content = af.read_text(encoding="utf-8").strip()
            except Exception as exc:
                logger.warning("analysis-md 読取失敗 %s: %s", af, exc)
                continue
            lines.append(f"### {af.name}")
            lines.append("")
            lines.append(content)
            lines.append("")

    out_path = RUN_REPORTS_DIR / f"run-{args.run_number}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
