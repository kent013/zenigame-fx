"""T045: Stage B WF fold per-individual inspection CLI.

archive Parquet から Stage B 通過個体を選び、Stage B WF backtest を再実行して
fold ごとの (start, end, n_trade, sum_pnl, oos_sharpe) を tabulate する。
「per-fold で 80% positive sharpe なのに total negative」の物理的説明を切り分け。

詳細: devnotes/20260427-0100-investigate-stageb-pnl-negative/
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

# run_ga 内 helper を直接 import (load bars + meta + bt factory)
from scripts.alpha_factory.run_ga import (  # noqa: E402
    _load_lane_bars,
    _make_bt_factory,
)
from src.alpha_factory.config import load_config  # noqa: E402
from src.alpha_factory.primitives import (  # noqa: E402
    RegistryEvaluator,
    ensure_registered,
)
from src.alpha_factory.walk_forward import make_wf_folds  # noqa: E402
from src.backtest.engine import run_backtest  # noqa: E402
from src.backtest.metrics import compute_metrics  # noqa: E402
from src.broker.mock import MockBroker  # noqa: E402
from src.dsl import genome_from_dict  # noqa: E402
from src.dsl.strategy import DslStrategy  # noqa: E402


def _load_archive_rows(parquet_path: Path) -> list[dict[str, Any]]:
    return list(pq.read_table(parquet_path).to_pylist())


def _pick_individuals(
    rows: list[dict[str, Any]],
    *,
    top: int,
    only_b_pass: bool,
) -> list[dict[str, Any]]:
    """fitness_pen 降順 top N (default は Stage B passing のみ)."""
    candidates = [r for r in rows if (not only_b_pass) or r.get("stage_b_pass")]
    candidates = [r for r in candidates if r.get("genome_json")]
    candidates.sort(
        key=lambda r: r.get("fitness_pen") or float("-inf"), reverse=True
    )
    return candidates[:top]


def inspect_one(
    *,
    rec: dict[str, Any],
    bars_18m: list,
    meta,
    backtest_config,
    primitive_evaluator: RegistryEvaluator,
    stage_cfg,
) -> str:
    """1 個体の WF fold を再実行して Markdown 表を返す."""
    name = rec.get("individual_name", "?")
    fitness_pen = rec.get("fitness_pen")
    archived_pnl = rec.get("total_pnl")
    archived_sharpe_a = rec.get("trade_sharpe_raw")
    archived_sharpe_b = rec.get("trade_sharpe_stage_b")
    pos_fold_ratio = rec.get("positive_fold_ratio_effective")

    genome_dict = json.loads(rec["genome_json"])
    genome = genome_from_dict(genome_dict)

    folds = make_wf_folds(
        bars_18m,
        train_days=stage_cfg.wf_train_days,
        test_days=stage_cfg.wf_test_days,
        step_days=stage_cfg.wf_step_days,
        embargo_days=stage_cfg.wf_embargo_days,
    )

    lines = [
        f"## Individual {name}",
        "",
        f"- archived fitness_pen: {fitness_pen}",
        f"- archived trade_sharpe_raw (Stage A): {archived_sharpe_a}",
        f"- archived trade_sharpe_stage_b (T044): {archived_sharpe_b}",
        f"- archived total_pnl: {archived_pnl}",
        f"- archived positive_fold_ratio_effective: {pos_fold_ratio}",
        f"- n_folds (re-computed): {len(folds)}",
        "",
        "| fold | start (UTC) | end (UTC) | n_bars | n_trade | sum_pnl | oos_sharpe |",
        "|-----:|-------------|-----------|-------:|--------:|--------:|-----------:|",
    ]

    fold_pnls: list[float] = []
    fold_sharpes: list[float] = []

    for i, (_train, test_bars) in enumerate(folds):
        if not test_bars:
            lines.append(f"| {i} | - | - | 0 | 0 | 0.00 | n/a |")
            continue
        try:
            strategy = DslStrategy(genome, primitive_evaluator)
            broker = MockBroker(instrument_meta=meta)
            res = run_backtest(test_bars, strategy, broker, backtest_config)
        except Exception as exc:
            lines.append(
                f"| {i} | {test_bars[0].bar_time} | {test_bars[-1].bar_time} | "
                f"{len(test_bars)} | err | err | err: {type(exc).__name__} |"
            )
            continue
        bt = compute_metrics(
            res.trades,
            res.equity_curve,
            trade_count_min_for_sharpe=stage_cfg.trade_count_min_for_sharpe,
        )
        n_trade = bt.trade_count
        sum_pnl = float(bt.total_pnl)
        oos_sharpe = (
            float(bt.trade_sharpe_raw)
            if bt.trade_sharpe_raw is not None
            else None
        )
        fold_pnls.append(sum_pnl)
        if oos_sharpe is not None:
            fold_sharpes.append(oos_sharpe)
        sharpe_str = f"{oos_sharpe:+.4f}" if oos_sharpe is not None else "n/a"
        lines.append(
            f"| {i} | {test_bars[0].bar_time} | {test_bars[-1].bar_time} | "
            f"{len(test_bars)} | {n_trade} | {sum_pnl:+.2f} | {sharpe_str} |"
        )

    total_pnl_sum = sum(fold_pnls)
    if fold_sharpes:
        sorted_s = sorted(fold_sharpes)
        median_sharpe = sorted_s[len(sorted_s) // 2]
        n_pos = sum(1 for s in fold_sharpes if s > 0)
        lines.append(
            f"| **sum** | | | | | **{total_pnl_sum:+.2f}** | "
            f"median **{median_sharpe:+.4f}** "
            f"({n_pos}/{len(fold_sharpes)} positive) |"
        )
    else:
        lines.append(
            f"| **sum** | | | | | **{total_pnl_sum:+.2f}** | n/a |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="T045: Stage B WF fold inspection",
    )
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "config" / "alpha_factory" / "default.yaml",
    )
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--all-b-pass", action="store_true")
    parser.add_argument("--include-non-b-pass", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.parquet.exists():
        print(f"[error] parquet not found: {args.parquet}", file=sys.stderr)
        return 2
    cfg = load_config(args.config)
    rows = _load_archive_rows(args.parquet)
    only_b = not args.include_non_b_pass
    top = 10**6 if args.all_b_pass else args.top
    picked = _pick_individuals(rows, top=top, only_b_pass=only_b)
    if not picked:
        print("(no candidates)")
        return 0

    print(f"# Stage B fold inspection ({len(picked)} individual(s))")
    print()
    print(f"- parquet: {args.parquet}")
    print(f"- instrument: {cfg.dataset.instrument}")
    print(
        f"- WF: train={cfg.stage_gate.wf_train_days}d "
        f"test={cfg.stage_gate.wf_test_days}d "
        f"step={cfg.stage_gate.wf_step_days}d "
        f"embargo={cfg.stage_gate.wf_embargo_days}d"
    )
    print()

    bundle = _load_lane_bars(
        cfg.dataset.instrument, cfg.dataset, cfg.stage_windows
    )
    bars_18m = bundle.bars_stage_b
    meta = bundle.meta
    bt_factory = _make_bt_factory(cfg.dataset, cfg.backtest)
    bt_cfg = bt_factory(cfg.dataset.instrument)

    ensure_registered()
    primitive_evaluator = RegistryEvaluator(pair=cfg.dataset.instrument)

    for rec in picked:
        report = inspect_one(
            rec=rec,
            bars_18m=bars_18m,
            meta=meta,
            backtest_config=bt_cfg,
            primitive_evaluator=primitive_evaluator,
            stage_cfg=cfg.stage_gate,
        )
        print(report)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
