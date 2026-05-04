"""Stage B 判定 SSOT 可視化 diagnostic script (cycle 20 施策 P1).

archive parquet を入力に Stage B 判定根拠と archive 列の対応関係を可視化する。

設計意図:
  cycle 6-19 で「archive 列 trade_sharpe_stage_b vs 判定 SSOT median_oos_sharpe」
  の混同が発生 (C2 違反)。 本 script は decision_trace を必須出力し、
  「どの規則・どの母集団で判定したか」 を同時固定する。

判定 SSOT (= src/alpha_factory/stage_gate.py:1163-1178):
  Stage B passed = (median_oos_sharpe >= stage_b_median_oos_sharpe_min)
                   ∧ (positive_fold_ratio >= stage_b_positive_fold_min)
                   ∧ not all_folds_unavailable

archive 観測補助列 (= 判定 SSOT ではない):
  - trade_sharpe_stage_b: Stage B IS 全期間 Sharpe (≠ median_oos_sharpe)
  - positive_fold_ratio_effective: unavailable 除外母数 (≠ positive_fold_ratio 全 fold 母数)

設計: devnotes/20260504-2120-fx-improve-c20-proper/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"

DECISION_TRACE_VERSION = "v1"
THRESHOLDS = {
    "stage_b_median_oos_sharpe_min": 0.05,
    "stage_b_positive_fold_min": 0.60,
}
USED_METRICS_SOURCE = "archive"  # = stage_b_reason_codes 経由で推測
UNAVAILABLE_IMPUTATION_POLICY = "fold metric_unavailable は 0 として母数に含める"


def load_run_effective_config(run_number: int) -> tuple[dict[str, Any], list[str]]:
    """summary.json から run-effective config 取得 (= analyze_stage_a_diagnostic.py と同方針)."""
    summary_path = RUN_REPORTS_DIR / f"run-{run_number}" / "summary.json"
    warnings_list: list[str] = []
    config: dict[str, Any] = {"_summary_path": str(summary_path)}
    if not summary_path.exists():
        warnings_list.append(f"summary.json 不在: {summary_path}")
        return config, warnings_list
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    sg = summary.get("stage_gate_config", {})
    config["stage_b_median_oos_sharpe_min"] = sg.get(
        "stage_b_median_oos_sharpe_min", THRESHOLDS["stage_b_median_oos_sharpe_min"]
    )
    config["stage_b_positive_fold_min"] = sg.get(
        "stage_b_positive_fold_min", THRESHOLDS["stage_b_positive_fold_min"]
    )
    config["summary_run_id"] = summary.get("run_id")
    return config, warnings_list


def categorize_stage_b_outcome(row: pd.Series) -> dict[str, Any]:
    """1 個体の Stage B 判定根拠を decision_trace で表現."""
    rc = row.get("stage_b_reason_codes")
    if isinstance(rc, str):
        reasons = [r for r in rc.split(";") if r]
    else:
        reasons = []
    return {
        "stage_b_pass": bool(row.get("stage_b_pass")),
        "fail_reasons": reasons,
        "median_oos_sharpe_below_min": "median_oos_sharpe<min" in reasons,
        "positive_fold_ratio_below_min": "positive_fold_ratio<min" in reasons,
        "all_folds_unavailable": "all_folds_unavailable" in reasons,
        "no_folds": "no_folds" in reasons,
        "insufficient_folds": "insufficient_folds" in reasons,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Stage B 判定 SSOT 可視化 diagnostic")
    p.add_argument("--run-id", required=True, help="例: run_20260504_111153")
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()

    archive_path = ARCHIVE_DIR / f"genomes_{args.run_id}.parquet"
    if not archive_path.exists():
        print(f"[error] archive not found: {archive_path}", file=sys.stderr)
        return 2
    df = pq.read_table(archive_path).to_pandas()

    run_number = int(df["run_number"].iloc[0]) if "run_number" in df.columns and len(df) > 0 else None
    if args.output_dir is not None:
        out_dir = args.output_dir
    elif run_number is not None:
        out_dir = RUN_REPORTS_DIR / f"run-{run_number}" / "diagnostics"
    else:
        print("[error] run_number 解決不能", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    rec_config, warnings_list = load_run_effective_config(run_number) if run_number is not None else ({}, [])

    a_pass = df[df["stage_a_pass"] == True].copy()  # noqa: E712
    b_pass = df[df["stage_b_pass"] == True].copy()  # noqa: E712

    # 全 a_pass 個体に decision_trace
    a_pass["_dt"] = a_pass.apply(categorize_stage_b_outcome, axis=1)

    # 失敗 reason 分布
    reason_dist: dict[str, int] = {}
    for dt in a_pass["_dt"]:
        if dt["stage_b_pass"]:
            reason_dist["__pass__"] = reason_dist.get("__pass__", 0) + 1
        for r in dt["fail_reasons"]:
            reason_dist[r] = reason_dist.get(r, 0) + 1

    # archive 観測補助列 vs 判定 SSOT の混同警告
    sb_max = a_pass["trade_sharpe_stage_b"].max() if len(a_pass) > 0 else None
    pos_fr_eff_max = a_pass["positive_fold_ratio_effective"].max() if len(a_pass) > 0 else None

    # AND 突破 (analytical = sb>=0.05 ∧ pos_fr_eff>=0.60) と stage_b_pass の差分
    if len(a_pass) > 0:
        analytical_and = a_pass[
            (a_pass["trade_sharpe_stage_b"] >= 0.05)
            & (a_pass["positive_fold_ratio_effective"] >= 0.60)
        ]
    else:
        analytical_and = pd.DataFrame()

    # b_pass 個体の詳細 (archive 観測列も併記)
    b_pass_detail = []
    if len(b_pass) > 0:
        for _, row in b_pass.iterrows():
            b_pass_detail.append({
                "individual_name": row.get("individual_name"),
                "generation": int(row.get("generation", -1)),
                "trade_count": int(row.get("trade_count", 0)),
                "fitness_pen": float(row.get("fitness_pen", 0)),
                "trade_sharpe_raw": float(row.get("trade_sharpe_raw", 0)),
                "trade_sharpe_stage_b_archive": float(row.get("trade_sharpe_stage_b", 0)),
                "positive_fold_ratio_effective_archive": float(row.get("positive_fold_ratio_effective", 0)),
                "n_fold_effective": float(row.get("n_fold_effective", 0)),
                "stage_c_pass": bool(row.get("stage_c_pass")),
                "live_criteria_compatible_trade_count": int(row.get("trade_count", 0)) >= 50,
            })

    payload: dict[str, Any] = {
        "run_id": args.run_id,
        "run_number": run_number,
        "decision_trace": {
            "rule_version": DECISION_TRACE_VERSION,
            "thresholds": {
                "stage_b_median_oos_sharpe_min": rec_config.get(
                    "stage_b_median_oos_sharpe_min", THRESHOLDS["stage_b_median_oos_sharpe_min"]
                ),
                "stage_b_positive_fold_min": rec_config.get(
                    "stage_b_positive_fold_min", THRESHOLDS["stage_b_positive_fold_min"]
                ),
            },
            "used_metrics_source": USED_METRICS_SOURCE,
            "unavailable_imputation_policy": UNAVAILABLE_IMPUTATION_POLICY,
            "judgment_logic": (
                "Stage B passed iff (median_oos_sharpe >= threshold) "
                "AND (positive_fold_ratio >= threshold) AND (not all_folds_unavailable)"
            ),
        },
        "stage_pass_counts": {
            "a": int((df["stage_a_pass"] == True).sum()),  # noqa: E712
            "b": int((df["stage_b_pass"] == True).sum()),  # noqa: E712
            "c": int((df["stage_c_pass"] == True).sum()),  # noqa: E712
        },
        "stage_b_reason_distribution": reason_dist,
        "archive_columns_warning": {
            "trade_sharpe_stage_b": "Stage B IS 全期間 Sharpe (= 判定 SSOT ではない、 median_oos_sharpe と混同禁止)",
            "positive_fold_ratio_effective": "unavailable 除外母数 (= 判定 SSOT ではない、 全 fold 母数の positive_fold_ratio と混同禁止)",
        },
        "analytical_AND_vs_stage_b_pass": {
            "analytical_AND_count": len(analytical_and),
            "actual_stage_b_pass_count": len(b_pass),
            "discrepancy": len(analytical_and) - len(b_pass),
            "note": (
                "discrepancy > 0 が観察された場合、 archive 観測補助列の AND と 判定 SSOT 不一致 "
                "(= 母数の違い + metric の違いによる identification error)"
            ),
        },
        "stage_b_pass_individuals": b_pass_detail,
        "warnings": warnings_list,
    }

    json_path = out_dir / "stage_b_judgment_audit.json"
    md_path = out_dir / "stage_b_judgment_audit.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown rendering
    lines: list[str] = []
    lines.append(f"# Stage B 判定 SSOT Audit: {args.run_id}")
    lines.append("")
    lines.append(f"- run_number: {run_number}")
    lines.append("")
    lines.append("## decision_trace (= C2/C4/C6 対策)")
    dt = payload["decision_trace"]
    lines.append(f"- rule_version: {dt['rule_version']}")
    lines.append(f"- thresholds: {dt['thresholds']}")
    lines.append(f"- used_metrics_source: {dt['used_metrics_source']}")
    lines.append(f"- unavailable_imputation_policy: {dt['unavailable_imputation_policy']}")
    lines.append(f"- judgment_logic: `{dt['judgment_logic']}`")
    lines.append("")
    lines.append("## archive 観測補助列の混同警告")
    for col, note in payload["archive_columns_warning"].items():
        lines.append(f"- `{col}`: {note}")
    lines.append("")
    lines.append("## Stage 通過数")
    sp = payload["stage_pass_counts"]
    lines.append(f"- A: {sp['a']} / B: {sp['b']} / C: {sp['c']}")
    lines.append("")
    lines.append("## Stage B 判定理由分布 (a_pass 個体ごと)")
    lines.append("| reason | count |")
    lines.append("|---|---:|")
    for r, c in sorted(payload["stage_b_reason_distribution"].items(), key=lambda x: -x[1]):
        lines.append(f"| {r} | {c} |")
    lines.append("")
    lines.append("## analytical AND vs stage_b_pass 不一致観察")
    av = payload["analytical_AND_vs_stage_b_pass"]
    lines.append(f"- analytical_AND (= sb>=0.05 ∧ pos_fr_eff>=0.60): {av['analytical_AND_count']}")
    lines.append(f"- actual stage_b_pass: {av['actual_stage_b_pass_count']}")
    lines.append(f"- discrepancy: {av['discrepancy']}")
    lines.append(f"- {av['note']}")
    lines.append("")
    if b_pass_detail:
        lines.append("## stage_b_pass=True 個体詳細")
        lines.append("| name | gen | trade_count | fitness_pen | sb_archive | pos_fr_eff | n_fold | C pass | live_criteria? |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for d in b_pass_detail:
            lines.append(
                f"| {d['individual_name']} | {d['generation']} | {d['trade_count']} | "
                f"{d['fitness_pen']:.4f} | {d['trade_sharpe_stage_b_archive']:.4f} | "
                f"{d['positive_fold_ratio_effective_archive']:.2f} | {d['n_fold_effective']:.0f} | "
                f"{d['stage_c_pass']} | {d['live_criteria_compatible_trade_count']} |"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[done] run={args.run_id} a_pass={sp['a']} b_pass={sp['b']} discrepancy={av['discrepancy']}")
    print(f"  -> {md_path}")
    print(f"  -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
