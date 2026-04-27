"""macro_index_daily.effective_from_utc + source columns (T057 Phase 2)

Revision ID: 004
Revises: 003
Create Date: 2026-04-27

`effective_from_utc` 列と `source` 列を追加する。
backfill は **Python での series 別 lag 計算** で実施 (SQL 方言依存を避け、
SQLite/PostgreSQL 両対応). 月次系列 (PCOPPUSDM/PALLFNFINDEXM) は 35 日 lag を
吸収する。NOT NULL 化は本 migration では行わず、application layer (aux_loader)
で defensive に補完 (Phase 2 既定). Phase 3 で NOT NULL 化を予定。

詳細: devnotes/20260427-2234-aux-data-loader-phase2/
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "macro_index_daily",
        sa.Column(
            "effective_from_utc",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "macro_index_daily",
        sa.Column("source", sa.String(length=40), nullable=True),
    )

    # backfill: Python で series 別 lag を計算 (方言非依存)
    from src.ingest.effective_from import compute_effective_from_utc

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, series_id, date FROM macro_index_daily "
            "WHERE effective_from_utc IS NULL"
        )
    ).fetchall()
    for row in rows:
        eff = compute_effective_from_utc(row.series_id, row.date)
        bind.execute(
            sa.text(
                "UPDATE macro_index_daily "
                "SET effective_from_utc = :eff, source = :src "
                "WHERE id = :id"
            ),
            {"eff": eff, "src": "policy_conservative", "id": row.id},
        )


def downgrade() -> None:
    op.drop_column("macro_index_daily", "source")
    op.drop_column("macro_index_daily", "effective_from_utc")
