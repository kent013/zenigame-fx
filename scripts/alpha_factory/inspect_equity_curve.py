"""T048: max_drawdown=0 多発調査用 equity_curve dump CLI.

archive Parquet から個体を選び、Stage A/B/C いずれかの backtest を再実行して
equity_curve を dump し、max_drawdown=0 の物理的説明を可視化する。

Usage:
    uv run python scripts/alpha_factory/inspect_equity_curve.py \\
        --parquet .cache/alpha_factory/runs/genomes_run_*.parquet \\
        --individual g22_i33 --stage a

詳細: devnotes/20260427-0100-investigate-max-drawdown-zero/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.alpha_factory.run_ga import (  # noqa: E402
    _load_lane_bars,
    _make_bt_factory,
)
from src.alpha_factory.config import load_config  # noqa: E402
from src.alpha_factory.primitives import (  # noqa: E402
    RegistryEvaluator,
    ensure_registered,
)
from src.backtest.engine import run_backtest  # noqa: E402
from src.backtest.metrics import compute_metrics  # noqa: E402
from src.broker.mock import MockBroker  # noqa: E402
from src.dsl import genome_from_dict  # noqa: E402
from src.dsl.strategy import DslStrategy  # noqa: E402


def _load_archive_rows(parquet_path: Path) -> list[dict[str, Any]]:
    return list(pq.read_table(parquet_path).to_pylist())


def _find_individual(
    rows: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    for r in rows:
        if r.get("individual_name") == name:
            return r
    return None


def _select_bars(bundle, stage: str) -> list:
    if stage == "a":
        return bundle.bars_stage_a
    if stage == "b":
        return bundle.bars_stage_b
    if stage == "c":
        return bundle.bars_holdout
    raise ValueError(f"unknown stage: {stage!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T048: equity_curve dump")
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "config" / "alpha_factory" / "default.yaml",
    )
    parser.add_argument("--individual", type=str, required=True)
    parser.add_argument("--stage", choices=["a", "b", "c"], default="a")
    parser.add_argument(
        "--max-points",
        type=int,
        default=200,
        help="equity_curve サンプリング上限 (default: 200)",
    )
    args = parser.parse_args(argv)

    if not args.parquet.exists():
        print(f"[error] parquet not found: {args.parquet}", file=sys.stderr)
        return 2
    cfg = load_config(args.config)
    rows = _load_archive_rows(args.parquet)
    rec = _find_individual(rows, args.individual)
    if rec is None:
        print(f"[error] individual not found: {args.individual}", file=sys.stderr)
        return 3
    if not rec.get("genome_json"):
        print(f"[error] genome_json missing for {args.individual}", file=sys.stderr)
        return 4

    bundle = _load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )
    bars = _select_bars(bundle, args.stage)
    bt_factory = _make_bt_factory(cfg.dataset, cfg.backtest)
    bt_cfg = bt_factory(cfg.dataset.instrument)

    ensure_registered()
    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)

    genome = genome_from_dict(json.loads(rec["genome_json"]))
    strategy = DslStrategy(genome, primitive_evaluator)
    broker = MockBroker(instrument_meta=bundle.meta)
    res = run_backtest(bars, strategy, broker, bt_cfg)
    bt = compute_metrics(
        res.trades,
        res.equity_curve,
        trade_count_min_for_sharpe=cfg.stage_gate.trade_count_min_for_sharpe,
    )

    # equity_curve sampling
    eq = list(res.equity_curve)
    if not eq:
        print("(equity_curve is empty)")
        return 0

    n = len(eq)
    step = max(1, n // args.max_points)
    sampled = eq[::step]

    print(f"# Equity Curve Inspection — {args.individual} (Stage {args.stage.upper()})")
    print()
    print(f"- archive max_drawdown_pct: {rec.get('max_drawdown_pct')}")
    print(f"- archive trade_count: {rec.get('trade_count')}")
    print("- recomputed metrics:")
    print(f"  - trade_count: {bt.trade_count}")
    print(f"  - total_pnl: {bt.total_pnl}")
    print(f"  - max_drawdown_pct: {bt.max_drawdown_pct}")
    print(f"  - trade_sharpe_raw: {bt.trade_sharpe_raw}")
    print()
    print(f"- equity_curve length: {n} (sampled every {step}th, total {len(sampled)} points)")
    print()
    print("- equity stats:")
    eq_floats = [float(p.equity) if hasattr(p, "equity") else float(p) for p in eq]
    print(f"  - min: {min(eq_floats):.2f}")
    print(f"  - max: {max(eq_floats):.2f}")
    print(f"  - first: {eq_floats[0]:.2f}")
    print(f"  - last: {eq_floats[-1]:.2f}")
    peak = eq_floats[0]
    max_dd = 0.0
    for v in eq_floats:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    print(f"  - manual max_dd_frac: {max_dd:.6f} (= {max_dd * 100:.4f}%)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
