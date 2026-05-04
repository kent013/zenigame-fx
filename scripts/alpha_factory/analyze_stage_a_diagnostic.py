"""Stage A root cause diagnostic 集計 script (Run-28 施策 C1).

既存 archive Parquet (`.cache/alpha_factory/runs/genomes_{run_id}.parquet`)
を入力に、 fitness_pen 分解 / trade_sharpe_raw 分布 / penalty 効果 /
n_nodes / active_clause 推移 を集計し、 Stage A pass=0 の root cause を
(P1) primitive / (P2) penalty / (P3) 探索 dynamics / INCONCLUSIVE に分類する。

GA 挙動には一切影響しない post-RUN diagnostic script。

設計: devnotes/20260504-1236-fx-improve/detailed-design.md (design-review Round 3 APPROVED)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / ".cache" / "alpha_factory" / "runs"
RUN_REPORTS_DIR = REPO_ROOT / "reports" / "run-reports"

# 分類判定の SSOT 閾値 (= heuristic、 docstring 根拠明示)
P1_RAW_MAX_THRESHOLD = 0.005  # primitive 不足判定の trade_sharpe_raw 上限
P1_RATIONALE = (
    "trade_sharpe_raw max が 0.005 未満 = primitive 構成が「market neutral random-like」 "
    "しか生成しておらず GA 探索が positive sharpe 領域へ到達不能"
)
P2_BASE_THRESHOLD = 3  # penalty kill 個体数の最低絶対値
P2_RATIO_THRESHOLD = 0.01  # n_valid に対する比率 (1%)
P3_STD_DROP_THRESHOLD = 0.5  # n_nodes std の世代間崩壊量
SENTINEL_THRESHOLD = -1e6  # T034 sentinel (NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE)


# ---------------------------------------------------------------------------
# config / data loaders
# ---------------------------------------------------------------------------


def load_run_effective_config(run_number: int) -> tuple[dict[str, Any], list[str]]:
    """summary.json から run-effective config を取得.

    過去 Run の診断時に default.yaml ではなく当時の summary.json から取得することで、
    config 変更による診断結果汚染を防ぐ (= design-review Round 2 R2-Cr1 対応).

    Returns:
        (config_dict, warnings_list)
    """
    summary_path = RUN_REPORTS_DIR / f"run-{run_number}" / "summary.json"
    warnings_list: list[str] = []
    config: dict[str, Any] = {"_source": "run_effective", "_summary_path": str(summary_path)}

    if not summary_path.exists():
        warnings_list.append(f"summary.json 不在: {summary_path}、 fallback 使用")
        config["_source"] = "fallback_default"
        config.update({"max_clause": None, "stage_a_alpha": None, "stage_a_threshold": None})
        return config, warnings_list

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    ga = summary.get("ga_config", {})
    sg = summary.get("stage_gate_config", {})

    config["max_clause"] = ga.get("max_clause")
    config["stage_a_alpha"] = sg.get("stage_a_alpha")
    config["stage_a_threshold"] = sg.get("stage_a_threshold")
    config["summary_run_id"] = summary.get("run_id")

    for key in ("max_clause", "stage_a_alpha", "stage_a_threshold"):
        if config[key] is None:
            warnings_list.append(
                f"summary.json から {key} 取得不能、 該当判定を degrade_confidence"
            )

    return config, warnings_list


# ---------------------------------------------------------------------------
# 共通 mask / バケット
# ---------------------------------------------------------------------------


def compute_valid_mask(df: pd.DataFrame) -> pd.Series:
    """sentinel 除外 + finite + 必須列存在の共通 mask (R1-W2 / R2-W2 対応)."""
    fp_finite = df["fitness_pen"].apply(
        lambda x: bool(np.isfinite(x)) if x is not None else False
    )
    ts_finite = df["trade_sharpe_raw"].apply(
        lambda x: bool(np.isfinite(x)) if x is not None else False
    )
    sentinel_excluded = df["fitness_pen"] > SENTINEL_THRESHOLD
    return fp_finite & ts_finite & sentinel_excluded


def _bucket_label(trade_count: int) -> str:
    if trade_count == 0:
        return "0"
    if trade_count < 50:
        return "1-49"
    if trade_count < 500:
        return "50-499"
    if trade_count < 1500:
        return "500-1499"
    return ">=1500"


# ---------------------------------------------------------------------------
# 集計関数
# ---------------------------------------------------------------------------


def compute_fitness_pen_decomposition(
    df: pd.DataFrame, alpha: float | None
) -> dict[str, Any]:
    """fitness_pen = trade_sharpe_raw - alpha * size_norm の 4 項分解.

    archive に size_norm 列なし → `size_norm = (raw - pen) / alpha` で逆算 (= 浮動小数誤差リスク)。
    alpha=None 時は size_norm を「参考値」 扱い。
    """
    valid = df[compute_valid_mask(df)].copy()
    out: dict[str, Any] = {}

    for col in ["trade_sharpe_raw", "fitness_pen"]:
        s = valid[col].dropna()
        out[col] = (
            {"max": float(s.max()), "mean": float(s.mean()), "std": float(s.std())}
            if len(s) > 0
            else {"max": None, "mean": None, "std": None}
        )

    if alpha is not None and alpha > 0:
        valid["penalty"] = (valid["trade_sharpe_raw"] - valid["fitness_pen"]).fillna(0.0)
        valid["size_norm_inferred"] = valid["penalty"] / alpha
        for col in ["size_norm_inferred", "penalty"]:
            s = valid[col].dropna()
            out[col] = (
                {"max": float(s.max()), "mean": float(s.mean()), "std": float(s.std())}
                if len(s) > 0
                else {"max": None, "mean": None, "std": None}
            )
        out["_alpha_used"] = alpha
        out["_size_norm_note"] = "逆算 size_norm = (raw - pen) / alpha (近似)"
    else:
        out["size_norm_inferred"] = {"max": None, "mean": None, "std": None}
        out["penalty"] = {"max": None, "mean": None, "std": None}
        out["_alpha_used"] = None
        out["_size_norm_note"] = "alpha 不在のため size_norm 逆算不能、 参考値扱い"

    return out


def compute_trade_sharpe_by_generation(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gen, g in df.groupby("generation"):
        ts = g["trade_sharpe_raw"].dropna()
        rows.append(
            {
                "generation": int(gen),
                "n": int(len(g)),
                "max": float(ts.max()) if len(ts) > 0 else None,
                "mean": float(ts.mean()) if len(ts) > 0 else None,
                "median": float(ts.median()) if len(ts) > 0 else None,
                "n_positive": int((ts > 0).sum()),
            }
        )
    return rows


def compute_trade_count_buckets(df: pd.DataFrame) -> list[dict[str, Any]]:
    df = df.copy()
    df["bucket"] = df["trade_count"].apply(_bucket_label)
    order = ["0", "1-49", "50-499", "500-1499", ">=1500"]
    out: list[dict[str, Any]] = []
    for label in order:
        sub = df[df["bucket"] == label]
        ts = sub["trade_sharpe_raw"].dropna()
        fp_valid = sub[sub["fitness_pen"] > SENTINEL_THRESHOLD]["fitness_pen"]
        out.append(
            {
                "bucket": label,
                "n": int(len(sub)),
                "trade_sharpe_mean": float(ts.mean()) if len(ts) > 0 else None,
                "fitness_pen_mean": float(fp_valid.mean()) if len(fp_valid) > 0 else None,
            }
        )
    return out


def compute_diversity(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gen, g in df.groupby("generation"):
        rows.append(
            {
                "generation": int(gen),
                "n_nodes_mean": float(g["n_nodes"].mean()),
                "n_nodes_std": float(g["n_nodes"].std()) if len(g) > 1 else 0.0,
                "active_clause_mean": float(g["active_clause"].mean()),
                "active_clause_unique": int(g["active_clause"].nunique()),
            }
        )
    return rows


def compute_penalty_effect(df: pd.DataFrame) -> dict[str, Any]:
    valid = df[compute_valid_mask(df)]
    raw_pos = valid[valid["trade_sharpe_raw"] > 0]
    return {
        "n_raw_positive": int(len(raw_pos)),
        "n_raw_positive_and_penalty_killed": int((raw_pos["fitness_pen"] <= 0).sum()),
        "n_raw_positive_and_pass": int((raw_pos["fitness_pen"] > 0).sum()),
    }


def compute_plateau_length(df: pd.DataFrame) -> tuple[int, int | None]:
    """best fitness_pen plateau 長と plateau 開始世代 (R2-W3 対応: math.isclose)."""
    valid = df[compute_valid_mask(df)]
    if len(valid) == 0:
        return 0, None
    by_gen = valid.groupby("generation")["fitness_pen"].max().sort_index()
    if len(by_gen) < 2:
        return 0, None
    last_value = float(by_gen.iloc[-1])
    plateau = 0
    plateau_start: int | None = None
    for gen, v in reversed(list(by_gen.items())):
        if math.isclose(float(v), last_value, abs_tol=1e-12):
            plateau += 1
            plateau_start = int(gen)
        else:
            break
    return plateau, plateau_start


def compute_extra_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """raw_positive_count / sentinel_by_generation / best_generation 等 (R2-Sg2)."""
    valid = df[compute_valid_mask(df)]
    raw_positive_count = int((valid["trade_sharpe_raw"] > 0).sum())
    fitness_pen_positive_count = int((valid["fitness_pen"] > 0).sum())

    sentinel_grouped = (
        df[df["fitness_pen"] <= SENTINEL_THRESHOLD].groupby("generation").size().to_dict()
    )
    sentinel_by_gen = {int(k): int(v) for k, v in sentinel_grouped.items()}

    best_generation: int | None = None
    if len(valid) > 0:
        best_idx = valid["fitness_pen"].idxmax()
        best_generation = int(valid.loc[best_idx, "generation"])

    return {
        "raw_positive_count": raw_positive_count,
        "fitness_pen_positive_count": fitness_pen_positive_count,
        "sentinel_by_generation": sentinel_by_gen,
        "best_generation": best_generation,
    }


def compute_data_quality(df: pd.DataFrame, warnings_list: list[str]) -> dict[str, Any]:
    valid = df[compute_valid_mask(df)]
    total_sentinel = int((df["fitness_pen"] <= SENTINEL_THRESHOLD).sum())
    return {
        "n_total": int(len(df)),
        "n_valid": int(len(valid)),
        "sentinel_breakdown": {
            "total_sentinel_individuals": total_sentinel,
            "note": (
                "T034 sentinel 値は全て -1e9 で同一、 archive に Stage A reason_codes 列なしのため "
                "NO_EXPOSURE / METRIC_UNAVAILABLE / SYSTEM_FAILURE の内訳分離不能"
            ),
        },
        "warnings": warnings_list,
    }


# ---------------------------------------------------------------------------
# 分類判定
# ---------------------------------------------------------------------------


def diagnose_root_cause(
    decomposition: dict[str, Any],
    diversity: list[dict[str, Any]],
    penalty_effect: dict[str, Any],
    *,
    n_valid: int,
    run_effective_config: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    """(P1) primitive / (P2) penalty / (P3) 探索 dynamics / INCONCLUSIVE 判定.

    config 取得不能時は P3 を `non_evaluable` 化 + confidence cap medium。
    """
    rationale: list[str] = []
    falsification: dict[str, Any] = {}
    raw_max = decomposition.get("trade_sharpe_raw", {}).get("max")
    confidence_cap = "high"
    evaluated_hypotheses: list[str] = []

    # P1: primitive 不足
    p1_match = raw_max is not None and raw_max < P1_RAW_MAX_THRESHOLD
    falsification["P1"] = {
        "condition": f"raw_max < {P1_RAW_MAX_THRESHOLD}",
        "actual": raw_max,
        "match": p1_match,
        "rationale": P1_RATIONALE if p1_match else None,
    }
    evaluated_hypotheses.append("P1")

    # P2: penalty / config (= 比率併用閾値、 R1-W1 対応)
    p2_threshold = max(P2_BASE_THRESHOLD, math.ceil(P2_RATIO_THRESHOLD * n_valid))
    p2_killed = penalty_effect["n_raw_positive_and_penalty_killed"]
    p2_match = p2_killed >= p2_threshold
    falsification["P2"] = {
        "condition": (
            f"penalty_killed >= max({P2_BASE_THRESHOLD}, "
            f"ceil({P2_RATIO_THRESHOLD}*N_valid={n_valid})) = {p2_threshold}"
        ),
        "actual": p2_killed,
        "match": p2_match,
    }
    evaluated_hypotheses.append("P2")

    # P3: 探索 dynamics (= R1-Cr1 / R2-Cr1 対応、 max_clause<=1 で N/A)
    max_clause_config = run_effective_config.get("max_clause")
    if max_clause_config is None:
        falsification["P3"] = {
            "condition": "n_nodes std drop > 0.5 ∧ active_clause unique == 1",
            "actual": "non_evaluable",
            "match": False,
            "non_evaluable_reason": "summary.json から max_clause 取得不能",
        }
        p3_match = False
        confidence_cap = "medium"
    elif max_clause_config <= 1:
        falsification["P3"] = {
            "condition": "n_nodes std drop > 0.5 ∧ active_clause unique == 1",
            "actual": "non_evaluable",
            "match": False,
            "non_evaluable_reason": (
                f"run-effective config max_clause={max_clause_config} <= 1 のため "
                "active_clause unique==1 は config 由来の擬陽性、 P3 識別力なし"
            ),
        }
        p3_match = False
    elif diversity:
        first_std = diversity[0]["n_nodes_std"]
        last_std = diversity[-1]["n_nodes_std"]
        active_unique = diversity[-1]["active_clause_unique"]
        std_drop = first_std - last_std
        p3_match = std_drop > P3_STD_DROP_THRESHOLD and active_unique == 1
        falsification["P3"] = {
            "condition": (
                f"n_nodes std drop > {P3_STD_DROP_THRESHOLD} ∧ "
                "active_clause unique == 1"
            ),
            "actual": {"std_drop": std_drop, "active_unique": active_unique},
            "match": p3_match,
        }
        evaluated_hypotheses.append("P3")
    else:
        p3_match = False

    # 集約 + 信頼度
    matches = [m for m, ok in [("P1", p1_match), ("P2", p2_match), ("P3", p3_match)] if ok]
    if len(matches) == 1:
        diagnosis = matches[0]
        confidence = "high" if confidence_cap == "high" else confidence_cap
    elif len(matches) > 1:
        diagnosis = "INCONCLUSIVE"
        confidence = "low"
        rationale.append(f"複数仮説該当: {matches} = 1 つに絞れず")
    else:
        diagnosis = "INCONCLUSIVE"
        confidence = "low"
        rationale.append("どの仮説にも明確該当せず")

    return diagnosis, rationale, {
        "confidence": confidence,
        "falsification": falsification,
        "evaluated_hypotheses": evaluated_hypotheses,
        "config_source": run_effective_config.get("_source", "unknown"),
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(payload: dict[str, Any]) -> str:
    """payload から human-readable Markdown レポートを構築."""
    lines: list[str] = []
    lines.append(f"# Stage A Root Cause Diagnostic: {payload['run_id']}")
    lines.append("")
    lines.append(f"- **run_number**: {payload['run_number']}")
    lines.append(f"- **diagnosis**: **{payload['diagnosis']}**")
    lines.append(f"- **confidence**: {payload['confidence']}")
    lines.append(f"- **config_source**: {payload['config_source']}")
    lines.append(f"- **evaluated_hypotheses**: {payload['evaluated_hypotheses']}")
    lines.append("")

    lines.append("## サマリー")
    sp = payload["stage_pass_counts"]
    lines.append(
        f"- Stage A pass: {sp['a']} / B pass: {sp['b']} / C pass: {sp['c']}"
    )
    lines.append(
        f"- best generation: {payload['extra_metrics']['best_generation']}"
    )
    lines.append(
        f"- best plateau length: {payload['plateau_length']} (start gen: {payload['plateau_start_generation']})"
    )
    lines.append("")

    lines.append("## 分類判定 (= 反証結果)")
    for hyp in ("P1", "P2", "P3"):
        f = payload["falsification"].get(hyp, {})
        lines.append(f"- **{hyp}**:")
        lines.append(f"  - condition: `{f.get('condition', '?')}`")
        lines.append(f"  - actual: `{f.get('actual', '?')}`")
        lines.append(f"  - match: **{f.get('match', '?')}**")
        if f.get("non_evaluable_reason"):
            lines.append(f"  - non_evaluable_reason: {f['non_evaluable_reason']}")
        if f.get("rationale"):
            lines.append(f"  - rationale: {f['rationale']}")
    lines.append("")

    if payload["diagnosis_rationale"]:
        lines.append("## 判定理由")
        for r in payload["diagnosis_rationale"]:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("## fitness_pen 分解")
    decomp = payload["fitness_pen_decomposition"]
    lines.append("| 統計量 | trade_sharpe_raw | size_norm (逆算) | penalty | fitness_pen |")
    lines.append("|---|---|---|---|---|")
    for stat in ("max", "mean", "std"):
        row = [stat]
        for col in ("trade_sharpe_raw", "size_norm_inferred", "penalty", "fitness_pen"):
            v = decomp.get(col, {}).get(stat)
            row.append(f"{v:.6f}" if v is not None else "—")
        lines.append("| " + " | ".join(row) + " |")
    if decomp.get("_size_norm_note"):
        lines.append(f"")
        lines.append(f"_注: {decomp['_size_norm_note']} (alpha={decomp.get('_alpha_used')})_")
    lines.append("")

    lines.append("## trade_sharpe_raw 世代別")
    lines.append("| generation | n | max | mean | median | n_positive |")
    lines.append("|---|---|---|---|---|---|")
    for r in payload["trade_sharpe_by_generation"]:
        lines.append(
            f"| {r['generation']} | {r['n']} | "
            f"{r['max']:.4f if isinstance(r['max'], float) else 'NaN'} | "
            f"{r['mean']:.4f if isinstance(r['mean'], float) else 'NaN'} | "
            f"{r['median']:.4f if isinstance(r['median'], float) else 'NaN'} | "
            f"{r['n_positive']} |"
        ) if False else lines.append(
            f"| {r['generation']} | {r['n']} | "
            f"{('%.4f' % r['max']) if r['max'] is not None else '—'} | "
            f"{('%.4f' % r['mean']) if r['mean'] is not None else '—'} | "
            f"{('%.4f' % r['median']) if r['median'] is not None else '—'} | "
            f"{r['n_positive']} |"
        )
    lines.append("")

    lines.append("## trade_count バケット別")
    lines.append("| バケット | n | trade_sharpe mean | fitness_pen mean |")
    lines.append("|---|---|---|---|")
    for r in payload["trade_count_buckets"]:
        lines.append(
            f"| {r['bucket']} | {r['n']} | "
            f"{('%.4f' % r['trade_sharpe_mean']) if r['trade_sharpe_mean'] is not None else '—'} | "
            f"{('%.4f' % r['fitness_pen_mean']) if r['fitness_pen_mean'] is not None else '—'} |"
        )
    lines.append("")

    lines.append("## diversity (n_nodes / active_clause 推移)")
    lines.append("| generation | n_nodes mean | n_nodes std | active_clause mean | active_clause unique |")
    lines.append("|---|---|---|---|---|")
    for r in payload["diversity"]:
        lines.append(
            f"| {r['generation']} | {r['n_nodes_mean']:.2f} | "
            f"{r['n_nodes_std']:.3f} | {r['active_clause_mean']:.2f} | "
            f"{r['active_clause_unique']} |"
        )
    lines.append("")

    lines.append("## penalty 効果")
    pe = payload["penalty_effect"]
    lines.append(f"- raw>0 個体数: {pe['n_raw_positive']}")
    lines.append(f"- raw>0 ∧ fitness_pen<=0 (= penalty で潰された): {pe['n_raw_positive_and_penalty_killed']}")
    lines.append(f"- raw>0 ∧ fitness_pen>0 (= 通過候補): {pe['n_raw_positive_and_pass']}")
    lines.append("")

    lines.append("## extra_metrics")
    em = payload["extra_metrics"]
    lines.append(f"- raw_positive_count: {em['raw_positive_count']}")
    lines.append(f"- fitness_pen_positive_count: {em['fitness_pen_positive_count']}")
    lines.append(f"- sentinel_by_generation: {em['sentinel_by_generation']}")
    lines.append("")

    lines.append("## data_quality")
    dq = payload["data_quality"]
    lines.append(f"- n_valid / n_total: {dq['n_valid']} / {dq['n_total']}")
    lines.append(
        f"- sentinel 個体数: {dq['sentinel_breakdown']['total_sentinel_individuals']}"
    )
    lines.append(f"  - {dq['sentinel_breakdown']['note']}")
    if dq.get("warnings"):
        lines.append("- warnings:")
        for w in dq["warnings"]:
            lines.append(f"  - {w}")
    lines.append("")

    lines.append("## run_effective_config (= audit trail)")
    rec = payload["run_effective_config"]
    lines.append(f"- _source: {rec.get('_source')}")
    lines.append(f"- summary_path: {rec.get('_summary_path')}")
    lines.append(f"- summary_run_id: {rec.get('summary_run_id')}")
    lines.append(f"- max_clause: {rec.get('max_clause')}")
    lines.append(f"- stage_a_alpha: {rec.get('stage_a_alpha')}")
    lines.append(f"- stage_a_threshold: {rec.get('stage_a_threshold')}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="Stage A root cause diagnostic")
    p.add_argument("--run-id", required=True, help="例: run_20260504_032451")
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()

    archive_path = ARCHIVE_DIR / f"genomes_{args.run_id}.parquet"
    if not archive_path.exists():
        print(f"[error] archive not found: {archive_path}", file=sys.stderr)
        return 2

    df = pq.read_table(archive_path).to_pandas()

    # run_number 解決
    run_number: int | None = None
    if "run_number" in df.columns and len(df) > 0:
        run_number = int(df["run_number"].iloc[0])

    # output_dir 確定
    if args.output_dir is not None:
        out_dir = args.output_dir
    elif run_number is not None:
        out_dir = RUN_REPORTS_DIR / f"run-{run_number}" / "diagnostics"
    else:
        print("[error] run_number 解決不能、 --output-dir を明示してください", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    # run-effective config 取得
    if run_number is not None:
        run_effective_config, warnings_list = load_run_effective_config(run_number)
    else:
        run_effective_config = {
            "_source": "fallback_default",
            "max_clause": None,
            "stage_a_alpha": None,
            "stage_a_threshold": None,
        }
        warnings_list = ["run_number 解決不能、 fallback_default 使用"]

    # R3-W1: summary.run_id == archive.run_id 検証
    summary_run_id = run_effective_config.get("summary_run_id")
    summary_run_id_matched = summary_run_id == args.run_id
    if not summary_run_id_matched and summary_run_id is not None:
        warnings_list.append(
            f"summary.run_id ({summary_run_id}) != archive run_id ({args.run_id}) "
            "= run_id 取り違えの可能性、 P3 判定を degrade"
        )
        # provenance 不一致は P3 を config_unavailable に degrade
        run_effective_config["max_clause"] = None

    alpha = run_effective_config.get("stage_a_alpha")

    # 集計
    decomposition = compute_fitness_pen_decomposition(df, alpha)
    by_gen = compute_trade_sharpe_by_generation(df)
    buckets = compute_trade_count_buckets(df)
    diversity = compute_diversity(df)
    penalty_effect = compute_penalty_effect(df)
    plateau_length, plateau_start = compute_plateau_length(df)
    extra_metrics = compute_extra_metrics(df)
    data_quality = compute_data_quality(df, warnings_list)

    # 分類判定
    diagnosis, rationale, judge_meta = diagnose_root_cause(
        decomposition,
        diversity,
        penalty_effect,
        n_valid=data_quality["n_valid"],
        run_effective_config=run_effective_config,
    )

    payload: dict[str, Any] = {
        "run_id": args.run_id,
        "run_number": run_number,
        "diagnosis": diagnosis,
        "confidence": judge_meta["confidence"],
        "config_source": judge_meta["config_source"],
        "evaluated_hypotheses": judge_meta["evaluated_hypotheses"],
        "diagnosis_rationale": rationale,
        "falsification": judge_meta["falsification"],
        "plateau_length": plateau_length,
        "plateau_start_generation": plateau_start,
        "stage_pass_counts": {
            "a": int((df["stage_a_pass"] == True).sum()),  # noqa: E712
            "b": int((df["stage_b_pass"] == True).sum()),  # noqa: E712
            "c": int((df["stage_c_pass"] == True).sum()),  # noqa: E712
        },
        "fitness_pen_decomposition": decomposition,
        "trade_sharpe_by_generation": by_gen,
        "trade_count_buckets": buckets,
        "diversity": diversity,
        "penalty_effect": penalty_effect,
        "extra_metrics": extra_metrics,
        "data_quality": data_quality,
        "run_effective_config": run_effective_config,
        "summary_run_id_matched": summary_run_id_matched,
    }

    json_path = out_dir / "stage_a_root_cause.json"
    md_path = out_dir / "stage_a_root_cause.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(
        f"[done] diagnosis={diagnosis} confidence={judge_meta['confidence']} "
        f"run={args.run_id} run_number={run_number}"
    )
    print(f"  -> {md_path}")
    print(f"  -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
