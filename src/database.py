"""SQLAlchemy setup: engine, session factory, and the DiagnosisRecord model.

SQLite chosen per hard constraint (no external DB service). Stores every
analysis so /history can look it up and /feedback can attach outcomes -
this is the audit trail a clinical tool needs to be trustworthy.
"""
import logging
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import get_settings

logger = logging.getLogger("diagnosis_engine.database")
settings = get_settings()

# check_same_thread=False: FastAPI may serve a request on a different thread
# than the one that opened the SQLite connection; safe here since each
# request gets its own short-lived session (see get_db below).
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
# StaticPool for sqlite ":memory:" (used by the test suite): without it, each new
# connection FastAPI opens on a threadpool worker gets its OWN blank in-memory
# database, so a record written by one request would be invisible to the next
# (e.g. /history right after /analyze). StaticPool forces every connection to
# reuse the same single underlying connection instead.
_engine_kwargs = {"poolclass": StaticPool} if ":memory:" in settings.database_url else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class PatientRecord(Base):
    """One stored diagnosis analysis, keyed loosely by patient_id for /history lookups."""

    __tablename__ = "patient_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    symptoms_json: Mapped[str] = mapped_column(Text)
    labs_json: Mapped[str] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comorbidities_json: Mapped[str] = mapped_column(Text, default="[]")
    result_json: Mapped[str] = mapped_column(Text)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_diagnosis: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# Columns added after the table already existed on disk in earlier days
# (patient_name/age/comorbidities_json). create_all() only creates missing
# TABLES, not missing COLUMNS on an existing one - without this, an old
# local data/database.db would 500 on its next query ("no such column").
# No Alembic in this project yet, so this is a minimal, idempotent
# ADD COLUMN pass instead of a full migration framework.
_NEW_COLUMNS = {
    "patient_name": "ALTER TABLE patient_records ADD COLUMN patient_name VARCHAR(256)",
    "age": "ALTER TABLE patient_records ADD COLUMN age INTEGER",
    "comorbidities_json": "ALTER TABLE patient_records ADD COLUMN comorbidities_json TEXT DEFAULT '[]'",
}


def _migrate_missing_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(patient_records)")}
        for column, ddl in _NEW_COLUMNS.items():
            if column not in existing:
                logger.info("Migrating patient_records: adding column %s", column)
                conn.exec_driver_sql(ddl)
        conn.commit()


def init_db() -> None:
    """Create tables if they don't exist, then patch in any columns added since."""
    Base.metadata.create_all(bind=engine)
    _migrate_missing_columns()
    logger.info("Database initialized at %s", settings.database_url)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, guarantees it's closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
