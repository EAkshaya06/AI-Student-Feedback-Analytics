"""SQLAlchemy models for private, live submissions and staff accounts."""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint


db = SQLAlchemy()


def utc_now() -> datetime:
    # Store UTC consistently; SQL backends without timezone-aware columns can
    # otherwise make SQLite login-window comparisons inconsistent.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FeedbackSubmission(db.Model):
    __tablename__ = "feedback_submissions"
    __table_args__ = (UniqueConstraint("batch_id", "item_index", name="uq_feedback_batch_item"),)

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(64), nullable=False, index=True)
    item_index = db.Column(db.Integer, nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
    department = db.Column(db.String(120), nullable=False, default="")
    academic_year = db.Column(db.String(32), nullable=False, default="")
    semester = db.Column(db.String(32), nullable=False, default="")
    subject = db.Column(db.String(160), nullable=False, default="")
    section = db.Column(db.String(80), nullable=False, default="")
    faculty = db.Column(db.String(160), nullable=False, default="")
    sentiment = db.Column(db.String(16), nullable=False)
    sentiment_score = db.Column(db.Float, nullable=False, default=0.0)
    mixed_opinion = db.Column(db.Boolean, nullable=False, default=False)
    language = db.Column(db.String(32), nullable=False)
    language_supported = db.Column(db.Boolean, nullable=False, default=False)
    sentiment_supported = db.Column(db.Boolean, nullable=False, default=True)
    analysis_method = db.Column(db.String(80), nullable=False)
    analysis_note = db.Column(db.String(300), nullable=False, default="")
    aspects_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class StaffAccount(db.Model):
    __tablename__ = "staff_accounts"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    faculty_key = db.Column(db.String(160), nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class LoginFailure(db.Model):
    __tablename__ = "login_failures"

    id = db.Column(db.Integer, primary_key=True)
    identifier_hash = db.Column(db.String(64), nullable=False, index=True)
    failed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
