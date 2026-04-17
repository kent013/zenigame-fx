from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
