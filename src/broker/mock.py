from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import structlog

from src.broker.margin import notional_home_currency, required_margin, validate_leverage
from src.broker.orders import (
    ExitReason,
    InsufficientEquityError,
    OrderSignal,
    PortfolioSnapshot,
    Position,
    PositionSide,
    Trade,
)
from src.domain.price import PriceBar

logger = structlog.get_logger(__name__)


def _is_finite_decimal(value: Decimal) -> bool:
    """Decimal が有限値（NaN / Infinity でない）か判定 (T056)。

    Decimal('NaN') / Decimal('Infinity') を `<= 0` 比較すると InvalidOperation を
    起こすため、比較演算前に本 helper でガードする。
    """
    return value.is_finite()


@dataclass(frozen=True)
class InstrumentMeta:
    """MockBroker が個別銘柄について把握しておくべき最小情報。

    SSOT 境界:
        * ``src/domain/instrument.py::CurrencyPair`` は ingest / oanda 層 SSOT で、
          pip_location / minimum_trade_size / maximum_order_units を含む
          full pair catalog を保持する。
        * ``InstrumentMeta`` は broker / backtest 層 SSOT で、P&L 計算・margin
          検証・ログ表示に最低限必要な情報のみを保持する。
          ``pip_size`` / ``display_precision`` は ``CurrencyPair`` から派生的に
          コピーできる（``default_pip_size_for_quote`` / ``default_display_precision_for_quote``
          ヘルパ参照）。

    Phase 4 note (T019):
        本 Phase では ``home=quote`` 前提の per-pair home モードで動作する
        (``MockBroker(home_currency=None)`` で ``meta.quote_currency`` を自動採用)。
        Phase 4 で ``home != quote`` をサポートする際は ``MockBroker`` 側で
        ``fx_rate_provider`` (新規引数、未実装) を受け取り quote→home 換算を
        実行する設計を予約済 (devnotes/20260424-0517-mock-broker-multi-currency)。

    Attributes:
        oanda_name: 銘柄 ID (例: ``USD_JPY``)。
        base_currency: 基軸通貨 (例: ``USD``)。
        quote_currency: 決済通貨 (例: ``JPY``)。
        margin_rate: OANDA 業者側の最小マージン率。
        pip_size: 1 pip の Decimal (OANDA 仕様: JPY-quote=0.01、USD-quote=0.0001)。
            後方互換のため default は USD-quote の 0.0001。JPY-quote を扱う呼び出し
            では明示指定または ``default_pip_size_for_quote`` 経由を推奨。
        display_precision: 価格表示の小数点以下桁数 (JPY-quote=3、USD-quote=5)。
    """

    oanda_name: str
    base_currency: str
    quote_currency: str
    margin_rate: Decimal  # OANDA 業者側の最小マージン率
    pip_size: Decimal = Decimal("0.0001")
    display_precision: int = 5

    def __post_init__(self) -> None:
        if self.pip_size <= 0:
            raise ValueError(f"pip_size must be > 0: {self.pip_size}")
        if self.display_precision < 0:
            raise ValueError(f"display_precision must be >= 0: {self.display_precision}")

    @staticmethod
    def default_pip_size_for_quote(quote_currency: str) -> Decimal:
        """quote currency から pip_size を自動決定する (OANDA 仕様)。"""
        return Decimal("0.01") if quote_currency.upper() == "JPY" else Decimal("0.0001")

    @staticmethod
    def default_display_precision_for_quote(quote_currency: str) -> int:
        """quote currency から display_precision を自動決定する (OANDA 仕様)。"""
        return 3 if quote_currency.upper() == "JPY" else 5


