"""Startup migrations for databases created before a schema change.

create_all() only creates missing TABLES; it never adds COLUMNS to existing
ones. The live SQLite DB persists across deploys, so columns added to a model
must be backfilled here at startup.
"""
import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Columns the ORM models expect but older deployed databases may lack,
# with the exact ALTER TABLE that adds them.
_BACKFILL_COLUMNS = {
    "registrations": [
        ("person_id", "ALTER TABLE registrations ADD COLUMN person_id INTEGER"),
    ],
}


def run_startup_migrations(engine: Engine) -> None:
    """Add missing columns to existing tables. Idempotent; safe on fresh DBs."""
    with engine.connect() as conn:
        for table, columns in _BACKFILL_COLUMNS.items():
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if not rows:
                continue  # table does not exist yet; create_all made it or will
            existing = {row[1] for row in rows}
            for column, ddl in columns:
                if column not in existing:
                    conn.execute(text(ddl))
                    logger.info("migration: added %s.%s", table, column)
        conn.commit()
