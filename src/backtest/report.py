from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from src.backtest.engine import BacktestResult
from src.backtest.metrics import BacktestMetrics, compute_metrics
from src.broker.orders import Trade


def _dec(v: Decimal | None) -> str:
    if v is None:
        return "∞"
    return f"{v:.6f}"


def _format_trade_row(t: Trade) -> str:
    return (
        f"| {t.position_id} | {t.instrument} | {t.side} | {t.units} | "
        f"{t.entry_time.isoformat()} | {_dec(t.entry_price)} | "
        f"{t.exit_time.isoformat()} | {_dec(t.exit_price)} | "
        f"{_dec(t.pnl)} | {t.exit_reason} |"
    )


def render_markdown(result: BacktestResult, metrics: BacktestMetrics) -> str:
    c = result.config
    lines: list[str] = []
    lines.append(f"# Backtest Report — {c.instrument}")
    lines.append("")
    lines.append(f"**生成**: {datetime.now(tz=UTC).isoformat()}")
    lines.append("")
    lines.append("## Config")
    lines.append("")
    lines.append(f"- instrument: `{c.instrument}`")
    lines.append(f"- period: `{c.start.isoformat()}` → `{c.end.isoformat()}`")
    lines.append(f"- initial_cash: {_dec(c.initial_cash)}")
    lines.append(f"- leverage: {c.leverage}x")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| 指標 | 値 |")
    lines.append("|------|----|")
    lines.append(f"| trade_count | {metrics.trade_count} |")
    lines.append(f"| win_count | {metrics.win_count} |")
    lines.append(f"| loss_count | {metrics.loss_count} |")
    lines.append(f"| win_rate | {_dec(metrics.win_rate)} |")
    lines.append(f"| total_pnl | {_dec(metrics.total_pnl)} |")
    lines.append(f"| avg_win | {_dec(metrics.avg_win)} |")
    lines.append(f"| avg_loss | {_dec(metrics.avg_loss)} |")
    lines.append(f"| profit_factor | {_dec(metrics.profit_factor)} |")
    lines.append(f"| max_drawdown | {_dec(metrics.max_drawdown)} |")
    lines.append(f"| max_drawdown_pct | {_dec(metrics.max_drawdown_pct)} |")
    lines.append(f"| final_equity | {_dec(metrics.final_equity)} |")
    lines.append("")
    lines.append("## Trades (first 10)")
    lines.append("")
    lines.append("| # | instrument | side | units | entry_time | entry_px | exit_time | exit_px | pnl | reason |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for t in result.trades[:10]:
        lines.append(_format_trade_row(t))
    if len(result.trades) > 20:
        lines.append("")
        lines.append("## Trades (last 10)")
        lines.append("")
        lines.append("| # | instrument | side | units | entry_time | entry_px | exit_time | exit_px | pnl | reason |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for t in result.trades[-10:]:
            lines.append(_format_trade_row(t))
    return "\n".join(lines) + "\n"


def _metrics_to_dict(m: BacktestMetrics) -> dict[str, object]:
    return {
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
    }


def _trade_to_dict(t: Trade) -> dict[str, object]:
    return {
        "position_id": t.position_id,
        "instrument": t.instrument,
        "side": t.side,
        "units": t.units,
        "entry_time": t.entry_time.isoformat(),
        "entry_price": str(t.entry_price),
        "exit_time": t.exit_time.isoformat(),
        "exit_price": str(t.exit_price),
        "pnl": str(t.pnl),
        "exit_reason": t.exit_reason,
    }


def write_report(result: BacktestResult, root: Path | None = None) -> Path:
    """backtest-YYYYMMDD-HHMMSS/ ディレクトリに result.md と result.json を書き出し、ディレクトリパスを返す。"""
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    root_dir = root or Path("reports/backtests")
    out_dir = root_dir / f"backtest-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(result.trades, result.equity_curve)

    md = render_markdown(result, metrics)
    (out_dir / "result.md").write_text(md, encoding="utf-8")

    payload = {
        "config": {
            "instrument": result.config.instrument,
            "start": result.config.start.isoformat(),
            "end": result.config.end.isoformat(),
            "initial_cash": str(result.config.initial_cash),
            "leverage": result.config.leverage,
        },
        "metrics": _metrics_to_dict(metrics),
        "trades": [_trade_to_dict(t) for t in result.trades],
    }
    (out_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir
