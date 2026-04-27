from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import structlog

from src.broker.mock import MockBroker
from src.broker.orders import Trade
from src.domain.price import PriceBar
from src.strategy.base import Strategy

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest 実行設定（T009 で Clause 対応 + spread/holding cost フィールド追加）。

    North Star (イントラデイ絶対制約) を engine レベルで担保するため、以下のいずれかが
    必ず有効である必要がある:
      - session_close_utc_hours が非空（hour 粒度での強制クローズ）
      - bars が複数 UTC date に跨る（既存 EOD 強制クローズが発動）
    両方が無効な場合、run_backtest 冒頭で ValueError raise（意図的ポリシー: 短時間単日の
    backtest であっても「イントラデイを設計で担保する」方針の厳密化）。

    Attributes:
        instrument: 銘柄 ID。
        start: 実行開始時刻。
        end: 実行終了時刻。
        initial_cash: 初期資金（home currency）。
        leverage: レバレッジ倍率（open シグナル時 submit で validate）。
        max_spread_bps: スプレッドフィルタ上限（bps）。None で無効。判定は「前バー close
            spread」で行う（no-lookahead）。
        holding_cost_per_day_bps: 保有コスト proxy（bps/day）。bar ごと線形按分で cash
            控除。デフォルト 0。負値禁止。本 TODO は rollover swap の正確再現ではなく
            holding cost proxy。
        session_close_utc_hours: hour 粒度の強制クローズ時刻集合（UTC）。空集合で無効。
            HH:MM 粒度は将来 TODO（本 TODO は hour のみ）。
        bar_minutes: bar の時間幅（分単位）。デフォルト 1（M1 前提）。holding cost 按分に
            使用。
    """

    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    max_spread_bps: Decimal | None = None
    holding_cost_per_day_bps: Decimal = Decimal("0")
    session_close_utc_hours: frozenset[int] = field(default_factory=frozenset)
    bar_minutes: int = 1

    def __post_init__(self) -> None:
        if self.holding_cost_per_day_bps < 0:
            raise ValueError(
                f"holding_cost_per_day_bps must be >= 0: {self.holding_cost_per_day_bps}"
            )
        if self.max_spread_bps is not None and self.max_spread_bps < 0:
            raise ValueError(
                f"max_spread_bps must be >= 0 when set: {self.max_spread_bps}"
            )
        if self.bar_minutes < 1:
            raise ValueError(f"bar_minutes must be >= 1: {self.bar_minutes}")
        for h in self.session_close_utc_hours:
            if not 0 <= h <= 23:
                raise ValueError(
                    f"session_close_utc_hours contains out-of-range value: {h}"
                )


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]
    equity_curve: list[tuple[datetime, Decimal]] = field(default_factory=list)


def run_backtest(
    bars: Iterable[PriceBar],
    strategy: Strategy,
    broker: MockBroker,
    config: BacktestConfig,
) -> BacktestResult:
    """Backtest を実行。Clause DslStrategy 前提（evaluator は strategy に bake-in 済）。

    Raises:
        ValueError:
            session_close_utc_hours が空 かつ bars が単一 UTC date の場合
            （イントラデイ絶対制約違反）。

    Notes:
        意図的ポリシー: 短時間単日の backtest であっても、`session_close_utc_hours` か
        bars の複数日跨ぎのどちらかで「イントラデイ強制クローズ」が成立する状態を要求する。
    """
    bars_list = list(bars)

    # 入口: イントラデイ絶対制約の事前検証（deposit より先に実施、副作用汚染回避）
    if not config.session_close_utc_hours:
        unique_dates = {b.bar_time.date() for b in bars_list}
        if len(unique_dates) <= 1:
            raise ValueError(
                "Intraday absolute constraint violation: bars span a single UTC date "
                "and session_close_utc_hours is empty. Provide session_close_utc_hours "
                "or ensure bars span multiple UTC dates."
            )

    # Strategy が prepare() を提供する場合、backtest 全バーを 1 度だけ渡して
    # primitive 配列を事前計算させる (DslStrategy.prepare 参照: O(N²) → O(N))。
    # Live feed / 単純 Strategy は prepare を持たず、ここは NoOp になる。
    prepare = getattr(strategy, "prepare", None)
    if callable(prepare):
        prepare(bars_list)

    broker.deposit(config.initial_cash)
    broker.set_spread_filter(config.max_spread_bps)

    equity_curve: list[tuple[datetime, Decimal]] = []

    # ループ前に集計カウンタを初期化（per-bar log 削除に伴いサマリ集計に切り替え、T055）
    session_close_drop_open_count: int = 0
    session_close_drop_pending_count: int = 0
    first_drop_open_bar_time: str | None = None

    for i, bar in enumerate(bars_list):
        session_closed_bar = bar.bar_time.hour in config.session_close_utc_hours

        # 0. session close bar なら pending の open 系シグナルを先頭で drop
        if session_closed_bar:
            n_dropped = broker.drop_pending_open()
            if n_dropped:
                session_close_drop_pending_count += n_dropped
                # logger 呼び出しなし（per-bar 完全削除、サマリで集計）

        # 1. pending fill（spread filter は broker.fill_pending 内部で適用）
        broker.fill_pending(bar)

        # 2. mark-to-market + holding cost
        broker.mark_to_market(bar)
        if config.holding_cost_per_day_bps > 0:
            broker.apply_bar_holding_cost(
                bar,
                per_day_bps=config.holding_cost_per_day_bps,
                bar_minutes=config.bar_minutes,
            )

        # 3. margin call
        broker.force_close_if_margin_call(bar)

        # 4. session close: 該当時刻で保有を全クローズ
        if session_closed_bar and broker.open_positions:
            broker.close_all(bar, reason="eod")

        # 5. strategy 判断
        snapshot = broker.snapshot()
        signals = strategy.on_bar(bar, snapshot)
        for signal in signals:
            if session_closed_bar and signal.kind in ("open_long", "open_short"):
                session_close_drop_open_count += 1
                if first_drop_open_bar_time is None:
                    first_drop_open_bar_time = bar.bar_time.isoformat()
                # logger 呼び出しなし（per-bar 完全削除、サマリで集計）
                continue
            broker.submit(signal, leverage=config.leverage)

        # 6. EOD 強制クローズ（既存）
        next_bar = bars_list[i + 1] if i + 1 < len(bars_list) else None
        is_eod = next_bar is None or next_bar.bar_time.date() != bar.bar_time.date()
        if is_eod and broker.open_positions:
            broker.close_all(bar, reason="eod")

        # 7. equity curve 記録
        equity_curve.append((bar.bar_time, broker.snapshot().equity))

    # 保険として端数決済
    if broker.open_positions and bars_list:
        broker.close_all(bars_list[-1], reason="end_of_run")

    logger.info(
        "backtest.finished",
        instrument=config.instrument,
        bars=len(bars_list),
        trades=len(broker.trades),
        final_equity=str(broker.snapshot().equity),
        session_close_drop_open_count=session_close_drop_open_count,
        session_close_drop_pending_count=session_close_drop_pending_count,
        first_drop_open_bar_time=first_drop_open_bar_time,
    )
    return BacktestResult(config=config, trades=broker.trades, equity_curve=equity_curve)
