from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import numpy as np
import structlog

from src.backtest.columnar import SCALE_RATIO, bars_to_columnar, scaled_to_price
from src.backtest.equity_curve import (
    EquityCurve,
    EquityCurveBuilder,
    decode_equity,
    encode_equity,
    validate_equity_scale_contract,
)
from src.backtest.session_block import SessionBlock, aggregate_session_blocks
from src.broker.mock import MockBroker
from src.broker.orders import ExitReason, PositionSide, Trade
from src.domain.price import PriceBar
from src.strategy.base import Strategy

logger = structlog.get_logger(__name__)

# T108: kernel が出力する exit reason code → ExitReason 文字列。
_REASON_CODE_TO_STR: tuple[ExitReason, ...] = (
    "signal",       # 0
    "eod",          # 1
    "margin_call",  # 2
    "end_of_run",   # 3
)


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
    # T105: equity_curve は lossless numpy 表現 (EquityCurve)。
    # 旧 list[tuple[datetime, Decimal]] は 1 genome Stage B 評価で約 90 万個の
    # 小オブジェクトを backtest 寿命中 retain し pymalloc アリーナを断片化させて
    # いた。@ref: devnotes/20260515-0827-backtest-decimal-churn/
    equity_curve: EquityCurve = field(default_factory=EquityCurve.empty)
    # T070: cascade port v2 Phase 2 配線. session_blocks は run_backtest 内で 1 回
    # 計算し、 caller は読むのみ (再計算禁止、 概念設計 §6.4 SSOT). default_factory で
    # backward-compat を維持 (= 既存 caller への影響なし).
    session_blocks: tuple[SessionBlock, ...] = field(default_factory=tuple)


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

    # T105: equity の scaled-int 表現 (SCALE 契約) が config 前提で成立するか
    # backtest 開始前に検証する (holding cost 有効化時は fail-closed)。
    validate_equity_scale_contract(config.holding_cost_per_day_bps)

    # T108: preflight を満たす場合は numba njit kernel 経路で実行 (wall 削減)。
    # observable behavior は Decimal 経路と bit-identical (golden で実証)。
    # preflight 不成立 / kernel overflow は Decimal 経路へ fail-safe フォールバック。
    if _can_use_kernel(bars_list, strategy, broker, config):
        kernel_result = _run_backtest_kernel(bars_list, strategy, broker, config)
        if kernel_result is not None:
            return kernel_result

    return _run_backtest_decimal(bars_list, strategy, broker, config)


def _run_backtest_decimal(
    bars_list: list[PriceBar],
    strategy: Strategy,
    broker: MockBroker,
    config: BacktestConfig,
) -> BacktestResult:
    """現行の純 Python / Decimal per-bar ループ (T108 以前の実装、不変)。

    kernel preflight 不成立または kernel overflow 時の fail-safe 経路。
    """
    # Strategy が prepare() を提供する場合、backtest 全バーを 1 度だけ渡して
    # primitive 配列を事前計算させる (DslStrategy.prepare 参照: O(N²) → O(N))。
    # Live feed / 単純 Strategy は prepare を持たず、ここは NoOp になる。
    prepare = getattr(strategy, "prepare", None)
    if callable(prepare):
        prepare(bars_list)

    broker.deposit(config.initial_cash)
    broker.set_spread_filter(config.max_spread_bps)

    # T105: equity_curve を事前確保 numpy バッファ (EquityCurveBuilder) で構築。
    # bar 数は bars_list で確定済み → index 代入で埋め、小オブジェクトを蓄積しない。
    equity_builder = EquityCurveBuilder(len(bars_list))

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
        equity_builder.append(bar.bar_time, broker.snapshot().equity)

    # 保険として端数決済
    if broker.open_positions and bars_list:
        broker.close_all(bars_list[-1], reason="end_of_run")

    # T056: negative equity 起因の open 系 drop 件数を pop して log 出力する
    # （pop semantics: broker 再利用時の混線防止、呼び出しで 0 に reset される）
    negative_equity_drop_open_count = broker.pop_negative_equity_drop_count()

    logger.info(
        "backtest.finished",
        instrument=config.instrument,
        bars=len(bars_list),
        trades=len(broker.trades),
        final_equity=str(broker.snapshot().equity),
        session_close_drop_open_count=session_close_drop_open_count,
        session_close_drop_pending_count=session_close_drop_pending_count,
        first_drop_open_bar_time=first_drop_open_bar_time,
        negative_equity_drop_open_count=negative_equity_drop_open_count,
    )

    # T070: SessionBlock 集計 (Round 1 [C3] transport SSOT). caller 再計算禁止 (§6.4).
    # T072 (詳細設計 § 4.9 / 2.2): mode="test" で broker_schedule / calendars は未配線.
    # Phase 2 で aggregate_session_blocks_production wrapper に置換予定 (= production caller).
    session_blocks = aggregate_session_blocks(bars_list, broker.trades, mode="test")

    return BacktestResult(
        config=config,
        trades=broker.trades,
        equity_curve=equity_builder.build(),
        session_blocks=session_blocks,
    )


