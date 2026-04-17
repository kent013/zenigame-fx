from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from src.backtest.grid_search import GridSearchResult, RunOutcome


def _dec(v: Decimal | None) -> str:
    if v is None:
        return "∞"
    return f"{v:.6f}"


def _params_to_str(params: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in params.items())


def _run_row(rank: int, run: RunOutcome) -> str:
    m = run.metrics
    return (
        f"| {rank} | `{_params_to_str(run.params)}` | {m.trade_count} | "
        f"{_dec(m.win_rate)} | {_dec(m.total_pnl)} | {_dec(m.profit_factor)} | "
        f"{_dec(m.max_drawdown)} | {_dec(m.max_drawdown_pct)} | {_dec(m.final_equity)} |"
    )


def render_markdown(result: GridSearchResult, top_n: int = 20) -> str:
    c = result.config
    lines: list[str] = []
    lines.append(f"# Grid Search Report — {c.strategy_name} on {c.instrument}")
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
    lines.append(f"- runs: {len(result.runs)}")
    lines.append("")
    lines.append("## Parameter Grid")
    lines.append("")
    for k, vs in c.parameter_grid.items():
        lines.append(f"- `{k}`: {list(vs)}")
    lines.append("")
    lines.append(f"## Top {min(top_n, len(result.runs))} by total_pnl")
    lines.append("")
    lines.append(
        "| rank | params | trades | win_rate | total_pnl | profit_factor | max_dd | max_dd_pct | final_equity |"
    )
    lines.append(
        "|------|--------|--------|----------|-----------|---------------|--------|------------|--------------|"
    )
    for rank, run in enumerate(result.runs[:top_n], start=1):
        lines.append(_run_row(rank, run))
    return "\n".join(lines) + "\n"


def _run_to_dict(run: RunOutcome) -> dict:
    m = run.metrics
    return {
        "params": run.params,
        "metrics": {
            "trade_count": m.trade_count,
            "win_count": m.win_count,
            "loss_count": m.loss_count,
            "win_rate": str(m.win_rate),
            "total_pnl": str(m.total_pnl),
            "avg_win": str(m.avg_win),
            "avg_loss": str(m.avg_loss),
            "profit_factor": None if m.profit_factor is None else str(m.profit_factor),
            "max_drawdown": str(m.max_drawdown),
            "max_drawdown_pct": str(m.max_drawdown_pct),
            "final_equity": str(m.final_equity),
        },
    }


def write_comparison_report(result: GridSearchResult, root: Path | None = None, top_n: int = 20) -> Path:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    root_dir = root or Path("reports/grid-searches")
    out_dir = root_dir / f"grid-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    md = render_markdown(result, top_n=top_n)
    (out_dir / "result.md").write_text(md, encoding="utf-8")

    payload = {
        "config": {
            "instrument": result.config.instrument,
            "start": result.config.start.isoformat(),
            "end": result.config.end.isoformat(),
            "initial_cash": str(result.config.initial_cash),
            "leverage": result.config.leverage,
            "strategy_name": result.config.strategy_name,
            "parameter_grid": {k: list(v) for k, v in result.config.parameter_grid.items()},
            "parallel": result.config.parallel,
        },
        "runs": [_run_to_dict(r) for r in result.runs],
    }
    (out_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir
