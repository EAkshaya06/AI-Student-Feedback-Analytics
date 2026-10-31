"""Database connection and tables for local SQLite or managed PostgreSQL."""
import os
from pathlib import Path
from sqlalchemy import (
    Boolean, Column, Index, Integer, MetaData, String, Table, Text,
    create_engine, select,
)

BASE_DIR = Path(__file__).resolve().parent.parent
default_db = BASE_DIR / "backend" / "data" / "feedback_submissions.sqlite3"
database_url = os.environ.get("DATABASE_URL")
is_production = os.environ.get("APP_ENV", "").lower() == "production" or os.environ.get("VERCEL") == "1"
if is_production and not database_url:
    raise RuntimeError("DATABASE_URL must point to a persistent PostgreSQL database in production.")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
else:
    database_url = os.environ.get("FEEDBACK_DB_URL", f"sqlite:///{default_db.as_posix()}")

if database_url.startswith("sqlite:"):
    default_db.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
else:
    engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=300)

metadata = MetaData()
submissions = Table(
    "submissions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", String(64), nullable=False),
    Column("feedback_text", Text, nullable=False),
    Column("department", String(160), nullable=False, default=""),
    Column("course", String(160), nullable=False, default=""),
    Column("faculty", String(160), nullable=False, default=""),
    Column("anonymous", Boolean, nullable=False, default=True),
    Column("analysis_json", Text, nullable=False),
)
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(254), nullable=False, unique=True, index=True),
    Column("display_name", String(160), nullable=False),
    Column("password_hash", String(256), nullable=False),
    Column("role", String(24), nullable=False),
    Column("faculty_key", String(160), nullable=True),
    Column("active", Boolean, nullable=False, default=True),
)
teacher_login_tokens = Table(
    "teacher_login_tokens", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("created_at", String(64), nullable=False),
    Column("expires_at", String(64), nullable=False),
    Column("used_at", String(64), nullable=True),
)
auth_login_attempts = Table(
    "auth_login_attempts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("identifier_hash", String(64), nullable=False),
    Column("created_at", String(64), nullable=False),
    Index("ix_auth_login_attempts_identifier_created", "identifier_hash", "created_at"),
    Index("ix_auth_login_attempts_created", "created_at"),
)
audit_events = Table(
    "audit_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", String(64), nullable=False),
    Column("actor_user_id", Integer, nullable=True),
    Column("actor_email", String(254), nullable=True),
    Column("action", String(80), nullable=False),
    Column("target_email", String(254), nullable=True),
    Column("details_json", Text, nullable=False, default="{}"),
)
Index("ix_audit_events_created", audit_events.c.created_at)

metadata.create_all(engine)

def fetch_submissions(faculty_key=None):
    query = select(submissions).order_by(submissions.c.id.desc())
    if faculty_key is not None:
        query = query.where(submissions.c.faculty == faculty_key)
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(query).mappings().all()]
