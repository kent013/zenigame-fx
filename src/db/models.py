from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.connection import Base


class CurrencyPair(Base):
    __tablename__ = "currency_pair"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oanda_name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(20), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pip_location: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    display_precision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    trade_units_precision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    margin_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    minimum_trade_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    maximum_order_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    bars_m1: Mapped[list[PriceBarM1]] = relationship("PriceBarM1", back_populates="pair", passive_deletes=False)

    def __repr__(self) -> str:
        return f"<CurrencyPair(oanda_name={self.oanda_name})>"


class PriceBarM1(Base):
    __tablename__ = "price_bar_m1"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pair_id: Mapped[int] = mapped_column(Integer, ForeignKey("currency_pair.id", ondelete="RESTRICT"), nullable=False)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_bid: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    high_bid: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    low_bid: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    close_bid: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    open_ask: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    high_ask: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    low_ask: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    close_ask: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pair: Mapped[CurrencyPair] = relationship("CurrencyPair", back_populates="bars_m1")

    __table_args__ = (
        UniqueConstraint("pair_id", "bar_time", name="uq_price_bar_m1_pair_time"),
        Index("ix_price_bar_m1_pair_time", "pair_id", "bar_time"),
        CheckConstraint("volume >= 0", name="ck_price_bar_m1_volume_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<PriceBarM1(pair_id={self.pair_id}, bar_time={self.bar_time})>"


class EconomicEventRow(Base):
    __tablename__ = "economic_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    impact: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    forecast: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("event_time", "currency", "name", name="uq_economic_event_time_ccy_name"),
        CheckConstraint("impact BETWEEN 1 AND 3", name="ck_economic_event_impact_range"),
        Index("ix_economic_event_time", "event_time"),
        Index("ix_economic_event_currency_time", "currency", "event_time"),
    )

    def __repr__(self) -> str:
        return f"<EconomicEventRow(event_time={self.event_time}, currency={self.currency}, name={self.name})>"


class MacroIndexDaily(Base):
    """FRED 由来の日足マクロ指標 (VIX / DXY / Treasury yields / breakeven 等)。

    `date` は FRED の observations[].date を素直に保持する。
    `effective_from_utc` は **その値が利用可能になる UTC 時刻** (T057 Phase 2):
    `bar.bar_time >= effective_from_utc` を満たして以降でしか forward-fill されない契約。
    daily 系列は `observation_date + 24h`、月次系列 (PCOPPUSDM 等) は `+35d` の保守的 lag。
    `source` は出所識別 (policy_conservative / fred_realtime_start / oanda_release_time).
    """

    __tablename__ = "macro_index_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # T057 Phase 2: effective_from_utc は migration 004 で追加。
    # 過去データの backfill は migration 内で series 別 lag で計算 (Python で実施)。
    effective_from_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("series_id", "date", name="uq_macro_index_daily_series_date"),
        Index("ix_macro_index_daily_series_date", "series_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<MacroIndexDaily(series_id={self.series_id}, date={self.date}, value={self.value})>"
