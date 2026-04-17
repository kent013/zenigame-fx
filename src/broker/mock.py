from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from src.broker.margin import notional_home_currency, required_margin, validate_leverage
from src.broker.orders import (
    ExitReason,
    OrderSignal,
    PortfolioSnapshot,
    Position,
    PositionSide,
    Trade,
)
from src.domain.price import PriceBar


@dataclass(frozen=True)
class InstrumentMeta:
    """MockBroker が個別銘柄について把握しておくべき最小情報。"""

    oanda_name: str
    base_currency: str
    quote_currency: str
    margin_rate: Decimal  # OANDA 業者側の最小マージン率


class MockBroker:
    def __init__(
        self,
        instrument_meta: InstrumentMeta,
        home_currency: str = "JPY",
        maintenance_margin_level_pct: Decimal = Decimal("100"),
    ) -> None:
        if instrument_meta.quote_currency != home_currency:
            raise NotImplementedError(
                f"MVP supports only quote==home. got quote={instrument_meta.quote_currency}, home={home_currency}"
            )
        self._meta = instrument_meta
        self._home = home_currency
        self._maintenance_pct = maintenance_margin_level_pct
        self._cash = Decimal(0)
        self._positions: dict[int, Position] = {}
        self._trades: list[Trade] = []
        self._pending: list[tuple[OrderSignal, int]] = []
        self._next_position_id = 1
        self._last_bar: PriceBar | None = None

    # ---- public API -------------------------------------------------------

    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._cash += amount

    def submit(self, signal: OrderSignal, leverage: int) -> None:
        # open 系の場合は leverage を事前バリデーション（ここで弾く方がデバッグしやすい）
        if signal.kind in ("open_long", "open_short"):
            validate_leverage(leverage, self._meta.margin_rate)
            if signal.units is None or signal.units <= 0:
                raise ValueError("open signals require units > 0")
        self._pending.append((signal, leverage))

    def fill_pending(self, bar: PriceBar) -> list[Trade]:
        if bar.pair_name != self._meta.oanda_name:
            raise ValueError(f"bar instrument {bar.pair_name} != broker {self._meta.oanda_name}")
        trades: list[Trade] = []
        for signal, leverage in self._pending:
            if signal.kind == "open_long":
                self._open_position("long", cast(int, signal.units), bar.ask.open, bar.bar_time, leverage)
            elif signal.kind == "open_short":
                self._open_position("short", cast(int, signal.units), bar.bid.open, bar.bar_time, leverage)
            elif signal.kind == "close_position":
                if signal.position_id is None:
                    raise ValueError("close_position requires position_id")
                trade = self._close_one(signal.position_id, bar, exit_kind="open", reason="signal")
                if trade is not None:
                    trades.append(trade)
            elif signal.kind == "close_all":
                trades.extend(self._close_all_internal(bar, exit_kind="open", reason="signal"))
        self._pending.clear()
        return trades

    def mark_to_market(self, bar: PriceBar) -> None:
        if bar.pair_name != self._meta.oanda_name:
            raise ValueError(f"bar instrument {bar.pair_name} != broker {self._meta.oanda_name}")
        self._last_bar = bar

    def force_close_if_margin_call(self, bar: PriceBar) -> list[Trade]:
        snap = self._snapshot_at(bar)
        if snap.margin_used == 0:
            return []
        if snap.margin_level_pct is not None and snap.margin_level_pct < self._maintenance_pct:
            return self._close_all_internal(bar, exit_kind="close", reason="margin_call")
        return []

    def close_all(self, bar: PriceBar, reason: str = "eod") -> list[Trade]:
        if reason not in ("signal", "eod", "margin_call", "end_of_run"):
            raise ValueError(f"invalid reason {reason}")
        return self._close_all_internal(bar, exit_kind="close", reason=cast(ExitReason, reason))

    def snapshot(self) -> PortfolioSnapshot:
        if self._last_bar is None:
            return PortfolioSnapshot(
                cash=self._cash, equity=self._cash, margin_used=Decimal(0), margin_level_pct=None, positions=()
            )
        return self._snapshot_at(self._last_bar)

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)

    @property
    def open_positions(self) -> list[Position]:
        return list(self._positions.values())

    @property
    def cash(self) -> Decimal:
        return self._cash

    # ---- internal ---------------------------------------------------------

    def _open_position(
        self, side: PositionSide, units: int, entry_price: Decimal, entry_time, leverage: int
    ) -> Position:
        notional = notional_home_currency(units=units, price_quote_per_base=entry_price, quote_is_home=True)
        margin = required_margin(notional, leverage)
        pos = Position(
            id=self._next_position_id,
            instrument=self._meta.oanda_name,
            side=side,
            units=units,
            entry_price=entry_price,
            entry_time=entry_time,
            entry_margin=margin,
            leverage=leverage,
        )
        self._next_position_id += 1
        self._positions[pos.id] = pos
        # Mark: MVP ではキャッシュから margin を即座に減らさず、snapshot で拘束額を計算する。
        # （国内 FX の「拘束証拠金」モデルを採用。cash は常に「入金額 - 実現損益」。）
        return pos

    def _close_one(self, position_id: int, bar: PriceBar, exit_kind: str, reason: ExitReason) -> Trade | None:
        pos = self._positions.pop(position_id, None)
        if pos is None:
            return None
        exit_price = self._exit_price(pos.side, bar, exit_kind)
        pnl = self._realized_pnl(pos, exit_price)
        self._cash += pnl
        trade = Trade(
            position_id=pos.id,
            instrument=pos.instrument,
            side=pos.side,
            units=pos.units,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=exit_price,
            exit_time=bar.bar_time,
            pnl=pnl,
            exit_reason=reason,
        )
        self._trades.append(trade)
        return trade

    def _close_all_internal(self, bar: PriceBar, exit_kind: str, reason: ExitReason) -> list[Trade]:
        trades: list[Trade] = []
        for pid in list(self._positions.keys()):
            trade = self._close_one(pid, bar, exit_kind=exit_kind, reason=reason)
            if trade is not None:
                trades.append(trade)
        return trades

    @staticmethod
    def _exit_price(side: PositionSide, bar: PriceBar, exit_kind: str) -> Decimal:
        # exit_kind: "open" = その bar 始値で約定 / "close" = bar 終値（強制決済・EOD・マージンコール）
        if side == "long":
            return bar.bid.open if exit_kind == "open" else bar.bid.close
        return bar.ask.open if exit_kind == "open" else bar.ask.close

    @staticmethod
    def _realized_pnl(pos: Position, exit_price: Decimal) -> Decimal:
        if pos.side == "long":
            return Decimal(pos.units) * (exit_price - pos.entry_price)
        return Decimal(pos.units) * (pos.entry_price - exit_price)

    def _unrealized_pnl(self, pos: Position, bar: PriceBar) -> Decimal:
        # 決済時と同じ方向で bar close を参照（long は bid、short は ask）
        exit_price = self._exit_price(pos.side, bar, exit_kind="close")
        return self._realized_pnl(pos, exit_price)

    def _snapshot_at(self, bar: PriceBar) -> PortfolioSnapshot:
        unrealized = sum((self._unrealized_pnl(p, bar) for p in self._positions.values()), Decimal(0))
        equity = self._cash + unrealized
        margin_used = sum((p.entry_margin for p in self._positions.values()), Decimal(0))
        margin_level: Decimal | None = None
        if margin_used > 0:
            margin_level = equity / margin_used * Decimal(100)
        return PortfolioSnapshot(
            cash=self._cash,
            equity=equity,
            margin_used=margin_used,
            margin_level_pct=margin_level,
            positions=tuple(self._positions.values()),
        )
