"""backtest broker simulation の numba njit kernel (T108)。

``engine.run_backtest`` の per-bar ループ + ``broker.MockBroker`` の約定・equity・
margin・session/EOD 強制クローズを、columnar scaled-int 入力に対する単一 njit
ループに畳む。signal (composite) は呼び出し側で事前計算した float64 配列を渡す
(値は現行と不変)。

数値契約 (詳細設計 §2-2):
- price/cash は scaled-int (PRICE_SCALE=1e5 / CASH_SCALE=1e8、SCALE_RATIO=1e3)。
- 約定数に逆流する 2 gate (margin call / spread filter) は商を作らず整数
  cross-multiply で判定する → Decimal と bit-identical (maint=100 / leverage=3 /
  max_spread 整数 の前提下。preflight が担保)。
- overflow は乗算前 sentinel で検出し、status を返して呼び出し側が Decimal 経路で
  再実行する (静的 hard gate は使わない)。

event ordering (詳細設計 §3、engine.py:147-199 と同順):
  drop_pending(session) → spread_filter → pre-fill equity gate → fill →
  mark_to_market → margin_call(post-fill) → session_close → on_bar/submit →
  EOD_close → equity 記録。

@ref: devnotes/20260520-1949-handoff-backtest-engine-numba/detailed-design.md §施策2
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit

    _USE_NUMBA = True
except ImportError:  # pragma: no cover - numba は依存に含まれる
    _USE_NUMBA = False

    def njit(*args, **kwargs):  # type: ignore[misc]
        def _wrap(func):
            return func

        if args and callable(args[0]):
            return args[0]
        return _wrap


_INT64_MAX = np.int64(9223372036854775807)

# exit reason codes (broker.orders.ExitReason に対応)
REASON_SIGNAL = 0
REASON_EOD = 1
REASON_MARGIN_CALL = 2
REASON_END_OF_RUN = 3

# status codes (kernel 戻り値)
STATUS_OK = 0
STATUS_OVERFLOW = 1


@njit(cache=True, fastmath=False)
def _add_overflows(a, b):
    """int64 加算 a+b が wrap するか (numba は silent wrap のため明示判定)。"""
    if b > 0 and a > _INT64_MAX - b:
        return True
    return bool(b < 0 and a < -_INT64_MAX - b)


@njit(cache=True, fastmath=False)
def simulate(
    bid_o, bid_h, bid_l, bid_c,
    ask_o, ask_h, ask_l, ask_c,
    hour, is_eod, epoch_ns,
    composite,
    session_mask,              # bool[24]
    entry_threshold, exit_threshold,  # float
    time_stop_min,             # int (0 で無効)
    units, leverage,           # int, int
    maint_num, maint_den,      # int, int (default 100,1)
    spread_active,             # bool
    max_spread_num, max_spread_den,  # int, int (default 10,1)
    initial_cash_scaled,       # int64 (CASH_SCALE)
    scale_ratio,               # int (= CASH_SCALE/PRICE_SCALE)
    warmup,                    # int
    # out 配列 (呼び出し側で n_bars 長を事前確保)
    out_entry_idx, out_exit_idx, out_side,
    out_entry_px, out_exit_px, out_reason, out_pos_id, out_equity_at_entry,
    out_equity_scaled,
):
    """broker simulation を実行し trade records + equity 配列を埋める。

    Returns:
        (status, n_trades, neg_equity_drop, session_drop_open, session_drop_pending)
        status==STATUS_OVERFLOW の場合、結果は不完全 → 呼び出し側が Decimal 再実行。
    """
    n = bid_c.shape[0]
    cash = initial_cash_scaled  # CASH_SCALE

    has_pos = False
    pos_side = 0
    pos_entry = 0       # PRICE_SCALE
    pos_entry_epoch = 0
    pos_entry_idx = 0
    pos_eq_at_entry = 0  # CASH_SCALE
    pos_id_cur = 0

    pending_kind = 0  # 0 none / 1 open_long / 2 open_short / 3 close
    last_num = 0
    last_den = 0  # 0 = 未設定

    pos_id_counter = 0
    n_trades = 0
    neg_drop = 0
    sess_drop_open = 0
    sess_drop_pending = 0

    # time_stop_min * 60e9 の overflow ガード (kernel 単体契約の硬化、impl-review R4 Suggestion)。
    if time_stop_min < 0 or np.int64(time_stop_min) > _INT64_MAX // np.int64(60_000_000_000):
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    time_stop_ns = np.int64(time_stop_min) * np.int64(60_000_000_000)

    # === 定数係数の overflow ガード (全て計算前に検査、計算順を guard と揃える) ===
    # pnl_factor (= units*scale_ratio): 全 `pnl_factor*delta` 積の一括安全証明の基。
    if units <= 0 or np.int64(units) > _INT64_MAX // np.int64(scale_ratio):
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    pnl_factor = np.int64(units) * np.int64(scale_ratio)
    pnl_safe = _INT64_MAX // pnl_factor
    # 価格は正値で |delta=p1-p2| <= max_abs_price。max_abs_price <= pnl_safe なら
    # 全乗算サイト (unreal/pnl) が int64 内に収まる (per-site 積ガード不要)。
    max_abs_price = max(np.max(ask_h), np.max(bid_h))  # 高値配列に最大価格が含まれる
    if max_abs_price > pnl_safe:
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    # margin LHS 係数 = 100*leverage*maint_den (guard 後に計算)。
    if leverage <= 0 or maint_den <= 0 or np.int64(leverage) > _INT64_MAX // np.int64(100):
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    lev100 = np.int64(100) * np.int64(leverage)
    if np.int64(maint_den) > _INT64_MAX // lev100:
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    margin_lhs_factor = lev100 * np.int64(maint_den)
    # margin RHS 係数 = maint_num*units*scale_ratio = maint_num*pnl_factor (guard 後)。
    if maint_num <= 0 or np.int64(maint_num) > _INT64_MAX // pnl_factor:
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    margin_rhs_factor = np.int64(maint_num) * pnl_factor
    # spread filter cross-multiply の overflow sentinel 用 safe 上界 (定数)。
    if max_spread_den <= 0 or np.int64(max_spread_den) > _INT64_MAX // np.int64(20000):
        return (STATUS_OVERFLOW, 0, 0, 0, 0)
    spread_lhs_factor = np.int64(20000) * np.int64(max_spread_den)
    spread_lhs_safe = _INT64_MAX // spread_lhs_factor
    spread_rhs_safe = _INT64_MAX // np.int64(max_spread_num) if max_spread_num > 0 else _INT64_MAX

    for i in range(n):
        session_closed = session_mask[hour[i]]

        # --- step1: session close なら pending open を drop ---
        if session_closed and (pending_kind == 1 or pending_kind == 2):
            sess_drop_pending += 1
            pending_kind = 0

        # --- step2: spread filter (前 bar close spread、20000 係数を保持) ---
        # (ask-bid)*20000/(ask+bid) > max_num/max_den を商を作らず cross-multiply で判定。
        if spread_active and (pending_kind == 1 or pending_kind == 2) and last_den > 0:
            # overflow sentinel (乗算前): 超過時は Decimal 経路へ
            last_num_abs = last_num if last_num >= 0 else -last_num
            if last_num_abs > spread_lhs_safe or last_den > spread_rhs_safe:
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            if last_num * spread_lhs_factor > max_spread_num * last_den:
                pending_kind = 0

        # --- step3: pre-fill equity gate (fill 前) ---
        if has_pos:
            unreal = (
                pnl_factor * (bid_c[i] - pos_entry)
                if pos_side == 1
                else pnl_factor * (pos_entry - ask_c[i])
            )
        else:
            unreal = np.int64(0)
        if _add_overflows(cash, unreal):
            return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
        equity_pre = cash + unreal
        if (pending_kind == 1 or pending_kind == 2) and equity_pre <= 0:
            neg_drop += 1
            pending_kind = 0

        # --- step4: fill (前 bar submit 分の約定) ---
        if pending_kind == 1 and not has_pos:
            has_pos = True
            pos_side = 1
            pos_entry = ask_o[i]
            pos_entry_epoch = epoch_ns[i]
            pos_entry_idx = i
            pos_eq_at_entry = equity_pre
            pos_id_counter += 1
            pos_id_cur = pos_id_counter
        elif pending_kind == 2 and not has_pos:
            has_pos = True
            pos_side = -1
            pos_entry = bid_o[i]
            pos_entry_epoch = epoch_ns[i]
            pos_entry_idx = i
            pos_eq_at_entry = equity_pre
            pos_id_counter += 1
            pos_id_cur = pos_id_counter
        elif pending_kind == 3 and has_pos:
            # close at OPEN price (exit_kind="open")
            if pos_side == 1:
                exit_px = bid_o[i]
                pnl = pnl_factor * (exit_px - pos_entry)
            else:
                exit_px = ask_o[i]
                pnl = pnl_factor * (pos_entry - exit_px)
            if _add_overflows(cash, pnl):
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            cash += pnl
            out_entry_idx[n_trades] = pos_entry_idx
            out_exit_idx[n_trades] = i
            out_side[n_trades] = pos_side
            out_entry_px[n_trades] = pos_entry
            out_exit_px[n_trades] = exit_px
            out_reason[n_trades] = REASON_SIGNAL
            out_pos_id[n_trades] = pos_id_cur
            out_equity_at_entry[n_trades] = pos_eq_at_entry
            n_trades += 1
            has_pos = False
        pending_kind = 0

        # --- step5: mark_to_market (当 bar close spread を更新) ---
        s = ask_c[i] + bid_c[i]
        if s > 0:
            last_num = ask_c[i] - bid_c[i]
            last_den = s

        # --- step6: margin call (post-fill equity 再計算、cross-multiply) ---
        if has_pos:
            unreal_post = (
                pnl_factor * (bid_c[i] - pos_entry)
                if pos_side == 1
                else pnl_factor * (pos_entry - ask_c[i])
            )
            if _add_overflows(cash, unreal_post):
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            equity_post = cash + unreal_post
            # overflow sentinel (乗算前)
            eq_abs = equity_post if equity_post >= 0 else -equity_post
            if eq_abs > _INT64_MAX // margin_lhs_factor:
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            entry_abs = pos_entry if pos_entry >= 0 else -pos_entry
            if entry_abs > _INT64_MAX // margin_rhs_factor:
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            lhs = equity_post * margin_lhs_factor
            rhs = margin_rhs_factor * pos_entry
            if lhs < rhs:
                if pos_side == 1:
                    exit_px = bid_c[i]
                    pnl = pnl_factor * (exit_px - pos_entry)
                else:
                    exit_px = ask_c[i]
                    pnl = pnl_factor * (pos_entry - exit_px)
                if _add_overflows(cash, pnl):
                    return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
                cash += pnl
                out_entry_idx[n_trades] = pos_entry_idx
                out_exit_idx[n_trades] = i
                out_side[n_trades] = pos_side
                out_entry_px[n_trades] = pos_entry
                out_exit_px[n_trades] = exit_px
                out_reason[n_trades] = REASON_MARGIN_CALL
                out_pos_id[n_trades] = pos_id_cur
                out_equity_at_entry[n_trades] = pos_eq_at_entry
                n_trades += 1
                has_pos = False

        # --- step7: session close (保有を全クローズ) ---
        if session_closed and has_pos:
            if pos_side == 1:
                exit_px = bid_c[i]
                pnl = pnl_factor * (exit_px - pos_entry)
            else:
                exit_px = ask_c[i]
                pnl = pnl_factor * (pos_entry - exit_px)
            if _add_overflows(cash, pnl):
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            cash += pnl
            out_entry_idx[n_trades] = pos_entry_idx
            out_exit_idx[n_trades] = i
            out_side[n_trades] = pos_side
            out_entry_px[n_trades] = pos_entry
            out_exit_px[n_trades] = exit_px
            out_reason[n_trades] = REASON_EOD
            out_pos_id[n_trades] = pos_id_cur
            out_equity_at_entry[n_trades] = pos_eq_at_entry
            n_trades += 1
            has_pos = False

        # --- step8: on_bar (snapshot は margin/session 後) → 次 bar 用 pending ---
        if i >= warmup:
            comp = composite[i]
            if has_pos:
                # exit 判定 (time_stop → hysteresis、いずれも close_position signal)
                time_stop_hit = (
                    time_stop_min > 0
                    and (epoch_ns[i] - pos_entry_epoch) >= time_stop_ns
                )
                hysteresis_hit = (
                    (pos_side == 1 and comp < exit_threshold)
                    or (pos_side == -1 and (-comp) < exit_threshold)
                )
                if time_stop_hit or hysteresis_hit:
                    pending_kind = 3
            else:
                # entry 判定 (session_closed の open は drop)
                new_kind = 0
                if comp >= entry_threshold:
                    new_kind = 1
                elif (-comp) >= entry_threshold:
                    new_kind = 2
                if new_kind != 0:
                    if session_closed:
                        sess_drop_open += 1
                    else:
                        pending_kind = new_kind

        # --- step9: EOD 強制クローズ ---
        if is_eod[i] and has_pos:
            if pos_side == 1:
                exit_px = bid_c[i]
                pnl = pnl_factor * (exit_px - pos_entry)
            else:
                exit_px = ask_c[i]
                pnl = pnl_factor * (pos_entry - exit_px)
            if _add_overflows(cash, pnl):
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            cash += pnl
            out_entry_idx[n_trades] = pos_entry_idx
            out_exit_idx[n_trades] = i
            out_side[n_trades] = pos_side
            out_entry_px[n_trades] = pos_entry
            out_exit_px[n_trades] = exit_px
            out_reason[n_trades] = REASON_EOD
            out_pos_id[n_trades] = pos_id_cur
            out_equity_at_entry[n_trades] = pos_eq_at_entry
            n_trades += 1
            has_pos = False

        # --- step10: equity 記録 (全クローズ後) ---
        if has_pos:
            unreal_rec = (
                pnl_factor * (bid_c[i] - pos_entry)
                if pos_side == 1
                else pnl_factor * (pos_entry - ask_c[i])
            )
            if _add_overflows(cash, unreal_rec):
                return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
            out_equity_scaled[i] = cash + unreal_rec
        else:
            out_equity_scaled[i] = cash

    # --- post: end_of_run 端数決済 (is_eod[n-1]=True で通常は到達しない) ---
    if has_pos and n > 0:
        last = n - 1
        if pos_side == 1:
            exit_px = bid_c[last]
            pnl = pnl_factor * (exit_px - pos_entry)
        else:
            exit_px = ask_c[last]
            pnl = pnl_factor * (pos_entry - exit_px)
        if _add_overflows(cash, pnl):
            return (STATUS_OVERFLOW, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
        cash += pnl
        out_entry_idx[n_trades] = pos_entry_idx
        out_exit_idx[n_trades] = last
        out_side[n_trades] = pos_side
        out_entry_px[n_trades] = pos_entry
        out_exit_px[n_trades] = exit_px
        out_reason[n_trades] = REASON_END_OF_RUN
        out_pos_id[n_trades] = pos_id_cur
        out_equity_at_entry[n_trades] = pos_eq_at_entry
        n_trades += 1
        has_pos = False
        out_equity_scaled[last] = cash

    return (STATUS_OK, n_trades, neg_drop, sess_drop_open, sess_drop_pending)
