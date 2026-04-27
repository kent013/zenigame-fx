"""macro_index_daily.effective_from_utc + source columns (T057 Phase 2)

Revision ID: 004
Revises: 003
Create Date: 2026-04-27

`effective_from_utc` 列と `source` 列を追加する。
backfill は **Python での series 別 lag 計算** で実施 (SQL 方言依存を避け、
SQLite/PostgreSQL 両対応). 月次系列 (PCOPPUSDM/PALLFNFINDEXM) は 35 日 lag を
吸収する。NOT NULL 化は本 migration では行わず、application layer (aux_loader)
で defensive に補完 (Phase 2 既定). Phase 3 で NOT NULL 化を予定。

**migration 再現性のため、policy table と計算ロジックは本ファイルに inline
固定する** (Codex impl-review round 1 [Critical] 反映、`src/ingest/effective_from`
は将来変更され得るため import しない).

詳細: devnotes/20260427-2234-aux-data-loader-phase2/
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


# T057 Phase 2 migration 004 時点での series 別保守的 lag (時間単位)。
# 後続で `src/ingest/effective_from.py` SERIES_POLICY_CONSERVATIVE が変更されても
# 本 migration の挙動は変えない (再現性確保).
_SERIES_POLICY_CONSERVATIVE_AT_REV004 = {
    "VIXCLS": 24,
    "DTWEXBGS": 24,
    "DGS10": 24,
    "DGS2": 24,
    "T10YIE": 24,
    "GOLDPMGBD228NLBM": 24,
    "DCOILWTICO": 24,
    "PCOPPUSDM": 24 * 35,
    "PALLFNFINDEXM": 24 * 35,
    "SP500": 24,
}
_DEFAULT_LAG_HOURS = 24


def _compute_effective_from_utc_pinned(series_id, observation_date):  # type: ignore[no-untyped-def]
    """migration 004 時点の policy 固定計算 (revision 再現性).

    `_SERIES_POLICY_CONSERVATIVE_AT_REV004` を使って observation_date + lag を返す。
    """
    lag = _SERIES_POLICY_CONSERVATIVE_AT_REV004.get(
        series_id, _DEFAULT_LAG_HOURS
    )
    return datetime.combine(observation_date, time.min, tzinfo=UTC) + timedelta(
        hours=lag
    )


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
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, series_id, date FROM macro_index_daily "
            "WHERE effective_from_utc IS NULL"
        )
    ).fetchall()
    for row in rows:
        eff = _compute_effective_from_utc_pinned(row.series_id, row.date)
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
