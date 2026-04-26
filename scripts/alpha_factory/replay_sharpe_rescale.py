"""T042: trade-level Sharpe → annualized Sharpe 換算 replay (Phase 0)。

archive Parquet (genomes_*.parquet) を読み、population 統計と換算後の
annualized Sharpe 分布を計算して JSON に書き出す。

換算式 (Phase 0 minimum, no autocorrelation correction):

    S_annual ≈ S_trade × sqrt(λ_day × 252)

ただし λ_day = trade_count / window_days_a (Stage A 観測 window)。
完全 Lo (2002) 式の自己相関補正 (adj_corr) は Phase 1+ で trade-level
時系列を archive に格納できる段階で導入する (詳細:
docs/alpha_factory/sharpe-rescale.md)。

学術引用:
- Andrew W. Lo (2002), "The Statistics of Sharpe Ratios",
  Financial Analysts Journal 58(4), 36-52. trade-level → annualized 換算と
  自己相関補正の標準的定式化。

USAGE:
    uv run python scripts/alpha_factory/replay_sharpe_rescale.py \\
        --parquet .cache/alpha_factory/runs/genomes_run_20260425_235717.parquet \\
        --window-days 60 \\
        --target-pass-rate 0.15 \\
        --output reports/sharpe-rescale/run-16-distribution.json
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Stage A 観測 window のデフォルト (config/alpha_factory/default.yaml と同期)。
# replay 専用ヘルパで yaml 読みは強制しない (CI/解析用途で軽量)。
DEFAULT_WINDOW_DAYS_A: int = 60
TRADING_DAYS_PER_YEAR: int = 252


@dataclass(frozen=True)
class AnnualizationResult:
    """個体ごとの換算結果."""

    trade_sharpe_raw: float
    trade_count: int
    lambda_day: float
    sharpe_annualized: float


def annualize_trade_sharpe(
    trade_sharpe_raw: float,
    trade_count: int,
    window_days: int,
) -> float | None:
    """trade-level Sharpe を annualized Sharpe に換算する。

    Args:
        trade_sharpe_raw: trade-level Sharpe ratio (μ_trade / σ_trade)。
        trade_count: 観測 window 内の trade 数。
        window_days: 観測 window 日数 (Stage A は 60)。

    Returns:
        年率換算 Sharpe。trade_count <= 0 または window_days <= 0、
        trade_sharpe_raw が NaN/inf の場合 None。
    """
    if window_days <= 0 or trade_count <= 0:
        return None
    if trade_sharpe_raw is None:
        return None
    if not math.isfinite(trade_sharpe_raw):
        return None
    lambda_day = trade_count / window_days
    return trade_sharpe_raw * math.sqrt(lambda_day * TRADING_DAYS_PER_YEAR)


def annualize_population(
    rows: list[dict[str, Any]],
    window_days: int,
) -> list[AnnualizationResult]:
    """archive 行の population 全体を換算した結果を返す。

    trade_count <= 0 または trade_sharpe_raw が None/NaN の行はスキップ。
    """
    results: list[AnnualizationResult] = []
    for r in rows:
        ts = r.get("trade_sharpe_raw")
        tc = r.get("trade_count")
        if ts is None or tc is None or tc <= 0:
            continue
        if not isinstance(ts, int | float):
            continue
        if not math.isfinite(float(ts)):
            continue
        s_ann = annualize_trade_sharpe(float(ts), int(tc), window_days)
        if s_ann is None:
            continue
        lambda_day = int(tc) / window_days
        results.append(
            AnnualizationResult(
                trade_sharpe_raw=float(ts),
                trade_count=int(tc),
                lambda_day=lambda_day,
                sharpe_annualized=s_ann,
            )
        )
    return results


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    s = sorted(values)
    n = len(s)

    def q(p: float) -> float:
        idx = max(0, min(n - 1, round((n - 1) * p)))
        return s[idx]

    return {
        "n": n,
        "min": s[0],
        "q25": q(0.25),
        "median": q(0.50),
        "q75": q(0.75),
        "q85": q(0.85),
        "q95": q(0.95),
        "max": s[-1],
        "mean": sum(s) / n,
    }


def summarize(
    results: list[AnnualizationResult],
    target_pass_rate: float,
) -> dict[str, Any]:
    """換算結果の population 統計と target_pass_rate 達成しきい値を出す。"""
    trade_sharpes = [r.trade_sharpe_raw for r in results]
    annualized = [r.sharpe_annualized for r in results]
    lambda_days = [r.lambda_day for r in results]

    summary: dict[str, Any] = {
        "n_individuals": len(results),
        "trade_sharpe_raw": _quantiles(trade_sharpes),
        "sharpe_annualized": _quantiles(annualized),
        "lambda_day": _quantiles(lambda_days),
        "target_pass_rate": target_pass_rate,
    }

    if results:
        # target_pass_rate=0.15 なら 85%ile (上位 15% が pass する閾値)
        n = len(results)
        s_sorted = sorted(trade_sharpes)
        pass_idx = round((n - 1) * (1.0 - target_pass_rate))
        summary["recommended_stage_a_threshold_trade_level"] = s_sorted[pass_idx]
        a_sorted = sorted(annualized)
        summary["recommended_threshold_annualized"] = a_sorted[pass_idx]
    return summary


def _read_archive(parquet_path: Path) -> list[dict[str, Any]]:
    """Parquet を Python list[dict] にロード。pyarrow 必須。"""
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path)
    return list(table.to_pylist())


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Trade-level Sharpe → annualized 換算 replay (T042)",
    )
    p.add_argument(
        "--parquet",
        type=Path,
        required=True,
        help="archive Parquet path (genomes_*.parquet)",
    )
    p.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS_A,
        help="Stage A 観測 window 日数 (default: 60)",
    )
    p.add_argument(
        "--target-pass-rate",
        type=float,
        default=0.15,
        help="Stage A target_pass_rate (default: 0.15)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="出力 JSON path (省略時 stdout)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.parquet.exists():
        print(f"[error] parquet not found: {args.parquet}")
        return 2

    rows = _read_archive(args.parquet)
    results = annualize_population(rows, window_days=args.window_days)
    summary = summarize(results, target_pass_rate=args.target_pass_rate)
    summary["source_parquet"] = str(args.parquet)
    summary["window_days"] = args.window_days
    summary["formula"] = (
        "S_annual ≈ S_trade × sqrt((trade_count / window_days) × 252)"
    )
    summary["formula_caveat"] = (
        "no autocorrelation correction (Phase 0 minimum). "
        "Lo (2002) 完全式は trade-level 時系列を archive に格納する Phase 1+ で導入。"
    )

    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output is None:
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"[ok] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
