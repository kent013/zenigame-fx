"""broker.Trade / backtest equity_curve から canonical_metrics 経路へ変換する adapter.

cascade port v2 Phase 2 切替コミット step 1 の SSOT (= dual-path の足場).

設計参照:
    devnotes/20260503-1024-B-phase2-step1-canonical-metrics/detailed-design.md
    (Codex 設計 review Round 2 APPROVED)

責務:
    - broker.Trade → canonical_metrics.TradeRecord 変換
    - backtest equity_curve → canonical_metrics.BarEquitySeries 変換
    - 評価窓の price bars から business_day_universe 構築

非責務 (= step 1 範囲外、 後続別 step):
    - Stage B (per-fold WF) / Stage C (holdout) の dual-path 拡張 (= step 1.5)
    - stage_bc_evaluator.evaluate_stage_b_pooled / evaluate_stage_c_lite の運用
      (= step 2)
    - is_session_close_drop / is_negative_equity_drop_open の broker engine 経由
      伝搬 (= 別 step、 step 1 では default False、 caller 側で
      flags_source="default_false" を log 明示)

設計根拠 (C1/C2 順守、 詳細設計 § 4.1 末尾):
    着手前調査で skeleton 段階の前提関数 (assign_session_bucket_and_business_day_index /
    compute_business_day_universe) が既存コードに不在を grep で確認。 別経路を広く
    探した結果、 既存の compute_bucket_for_bar (src/backtest/session_block.py:304)
    が同等責務の SSOT。 BUSINESS_DAY_EPOCH (= 1970-01-01) からの UTC date 日数
    encoding は canonical_metrics の契約 (= 同一 universe / trades で consistent な
    int) を満たす最小実装。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    SessionBucket,
    TradeRecord,
)
from src.backtest.session_block import (
    SessionBlockBucket,
    compute_bucket_for_bar,
    compute_bucket_for_trade,
)
from src.broker.orders import Trade as BrokerTrade
from src.domain.price import PriceBar

__all__ = [
    "BUSINESS_DAY_EPOCH",
    "compute_business_day_universe_from_bars",
    "equity_curve_to_bar_equity_series",
    "trade_to_trade_record",
]

# business_day_index encoding: UTC date を 1970-01-01 epoch からの日数で整数化
# (= canonical_metrics の business_day_index >= 0 契約を満たす)。
# trade_to_trade_record と compute_business_day_universe_from_bars 双方が
# この同一 scheme を使うことで universe / trades の consistency を保証。
BUSINESS_DAY_EPOCH: Final[date] = date(1970, 1, 1)


def _convert_bucket(literal: SessionBlockBucket) -> SessionBucket:
    """SessionBlockBucket (Literal["tokyo"|"london"|"ny"]) → SessionBucket (StrEnum).

    両者は値文字列が一致するため StrEnum constructor で変換可能。
    """
    return SessionBucket(literal)


def _business_day_index_for(exit_or_bar_time_utc: datetime) -> int:
    """UTC datetime を BUSINESS_DAY_EPOCH (1970-01-01) からの日数で整数化.

    canonical_metrics は business_day_index >= 0 の整数を要求するのみで、
    具体値は問わない (= 同一 universe / trades で consistent であれば OK)。
    本 helper は trade_to_trade_record と compute_business_day_universe_from_bars
    で共有され、 同一 UTC date scheme を担保する。

    Codex impl-review Round 1 [Warning] 取込: 1970-01-01 以前のデータが
    流入した場合は ValueError raise (= canonical_metrics の business_day_index
    >= 0 契約違反を caller 側で発見可能、 既存 backtest engine の運用想定では
    この経路に到達しない defensive ガード)。
    """
    days = (exit_or_bar_time_utc.date() - BUSINESS_DAY_EPOCH).days
    if days < 0:
        raise ValueError(
            f"business_day_index must be >= 0 (BUSINESS_DAY_EPOCH={BUSINESS_DAY_EPOCH}), "
            f"got {days} from {exit_or_bar_time_utc.isoformat()}"
        )
    return days


def trade_to_trade_record(broker_trade: BrokerTrade) -> TradeRecord:
    """broker.Trade を canonical TradeRecord に変換.

    Args:
        broker_trade: backtest engine が生成した Trade (= entry_time / exit_time
            は UTC-aware で utcoffset=0、 compute_bucket_for_bar が validate)。

    Returns:
        canonical_metrics.TradeRecord:
        - session_bucket: compute_bucket_for_trade で算出 (= exit_time UTC hour 駆動)
        - business_day_index: exit_time UTC date を BUSINESS_DAY_EPOCH からの日数で整数化
        - pnl_net / spread_cost / holding_cost: Decimal → float (T078 で broker 側追加済)
        - is_session_close_drop / is_negative_equity_drop_open: step 1 では default False
          (= step 1 range外、 後続別 step で broker engine から伝搬。 caller 側で
          flags_source="default_false" を log 明示する責務)

    Raises:
        ValueError: broker_trade.exit_time が naive datetime / 非 UTC offset
            (= compute_bucket_for_trade 内で validate)。
        TradeRecordInvalidError: TradeRecord __post_init__ invariant 違反
            (= entry_time >= exit_time / non-finite pnl 等)。
    """
    bucket_literal = compute_bucket_for_trade(broker_trade)
    return TradeRecord(
        entry_time_utc=broker_trade.entry_time,
        exit_time_utc=broker_trade.exit_time,
        pnl_net=float(broker_trade.pnl),
        session_bucket=_convert_bucket(bucket_literal),
        business_day_index=_business_day_index_for(broker_trade.exit_time),
        # step 1 では default False (= 後続別 step で broker engine から伝搬)
        is_session_close_drop=False,
        is_negative_equity_drop_open=False,
        spread_cost=float(broker_trade.spread_cost),
        holding_cost=float(broker_trade.holding_cost),
    )


def equity_curve_to_bar_equity_series(
    equity_curve: list[tuple[datetime, Decimal]],
) -> BarEquitySeries:
    """backtest engine の equity_curve を canonical BarEquitySeries に変換.

    Args:
        equity_curve: list[(timestamp_utc, equity)]、 backtest engine の出力契約で
            時系列順 / 重複 timestamp なし / 全 UTC-aware が保証されている。

    Returns:
        BarEquitySeries (= __post_init__ で UTC-aware / strict monotone /
        finite equity を invariant チェック)。

    Raises:
        BarEquityInvalidError: invariant 違反 (= naive timestamp / 重複 / 逆順 / NaN)。
    """
    points = tuple(
        BarEquityPoint(timestamp_utc=ts, equity=float(eq)) for ts, eq in equity_curve
    )
    return BarEquitySeries(points=points)


def compute_business_day_universe_from_bars(
    bars: Iterable[PriceBar],
) -> dict[SessionBucket, frozenset[int]]:
    """評価窓の全 price bars から (bucket, business_day_index) ペア集合を universe として返す.

    入力契約 (Codex Round 2 [Suggestion] 1 取込で明文化):
        bars は **対象 stage 評価窓の全 price bars** (= Stage A なら bars_60d、
        Stage B なら bars_stage_b、 Stage C なら bars_holdout) を想定。
        約定周辺 bars や equity_curve 由来 bars を渡すと、 空 block が universe から
        欠落して synthesis § 6.3 の WR neutral 0.5 規約が崩れる (= 集計が活動量依存で
        上振れする)。

    SSOT 規範 (= synthesis § 6.3 WR neutral 0.5 整合):
        bars の bar_time UTC date × bucket (= compute_bucket_for_bar(bar_time)) で
        universe を生成。 約定がない bucket / day も universe に含まれ、
        evaluate_canonical_five の WR 計算で trade_count_block=0 → WR neutral 0.5
        が適切に発動する。

    Args:
        bars: 評価窓の全 bar (時系列順、 UTC tz-aware)。

    Returns:
        dict[SessionBucket, frozenset[int]]: 必ず 3 bucket key 全件 (TOKYO/LONDON/NY)、
        各 frozenset は bar が触れた business_day_index 集合。

    Raises:
        ValueError: bar_time が naive datetime / 非 UTC offset
            (= compute_bucket_for_bar 内で validate)。
    """
    universe: dict[SessionBucket, set[int]] = {
        SessionBucket.TOKYO: set(),
        SessionBucket.LONDON: set(),
        SessionBucket.NY: set(),
    }
    for bar in bars:
        bucket = _convert_bucket(compute_bucket_for_bar(bar.bar_time))
        universe[bucket].add(_business_day_index_for(bar.bar_time))
    return {k: frozenset(v) for k, v in universe.items()}
