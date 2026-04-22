"""macro_index_daily table

Revision ID: 003
Revises: 002
Create Date: 2026-04-22

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_index_daily",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("series_id", sa.String(length=20), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("series_id", "date", name="uq_macro_index_daily_series_date"),
    )
    op.create_index(
        "ix_macro_index_daily_series_date",
        "macro_index_daily",
        ["series_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_macro_index_daily_series_date", table_name="macro_index_daily")
    op.drop_table("macro_index_daily")