# ---------------------------------------------------------------------------
# T108: numba njit kernel 経路 (broker per-bar simulation の高速化)
# ---------------------------------------------------------------------------


def _can_use_kernel(
    bars_list: list[PriceBar],
    strategy: Strategy,
    broker: MockBroker,
    config: BacktestConfig,
) -> bool:
    """kernel preflight (詳細設計 §5)。不成立は Decimal 経路。

    条件 (cross-multiply 終端性証明 / scope の前提):
      1. holding_cost_per_day_bps == 0 (除算経路を持ち込まない)
      2. maintenance == 100 かつ max_spread が整数 bps (整数比較の前提)
      3. leverage == 3 (production default、証明は leverage 素因数に依存)
      4. strategy が DslStrategy かつ session_close なし かつ prepared path 対応
      5. 単一 signal 契約 (DslStrategy.on_bar は 0/1 件) は構造的に保証済
    overflow は preflight の hard gate にせず kernel 内 sentinel + 再実行で扱う。
    """
    from src.dsl.strategy import DslStrategy

    if not bars_list:
        return False
    if config.holding_cost_per_day_bps != 0:
        return False
    if config.max_spread_bps is not None and config.max_spread_bps != int(config.max_spread_bps):
        return False
    if broker._maintenance_pct != Decimal(100):
        return False
    if config.leverage != 3:
        return False
    if not isinstance(strategy, DslStrategy):
        return False
    if strategy._session_close is not None:
        return False
    return hasattr(strategy._evaluator, "evaluate_all_bars")


