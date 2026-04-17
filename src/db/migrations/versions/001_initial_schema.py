"""initial schema: currency_pair, price_bar_m1

Revision ID: 001
Revises:
Create Date: 2026-04-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "currency_pair",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("oanda_name", sa.String(length=20), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=20), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("pip_location", sa.SmallInteger(), nullable=False),
        sa.Column("display_precision", sa.SmallInteger(), nullable=False),
        sa.Column("trade_units_precision", sa.SmallInteger(), nullable=False),
        sa.Column("margin_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("minimum_trade_size", sa.BigInteger(), nullable=False),
        sa.Column("maximum_order_units", sa.BigInteger(), nullable=False),
        sa.Column("instrument_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "price_bar_m1",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "pair_id",
            sa.Integer(),
            sa.ForeignKey("currency_pair.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_bid", sa.Numeric(12, 6), nullable=False),
        sa.Column("high_bid", sa.Numeric(12, 6), nullable=False),
        sa.Column("low_bid", sa.Numeric(12, 6), nullable=False),
        sa.Column("close_bid", sa.Numeric(12, 6), nullable=False),
        sa.Column("open_ask", sa.Numeric(12, 6), nullable=False),
        sa.Column("high_ask", sa.Numeric(12, 6), nullable=False),
        sa.Column("low_ask", sa.Numeric(12, 6), nullable=False),
        sa.Column("close_ask", sa.Numeric(12, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pair_id", "bar_time", name="uq_price_bar_m1_pair_time"),
        sa.CheckConstraint("volume >= 0", name="ck_price_bar_m1_volume_nonneg"),
    )
    op.create_index("ix_price_bar_m1_pair_time", "price_bar_m1", ["pair_id", "bar_time"])


def downgrade() -> None:
    op.drop_index("ix_price_bar_m1_pair_time", table_name="price_bar_m1")
    op.drop_table("price_bar_m1")
    op.drop_table("currency_pair")