class MockBroker:
    def __init__(
        self,
        instrument_meta: InstrumentMeta,
        *,
        home_currency: str | None = None,
        maintenance_margin_level_pct: Decimal = Decimal("100"),
    ) -> None:
        """MockBroker を初期化する。

        Args:
            instrument_meta: 銘柄メタ情報。
            home_currency: 口座 home 通貨。``None`` の場合は
                ``instrument_meta.quote_currency`` を自動採用する (per-pair home モード、
                T019 で導入)。明示指定した場合は ``meta.quote_currency`` と一致必須。
                Phase 4 で ``fx_rate_provider`` を導入するまでは、不一致は
                ``NotImplementedError`` を raise する (fail-fast)。
            maintenance_margin_level_pct: マージンコール発動閾値 (%)。

        Raises:
            NotImplementedError: ``home_currency`` が明示指定され、かつ
                ``meta.quote_currency`` と一致しない場合。Phase 4 で
                ``fx_rate_provider`` を追加すれば解消される予定。
        """
        resolved_home = (
            home_currency if home_currency is not None
            else instrument_meta.quote_currency
        )
        if instrument_meta.quote_currency != resolved_home:
            raise NotImplementedError(
                f"MockBroker phase 2 requires quote==home. "
                f"got quote={instrument_meta.quote_currency}, home={resolved_home}. "
                "Phase 4 will introduce fx_rate_provider for quote-to-home conversion."
            )
        self._meta = instrument_meta
        self._home = resolved_home
        self._maintenance_pct = maintenance_margin_level_pct
        self._cash = Decimal(0)
        self._positions: dict[int, Position] = {}
        self._trades: list[Trade] = []
        self._pending: list[tuple[OrderSignal, int]] = []
        self._next_position_id = 1
        self._last_bar: PriceBar | None = None
        # T009: spread filter (前バー close spread で reject)
        self._max_spread_bps: Decimal | None = None
        self._last_close_spread_bps: Decimal | None = None
        # T009: holding cost 累計（position_id → 累積 cost）
        self._holding_cost_by_position: dict[int, Decimal] = {}
        # T028: per-bar snapshot cache。単一 tuple slot (bar, snapshot) で atomic
        # に更新し None で invalidate する。3 calls/bar → 1 call/bar に削減
        # (O(N²)→O(N) 最適化)。cache hit は `bar is cache[0]` identity 判定で
        # object reference を保持することで id() 再利用問題を回避
        # (T028 conceptual-design Round 3 Critical 対応)。
        self._snapshot_cache: tuple[PriceBar, PortfolioSnapshot] | None = None
        # T056: negative equity 起因で drop された open 系 signal の累計件数。
        # L1 (fill_pending 冒頭 gate) + L2 (_open_position 内 InsufficientEquityError)
        # の両方で加算される。pop_negative_equity_drop_count() で取り出すと 0 に reset。
        # spread filter / session_close 起因の drop はここに含めない（独立 counter）。
        self._negative_equity_drop_count: int = 0

    # ---- public API -------------------------------------------------------

    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._cash += amount
        self._invalidate_snapshot_cache()

    def submit(self, signal: OrderSignal, leverage: int) -> None:
        # open 系の場合は leverage を事前バリデーション（ここで弾く方がデバッグしやすい）
        if signal.kind in ("open_long", "open_short"):
            validate_leverage(leverage, self._meta.margin_rate)
            if signal.units is None or signal.units <= 0:
                raise ValueError("open signals require units > 0")
        self._pending.append((signal, leverage))

    def set_spread_filter(self, max_spread_bps: Decimal | None) -> None:
        """engine から呼ばれる。None で無効。"""
        if max_spread_bps is not None and max_spread_bps < 0:
            raise ValueError(f"max_spread_bps must be >= 0 when set: {max_spread_bps}")
        self._max_spread_bps = max_spread_bps

    def drop_pending_open(self) -> int:
        """pending の open_long / open_short を drop して件数を返す。

        呼び出し元（engine.run_backtest）が return 値で件数を集計する設計。
        broker 内では log を出さない（per-bar 呼び出しの hot path コスト削減）。

        Returns:
            drop 件数。
        """
        before = len(self._pending)
        self._pending = [
            (sig, lev) for (sig, lev) in self._pending
            if sig.kind not in ("open_long", "open_short")
        ]
        return before - len(self._pending)

    def fill_pending(self, bar: PriceBar) -> list[Trade]:
        if bar.pair_name != self._meta.oanda_name:
            raise ValueError(f"bar instrument {bar.pair_name} != broker {self._meta.oanda_name}")

        # T009: spread filter（前バー close spread で reject）
        if (
            self._max_spread_bps is not None
            and self._last_close_spread_bps is not None
            and self._last_close_spread_bps > self._max_spread_bps
        ):
            before = len(self._pending)
            self._pending = [
                (sig, lev) for (sig, lev) in self._pending
                if sig.kind not in ("open_long", "open_short")
            ]
            rejected = before - len(self._pending)
            if rejected:
                logger.info(
                    "broker.submit.rejected_by_spread",
                    n_rejected=rejected,
                    last_close_spread_bps=str(self._last_close_spread_bps),
                    max_spread_bps=str(self._max_spread_bps),
                )

        # T-sharpe: bar 処理開始時点（全 fill 前）の equity を一度だけ取得し、
        # 同一 bar 内のすべての _open_position に共通で渡す（fill 順依存禁止）
        pre_fill_equity = self._snapshot_at(bar).equity

        # T056 L1: equity 非有限値 / 非正値での open 系 drop（fail-closed）
        # 注: 同 bar 内の close signal による equity recovery は意図的に取り逃がす
        # （conservative policy、設計 §2.3 参照）。close 系は通常実行する。
        if not _is_finite_decimal(pre_fill_equity) or pre_fill_equity <= Decimal(0):
            before = len(self._pending)
            self._pending = [
                (sig, lev) for (sig, lev) in self._pending
                if sig.kind not in ("open_long", "open_short")
            ]
            self._negative_equity_drop_count += before - len(self._pending)

        trades: list[Trade] = []
        for signal, leverage in self._pending:
            if signal.kind == "open_long":
                # T056 L2: L1 を通り抜けた異常経路の最終防御。drop 扱いで継続
                try:
                    self._open_position(
                        "long", cast(int, signal.units), bar.ask.open, bar.bar_time, leverage,
                        equity_at_entry=pre_fill_equity,
                    )
                except InsufficientEquityError:
                    self._negative_equity_drop_count += 1
                    continue
            elif signal.kind == "open_short":
                try:
                    self._open_position(
                        "short", cast(int, signal.units), bar.bid.open, bar.bar_time, leverage,
                        equity_at_entry=pre_fill_equity,
                    )
                except InsufficientEquityError:
                    self._negative_equity_drop_count += 1
                    continue
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

    def pop_negative_equity_drop_count(self) -> int:
        """L1 + L2 で drop した open 系 signal の累計件数を返し、内部 counter を 0 に reset (T056)。

        pop semantics: 呼び出すたびに「前回 pop 以降の累計」を返す。
        複数 backtest 連続実行や broker 再利用時の混線を防ぐ。

        `run_backtest` は backtest 完了時に 1 回 pop して `backtest.finished` log の
        `negative_equity_drop_open_count` field に渡す。

        Returns:
            前回 pop 以降の drop 件数（0 初期化済）。
        """
        n = self._negative_equity_drop_count
        self._negative_equity_drop_count = 0
        return n

    def mark_to_market(self, bar: PriceBar) -> None:
        if bar.pair_name != self._meta.oanda_name:
            raise ValueError(f"bar instrument {bar.pair_name} != broker {self._meta.oanda_name}")
        self._last_bar = bar
        # T009: 次バー fill_pending で参照される close spread bps を更新
        mid_close = (bar.ask.close + bar.bid.close) / Decimal(2)
        if mid_close > 0:
            spread_bps = (bar.ask.close - bar.bid.close) / mid_close * Decimal(10000)
            self._last_close_spread_bps = spread_bps
        # mid_close <= 0 の場合は更新しない（防御）

    def apply_bar_holding_cost(
        self,
        bar: PriceBar,
        *,
        per_day_bps: Decimal,
        bar_minutes: int,
    ) -> Decimal:
        """bar 単位で holding cost を cash から控除、かつ各 position に累計。

        per_bar_bps = per_day_bps × (bar_minutes / 1440)
        cost_i = |notional_home_i| × per_bar_bps / 10000   （i = 各 open position）
        total_cost = Σ cost_i

        効果:
          - self._cash -= total_cost（equity に即時反映）
          - 各 position の累計 holding cost を self._holding_cost_by_position[pos.id] に加算
          - _close_one で Trade.pnl から「当該 position の累計 holding cost」を差し引く
            → total_pnl = sum(trade.pnl) が holding cost 反映済みの値になる

        Returns:
            控除された総額（正値）。
        """
        if per_day_bps <= 0 or bar_minutes <= 0 or not self._positions:
            return Decimal(0)
        if bar.pair_name != self._meta.oanda_name:
            raise ValueError(f"bar instrument {bar.pair_name} != broker {self._meta.oanda_name}")
        per_bar_bps = per_day_bps * Decimal(bar_minutes) / Decimal(1440)
        total_cost = Decimal(0)
        for pos in self._positions.values():
            notional = notional_home_currency(
                units=pos.units,
                price_quote_per_base=pos.entry_price,
                quote_is_home=True,
            )
            cost = notional * per_bar_bps / Decimal(10000)
            total_cost += cost
            self._holding_cost_by_position[pos.id] = (
                self._holding_cost_by_position.get(pos.id, Decimal(0)) + cost
            )
        if total_cost > 0:
            self._cash -= total_cost
            self._invalidate_snapshot_cache()
        return total_cost

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
        self,
        side: PositionSide,
        units: int,
        entry_price: Decimal,
        entry_time,
        leverage: int,
        *,
        equity_at_entry: Decimal,
    ) -> Position:
        # T056 L2: defensive guard（L1 を通り抜ける経路があれば fail-fast）
        # `fill_pending` ループ内で InsufficientEquityError を捕捉して drop 扱いに統一
        if not _is_finite_decimal(equity_at_entry) or equity_at_entry <= Decimal(0):
            raise InsufficientEquityError(
                f"_open_position called with non-finite or non-positive equity: "
                f"{equity_at_entry}"
            )
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
            equity_at_entry=equity_at_entry,
        )
        self._next_position_id += 1
        self._positions[pos.id] = pos
        # Mark: MVP ではキャッシュから margin を即座に減らさず、snapshot で拘束額を計算する。
        # （国内 FX の「拘束証拠金」モデルを採用。cash は常に「入金額 - 実現損益」。）
        self._invalidate_snapshot_cache()
        return pos

    def _close_one(self, position_id: int, bar: PriceBar, exit_kind: str, reason: ExitReason) -> Trade | None:
        pos = self._positions.pop(position_id, None)
        if pos is None:
            return None
        exit_price = self._exit_price(pos.side, bar, exit_kind)
        raw_pnl = self._realized_pnl(pos, exit_price)
        # T009: 累積 holding cost を pnl から差し引いて Trade.pnl に net_pnl として記録
        # cash は apply_bar_holding_cost で既に cost を減算済みなので、raw_pnl のみ加算
        # （二重控除を回避）。
        cost_accum = self._holding_cost_by_position.pop(pos.id, Decimal(0))
        net_pnl = raw_pnl - cost_accum
        # T070: entry/exit spread を別 field 化 (Trade.pnl 未反映、 監査・stress 用).
        # 詳細設計 §4.5 SSOT: exit bar の bid/ask spread × 2 を entry+exit 往復 spread
        # の概算プロキシとして採用 (Roll 1984)。 厳密な entry_spread 取得は Phase 2.
        spread_cost = self._compute_trade_spread_cost(pos, bar)
        self._cash += raw_pnl
        trade = Trade(
            position_id=pos.id,
            instrument=pos.instrument,
            side=pos.side,
            units=pos.units,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=exit_price,
            exit_time=bar.bar_time,
            pnl=net_pnl,
            exit_reason=reason,
            equity_at_entry=pos.equity_at_entry,
            spread_cost=spread_cost,
            holding_cost=cost_accum,
        )
        self._trades.append(trade)
        self._invalidate_snapshot_cache()
        return trade

    @staticmethod
    def _compute_trade_spread_cost(pos: Position, bar: PriceBar) -> Decimal:
        """entry/exit の bid/ask spread から trade-level spread cost を推定する (T070).

        SSOT: 概念設計 §3.4.0 (spread_cost は監査・stress 用記録、 既存 pnl 未反映).

        計算式 (詳細設計 §4.5):
            exit_spread = bar.spread_close  # ask.close - bid.close
            spread_cost_per_unit = exit_spread * 2  # entry+exit 往復近似 (Roll 1984)
            spread_cost = abs(pos.units) * spread_cost_per_unit

        T070 では「exit bar の spread × 2」を entry+exit 往復 spread の概算
        プロキシとして採用 (Roll 1984)。 厳密な entry_spread 取得は Phase 2 で
        broker 改造 (Position.entry_spread 保持) により対応.

        異常データ (bid > ask 等) で spread_close < 0 の場合は 0 に clamp し、
        SessionBlock.spread_cost_total >= 0 invariant を破らない (Round 1 [W1]).

        Returns:
            spread_cost (>= 0).
        """
        exit_spread = bar.spread_close
        if exit_spread < 0:
            exit_spread = Decimal(0)
        spread_cost_per_unit = exit_spread * Decimal(2)
        return abs(Decimal(pos.units)) * spread_cost_per_unit

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
        # T028: cache hit 経路 — object reference 同一性判定 (`is`) で
        # 同一 bar の 2 回目以降の呼び出しは cached PortfolioSnapshot を
        # 即 return する。演算順序を一切変えないため bit-identical が
        # 構造的に保証される。
        cache = self._snapshot_cache
        if cache is not None and cache[0] is bar:
            return cache[1]
        # cache miss: 既存ロジックで compute (ロジック本体は不変)
        unrealized = sum((self._unrealized_pnl(p, bar) for p in self._positions.values()), Decimal(0))
        equity = self._cash + unrealized
        margin_used = sum((p.entry_margin for p in self._positions.values()), Decimal(0))
        margin_level: Decimal | None = None
        if margin_used > 0:
            margin_level = equity / margin_used * Decimal(100)
        snapshot = PortfolioSnapshot(
            cash=self._cash,
            equity=equity,
            margin_used=margin_used,
            margin_level_pct=margin_level,
            positions=tuple(self._positions.values()),
        )
        # T028: cache 書き込み — 1 回の tuple 代入で atomic に更新する。
        # 例外時はここに到達しないため中間状態が残らない。
        self._snapshot_cache = (bar, snapshot)
        return snapshot

    def _invalidate_snapshot_cache(self) -> None:
        """次回 ``_snapshot_at`` 呼び出しで cache miss を強制する。

        cash / positions の変化時に呼ぶ。bar 進行による invalidate は
        ``cache[0] is bar`` の identity 比較で自動検出されるため不要。

        単一スロットに ``None`` 代入で invalidate 完了（atomic）。
        """
        self._snapshot_cache = None