def _run_backtest_kernel(
    bars_list: list[PriceBar],
    strategy: Strategy,
    broker: MockBroker,
    config: BacktestConfig,
) -> BacktestResult | None:
    """kernel 経路で backtest を実行する。

    Returns:
        BacktestResult。prepared path 非対応 / kernel overflow の場合は ``None``
        (呼び出し側が Decimal 経路へフォールバック)。
    """
    from src.backtest._sim_kernel import STATUS_OK, simulate
    from src.dsl.composite import compute_composite_at_bar_jit
    from src.dsl.strategy import DslStrategy

    # preflight (_can_use_kernel) で保証済だが mypy 型絞り込み + 契約明示。
    assert isinstance(strategy, DslStrategy)

    n = len(bars_list)
    # prepared flat 配列を構築 (現行と同一)。evaluator 非対応なら None。
    strategy.prepare(bars_list)
    prepared = strategy._prepared
    if prepared is None:
        return None

    warmup: int = strategy._warmup

    # composite を現行と同一の per-idx njit 呼びで構築 (float bit 一致を構造保証)。
    # active_clause_indices も on_bar と同一ロジックで再現 (observability parity)。
    composite = np.empty(n, dtype=np.float64)
    buf = prepared.clause_score_buffer
    active: set[int] = set()
    n_clauses = buf.shape[0]
    for i in range(n):
        composite[i] = compute_composite_at_bar_jit(
            i,
            prepared.clause_weights,
            prepared.dir_weights_flat,
            prepared.dir_offsets,
            prepared.dir_signal_idx,
            prepared.gate_offsets,
            prepared.gate_signal_idx,
            prepared.unique_signal_matrix,
            buf,
        )
        if i >= warmup:
            for ci in range(n_clauses):
                if buf[ci] != 0.0:
                    active.add(ci)
    strategy._active_clause_indices = active

    col = bars_to_columnar(bars_list)

    session_mask = np.zeros(24, dtype=np.bool_)
    for h in config.session_close_utc_hours:
        session_mask[h] = True

    genome = strategy._genome
    pos_cfg = genome.position
    units = genome.units

    if config.max_spread_bps is None:
        spread_active = False
        max_num, max_den = 0, 1
    else:
        spread_active = True
        max_num, max_den = int(config.max_spread_bps), 1

    initial_cash_scaled = encode_equity(config.initial_cash)

    out_entry_idx = np.empty(n, dtype=np.int64)
    out_exit_idx = np.empty(n, dtype=np.int64)
    out_side = np.empty(n, dtype=np.int64)
    out_entry_px = np.empty(n, dtype=np.int64)
    out_exit_px = np.empty(n, dtype=np.int64)
    out_reason = np.empty(n, dtype=np.int64)
    out_pos_id = np.empty(n, dtype=np.int64)
    out_equity_at_entry = np.empty(n, dtype=np.int64)
    out_equity_scaled = np.empty(n, dtype=np.int64)

    status, n_trades, neg_drop, sess_drop_open, sess_drop_pending = simulate(
        col.bid_o, col.bid_h, col.bid_l, col.bid_c,
        col.ask_o, col.ask_h, col.ask_l, col.ask_c,
        col.hour, col.is_eod, col.epoch_ns,
        composite, session_mask,
        float(pos_cfg.entry_threshold), float(pos_cfg.exit_threshold),
        int(pos_cfg.time_stop_min), int(units), int(config.leverage),
        100, 1, spread_active, int(max_num), int(max_den),
        int(initial_cash_scaled), int(SCALE_RATIO), int(warmup),
        out_entry_idx, out_exit_idx, out_side, out_entry_px, out_exit_px,
        out_reason, out_pos_id, out_equity_at_entry, out_equity_scaled,
    )
    if status != STATUS_OK:
        # overflow → Decimal 経路で再実行 (run 監査用に明示ログ)。
        logger.warning(
            "backtest.kernel_overflow_fallback",
            instrument=config.instrument,
            bars=n,
            trades_before_overflow=int(n_trades),
        )
        return None

    instrument = broker._meta.oanda_name
    trades: list[Trade] = []
    for t in range(int(n_trades)):
        side: PositionSide = "long" if int(out_side[t]) == 1 else "short"
        e_idx = int(out_entry_idx[t])
        x_idx = int(out_exit_idx[t])
        entry_price = scaled_to_price(int(out_entry_px[t]))
        exit_price = scaled_to_price(int(out_exit_px[t]))
        if side == "long":
            raw_pnl = Decimal(units) * (exit_price - entry_price)
        else:
            raw_pnl = Decimal(units) * (entry_price - exit_price)
        exit_bar = bars_list[x_idx]
        exit_spread = exit_bar.spread_close
        if exit_spread < 0:
            exit_spread = Decimal(0)
        spread_cost = abs(Decimal(units)) * exit_spread * Decimal(2)
        trades.append(
            Trade(
                position_id=int(out_pos_id[t]),
                instrument=instrument,
                side=side,
                units=units,
                entry_price=entry_price,
                entry_time=bars_list[e_idx].bar_time,
                exit_price=exit_price,
                exit_time=exit_bar.bar_time,
                pnl=raw_pnl,  # holding_cost=0 → net_pnl == raw_pnl
                exit_reason=_REASON_CODE_TO_STR[int(out_reason[t])],
                equity_at_entry=decode_equity(int(out_equity_at_entry[t])),
                spread_cost=spread_cost,
                holding_cost=Decimal(0),
            )
        )

    equity_curve = EquityCurve(col.epoch_ns, out_equity_scaled)

    # broker 最終状態を同期する (observable behavior contract:
    # broker.cash / open_positions / trades を読む caller・既存テストのため)。
    # 末尾 bar は is_eod=True で必ず flat → equity[-1] == 最終 cash。
    broker._cash = decode_equity(int(out_equity_scaled[-1]))
    broker._positions = {}
    broker._trades = trades
    broker._last_bar = bars_list[-1]

    logger.info(
        "backtest.finished",
        instrument=config.instrument,
        bars=n,
        trades=len(trades),
        final_equity=str(broker._cash),
        session_close_drop_open_count=int(sess_drop_open),
        session_close_drop_pending_count=int(sess_drop_pending),
        first_drop_open_bar_time=None,
        negative_equity_drop_open_count=int(neg_drop),
        engine="kernel",
    )

    session_blocks = aggregate_session_blocks(bars_list, trades, mode="test")

    return BacktestResult(
        config=config,
        trades=trades,
        equity_curve=equity_curve,
        session_blocks=session_blocks,
    )
