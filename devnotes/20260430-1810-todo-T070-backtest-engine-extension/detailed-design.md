# 詳細設計: T070 — Backtest engine 拡張 (session bucket / spread_cost / session block PnL)

**作成日時**: 2026-04-30 18:50 JST (Round 2 改訂: 19:05 JST)
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 4 APPROVED 済 (`conceptual-review-round-4.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 / §4 の擬似コードは概念設計 §3.4.0 (会計契約) / §5 (API) と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `f5e6fc2` (T069 commit 後)
**改訂履歴**: Round 1 [C1-C4] / [W1-W3] / [S1-S3] 全反映 (`detailed-review-round-1.md` 参照)

## 0. 詳細設計の責務

概念設計で確定した会計契約 / API / アルゴリズム / 不変条件を **コード単位** に展開:
- 完全な擬似コード (Python に近いがフォーマットは設計書)
- spread_cost 計算式の正式化 (PriceBar.bid/ask から)
- caller signature 完全展開
- F1-F23 と test_id の 1:1 対応 (Phase 1 / Phase 2 切り分け)
- DoD / Phase 1 / Phase 2 切り分け

## 1. ファイル / 関数 / クラス 完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/backtest/session_block.py` | `SessionBlockBucket`, `BLOCK_BUCKET_RANGES_UTC`, `SessionBlock`, `compute_bucket_for_bar`, `compute_bucket_for_trade`, `aggregate_session_blocks`, `apply_spread_stress` | +200 |
| `tests/backtest/test_session_block.py` | F1, F3, F6, F7, F11, F12, F15, F18, F22 + happy path | +250 |

### 1.2 既存ファイル変更

| Path | 関数 / 行 | 変更内容 | LOC 増減 |
|---|---|---|---|
| `src/broker/orders.py:33-46` | `Trade` dataclass | `spread_cost: Decimal = Decimal(0)` + `holding_cost: Decimal = Decimal(0)` 追加 | +2 |
| `src/broker/mock.py:400-424` | `_close_one` | spread_cost 計算 + holding_cost 転記 + Trade 構築引数追加 | +6 |
| `src/backtest/engine.py:74-78` | `BacktestResult` | `session_blocks: tuple[SessionBlock, ...] = field(default_factory=tuple)` 追加 | +2 |
| `src/backtest/engine.py:185-196` | `run_backtest` 末尾 | `aggregate_session_blocks(bars_list, broker.trades)` 計算 + `BacktestResult` 同梱 | +5 |
| `tests/broker/test_orders.py` | Trade test | F23: 新 field default + invariant test | +20 |
| `tests/broker/test_mock.py` | _close_one test | F8 / F13 / F19: spread_cost / holding_cost 転記 + 二重計上なし | +50 |
| `tests/backtest/test_engine.py` | run_backtest test | F4 / F16: session_blocks 同梱 + block invariant | +40 |
| `docs/alpha_factory/stage-gates.md` | T070 セクション | 仕様追記 | +40 |

### 1.3 Phase 2 申し送り (T070 PR では touch しない)

- T064 stage_bc_evaluator: apply_spread_stress を T070 import に置換 + `TradeRecord` 表記 → `Trade` 統一 (Round 1 [W2])
- T061 canonical_metrics: SessionBlock を入力に SR_session_worst / WR_worst 計算
- T072 DST/holiday: BLOCK_BUCKET_RANGES_UTC への DST 例外
- run_ga.py / 既存 backtest_runner: BacktestResult.session_blocks の caller 配線
- run report / archive: spread_cost / holding_cost / pnl_before_costs の log/report 露出 (F17/F20)

## 2. 既存 caller signature 完全展開 (Round 1 [C3] 反映、 実 grep 結果で網羅化)

T070 PR は library + dataclass field 追加が中心、 既存 signature の **破壊変更なし**:

### 2.1 Trade 構築 caller 完全リスト (`grep -rn "Trade(" src/ tests/ scripts/` 結果)

| ファイル:行 | 構築方法 | T070 PR 影響 |
|---|---|---|
| `src/broker/mock.py:412` | keyword 構築 (12 field 全列挙) | T070 で改造済 (= spread_cost / holding_cost を追加渡し) |
| `tests/backtest/test_advanced_metrics.py:14` | keyword 構築 (helper fixture) | 影響なし (default 適用、 spread_cost=0 / holding_cost=0) |
| `tests/backtest/test_metrics.py:21` | keyword 構築 (helper fixture) | 影響なし (default 適用) |
| `tests/alpha_factory/test_stage_gate.py:854` | keyword 構築 (overnight_trade) | 影響なし (default 適用) |
| `tests/alpha_factory/test_stage_gate.py:867` | keyword 構築 (overnight_trade2) | 影響なし (default 適用) |

→ 全 caller が **keyword 構築** のため、 新 field 追加 (default 付き) で破壊変更なし。 positional 構築は既存コードベースに不在 (grep で確認済)。

### 2.2 BacktestResult 構築 caller 完全リスト

| ファイル:行 | 構築方法 | T070 PR 影響 |
|---|---|---|
| `src/backtest/engine.py:196` | keyword 構築 (config, trades, equity_curve) | T070 で改造済 (= session_blocks を追加渡し) |
| `tests/alpha_factory/test_stage_gate.py:895` | keyword 構築 (config, trades, equity_curve) | 影響なし (default_factory=tuple、 session_blocks 省略可) |

→ 全 caller が **keyword 構築**。 default_factory で破壊変更なし。

### 2.3 関数 caller (signature 不変)

| Caller | 既存 signature | T070 PR 影響 |
|---|---|---|
| `_close_one()` 内部 caller (`MockBroker._close_all_internal` 等) | `(position_id, bar, exit_kind, reason)` | signature 不変、 内部実装変更のみ |
| `MockBroker.apply_bar_holding_cost` | `(bar, *, per_day_bps, bar_minutes)` | 影響なし (T070 で touch しない、 既存挙動維持) |
| `run_backtest()` 既存 caller | `(bars, strategy, broker, config)` | signature 不変、 戻り値の `BacktestResult.session_blocks` が default_factory で backward-compat |

### 2.4 grep DoD (= F9 / F23 PR review check)

T070 PR 実装時の確認:
```bash
grep -rn "Trade(" src/ tests/ scripts/ --include="*.py" | grep -v "OrderSignal\|class Trade\|TradeRecord"
grep -rn "BacktestResult(" src/ tests/ scripts/ --include="*.py"
```
全 caller が keyword 構築であり、 新 field 追加で破壊変更なしを再確認。

## 3. データモデル詳細 (擬似コード)

### 3.1 SessionBlockBucket

```python
# src/backtest/session_block.py

from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Final, Literal

from src.broker.orders import Trade
from src.domain.price import PriceBar

__all__ = [
    "SessionBlockBucket",
    "BLOCK_BUCKET_RANGES_UTC",
    "SessionBlock",
    "compute_bucket_for_bar",
    "compute_bucket_for_trade",
    "aggregate_session_blocks",
    "apply_spread_stress",
]

SessionBlockBucket = Literal["tokyo", "london", "ny"]

# 8h covering partition (synthesis § 4.4 SSOT). primitives の 9h overlap windows
# (`src/alpha_factory/primitives/_indicators.py:51-55` の `_SESSION_RANGES_UTC`) と
# は別責務、 並列管理。
BLOCK_BUCKET_RANGES_UTC: Final[dict[SessionBlockBucket, tuple[int, int]]] = {
    "tokyo":  (0, 8),    # [0, 8) UTC hour
    "london": (8, 16),   # [8, 16)
    "ny":     (16, 24),  # [16, 24)
}

# Phase 2 で T072 が DST/holiday 例外を別 layer で扱う。 T070 では UTC 単純基準。

_BUCKETS: Final[tuple[SessionBlockBucket, ...]] = tuple(BLOCK_BUCKET_RANGES_UTC.keys())  # SSOT 駆動 (Round 2 [W1] 反映)
_M1_EXPECTED_BAR_COUNT: Final[int] = 480  # 8h × 60min
```

### 3.2 SessionBlock

```python
@dataclass(frozen=True)
class SessionBlock:
    """1 営業日 (UTC date) × 1 bucket = 1 block (synthesis § 4.4 SSOT).

    SSOT: 概念設計 §3.4 / §4.3.

    属性:
        business_date: UTC date (date object). T072 で営業日定義の精緻化予定.
        bucket: tokyo / london / ny.
        bar_count: block 内 bar 数 (M1 想定で 8h = 480 bars).
        trade_count: block 内 trade 数 (= trade.exit_time が本 block に属する trade).
        pnl_net: block 内 trade の全 cost 控除済 net 合計
            (= sum(t.pnl - t.spread_cost), holding は既に Trade.pnl に net、
             spread は block 集計時に別途控除. §3.4.0 SSOT 参照).
        pnl_before_costs: pnl_net + spread_cost_total + holding_cost_total
            (= 控除前 gross. = sum(t.pnl + t.holding_cost) と同値).
        spread_cost_total: block 内 trade の spread_cost 合計.
        holding_cost_total: block 内 trade の holding_cost 合計.

    不変条件 (__post_init__ で assert):
        bar_count >= 0
        trade_count >= 0
        spread_cost_total >= 0
        holding_cost_total >= 0
        pnl_before_costs == pnl_net + spread_cost_total + holding_cost_total
    """

    business_date: date
    bucket: SessionBlockBucket
    bar_count: int
    trade_count: int
    pnl_net: Decimal
    pnl_before_costs: Decimal
    spread_cost_total: Decimal
    holding_cost_total: Decimal

    def __post_init__(self) -> None:
        if self.bar_count < 0:
            raise ValueError(f"bar_count must be >= 0, got {self.bar_count}")
        if self.trade_count < 0:
            raise ValueError(f"trade_count must be >= 0, got {self.trade_count}")
        if self.spread_cost_total < 0:
            raise ValueError(
                f"spread_cost_total must be >= 0, got {self.spread_cost_total}"
            )
        if self.holding_cost_total < 0:
            raise ValueError(
                f"holding_cost_total must be >= 0, got {self.holding_cost_total}"
            )
        # F6 invariant
        expected = self.pnl_net + self.spread_cost_total + self.holding_cost_total
        if self.pnl_before_costs != expected:
            raise ValueError(
                f"pnl_before_costs ({self.pnl_before_costs}) != "
                f"pnl_net + spread_cost_total + holding_cost_total ({expected})"
            )

    @property
    def is_empty_trade_block(self) -> bool:
        """trade_count == 0 (= synthesis § 6.3 0.5 neutral 対象).

        Round 1 [S1] 反映: T061 / T072 が neutral / boundary を機械判定.
        """
        return self.trade_count == 0

    @property
    def is_partial_bar_block(self) -> bool:
        """bar_count < 480 (= 末日・週末・holiday で 8h 不足).

        T072 で正確な期待 bar_count を計算する場合は本 property を上書き予定.
        T070 SSOT は M1 前提で `expected_bar_count = 480`.
        """
        return self.bar_count < _M1_EXPECTED_BAR_COUNT
```

### 3.3 Trade 拡張 (既存改造)

```python
# src/broker/orders.py:33-46

@dataclass(frozen=True)
class Trade:
    position_id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_time: datetime
    pnl: Decimal               # 既存挙動: net of holding_cost (= raw_pnl - holding_cost_accum)
    exit_reason: ExitReason
    equity_at_entry: Decimal = Decimal(0)
    # T070 追加 (概念設計 §3.4.0 / §3.5 SSOT 参照)
    spread_cost: Decimal = Decimal(0)   # 記録のみ、 既存 pnl 未反映 (= 監査・stress 用 field)
    holding_cost: Decimal = Decimal(0)  # _holding_cost_by_position 転記 (= 既存 pnl に既反映済)
```

## 4. アルゴリズム詳細 (擬似コード)

### 4.1 compute_bucket_for_bar / compute_bucket_for_trade

```python
def compute_bucket_for_bar(bar_time: datetime) -> SessionBlockBucket:
    """UTC hour から SessionBlockBucket を決定論的に割当.

    SSOT: 概念設計 §5.1. Round 1 [C1] 反映で BLOCK_BUCKET_RANGES_UTC 駆動に変更
    (= 8 / 16 を直書きせず、 単一 SSOT を参照).

    Args:
        bar_time: timezone-aware UTC datetime.

    Returns:
        SessionBlockBucket.

    Raises:
        ValueError: bar_time.tzinfo is None / 非 UTC offset.
        RuntimeError: BLOCK_BUCKET_RANGES_UTC が 24h covering を満たさない場合
            (= const 改変に対する defense-in-depth、 通常発生しない).
    """
    if bar_time.tzinfo is None:
        raise ValueError(
            f"bar_time must be timezone-aware (UTC), got naive: {bar_time}"
        )
    offset = bar_time.utcoffset()
    if offset != timedelta(0):
        raise ValueError(
            f"bar_time must be UTC offset, got offset={offset}: {bar_time}"
        )
    hour = bar_time.hour  # 0-23
    # BLOCK_BUCKET_RANGES_UTC 駆動 (= 単一 SSOT 参照、 Round 1 [C1] 反映)
    for bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
        if start <= hour < end:
            return bucket
    raise RuntimeError(
        f"hour {hour} not covered by BLOCK_BUCKET_RANGES_UTC "
        f"(= partition contract violation): {BLOCK_BUCKET_RANGES_UTC}"
    )


def compute_bucket_for_trade(trade: Trade) -> SessionBlockBucket:
    """trade 帰属 bucket を決定論的に算出 (= trade.exit_time 基準).

    SSOT: 概念設計 §5.1 / §3.4.1 (全 cost を exit bucket 一括帰属).

    Args:
        trade: Trade dataclass.

    Returns:
        SessionBlockBucket (= compute_bucket_for_bar(trade.exit_time) と同義).
    """
    return compute_bucket_for_bar(trade.exit_time)
```

### 4.2 aggregate_session_blocks

```python
def aggregate_session_blocks(
    bars: Sequence[PriceBar],
    trades: Sequence[Trade],
) -> tuple[SessionBlock, ...]:
    """bars と trades から SessionBlock 配列を構築する (pure function).

    SSOT: 概念設計 §3.4.0 / §5.2.

    集計式 (§3.4.0 SSOT):
        pnl_net = sum(t.pnl - t.spread_cost for t in trades_in_block)
        pnl_before_costs = sum(t.pnl + t.holding_cost for t in trades_in_block)
        spread_cost_total = sum(t.spread_cost for t in trades_in_block)
        holding_cost_total = sum(t.holding_cost for t in trades_in_block)

    date universe (Round 1 [W1] SSOT):
        bars が触れた UTC date set × 3 bucket = 全 (date, bucket) 組合せ.
        empty block (trade_count=0 / bar_count=0) も含む.

    Args:
        bars: backtest 期間中の全 bar (時系列順、 UTC tz-aware).
        trades: backtest で生成された全 trade.

    Returns:
        SessionBlock の tuple. (date, bucket) で sort.

    Raises:
        ValueError: bar_time / trade.exit_time が naive / 非 UTC.
    """
    # 1. bars を (date, bucket) でグループ化、 bar_count を集計
    bar_count_map: dict[tuple[date, SessionBlockBucket], int] = {}
    date_set: set[date] = set()
    for bar in bars:
        bucket = compute_bucket_for_bar(bar.bar_time)  # ValueError raise 経路
        d = bar.bar_time.date()
        date_set.add(d)
        key = (d, bucket)
        bar_count_map[key] = bar_count_map.get(key, 0) + 1

    # 2. trades を (date, bucket) でグループ化、 集計
    trade_groups: dict[tuple[date, SessionBlockBucket], list[Trade]] = {}
    for trade in trades:
        bucket = compute_bucket_for_trade(trade)  # ValueError raise 経路
        d = trade.exit_time.date()
        date_set.add(d)  # trade exit_time が bars 範囲外 (= edge case) でも include
        key = (d, bucket)
        trade_groups.setdefault(key, []).append(trade)

    # 3. date universe = bars + trades が触れた全 UTC date × 3 bucket
    blocks: list[SessionBlock] = []
    for d in sorted(date_set):
        for bucket in _BUCKETS:
            key = (d, bucket)
            bar_count = bar_count_map.get(key, 0)
            block_trades = trade_groups.get(key, [])
            trade_count = len(block_trades)

            # §3.4.0 SSOT 集計式
            pnl_net = sum(
                (t.pnl - t.spread_cost for t in block_trades),
                start=Decimal(0),
            )
            pnl_before_costs = sum(
                (t.pnl + t.holding_cost for t in block_trades),
                start=Decimal(0),
            )
            spread_cost_total = sum(
                (t.spread_cost for t in block_trades),
                start=Decimal(0),
            )
            holding_cost_total = sum(
                (t.holding_cost for t in block_trades),
                start=Decimal(0),
            )

            blocks.append(SessionBlock(
                business_date=d,
                bucket=bucket,
                bar_count=bar_count,
                trade_count=trade_count,
                pnl_net=pnl_net,
                pnl_before_costs=pnl_before_costs,
                spread_cost_total=spread_cost_total,
                holding_cost_total=holding_cost_total,
            ))

    return tuple(blocks)
```

### 4.3 apply_spread_stress (T064 申し送り解消、 Round 1 [C2] / [S1] 反映)

```python
def apply_spread_stress(
    trades: Sequence[Trade],
    multiplier: Decimal,
) -> tuple[Trade, ...]:
    """各 trade の spread_cost を multiplier 倍にして pnl を再計算した tuple を返す.

    SSOT: 概念設計 §5.3 / §3.4.0.

    Stress 適用式 (= 既存 broker は spread を pnl 控除していないため、 stress 倍率による
    余計分のみを pnl から控除する):
        delta_spread = trade.spread_cost * (multiplier - Decimal(1))
        new_pnl = trade.pnl - delta_spread
        new_spread_cost = trade.spread_cost * multiplier
        new_holding_cost = trade.holding_cost  # 不変 (stress は spread 専用)

    multiplier=1 で no-op (delta=0、 new_pnl=trade.pnl, new_spread_cost=trade.spread_cost).

    ### 契約境界 (Round 1 [C2] / [S1] 反映、 Trade(normal) vs Trade(stressed) 分離)

    **Trade(normal)** (= 通常 broker 出力 / aggregate_session_blocks 入力):
        invariant: `Trade.pnl + Trade.holding_cost == raw_pnl` (price-diff pnl)
        F13 invariant 適用範囲。

    **Trade(stressed)** (= apply_spread_stress 出力):
        invariant: `Trade.pnl + Trade.holding_cost == raw_pnl - delta_spread`
                   (= 元 raw_pnl から余計 spread を控除した擬似 pnl)
        F13 invariant は **適用しない** (= stress 済 trade は通常会計と別レイヤー).
        下流 (T064 stress evaluator) が「stress 済 trade は集計・SR 計算用、 broker.cash には
        反映されない」 を契約として扱う必要あり.

    aggregate_session_blocks は Trade(normal) を入力前提 (= caller が stress 済 trade を
    渡した場合の SessionBlock invariant 保証は別途 caller 責務).

    Args:
        trades: 元 Trade(normal) sequence.
        multiplier: spread cost 倍率 (>= 1.0、 finite).

    Returns:
        新 Trade(stressed) tuple (元 tuple は不変、 frozen dataclass).

    Raises:
        ValueError: multiplier < 1.0 / NaN / Infinite.
    """
    if not multiplier.is_finite():
        raise ValueError(f"multiplier must be finite, got {multiplier}")
    if multiplier < Decimal(1):
        raise ValueError(f"multiplier must be >= 1.0, got {multiplier}")

    delta_factor = multiplier - Decimal(1)
    return tuple(
        replace(
            t,
            pnl=t.pnl - t.spread_cost * delta_factor,
            spread_cost=t.spread_cost * multiplier,
        )
        for t in trades
    )
```

### 4.4 MockBroker._close_one 改造 (既存最小変更)

```python
# src/broker/mock.py:400-424 (改造後)

def _close_one(
    self, position_id: int, bar: PriceBar, exit_kind: str, reason: ExitReason
) -> Trade | None:
    pos = self._positions.pop(position_id, None)
    if pos is None:
        return None
    exit_price = self._exit_price(pos.side, bar, exit_kind)
    raw_pnl = self._realized_pnl(pos, exit_price)
    # T009: 累積 holding cost を pnl から差し引く (既存挙動維持)
    cost_accum = self._holding_cost_by_position.pop(pos.id, Decimal(0))
    net_pnl = raw_pnl - cost_accum
    # T070 追加: entry/exit spread を別 field 化 (Trade.pnl 未反映、 監査・stress 用)
    spread_cost = self._compute_trade_spread_cost(pos, bar)  # 詳細式は §4.5
    self._cash += raw_pnl  # 既存挙動維持
    trade = Trade(
        position_id=pos.id,
        instrument=pos.instrument,
        side=pos.side,
        units=pos.units,
        entry_price=pos.entry_price,
        entry_time=pos.entry_time,
        exit_price=exit_price,
        exit_time=bar.bar_time,
        pnl=net_pnl,                      # 既存挙動: net of holding_cost
        exit_reason=reason,
        equity_at_entry=pos.equity_at_entry,
        spread_cost=spread_cost,          # T070 追加
        holding_cost=cost_accum,          # T070 追加 (既存累積を転記)
    )
    self._trades.append(trade)
    self._invalidate_snapshot_cache()
    return trade
```

### 4.5 MockBroker._compute_trade_spread_cost (新規 helper)

spread_cost 計算式 (詳細設計で確定):

```python
def _compute_trade_spread_cost(self, pos: Position, bar: PriceBar) -> Decimal:
    """entry / exit の bid/ask spread から trade-level spread cost を推定.

    SSOT: 概念設計 §3.4.0 (spread_cost は監査・stress 用記録、 既存 pnl 未反映).

    計算式:
        # entry 時の spread (= 既に履歴で broker が知っている entry bar の bid/ask)
        # ただし MockBroker は entry 時の spread を保持していないため、
        # T070 では「exit bar の spread」を spread_cost の 2 倍プロキシとして採用
        # (= entry/exit の往復 spread の概算).
        # 注: 厳密な entry spread を取りたい場合は Phase 2 で broker 改造が必要.
        exit_spread = bar.spread_close  # ask.close - bid.close
        spread_cost_per_unit = exit_spread * 2  # entry + exit の往復近似
        spread_cost = abs(pos.units) * spread_cost_per_unit

    妥協点 (Phase 2 申し送り):
        - 厳密に「entry 時の spread」 を取得するには Position.entry_spread を broker が
          保持する必要あり (= dataclass 拡張)
        - T070 では「exit bar spread × 2」 を近似値として採用、 詳細実装で式の妥当性を再検証
        - apply_spread_stress は spread_cost を倍率変更するだけで、 spread_cost 自体の
          正確性は問わない (= multiplier=2 で「現在の 2 倍だった場合」 の pnl を再現する
          仕組みは spread_cost が定数倍されている限り正しい)

    根拠 (Round 1 [S3] 反映、 文献):
        Roll, R. (1984) "A Simple Implicit Measure of the Effective Bid-Ask Spread in an
        Efficient Market" (Journal of Finance) — bid-ask spread の往復取引コストとして
        2 倍が標準推定。 ただし本文献は equity market が対象、 FX への直接適用は要確認.

    Args:
        pos: 閉じる Position.
        bar: 閉じる時の PriceBar.

    Returns:
        spread_cost (>= 0).
    """
    exit_spread = bar.spread_close  # ask.close - bid.close, 既存 PriceBar.property
    # Round 1 [W1] 反映: 異常データ (bid > ask 等) で spread_close < 0 の場合は 0 に clamp、
    # SessionBlock.spread_cost_total >= 0 invariant を破らない
    if exit_spread < 0:
        exit_spread = Decimal(0)
    spread_cost_per_unit = exit_spread * Decimal(2)  # entry + exit 往復近似 (Roll 1984)
    spread_cost = abs(Decimal(pos.units)) * spread_cost_per_unit
    return spread_cost
```

### 4.6 BacktestResult / run_backtest 改造

```python
# src/backtest/engine.py

@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]
    equity_curve: list[tuple[datetime, Decimal]] = field(default_factory=list)
    # T070 追加 (Round 1 [C3] 反映、 transport SSOT)
    session_blocks: tuple[SessionBlock, ...] = field(default_factory=tuple)


def run_backtest(...) -> BacktestResult:
    # ... (既存処理は変更なし) ...

    logger.info(
        "backtest.finished",
        # ... (既存 fields) ...
    )

    # T070 追加: SessionBlock 集計 (Round 1 [C3] transport SSOT)
    session_blocks = aggregate_session_blocks(bars_list, broker.trades)

    return BacktestResult(
        config=config,
        trades=broker.trades,
        equity_curve=equity_curve,
        session_blocks=session_blocks,
    )
```

## 5. テスト計画詳細 (F1-F23 1:1 対応)

### 5.1 `tests/backtest/test_session_block.py` (新規)

```python
class TestComputeBucketForBar:
    def test_F1_bucket_assignment_at_tokyo(self):
        # F1 / F3: hour 0-7 → tokyo
        for h in range(0, 8):
            t = datetime(2024, 1, 15, h, 0, tzinfo=timezone.utc)
            assert compute_bucket_for_bar(t) == "tokyo"

    def test_F1_bucket_assignment_at_london(self):
        for h in range(8, 16):
            t = datetime(2024, 1, 15, h, 0, tzinfo=timezone.utc)
            assert compute_bucket_for_bar(t) == "london"

    def test_F1_bucket_assignment_at_ny(self):
        for h in range(16, 24):
            t = datetime(2024, 1, 15, h, 0, tzinfo=timezone.utc)
            assert compute_bucket_for_bar(t) == "ny"

    def test_F18_naive_datetime_raises(self):
        # F18 (Round 1)
        with pytest.raises(ValueError, match="timezone-aware"):
            compute_bucket_for_bar(datetime(2024, 1, 15, 12, 0))

    def test_F18_non_utc_offset_raises(self):
        # F18: JST (UTC+9) は reject
        from datetime import timedelta
        jst = timezone(timedelta(hours=9))
        with pytest.raises(ValueError, match="UTC offset"):
            compute_bucket_for_bar(datetime(2024, 1, 15, 12, 0, tzinfo=jst))


class TestSessionBlockInvariants:
    def test_F6_invariant_violation_raises(self):
        # F6: pnl_before_costs != pnl_net + spread + holding で raise
        with pytest.raises(ValueError, match="pnl_before_costs"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=480,
                trade_count=0,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(100),  # 不整合
                spread_cost_total=Decimal(0),
                holding_cost_total=Decimal(0),
            )

    def test_F11_negative_bar_count_raises(self):
        # F11: bar_count >= 0
        with pytest.raises(ValueError, match="bar_count"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=-1,
                trade_count=0,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(0),
                spread_cost_total=Decimal(0),
                holding_cost_total=Decimal(0),
            )

    def test_F11_property_is_empty_trade_block(self):
        block = SessionBlock(
            business_date=date(2024, 1, 15), bucket="tokyo",
            bar_count=480, trade_count=0,
            pnl_net=Decimal(0), pnl_before_costs=Decimal(0),
            spread_cost_total=Decimal(0), holding_cost_total=Decimal(0),
        )
        assert block.is_empty_trade_block is True
        assert block.is_partial_bar_block is False

    def test_F11_property_is_partial_bar_block(self):
        block = SessionBlock(
            business_date=date(2024, 1, 15), bucket="tokyo",
            bar_count=200, trade_count=0,  # < 480
            pnl_net=Decimal(0), pnl_before_costs=Decimal(0),
            spread_cost_total=Decimal(0), holding_cost_total=Decimal(0),
        )
        assert block.is_partial_bar_block is True


class TestAggregateSessionBlocks:
    def test_F7_empty_block_generated_when_no_trades(self):
        # F7: trade_count=0 でも block 生成
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        blocks = aggregate_session_blocks(bars, trades=[])
        assert len(blocks) == 3  # 1 day × 3 bucket
        assert all(b.is_empty_trade_block for b in blocks)
        assert all(b.bar_count == 480 for b in blocks)  # M1 full day

    def test_F3_date_universe_from_bars(self):
        # F3: bars が触れた UTC date set × 3 bucket
        bars_d1 = _make_bars_for_full_day(date(2024, 1, 15))
        bars_d2 = _make_bars_for_full_day(date(2024, 1, 16))
        bars = bars_d1 + bars_d2
        blocks = aggregate_session_blocks(bars, trades=[])
        assert len(blocks) == 6  # 2 dates × 3 bucket

    def test_F12_invariant_holds_for_aggregated(self):
        # F12: aggregate 結果も invariant 保持
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        trades = [_make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=timezone.utc),
            pnl=Decimal(10), spread_cost=Decimal(2), holding_cost=Decimal(1),
        )]
        blocks = aggregate_session_blocks(bars, trades)
        for b in blocks:
            assert b.pnl_before_costs == b.pnl_net + b.spread_cost_total + b.holding_cost_total

    def test_F22_pnl_net_uses_spread_subtraction(self):
        # F22: pnl_net = sum(t.pnl - t.spread_cost) (= 監査記録の意味、 §3.4.0 SSOT)
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=timezone.utc),
            pnl=Decimal(10), spread_cost=Decimal(3), holding_cost=Decimal(1),
        )
        blocks = aggregate_session_blocks(bars, [trade])
        tokyo_block = next(b for b in blocks if b.bucket == "tokyo")
        assert tokyo_block.pnl_net == Decimal(7)  # 10 - 3
        assert tokyo_block.pnl_before_costs == Decimal(11)  # 10 + 1


class TestApplySpreadStress:
    def test_F22_multiplier_1_is_noop(self):
        trade = _make_trade(pnl=Decimal(10), spread_cost=Decimal(2))
        result = apply_spread_stress([trade], multiplier=Decimal(1))
        assert result[0].pnl == Decimal(10)
        assert result[0].spread_cost == Decimal(2)

    def test_F22_multiplier_2_doubles_spread_cost(self):
        trade = _make_trade(pnl=Decimal(10), spread_cost=Decimal(2))
        result = apply_spread_stress([trade], multiplier=Decimal(2))
        # delta_spread = 2 * (2-1) = 2
        # new_pnl = 10 - 2 = 8
        # new_spread_cost = 2 * 2 = 4
        assert result[0].pnl == Decimal(8)
        assert result[0].spread_cost == Decimal(4)

    def test_F5_multiplier_below_one_raises(self):
        # F5
        trade = _make_trade(pnl=Decimal(10), spread_cost=Decimal(2))
        with pytest.raises(ValueError, match="multiplier must be >= 1.0"):
            apply_spread_stress([trade], multiplier=Decimal("0.5"))


class TestPartitionInvariant:
    def test_F15_block_bucket_ranges_cover_24h(self):
        # F15 / F18: 8h × 3 = 24h covering、 重複なし
        ranges = sorted(BLOCK_BUCKET_RANGES_UTC.values())
        # 重複なし
        for i in range(len(ranges) - 1):
            assert ranges[i][1] == ranges[i+1][0]
        # 24h カバー
        assert ranges[0][0] == 0
        assert ranges[-1][1] == 24
```

### 5.2 `tests/broker/test_orders.py` 拡張

```python
def test_F23_trade_default_costs_are_zero():
    # F23: spread_cost / holding_cost default
    trade = Trade(
        position_id=1, instrument="EUR_USD", side="long", units=10000,
        entry_price=Decimal("1.1"), entry_time=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        exit_price=Decimal("1.11"), exit_time=datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
        pnl=Decimal(100), exit_reason="signal",
    )
    assert trade.spread_cost == Decimal(0)
    assert trade.holding_cost == Decimal(0)


def test_F23_trade_with_costs():
    trade = Trade(
        position_id=1, instrument="EUR_USD", side="long", units=10000,
        entry_price=Decimal("1.1"), entry_time=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        exit_price=Decimal("1.11"), exit_time=datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
        pnl=Decimal(100), exit_reason="signal",
        spread_cost=Decimal(3),
        holding_cost=Decimal(2),
    )
    assert trade.spread_cost == Decimal(3)
    assert trade.holding_cost == Decimal(2)
```

### 5.3 `tests/broker/test_mock.py` 拡張

```python
def test_F8_close_one_records_spread_cost_and_holding_cost():
    # F8: _close_one が Trade の新 field を埋める
    broker = _make_broker_with_position()
    bar = _make_bar_with_spread(
        bar_time=datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
        bid_close=Decimal("1.10"),
        ask_close=Decimal("1.1002"),  # spread = 0.0002
    )
    trade = broker._close_one(position_id=1, bar=bar, exit_kind="close", reason="signal")
    assert trade is not None
    # spread_cost = abs(units) * (spread * 2) = 10000 * 0.0004 = 4.0
    expected_spread = abs(Decimal(10000)) * (bar.spread_close * Decimal(2))
    assert trade.spread_cost == expected_spread
    # holding_cost は既存累積を転記 (test fixture 次第、 ここでは 0 想定)
    assert trade.holding_cost == Decimal(0)


def test_F13_invariant_pnl_plus_holding_equals_raw():
    # F13 invariant: Trade.pnl + Trade.holding_cost == raw_pnl (price-diff pnl)
    broker = _make_broker_with_holding_cost_accumulated(holding=Decimal(5))
    bar = _make_bar(bar_time=datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc))
    trade = broker._close_one(...)
    raw_pnl = ...  # broker._realized_pnl の結果と一致するはず
    assert trade.pnl + trade.holding_cost == raw_pnl


def test_F19_no_double_counting_of_holding_cost():
    # F19: 既存 cash 動きが Trade.holding_cost 追加で変わらない
    broker_before = _make_broker_with_position()
    broker_before.apply_bar_holding_cost(...)
    cash_before_close = broker_before._cash
    trade = broker_before._close_one(...)
    cash_after_close = broker_before._cash
    # cash の動きは raw_pnl のみ (= 既存挙動)
    raw_pnl = ...
    assert cash_after_close == cash_before_close + raw_pnl
    # Trade.holding_cost は記録のみで cash に追加 debit していない
    assert trade.holding_cost > Decimal(0)  # 累積は転記されている
```

### 5.4 `tests/backtest/test_engine.py` 拡張

```python
def test_F4_run_backtest_returns_session_blocks():
    # F4 (Phase 1): BacktestResult.session_blocks が同梱
    result = _run_backtest_minimal(...)
    assert isinstance(result.session_blocks, tuple)
    assert len(result.session_blocks) >= 3  # 1 day なら 3 bucket


def test_F16_session_blocks_use_exit_time_for_attribution():
    # F16 (Round 1): trade.exit_time が tokyo で entry_time が london でも tokyo 帰属
    result = _run_backtest_with_cross_session_trade(...)
    # 検証: tokyo block の trade_count == 1
    tokyo_block = next(b for b in result.session_blocks if b.bucket == "tokyo")
    assert tokyo_block.trade_count == 1
```

## 6. 命名 / 表記揺れチェック (Round 4 [W11] 反映)

- `_close_one` (既存) で表記統一、 `_close_position` は使用しない
- `pnl_before_costs` (T070 SSOT) で表記統一、 `pnl_gross` は使用しない
- `Trade` (zenigame-fx) で表記統一、 `TradeRecord` (T064 表記) は Phase 2 で T064 改訂申し送り
- `BLOCK_BUCKET_RANGES_UTC` と `_SESSION_RANGES_UTC` (primitives) は別責務、 docstring で明示

## 7. F1-F23 失敗モード対応マトリクス (Phase 1 / Phase 2 / PR review 1:1)

| failure | 対応 | test_id (Phase 1) | Phase 2 IT / PR check |
|---|---|---|---|
| F1 bar_time naive で bucket 誤判定 | compute_bucket_for_bar で tz check | `test_F18_naive_datetime_raises` (※ F18 と統合) | — |
| F2 bar_time 非 UTC | utcoffset != timedelta(0) check | `test_F18_non_utc_offset_raises` | — |
| F3 bucket 重複・空白 | BLOCK_BUCKET_RANGES_UTC Final + invariant test | `test_F15_block_bucket_ranges_cover_24h` | — |
| F4 trade exit/entry 異 bucket で集計歪み | exit bucket 一括帰属 | `test_F16_session_blocks_use_exit_time_for_attribution` | — |
| F5 multiplier < 1.0 で apply_spread_stress 暴走 | ValueError raise | `test_F5_multiplier_below_one_raises` | — |
| F6 SessionBlock invariant 違反 | __post_init__ raise | `test_F6_invariant_violation_raises` | — |
| F7 empty block 漏れ | 全 (date, bucket) 生成 | `test_F7_empty_block_generated_when_no_trades` | — |
| F8 _close_one が spread_cost / holding_cost 埋め忘れ | engine path 1 箇所化 + unit test | `test_F8_close_one_records_spread_cost_and_holding_cost` | — |
| F9 既存 Trade caller positional 構築壊れ | default 付き末尾追加 + grep DoD | (PR review、 grep 確認) | `Phase1-PR-CHECK-F9` |
| F10 (旧) holding_cost_per_bar unit ずれ | 廃止 (Round 2 [C1] でtrade level 統合) | — | — |
| F11 SessionBlock field 範囲 | __post_init__ raise | `test_F11_negative_bar_count_raises` / `test_F11_property_*` | — |
| F12 aggregate 結果も invariant 保持 | aggregate_session_blocks SSOT 式 | `test_F12_invariant_holds_for_aggregated` | — |
| F13 spread_cost decomposition contract | invariant `Trade.pnl + Trade.holding_cost == raw_pnl` | `test_F13_invariant_pnl_plus_holding_equals_raw` | — |
| F14 caller 再計算 | BacktestResult.session_blocks SSOT | (PR review、 lint) | `Phase2-IT-F14` |
| F15 date universe 差 | bars touched UTC date set | `test_F3_date_universe_from_bars` (F3 と統合) | — |
| F16 entry/exit 跨ぎ trade 集計 | exit bucket 一括帰属 | `test_F16_session_blocks_use_exit_time_for_attribution` | — |
| F17 spread_cost log/report 露出 | Phase 2 申し送り | — | `Phase2-IT-F17` |
| F18 naive / 非 UTC | tz check | `test_F18_naive_datetime_raises` / `test_F18_non_utc_offset_raises` | — |
| F19 holding_cost 二重計上 | Trade.holding_cost は記録のみ、 cash 操作なし | `test_F19_no_double_counting_of_holding_cost` | — |
| F20 spread_cost / holding_cost log 露出 | Phase 2 申し送り | — | `Phase2-IT-F20` |
| F21 caller 再計算で指標差分 | BacktestResult.session_blocks SSOT | (PR review、 lint) | `Phase2-IT-F21` |
| F22 spread_cost 解釈分岐 | §3.4.0 SSOT で「監査記録、 既存 pnl 未反映」 | `test_F22_pnl_net_uses_spread_subtraction` / `test_F22_multiplier_*` | — |
| F23 orders.py への field 追加漏れ | §3.1 / §6.2 / §9.1 全反映 + default test | `test_F23_trade_default_costs_are_zero` / `test_F23_trade_with_costs` | — |

## 8. backward-compat 確認

### 8.1 Trade dataclass 拡張

- 既存 `Trade(...)` 全位置引数構築 (= 12 fields) は影響なし (新 2 fields default)
- 全 keyword 構築は影響なし
- 全 field 列挙の caller (= テスト fixture 等) は **更新必要**: `grep -rn "Trade(" src/ tests/ scripts/` で検出

### 8.2 BacktestResult dataclass 拡張

- 既存 `BacktestResult(config=, trades=, equity_curve=)` keyword 構築は影響なし (default_factory=tuple)
- 全 positional 構築は **影響なし** (= field 順序末尾に追加、 default_factory 付き)

### 8.3 既存 test 群への影響

T070 PR 実装時に grep DoD:
- `grep -rn "Trade(" src/ tests/ scripts/`
- `grep -rn "BacktestResult(" src/ tests/ scripts/`

更新必要なら同 PR 内で対応。

## 9. DoD (Definition of Done)

### 9.1 Implementation
- [ ] `src/backtest/session_block.py` 新規実装 (SessionBlockBucket, BLOCK_BUCKET_RANGES_UTC, SessionBlock + 4 関数)
- [ ] `src/broker/orders.py` Trade に spread_cost + holding_cost field 追加 (default=Decimal(0))
- [ ] `src/broker/mock.py` _close_one で spread_cost 計算 + holding_cost 転記
- [ ] `src/backtest/engine.py` BacktestResult.session_blocks + run_backtest 末尾で aggregate_session_blocks
- [ ] `docs/alpha_factory/stage-gates.md` T070 セクション追加

### 9.2 Tests
- [ ] `tests/backtest/test_session_block.py` F1, F3, F5, F6, F7, F11, F12, F15, F18, F22 unit test
- [ ] `tests/broker/test_orders.py` F23 default + invariant test
- [ ] `tests/broker/test_mock.py` F8, F13, F19 test
- [ ] `tests/backtest/test_engine.py` F4, F16 test
- [ ] 全既存 test 通過 (破壊変更なし確認)
- [ ] ruff / pyright clean

### 9.3 Cross-PR / PR review checklist
- [ ] `Phase1-PR-CHECK-F9`: `grep -rn "Trade(" src/ tests/ scripts/` で全 construction を確認、 positional 構築壊れなし
- [ ] PR description で「Phase 1 範囲 / Phase 2 申し送り」 を明記
- [ ] T064 詳細設計改訂を Phase 2 申し送り (apply_spread_stress を T070 関数に置換 + TradeRecord → Trade)

## 10. Phase 1 / Phase 2 申し送り (合計 13 項目、 Round 1 [W3] 反映で項目数整合)

### 10.1 Phase 1 (T070 PR で同時更新、 6 項目)
| # | 箇所 | 変更内容 |
|---|---|---|
| 1 | `src/backtest/session_block.py` | 新設 (SessionBlockBucket / BLOCK_BUCKET_RANGES_UTC / SessionBlock + 4 関数) |
| 2 | `src/broker/orders.py` | Trade に spread_cost + holding_cost field 追加 |
| 3 | `src/broker/mock.py` | _close_one 改造 (spread_cost 計算 + holding_cost 転記) |
| 4 | `src/backtest/engine.py` | BacktestResult.session_blocks + run_backtest 末尾で aggregate |
| 5 | `tests/` 4 ファイル拡張 (test_session_block / test_orders / test_mock / test_engine) | F1, F3, F5-F8, F11-F13, F15-F16, F18-F19, F22-F23 |
| 6 | `docs/alpha_factory/stage-gates.md` | T070 セクション追記 |

### 10.2 Phase 2 (cascade port 切替 commit、 7 項目)
| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 7 | T064 stage_bc_evaluator (PR 配置時) | apply_spread_stress を T070 import に置換 + TradeRecord → Trade 統一 | T064 / Phase 2 |
| 8 | T061 canonical_metrics (PR 配置時) | BacktestResult.session_blocks を入力に SR_session_worst / WR_worst | T061 / Phase 2 |
| 9 | T072 DST/holiday boundary | block_bucket_ranges への DST 例外、 holiday 時 block の特別扱い | T072 |
| 10 | run_ga.py / 既存 backtest_runner | session_blocks の caller 配線 (再計算禁止、 §6.4 SSOT) | Phase 2 |
| 11 | run report 出力 / archive 経路 | Trade.spread_cost / holding_cost / SessionBlock を log/report/archive 露出 (F17/F20) | Phase 2 |
| 12 | T064 設計改訂 | TradeRecord → Trade 命名統一 | T064 詳細設計改訂 |
| 13 | broker.entry_spread 保持改造 | spread_cost を「entry_spread + exit_spread」 で正確化 (現状 exit×2 近似、 Roll 1984 近似で代用) | Phase 2 |

## 11. 重要な設計判断 SSOT (詳細設計内、 概念設計と同期)

1. **8h × 3 covering partition** (§3.1 / §3.2) — concept §3.2 / §4.2
2. **trade exit_time で全 cost 一括帰属** (§4.1 compute_bucket_for_trade) — concept §3.4.1
3. **empty block も生成 + invariant property** (§3.2 SessionBlock + §4.2 aggregate) — concept §3.4 / §4.3
4. **会計契約: Trade.holding_cost は転記のみ、 spread_cost は独立記録** (§3.3 + §4.4) — concept §3.4.0
5. **BacktestResult.session_blocks transport SSOT** (§4.6) — concept §6.4
6. **spread_cost 計算: exit_spread × 2 近似 (Phase 1)、 entry_spread 厳密化は Phase 2** (§4.5) — concept §6.3
7. **apply_spread_stress 代数: new_pnl = pnl - spread_cost × (multiplier - 1)** (§4.3) — concept §3.4.0
8. **bar 用 / trade 用 bucket 関数を分離** (§4.1) — concept §5.1

## 12. open issues (詳細実装時に再確認)

- spread_cost = exit_spread × 2 の近似が「entry/exit 往復 spread」 として妥当か実測で再検証 (= 詳細実装時に Phase 2 改造判断)
- `_holding_cost_by_position` の既存 dict が `_close_one` で `pop` されるタイミングと test fixture の互換性
- T064 PR で配置される `apply_spread_stress` skeleton と T070 関数 import 経路の整合 (Phase 2 配線確認)
