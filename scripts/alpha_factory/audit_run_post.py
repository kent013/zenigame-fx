#!/usr/bin/env python3
"""archive Parquet 後処理 DSR audit (Phase 1: post-processing path).

cycle 13 軽量 DSR 配線復帰の Phase 1 実装。 既存 archive 列 (sharpe / fold-level metrics)
から DSR proxy を計算し、 reports/run-reports/run-{N}/dsr_audit.json として出力する。
SessionBlock 駆動の正規 DSR は Phase 2 (cycle 14-15) で audit.compute_audit_dsr_for_genome
を run_ga.py 評価ループから呼び出す形で本格実装する。

DSR proxy 公式 (Bailey, Lopez de Prado, Borwein, Zhu, 2014 を archive metric ベースに簡略化):
    DSR_proxy = SR / (1 + (1/N) * SR^2 * 0.5)
ここで N = n_fold_effective (fold OOS 観測数)。 多重比較補正は GA total population (M=5856) を
log(M) ≈ 8.7 として SR^* threshold = sqrt(2*log(M)/N) と比較。

Usage:
    uv run python scripts/alpha_factory/audit_run_post.py --run-number 65
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]


def compute_dsr_proxy(sharpe: float, n_fold: int) -> float:
    """SR を fold 観測数で補正した DSR proxy.

    SE(SR) ≈ sqrt((1 + 0.5 * SR^2) / N) を用いて DSR proxy = SR / (1 + SE)。
    """
    if n_fold <= 0 or not math.isfinite(sharpe):
        return float("nan")
    se = math.sqrt(max(0.0, (1.0 + 0.5 * sharpe * sharpe) / n_fold))
    return sharpe / (1.0 + se)


def compute_dsr_threshold(m_trials: int, n_fold: int) -> float:
    """多重比較補正後の SR threshold (Bailey-Lopez de Prado 2014 簡略化)."""
    if n_fold <= 0 or m_trials <= 1:
        return float("nan")
    # bonferroni-like: SR^* = sqrt(2 * log(M) / N)
    return math.sqrt(2.0 * math.log(m_trials) / n_fold)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post-process DSR audit on archive Parquet")
    parser.add_argument("--run-number", type=int, required=True)
    args = parser.parse_args(argv)

    summary_path = REPO_ROOT / "reports" / "run-reports" / f"run-{args.run_number}" / "summary.json"
    if not summary_path.exists():
        print(f"[error] {summary_path} not found", file=sys.stderr)
        return 1

    summary = json.loads(summary_path.read_text())
    run_id = summary["run_id"]
    archive_path = REPO_ROOT / ".cache" / "alpha_factory" / "runs" / f"genomes_{run_id}.parquet"
    if not archive_path.exists():
        print(f"[error] {archive_path} not found", file=sys.stderr)
        return 1

    df = pq.read_table(str(archive_path)).to_pandas()
    n_total = len(df)

    sa = df[df["stage_a_pass"] == True]  # noqa: E712
    sb = df[df["stage_b_pass"] == True]  # noqa: E712

    audit_records = []
    for _, row in sa.iterrows():
        sr_raw = row.get("trade_sharpe_raw") or row.get("fitness_pen") or 0.0
        sr_b = row.get("trade_sharpe_stage_b")
        n_fold = int(row.get("n_fold_effective") or 0)
        sr = float(sr_b) if sr_b and math.isfinite(float(sr_b)) else float(sr_raw)
        dsr = compute_dsr_proxy(sr, n_fold)
        threshold = compute_dsr_threshold(n_total, n_fold)
        audit_records.append({
            "name": row["individual_name"],
            "generation": int(row["generation"]),
            "fitness_pen": float(row["fitness_pen"]) if math.isfinite(float(row["fitness_pen"])) else None,
            "sharpe_used": sr,
            "n_fold_effective": n_fold,
            "dsr_proxy": dsr if math.isfinite(dsr) else None,
            "dsr_threshold": threshold if math.isfinite(threshold) else None,
            "dsr_pass": dsr > threshold if (math.isfinite(dsr) and math.isfinite(threshold)) else None,
            "stage_a_pass": bool(row["stage_a_pass"]),
            "stage_b_pass": bool(row["stage_b_pass"]),
            "stage_c_pass": bool(row["stage_c_pass"]),
        })

    # ソート: stage_b_pass desc, dsr_pass desc, dsr_proxy desc
    audit_records.sort(
        key=lambda r: (
            -1 if r["stage_b_pass"] else 0,
            -1 if r.get("dsr_pass") else 0,
            -(r["dsr_proxy"] or -math.inf),
        )
    )

    # サマリー集計
    n_dsr_pass = sum(1 for r in audit_records if r.get("dsr_pass"))
    n_stage_b_dsr_pass = sum(
        1 for r in audit_records if r["stage_b_pass"] and r.get("dsr_pass")
    )

    output = {
        "run_id": run_id,
        "run_number": args.run_number,
        "audit_method": "post_processing_phase1_dsr_proxy",
        "audit_formula": "DSR_proxy = SR / (1 + SE), SE = sqrt((1+0.5*SR^2)/N), SR^* = sqrt(2*log(M)/N), M=5856 trials",
        "reference": "Bailey, Lopez de Prado, Borwein, Zhu (2014) The Probability of Backtest Overfitting (簡略化)",
        "phase_1_caveat": "正規 DSR は SessionBlock 駆動 (audit.compute_audit_dsr_for_genome)、 本 Phase 1 は archive sharpe / n_fold ベースの proxy",
        "n_total_individuals": n_total,
        "n_stage_a_pass": len(sa),
        "n_stage_b_pass": len(sb),
        "n_stage_c_pass": int(df["stage_c_pass"].sum()),
        "n_dsr_proxy_pass": n_dsr_pass,
        "n_stage_b_and_dsr_pass": n_stage_b_dsr_pass,
        "top_dsr_pass_individuals": audit_records[:20],
    }

    out_path = REPO_ROOT / "reports" / "run-reports" / f"run-{args.run_number}" / "dsr_audit.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"[done] DSR audit written to {out_path}")
    print(
        f"summary: total={n_total}, sa_pass={len(sa)}, sb_pass={len(sb)}, "
        f"dsr_proxy_pass={n_dsr_pass}, sb_and_dsr_pass={n_stage_b_dsr_pass}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
