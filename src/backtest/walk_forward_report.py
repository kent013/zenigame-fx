from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from src.backtest.walk_forward import FoldOutcome, WalkForwardResult, aggregate


def _dec(v: Decimal | None) -> str:
    if v is None:
        return "∞"
    return f"{v:.6f}"


def _params_str(params: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in params.items())


def _row(fold: FoldOutcome) -> str:
    s = fold.slice
    tr = fold.train_metrics
    te = fold.test_metrics
    return (
        f"| {s.index} | {s.train_start.date()}→{s.train_end.date()} | "
        f"{s.test_start.date()}→{s.test_end.date()} | `{_params_str(fold.best_params)}` | "
        f"{_dec(tr.total_pnl)} | {_dec(te.total_pnl)} | "
        f"{_dec(tr.win_rate)} | {_dec(te.win_rate)} | "
        f"{_dec(tr.max_drawdown_pct)} | {_dec(te.max_drawdown_pct)} |"
    )


def render_markdown(result: WalkForwardResult) -> str:
    c = result.config
    agg = aggregate(result)
    lines: list[str] = []
    lines.append(f"# Walk-Forward Report — {c.strategy_name} on {c.instrument}")
    lines.append("")
    lines.append(f"**生成**: {datetime.now(tz=UTC).isoformat()}")
    lines.append("")
    lines.append("## Config")
    lines.append("")
    lines.append(f"- instrument: `{c.instrument}`")
    lines.append(f"- period: `{c.start.isoformat()}` → `{c.end.isoformat()}`")
    lines.append(f"- initial_cash: {_dec(c.initial_cash)}")
    lines.append(f"- leverage: {c.leverage}x")
    lines.append(f"- strategy: `{c.strategy_name}`")
    lines.append(f"- mode: `{c.mode}` / train={c.train_days}d test={c.test_days}d step={c.step_days}d")
    lines.append("")
    lines.append("## Parameter Grid")
    lines.append("")
    for k, vs in c.parameter_grid.items():
        lines.append(f"- `{k}`: {list(vs)}")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append("| 指標 | 値 |")
    lines.append("|------|----|")
    lines.append(f"| folds | {len(result.folds)} |")
    lines.append(f"| train_total_pnl | {_dec(agg['train_total_pnl'])} |")
    lines.append(f"| test_total_pnl | {_dec(agg['test_total_pnl'])} |")
    lines.append(f"| train_win_rate_avg | {_dec(agg['train_win_rate_avg'])} |")
    lines.append(f"| test_win_rate_avg | {_dec(agg['test_win_rate_avg'])} |")
    lines.append(f"| train_max_dd_pct_max | {_dec(agg['train_max_dd_pct_max'])} |")
    lines.append(f"| test_max_dd_pct_max | {_dec(agg['test_max_dd_pct_max'])} |")
    lines.append(f"| overfit_score | {_dec(agg['overfit_score'])} |")
    lines.append("")
    lines.append("## Folds")
    lines.append("")
    lines.append(
        "| # | train | test | best_params | train_pnl | test_pnl | train_wr | test_wr | train_dd% | test_dd% |"
    )
    lines.append(
        "|---|-------|------|-------------|-----------|----------|----------|---------|-----------|----------|"
    )
    for fold in result.folds:
        lines.append(_row(fold))
    return "\n".join(lines) + "\n"


def _fold_to_dict(fold: FoldOutcome) -> dict:
    return {
        "index": fold.slice.index,
        "train_start": fold.slice.train_start.isoformat(),
        "train_end": fold.slice.train_end.isoformat(),
        "test_start": fold.slice.test_start.isoformat(),
        "test_end": fold.slice.test_end.isoformat(),
        "best_params": fold.best_params,
        "train_metrics": {
            "trade_count": fold.train_metrics.trade_count,
            "total_pnl": str(fold.train_metrics.total_pnl),
            "win_rate": str(fold.train_metrics.win_rate),
            "max_drawdown_pct": str(fold.train_metrics.max_drawdown_pct),
        },
        "test_metrics": {
            "trade_count": fold.test_metrics.trade_count,
            "total_pnl": str(fold.test_metrics.total_pnl),
            "win_rate": str(fold.test_metrics.win_rate),
            "max_drawdown_pct": str(fold.test_metrics.max_drawdown_pct),
        },
    }


def write_walk_forward_report(result: WalkForwardResult, root: Path | None = None) -> Path:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    root_dir = root or Path("reports/walk-forwards")
    out_dir = root_dir / f"wf-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    md = render_markdown(result)
    (out_dir / "result.md").write_text(md, encoding="utf-8")

    agg = aggregate(result)
    payload = {
        "config": {
            "instrument": result.config.instrument,
            "start": result.config.start.isoformat(),
            "end": result.config.end.isoformat(),
            "initial_cash": str(result.config.initial_cash),
            "leverage": result.config.leverage,
            "strategy_name": result.config.strategy_name,
            "parameter_grid": {k: list(v) for k, v in result.config.parameter_grid.items()},
            "train_days": result.config.train_days,
            "test_days": result.config.test_days,
            "step_days": result.config.step_days,
            "mode": result.config.mode,
        },
        "aggregate": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in agg.items()},
        "folds": [_fold_to_dict(f) for f in result.folds],
    }
    (out_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir
