"""economic_event table

Revision ID: 002
Revises: 001
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economic_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("impact", sa.SmallInteger(), nullable=False),
        sa.Column("forecast", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual", sa.Numeric(18, 6), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_time", "currency", "name", name="uq_economic_event_time_ccy_name"),
        sa.CheckConstraint("impact BETWEEN 1 AND 3", name="ck_economic_event_impact_range"),
    )
    op.create_index("ix_economic_event_time", "economic_event", ["event_time"])
    op.create_index("ix_economic_event_currency_time", "economic_event", ["currency", "event_time"])


def downgrade() -> None:
    op.drop_index("ix_economic_event_currency_time", table_name="economic_event")
    op.drop_index("ix_economic_event_time", table_name="economic_event")
    op.drop_table("economic_event")
