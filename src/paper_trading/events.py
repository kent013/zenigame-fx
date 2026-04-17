from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog

from src.broker.orders import OrderSignal, PortfolioSnapshot, Trade
from src.domain.price import PriceBar

logger = structlog.get_logger(__name__)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(v) for v in value]
    return value


class EventLogger:
    """Paper Trading の監査イベントを JSONL に書き出す。

    1 セッション = 1 ディレクトリ。events.jsonl に逐次追記、daily-pnl.md に EOD サマリを追記する。
    """

    def __init__(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = log_dir / "events.jsonl"
        self._daily_path = log_dir / "daily-pnl.md"
        self._events_path.touch(exist_ok=True)
        self._dir = log_dir

    @property
    def log_dir(self) -> Path:
        return self._dir

    def _write_event(self, kind: str, payload: dict[str, Any]) -> None:
        event = {"ts": datetime.now(tz=UTC).isoformat(), "kind": kind, "payload": _to_jsonable(payload)}
        with self._events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> None:
        self._write_event(
            "bar",
            {
                "instrument": bar.pair_name,
                "bar_time": bar.bar_time,
                "bid_close": bar.bid.close,
                "ask_close": bar.ask.close,
                "equity": snapshot.equity,
                "cash": snapshot.cash,
                "margin_used": snapshot.margin_used,
                "margin_level_pct": snapshot.margin_level_pct,
                "open_positions": len(snapshot.positions),
            },
        )

    def log_signal(self, signal: OrderSignal, bar: PriceBar, snapshot: PortfolioSnapshot) -> None:
        self._write_event(
            "signal",
            {
                "kind": signal.kind,
                "units": signal.units,
                "position_id": signal.position_id,
                "instrument": bar.pair_name,
                "bar_time": bar.bar_time,
                "equity_before": snapshot.equity,
            },
        )

    def log_trade(self, trade: Trade) -> None:
        self._write_event(
            "trade",
            {
                "position_id": trade.position_id,
                "instrument": trade.instrument,
                "side": trade.side,
                "units": trade.units,
                "entry_time": trade.entry_time,
                "entry_price": trade.entry_price,
                "exit_time": trade.exit_time,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "exit_reason": trade.exit_reason,
            },
        )

    def write_daily_summary(self, day: str, trades: list[Trade], snapshot: PortfolioSnapshot) -> None:
        total_pnl = sum((t.pnl for t in trades), Decimal(0))
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        win_rate = (Decimal(len(wins)) / Decimal(len(trades))) if trades else Decimal(0)
        lines = [
            f"## {day}",
            "",
            f"- trades: {len(trades)}",
            f"- win_count: {len(wins)}",
            f"- loss_count: {len(losses)}",
            f"- win_rate: {win_rate:.4f}",
            f"- total_pnl: {total_pnl}",
            f"- equity_eod: {snapshot.equity}",
            "",
        ]
        with self._daily_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def flush(self) -> None:
        # open()/write() で都度 flush されているので明示的な flush は不要だが、
        # API 互換のため no-op を残す（将来 DB 追加時に使う）
        return
