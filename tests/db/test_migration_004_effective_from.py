"""T057 Gate A: migration 004 (macro_index_daily.effective_from_utc + source) tests.

Migration 004 のロジックを直接テストする (alembic stamp は重く避ける).
backfill は Python の compute_effective_from_utc で行うため
SQLite / PostgreSQL 両対応であることを確認.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.db.connection import Base
from src.db.models import MacroIndexDaily


@pytest.fixture
def sqlite_engine():
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    original_visit = SQLiteTypeCompiler.visit_BIGINT

    def _visit_bigint_as_integer(self, type_, **kw):  # type: ignore[no-untyped-def]
        return "INTEGER"

    SQLiteTypeCompiler.visit_BIGINT = _visit_bigint_as_integer  # type: ignore[method-assign]
    engine = create_engine("sqlite://", future=True)
    try:
        Base.metadata.create_all(engine, tables=[MacroIndexDaily.__table__])
        yield engine
    finally:
        SQLiteTypeCompiler.visit_BIGINT = original_visit  # type: ignore[method-assign]
        engine.dispose()


def test_macro_index_daily_has_effective_from_utc_column() -> None:
    """schema レベルで列が存在することを確認."""
    cols = set(MacroIndexDaily.__table__.columns.keys())
    assert "effective_from_utc" in cols
    assert "source" in cols


def test_migration_004_backfill_logic_daily_series(sqlite_engine) -> None:
    """daily 系列 (VIXCLS) の backfill が +24h policy で適用される."""
    SessionLocal = sessionmaker(bind=sqlite_engine, future=True)
    with SessionLocal() as session:
        # backfill 前 (effective_from_utc=NULL) の状態を再現
        session.add(
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 4, 1),
                value=Decimal("18.0"),
                fetched_at=datetime(2026, 4, 2, tzinfo=UTC),
                effective_from_utc=None,  # backfill 対象
                source=None,
            )
        )
        session.commit()

    # migration 004 と同じロジックで backfill
    from src.ingest.effective_from import compute_effective_from_utc

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, series_id, date FROM macro_index_daily "
                "WHERE effective_from_utc IS NULL"
            )
        ).fetchall()
        assert len(rows) == 1
        for r in rows:
            r_date = r.date if isinstance(r.date, date) else date.fromisoformat(r.date)
            eff = compute_effective_from_utc(r.series_id, r_date)
            conn.execute(
                text(
                    "UPDATE macro_index_daily "
                    "SET effective_from_utc = :eff, source = :src "
                    "WHERE id = :id"
                ),
                {
                    "eff": eff.isoformat(),
                    "src": "policy_conservative",
                    "id": r.id,
                },
            )
        conn.commit()

    with SessionLocal() as session:
        row = session.scalars(sa.select(MacroIndexDaily)).one()
        assert row.effective_from_utc is not None
        assert row.source == "policy_conservative"
        # daily 系列なので +24h
        assert row.effective_from_utc.year == 2026
        assert row.effective_from_utc.month == 4
        assert row.effective_from_utc.day == 2  # 4/1 + 1day


def test_migration_004_backfill_logic_monthly_series(sqlite_engine) -> None:
    """月次系列 (PCOPPUSDM) の backfill が +35d policy で適用される."""
    SessionLocal = sessionmaker(bind=sqlite_engine, future=True)
    with SessionLocal() as session:
        session.add(
            MacroIndexDaily(
                series_id="PCOPPUSDM",
                date=date(2026, 1, 1),
                value=Decimal("9000"),
                fetched_at=datetime(2026, 2, 5, tzinfo=UTC),
                effective_from_utc=None,
                source=None,
            )
        )
        session.commit()

    from src.ingest.effective_from import compute_effective_from_utc

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, series_id, date FROM macro_index_daily "
                "WHERE effective_from_utc IS NULL"
            )
        ).fetchall()
        for r in rows:
            r_date = r.date if isinstance(r.date, date) else date.fromisoformat(r.date)
            eff = compute_effective_from_utc(r.series_id, r_date)
            conn.execute(
                text(
                    "UPDATE macro_index_daily "
                    "SET effective_from_utc = :eff, source = :src "
                    "WHERE id = :id"
                ),
                {
                    "eff": eff.isoformat(),
                    "src": "policy_conservative",
                    "id": r.id,
                },
            )
        conn.commit()

    with SessionLocal() as session:
        row = session.scalars(sa.select(MacroIndexDaily)).one()
        # 月次なので +35d → 1/1 + 35 days = 2/5
        assert row.effective_from_utc.month == 2
        assert row.effective_from_utc.day == 5
        assert row.source == "policy_conservative"
