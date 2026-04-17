from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from src.backtest.ensemble import EnsembleResult, StrategyRun


def _dec(v: Decimal | None) -> str:
    if v is None:
        return "∞"
    return f"{v:.6f}"


def _params_str(params: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in params.items())


def _run_row(run: StrategyRun) -> str:
    m = run.metrics
    return (
        f"| `{run.spec.name}` | `{run.spec.strategy}` | `{_params_str(run.spec.params)}` | "
        f"{_dec(run.capital_allocated)} | {m.trade_count} | {_dec(m.win_rate)} | "
        f"{_dec(m.total_pnl)} | {_dec(m.sharpe)} | {_dec(m.max_drawdown_pct)} | {_dec(m.final_equity)} |"
    )


def render_markdown(result: EnsembleResult) -> str:
    c = result.config
    lines: list[str] = []
    lines.append(f"# Ensemble Report — {c.instrument}")
    lines.append("")
    lines.append(f"**生成**: {datetime.now(tz=UTC).isoformat()}")
    lines.append("")
    lines.append("## Config")
    lines.append("")
    lines.append(f"- instrument: `{c.instrument}`")
    lines.append(f"- period: `{c.start.isoformat()}` → `{c.end.isoformat()}`")
    lines.append(f"- initial_cash (ensemble total): {_dec(c.initial_cash)}")
    lines.append(f"- leverage: {c.leverage}x")
    lines.append(f"- strategies: {len(c.specs)}")
    lines.append("")
    lines.append("## Per-strategy")
    lines.append("")
    lines.append(
        "| label | strategy | params | capital | trades | win_rate | total_pnl | sharpe | max_dd_pct | final_equity |"
    )
    lines.append(
        "|-------|----------|--------|---------|--------|----------|-----------|--------|------------|--------------|"
    )
    for run in result.per_strategy:
        lines.append(_run_row(run))
    lines.append("")
    lines.append("## Combined")
    lines.append("")
    if result.combined_metrics:
        m = result.combined_metrics
        lines.append("| 指標 | 値 |")
        lines.append("|------|----|")
        lines.append(f"| trade_count | {m.trade_count} |")
        lines.append(f"| win_rate | {_dec(m.win_rate)} |")
        lines.append(f"| total_pnl | {_dec(m.total_pnl)} |")
        lines.append(f"| sharpe | {_dec(m.sharpe)} |")
        lines.append(f"| sortino | {_dec(m.sortino)} |")
        lines.append(f"| calmar | {_dec(m.calmar)} |")
        lines.append(f"| max_drawdown_pct | {_dec(m.max_drawdown_pct)} |")
        lines.append(f"| final_equity | {_dec(m.final_equity)} |")
    lines.append("")
    lines.append("## Return correlation (Pearson, upper-triangle)")
    lines.append("")
    lines.append("| pair | corr |")
    lines.append("|------|------|")
    for (a, b), corr in sorted(result.correlation.items()):
        corr_str = "-" if corr is None else f"{corr:.4f}"
        lines.append(f"| `{a}` × `{b}` | {corr_str} |")
    return "\n".join(lines) + "\n"


def _run_to_dict(run: StrategyRun) -> dict:
    m = run.metrics
    return {
        "label": run.spec.name,
        "strategy": run.spec.strategy,
        "params": run.spec.params,
        "capital_allocated": str(run.capital_allocated),
        "trade_count": m.trade_count,
        "total_pnl": str(m.total_pnl),
        "win_rate": str(m.win_rate),
        "sharpe": None if m.sharpe is None else str(m.sharpe),
        "max_drawdown_pct": str(m.max_drawdown_pct),
        "final_equity": str(m.final_equity),
    }


def write_ensemble_report(result: EnsembleResult, root: Path | None = None) -> Path:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    root_dir = root or Path("reports/ensembles")
    out_dir = root_dir / f"ensemble-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    md = render_markdown(result)
    (out_dir / "result.md").write_text(md, encoding="utf-8")

    payload: dict = {
        "config": {
            "instrument": result.config.instrument,
            "start": result.config.start.isoformat(),
            "end": result.config.end.isoformat(),
            "initial_cash": str(result.config.initial_cash),
            "leverage": result.config.leverage,
            "specs": [{"name": s.name, "strategy": s.strategy, "params": s.params} for s in result.config.specs],
            "weights": None if result.config.weights is None else [str(w) for w in result.config.weights],
        },
        "per_strategy": [_run_to_dict(r) for r in result.per_strategy],
        "correlation": {f"{a}|{b}": corr for (a, b), corr in result.correlation.items()},
    }
    if result.combined_metrics is not None:
        m = result.combined_metrics
        payload["combined_metrics"] = {
            "trade_count": m.trade_count,
            "total_pnl": str(m.total_pnl),
            "win_rate": str(m.win_rate),
            "sharpe": None if m.sharpe is None else str(m.sharpe),
            "sortino": None if m.sortino is None else str(m.sortino),
            "calmar": None if m.calmar is None else str(m.calmar),
            "max_drawdown_pct": str(m.max_drawdown_pct),
            "final_equity": str(m.final_equity),
        }
    (out_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir
