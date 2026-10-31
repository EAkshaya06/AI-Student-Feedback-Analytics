"""Flask application for anonymous student feedback and protected staff analytics."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import secrets
import uuid
import csv
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, request, send_file, send_from_directory, session, url_for
from sqlalchemy import func, inspect
from werkzeug.security import check_password_hash, generate_password_hash

try:  # Supports `python backend/app.py` and importing `backend.app`.
    from database import FeedbackSubmission, LoginFailure, StaffAccount, db, utc_now
    from services.analysis_engine import analyze_comment
except ImportError:
    from backend.database import FeedbackSubmission, LoginFailure, StaffAccount, db, utc_now
    from backend.services.analysis_engine import analyze_comment


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "backend" / "data"
HISTORICAL_FILE = DATA_DIR / "feedback.csv"

app = Flask(__name__)
configured_secret = os.environ.get("SECRET_KEY")
if not configured_secret and os.environ.get("VERCEL"):
    raise RuntimeError("Set SECRET_KEY in the deployment environment before starting the app.")
app.secret_key = configured_secret or secrets.token_urlsafe(48)
if not configured_secret:
    app.logger.warning("SECRET_KEY is unset; this local session key changes whenever the server restarts.")

database_url = os.environ.get("DATABASE_URL", "").strip()
if os.environ.get("VERCEL") and not database_url:
    raise RuntimeError("Set DATABASE_URL to a persistent PostgreSQL database for Vercel; function files are not persistent storage.")
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
elif database_url.startswith("postgresql://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
if not database_url:
    default_db = (DATA_DIR / "feedback_submissions.sqlite3").resolve().as_posix()
    database_url = f"sqlite:///{default_db}"

app.config.update(
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    MAX_CONTENT_LENGTH=1_100_000,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")) or os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
db.init_app(app)


def _bootstrap_admin() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email and not password:
        if os.environ.get("VERCEL"):
            raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD before deploying the staff dashboard.")
        app.logger.warning("No initial admin configured. Set ADMIN_EMAIL and ADMIN_PASSWORD to provision one.")
        return
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(password) < 12:
        if os.environ.get("VERCEL"):
            raise RuntimeError("Use a valid ADMIN_EMAIL and a 12+ character ADMIN_PASSWORD before deploying.")
        app.logger.error("Initial admin was not created: use a valid ADMIN_EMAIL and a 12+ character ADMIN_PASSWORD.")
        return
    existing = StaffAccount.query.filter(func.lower(StaffAccount.email) == email).first()
    if existing is None:
        db.session.add(StaffAccount(
            email=email,
            password_hash=generate_password_hash(password),
            role="admin",
            active=True,
        ))
        db.session.commit()
    elif existing.role != "admin":
        message = "ADMIN_EMAIL belongs to a non-admin account; choose a distinct administrator email."
        if os.environ.get("VERCEL"):
            raise RuntimeError(message)
        app.logger.error(message)


def _validate_existing_schema() -> None:
    inspector = inspect(db.engine)
    for model in (FeedbackSubmission, StaffAccount, LoginFailure):
        table_name = model.__tablename__
        if not inspector.has_table(table_name):
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        required_columns = {column.name for column in model.__table__.columns}
        missing = sorted(required_columns - existing_columns)
        if missing:
            raise RuntimeError(
                f"Database table '{table_name}' needs a reviewed migration before this version can start; "
                f"missing columns: {', '.join(missing)}. No existing rows were changed."
            )


def _preserve_and_migrate_legacy_records() -> None:
    try:
        from sqlalchemy import text
        inspector = inspect(db.engine)
        if inspector.has_table("submissions") and inspector.has_table("feedback_submissions"):
            if FeedbackSubmission.query.first() is None:
                rows = db.session.execute(text("SELECT id, created_at, feedback_text, department, course, faculty, analysis_json FROM submissions")).mappings().all()
                for r in rows:
                    analysis = {}
                    if r.get("analysis_json"):
                        try:
                            analysis = json.loads(r["analysis_json"])
                        except Exception:
                            pass
                    dt = utc_now()
                    if r.get("created_at"):
                        try:
                            dt = datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
                        except Exception:
                            pass
                    db.session.add(FeedbackSubmission(
                        batch_id=f"legacy-{r['id']}",
                        item_index=0,
                        feedback_text=r.get("feedback_text") or "",
                        department=r.get("department") or "",
                        academic_year="",
                        semester="",
                        subject=r.get("course") or "",
                        section="",
                        faculty=r.get("faculty") or "",
                        sentiment=str(analysis.get("sentiment") or "neutral").lower(),
                        sentiment_score=float(analysis.get("sentiment_score", 0.0) if isinstance(analysis.get("sentiment_score"), (int, float)) else 0.0),
                        mixed_opinion=bool(analysis.get("mixed_opinion", False)),
                        language="English",
                        language_supported=True,
                        sentiment_supported=True,
                        analysis_method="legacy_preserved",
                        analysis_note="Preserved from earlier production submissions",
                        aspects_json=json.dumps(analysis.get("aspects") or []),
                        created_at=dt,
                    ))
                db.session.commit()
        if inspector.has_table("users") and inspector.has_table("staff_accounts"):
            if StaffAccount.query.first() is None:
                users_rows = db.session.execute(text("SELECT email, password_hash, role, faculty_key, active FROM users")).mappings().all()
                for u in users_rows:
                    if u.get("email") and u.get("password_hash"):
                        db.session.add(StaffAccount(
                            email=str(u["email"]).strip().lower(),
                            password_hash=str(u["password_hash"]),
                            role=str(u.get("role") or "faculty").lower(),
                            faculty_key=str(u.get("faculty_key") or ""),
                            active=bool(u.get("active", True)),
                        ))
                db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning(f"Legacy record migration notice: {exc}")


with app.app_context():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _validate_existing_schema()
    db.create_all()
    _preserve_and_migrate_legacy_records()
    _bootstrap_admin()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith("/api/") or request.path in {"/dashboard", "/dashboard.html", "/analysis", "/analysis.html", "/predictions", "/predictions.html"}:
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response


def _csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.before_request
def protect_state_changes():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not supplied or not expected or not hmac.compare_digest(supplied, expected):
            return jsonify(success=False, message="Your session expired. Refresh the page and try again."), 400


def staff_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        email = session.get("staff_email")
        account = StaffAccount.query.filter_by(email=email, active=True).first() if email else None
        if account is None:
            if request.path.startswith("/api/"):
                return jsonify(success=False, message="Sign in to view staff analytics."), 401
            return redirect(url_for("login_page", next=request.path))
        g.staff = account
        return function(*args, **kwargs)
    return wrapped


def admin_required(function):
    @wraps(function)
    @staff_required
    def wrapped(*args, **kwargs):
        if g.staff.role != "admin":
            return jsonify(success=False, message="Administrator access is required."), 403
        return function(*args, **kwargs)
    return wrapped


def _safe_next(value: str) -> str:
    parsed = urlparse(value or "")
    safe_path = not any(char in value for char in ("\\", "\r", "\n"))
    return value if safe_path and not parsed.netloc and value.startswith("/") and not value.startswith("//") else "/dashboard"


@app.get("/")
@app.get("/index.html")
def home_page():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/login")
@app.get("/login.html")
def login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.get("/teacher-login")
def teacher_login_compat():
    return redirect(url_for("login_page"))


@app.get("/dashboard")
@app.get("/dashboard.html")
@staff_required
def dashboard_page():
    return send_from_directory(FRONTEND_DIR, "dashboard.html")


@app.get("/feedback")
@app.get("/feedback.html")
def feedback_page():
    return send_from_directory(FRONTEND_DIR, "feedback.html")


@app.get("/analysis")
@app.get("/analysis.html")
@staff_required
def analysis_page():
    return send_from_directory(FRONTEND_DIR, "analysis.html")


@app.get("/predictions")
@app.get("/predictions.html")
@staff_required
def predictions_page():
    return send_from_directory(FRONTEND_DIR, "predictions.html")


@app.get("/css/<path:filename>")
def css_files(filename):
    return send_from_directory(FRONTEND_DIR / "css", filename)


@app.get("/js/<path:filename>")
def js_files(filename):
    return send_from_directory(FRONTEND_DIR / "js", filename)


@app.get("/api/session")
def session_info():
    account = StaffAccount.query.filter_by(email=session.get("staff_email"), active=True).first() if session.get("staff_email") else None
    return jsonify(
        authenticated=account is not None,
        role=account.role if account else None,
        email=account.email if account else None,
        csrf_token=_csrf_token(),
    )


def _login_identifier(email: str) -> str:
    key = (app.secret_key or "").encode("utf-8")
    value = email.lower().encode("utf-8")
    return hmac.new(key, value, hashlib.sha256).hexdigest()


@app.post("/api/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="Send sign-in details as JSON."), 400
    email = str(payload.get("email", "")).strip().lower()[:254]
    password = str(payload.get("password", ""))[:256]
    identifier = _login_identifier(email)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(minutes=15)
    failures = LoginFailure.query.filter(
        LoginFailure.identifier_hash == identifier,
        LoginFailure.failed_at >= cutoff,
    ).count()
    if failures >= 5:
        return jsonify(success=False, message="Too many sign-in attempts. Wait 15 minutes before trying again."), 429

    account = StaffAccount.query.filter(func.lower(StaffAccount.email) == email, StaffAccount.active.is_(True)).first()
    if account is None or not check_password_hash(account.password_hash, password):
        db.session.add(LoginFailure(identifier_hash=identifier, failed_at=now))
        LoginFailure.query.filter(LoginFailure.failed_at < cutoff).delete(synchronize_session=False)
        db.session.commit()
        return jsonify(success=False, message="Email or password is incorrect."), 401

    LoginFailure.query.filter_by(identifier_hash=identifier).delete(synchronize_session=False)
    db.session.commit()
    session.clear()
    session.permanent = True
    session["staff_email"] = account.email
    _csrf_token()
    return jsonify(success=True, role=account.role, next=_safe_next(str(payload.get("next", ""))), csrf_token=session["csrf_token"])


@app.post("/api/logout")
@staff_required
def logout():
    session.clear()
    return jsonify(success=True)


def _record_to_dict(row: FeedbackSubmission) -> dict[str, Any]:
    try:
        aspects = json.loads(row.aspects_json or "[]")
    except (TypeError, json.JSONDecodeError):
        aspects = []
    created = row.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "feedback": row.feedback_text,
        "feedback_text": row.feedback_text,
        "department": row.department,
        "academic_year": row.academic_year,
        "semester": row.semester,
        "subject": row.subject,
        "section": row.section,
        "faculty": row.faculty,
        "sentiment": row.sentiment,
        "predicted_sentiment": row.sentiment,
        "sentiment_score": row.sentiment_score,
        "mixed_opinion": row.mixed_opinion,
        "language": row.language,
        "language_supported": row.language_supported,
        "sentiment_supported": row.sentiment_supported,
        "analysis_method": row.analysis_method,
        "analysis_note": row.analysis_note,
        "aspects": aspects,
        "emotion": "Not analyzed",
        "category": "student feedback",
        "source": "live",
        "created_at": created.isoformat() if created else "",
    }


@lru_cache(maxsize=1)
def _historical_records() -> list[dict[str, Any]]:
    """The raw feedback.csv is the sole historical source; derived CSVs are not counted again."""
    if not HISTORICAL_FILE.exists():
        return []
    rows = []
    with HISTORICAL_FILE.open("r", encoding="utf-8-sig", newline="") as source_file:
        for index, raw in enumerate(csv.DictReader(source_file)):
            comment = str(raw.get("text", raw.get("feedback", ""))).strip()
            if not comment:
                continue
            sentiment = str(raw.get("sentiment", raw.get("predicted_sentiment", "neutral"))).strip().lower()
            if sentiment in {"1", "1.0", "positive"}:
                sentiment = "positive"
            elif sentiment in {"-1", "-1.0", "negative"}:
                sentiment = "negative"
            elif sentiment not in {"positive", "negative", "neutral"}:
                sentiment = "neutral"
            try:
                sentiment_score = float(raw.get("sentiment_score") or 0)
            except (TypeError, ValueError):
                sentiment_score = 0.0
            analysis = analyze_comment(comment)
            rows.append({
                "id": f"historical-{index}",
                "feedback": comment,
                "feedback_text": comment,
                "department": "",
                "academic_year": "",
                "semester": "",
                "subject": "",
                "section": "",
                "faculty": "",
                "sentiment": sentiment,
                "predicted_sentiment": str(raw.get("predicted_sentiment", sentiment)).lower() if raw.get("predicted_sentiment") else sentiment,
                "sentiment_score": sentiment_score,
                "mixed_opinion": analysis["mixed_opinion"],
                "language": analysis["language"],
                "language_supported": analysis["language_supported"],
                "sentiment_supported": bool(raw.get("sentiment") or raw.get("predicted_sentiment")),
                "analysis_method": "historical_dataset_label",
                "analysis_note": "Historical sentiment label from feedback.csv; date and academic metadata were not included.",
                "aspects": analysis["aspects"],
                "emotion": str(raw.get("emotion", "Not available") or "Not available"),
                "category": str(raw.get("category", "Uncategorized") or "Uncategorized"),
                "source": "historical",
                "created_at": "",
            })
    return rows


def _all_live_records(staff=None) -> list[dict[str, Any]]:
    query = FeedbackSubmission.query
    if staff is not None and staff.role == "faculty":
        key = (staff.faculty_key or "").strip().lower()
        if not key:
            return []
        query = query.filter(func.lower(FeedbackSubmission.faculty) == key)
    return [_record_to_dict(row) for row in query.order_by(FeedbackSubmission.created_at.desc()).all()]


def _selected_records(args, staff=None) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    source = str(args.get("source", "historical")).lower()
    if source not in {"historical", "live", "all"}:
        raise ValueError("Choose historical, live, or all as the data source.")
    if staff is not None and staff.role == "faculty":
        source = "live"
    records = []
    if source in {"historical", "all"} and not (staff and staff.role == "faculty"):
        records.extend(dict(record) for record in _historical_records())
    if source in {"live", "all"}:
        records.extend(_all_live_records(staff))

    filters = {}
    for key in ("department", "academic_year", "semester", "subject", "faculty"):
        value = str(args.get(key, "")).strip()
        if value:
            if len(value) > 160:
                raise ValueError(f"{key.replace('_', ' ').title()} filter is too long.")
            filters[key] = value.casefold()
    if args.get("date_from") or args.get("date_to"):
        try:
            date_from = date.fromisoformat(args.get("date_from")) if args.get("date_from") else None
            date_to = date.fromisoformat(args.get("date_to")) if args.get("date_to") else None
        except ValueError:
            raise ValueError("Use YYYY-MM-DD for date filters.") from None
        if date_from and date_to and date_from > date_to:
            raise ValueError("The start date must be on or before the end date.")
        for record in records:
            timestamp = record.get("created_at", "")
            if not timestamp:
                record["_date_filter_unavailable"] = True
                continue
            record_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
            if date_from and record_date < date_from or date_to and record_date > date_to:
                record["_date_filter_unavailable"] = True

    selected = []
    for record in records:
        if record.get("_date_filter_unavailable"):
            continue
        if all(str(record.get(key, "")).casefold() == value for key, value in filters.items()):
            selected.append(record)
    notes = []
    if args.get("date_from") or args.get("date_to"):
        if source in {"historical", "all"}:
            notes.append("Historical/demo records have no timestamps, so date filters only include live submissions.")
    return selected, {"source": source, **filters, **({"date_from": args["date_from"]} if args.get("date_from") else {}), **({"date_to": args["date_to"]} if args.get("date_to") else {})}, notes


def _options(records: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(row.get(key, "")).strip() for row in records if str(row.get(key, "")).strip()}, key=str.casefold)


def _group_counts(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    groups: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        label = str(record.get(key, "")).strip()
        if label and record.get("sentiment_supported", record.get("language_supported", True)):
            groups[label][record["sentiment"]] += 1
    return {label: dict(counts) for label, counts in sorted(groups.items(), key=lambda item: item[0].casefold())}


def _insights(records: list[dict[str, Any]], aspect_counts: dict[str, dict[str, int]], monthly: dict[str, dict[str, int]]) -> dict[str, Any]:
    strengths = []
    concerns = []
    for aspect, counts in aspect_counts.items():
        if counts["positive"]:
            examples = []
            for record in records:
                for result in record.get("aspects", []):
                    if result.get("aspect") == aspect and result.get("sentiment") == "positive" and result.get("evidence"):
                        examples.append(result["evidence"])
            strengths.append({"aspect": aspect, "mentions": counts["positive"], "evidence": list(dict.fromkeys(examples))[:2]})
        if counts["negative"]:
            examples = []
            for record in records:
                for result in record.get("aspects", []):
                    if result.get("aspect") == aspect and result.get("sentiment") == "negative" and result.get("evidence"):
                        examples.append(result["evidence"])
            concerns.append({"aspect": aspect, "mentions": counts["negative"], "evidence": list(dict.fromkeys(examples))[:2]})
    strengths.sort(key=lambda item: (-item["mentions"], item["aspect"]))
    concerns.sort(key=lambda item: (-item["mentions"], item["aspect"]))
    trend = None
    months = sorted(monthly)
    if len(months) >= 2:
        previous, current = months[-2:]
        trend = {
            "from": previous,
            "to": current,
            "previous_count": monthly[previous]["total"],
            "current_count": monthly[current]["total"],
            "message": f"Feedback volume changed from {monthly[previous]['total']} in {previous} to {monthly[current]['total']} in {current}.",
        }
    return {"strengths": strengths[:5], "improvement_areas": concerns[:5], "trend": trend}


def _analytics_payload(records: list[dict[str, Any]], filters: dict[str, str], notes: list[str], staff) -> dict[str, Any]:
    total = len(records)
    analyzed_records = [row for row in records if row.get("sentiment_supported", row.get("language_supported", True))]
    sentiment = Counter(row.get("sentiment", "neutral") for row in analyzed_records)
    sentiment_counts = {label: int(sentiment.get(label, 0)) for label in ("positive", "neutral", "negative")}
    sentiment_total = len(analyzed_records)
    percentages = {key: round(value * 100 / sentiment_total, 2) if sentiment_total else 0 for key, value in sentiment_counts.items()}
    emotion = dict(Counter(row.get("emotion", "Not available") for row in records if row.get("emotion") not in {"", "Not available", "Not analyzed"}))
    category = dict(Counter(row.get("category", "Uncategorized") for row in records if row.get("category")))
    sentiment_by_category = _group_counts(records, "category")

    aspect_counts: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        for aspect in record.get("aspects", []):
            name = aspect.get("aspect")
            label = aspect.get("sentiment")
            if name and label in {"positive", "neutral", "negative"}:
                aspect_counts[name][label] += 1
    aspect_distribution = {
        name: {"positive": int(counts.get("positive", 0)), "neutral": int(counts.get("neutral", 0)), "negative": int(counts.get("negative", 0))}
        for name, counts in sorted(aspect_counts.items())
    }
    aspect_semester_counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for record in records:
        semester = str(record.get("semester", "")).strip()
        if not semester:
            continue
        for aspect in record.get("aspects", []):
            if aspect.get("aspect") and aspect.get("sentiment") in {"positive", "neutral", "negative"}:
                aspect_semester_counts[(aspect["aspect"], semester)][aspect["sentiment"]] += 1
    aspect_by_semester = [
        {"aspect": aspect, "semester": semester, **{key: int(counts.get(key, 0)) for key in ("positive", "neutral", "negative")}, "total": int(sum(counts.values()))}
        for (aspect, semester), counts in sorted(aspect_semester_counts.items())
    ]

    monthly_counts: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        created = record.get("created_at", "")
        if created:
            month = datetime.fromisoformat(created.replace("Z", "+00:00")).strftime("%Y-%m")
            monthly_counts[month]["total"] += 1
            if record.get("sentiment_supported", record.get("language_supported", True)):
                monthly_counts[month][record["sentiment"]] += 1
    monthly = {month: {**{key: int(counts.get(key, 0)) for key in ("positive", "neutral", "negative")}, "total": int(counts["total"])} for month, counts in sorted(monthly_counts.items())}

    authorized_records = [record for record in records if staff.role == "admin" or record["source"] == "live"]
    source = filters.get("source", "historical")
    all_in_scope = [dict(record) for record in _historical_records()] if staff.role == "admin" and source in {"historical", "all"} else []
    if source in {"live", "all"}:
        all_in_scope.extend(_all_live_records(staff))
    options = {key: _options(all_in_scope, key) for key in ("department", "academic_year", "semester", "subject", "faculty")}
    computed_insights = _insights(authorized_records, aspect_distribution, monthly)

    return {
        "success": True,
        "total": total,
        "sentiment_total": sentiment_total,
        "unsupported_sentiment_count": total - sentiment_total,
        "positive": sentiment_counts["positive"],
        "neutral": sentiment_counts["neutral"],
        "negative": sentiment_counts["negative"],
        "positive_percentage": percentages["positive"],
        "neutral_percentage": percentages["neutral"],
        "negative_percentage": percentages["negative"],
        "sentiment": sentiment_counts,
        "sentiment_percentages": percentages,
        "emotion": emotion,
        "category": category,
        "sentiment_by_category": sentiment_by_category,
        "aspect_distribution": aspect_distribution,
        "aspect_by_semester": aspect_by_semester,
        "department_analysis": _group_counts(records, "department"),
        "semester_analysis": _group_counts(records, "semester"),
        "subject_analysis": _group_counts(records, "subject"),
        "monthly_trend": monthly,
        "insights": computed_insights,
        "filter_options": options,
        "filters": filters,
        "data_source": filters.get("source", "historical"),
        "data_source_label": {"historical": "Historical/demo dataset", "live": "Live student submissions", "all": "Combined historical/demo and live submissions"}.get(filters.get("source", "historical")),
        "notes": notes,
    }


@app.get("/api/analytics")
@staff_required
def analytics():
    try:
        records, filters, notes = _selected_records(request.args, g.staff)
        return jsonify(_analytics_payload(records, filters, notes, g.staff))
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 400


@app.route("/api/feedback", methods=["GET", "POST"])
def feedback_api():
    if request.method == "GET":
        if not session.get("staff_email"):
            return jsonify(success=False, message="Sign in to view feedback."), 401
        account = StaffAccount.query.filter_by(email=session.get("staff_email"), active=True).first()
        if not account:
            return jsonify(success=False, message="Sign in to view feedback."), 401
        g.staff = account
        try:
            records, filters, notes = _selected_records(request.args, account)
        except ValueError as error:
            return jsonify(success=False, message=str(error)), 400
        count = len(records)
        try:
            limit = max(0, min(1000, int(request.args.get("limit", "0"))))
        except ValueError:
            return jsonify(success=False, message="Feedback limit must be a whole number."), 400
        if filters.get("source") == "all":
            records.sort(key=lambda row: row.get("created_at", ""), reverse=True)
            records.sort(key=lambda row: row.get("source") != "live")
        if limit:
            records = records[:limit]
        return jsonify(success=True, count=count, data=records, filters=filters, notes=notes)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="Send feedback as JSON."), 400
    raw_comments = payload.get("comments", payload.get("text", []))
    if isinstance(raw_comments, str):
        comments = [line.strip() for line in raw_comments.splitlines() if line.strip()]
    elif isinstance(raw_comments, list):
        if any(not isinstance(value, str) for value in raw_comments):
            return jsonify(success=False, message="Each feedback comment must be text."), 400
        comments = [value.strip() for value in raw_comments if value.strip()]
    else:
        return jsonify(success=False, message="Add at least one feedback comment."), 400
    if not comments:
        return jsonify(success=False, message="Add at least one feedback comment."), 400
    if len(comments) > 100:
        return jsonify(success=False, message="Submit up to 100 comments at a time."), 400
    if any(len(comment) > 20_000 for comment in comments):
        return jsonify(success=False, message="Each comment must be 20,000 characters or fewer."), 400
    if any(any(ord(char) < 32 and char not in "\t\n\r" for char in comment) for comment in comments):
        return jsonify(success=False, message="Remove unsupported control characters from the feedback."), 400

    metadata = payload.get("metadata", payload)
    if not isinstance(metadata, dict):
        return jsonify(success=False, message="Academic details must be sent as an object."), 400
    fields = {"department": 120, "academic_year": 32, "semester": 32, "subject": 160, "section": 80, "faculty": 160}
    academic = {}
    for name, limit in fields.items():
        value = str(metadata.get(name, "")).strip()
        if len(value) > limit or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            return jsonify(success=False, message=f"Check the {name.replace('_', ' ')} field."), 400
        academic[name] = value

    try:
        batch_id = str(uuid.UUID(str(payload.get("batch_id") or uuid.uuid4())))
    except (ValueError, TypeError, AttributeError):
        return jsonify(success=False, message="The submission reference is invalid. Refresh and try again."), 400
    existing = FeedbackSubmission.query.filter_by(batch_id=batch_id).order_by(FeedbackSubmission.item_index).all()
    if existing:
        return jsonify(success=True, duplicate_batch=True, count=len(existing), results=[])

    rows = []
    results = []
    for item_index, comment in enumerate(comments):
        analysis = analyze_comment(comment)
        row = FeedbackSubmission(
            batch_id=batch_id,
            item_index=item_index,
            feedback_text=comment,
            **academic,
            sentiment=analysis["sentiment"],
            sentiment_score=analysis["sentiment_score"],
            mixed_opinion=analysis["mixed_opinion"],
            language=analysis["language"],
            language_supported=analysis["language_supported"],
            sentiment_supported=analysis["language_supported"],
            analysis_method=analysis["analysis_method"],
            analysis_note=analysis["analysis_note"],
            aspects_json=json.dumps(analysis["aspects"], ensure_ascii=False),
        )
        rows.append(row)
        results.append({"feedback": comment, **{key: value for key, value in analysis.items() if not key.startswith("_")}})
    db.session.add_all(rows)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        existing = FeedbackSubmission.query.filter_by(batch_id=batch_id).order_by(FeedbackSubmission.item_index).all()
        if existing:
            return jsonify(success=True, duplicate_batch=True, count=len(existing), results=[])
        app.logger.exception("Feedback submission could not be stored")
        return jsonify(success=False, message="Feedback could not be saved. Please try again."), 500
    return jsonify(success=True, count=len(rows), stored=True, results=results), 201


@app.post("/api/analyze")
def analyze_feedback():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="Send feedback as JSON."), 400
    comments = payload.get("comments", payload.get("text", []))
    if isinstance(comments, str):
        comments = [line.strip() for line in comments.splitlines() if line.strip()]
    if not isinstance(comments, list):
        return jsonify(success=False, message="Add feedback comments as a list or one comment per line."), 400
    if any(not isinstance(item, str) for item in comments):
        return jsonify(success=False, message="Each feedback comment must be text."), 400
    comments = [item.strip() for item in comments if item.strip()]
    if not comments or len(comments) > 100 or any(len(item) > 20_000 for item in comments):
        return jsonify(success=False, message="Submit between 1 and 100 comments, each up to 20,000 characters."), 400
    if any(any(ord(char) < 32 and char not in "\t\n\r" for char in comment) for comment in comments):
        return jsonify(success=False, message="Remove unsupported control characters from the feedback."), 400
    results = []
    for comment in comments:
        analysis = analyze_comment(comment)
        results.append({"feedback": comment, **{key: value for key, value in analysis.items() if not key.startswith("_")}})
    supported_results = [result for result in results if result["language_supported"]]
    counts = {label: sum(result["sentiment"] == label for result in supported_results) for label in ("positive", "neutral", "negative")}
    total = len(results)
    analyzed_total = len(supported_results)
    mixed = any(result["mixed_opinion"] for result in results)
    return jsonify(
        success=True,
        total=total,
        sentiment_total=analyzed_total,
        unsupported_sentiment_count=total - analyzed_total,
        sentiment_counts=counts,
        sentiment="unsupported" if not analyzed_total else "mixed" if mixed and counts["positive"] and counts["negative"] else max(counts, key=counts.get),
        positive_percentage=round(counts["positive"] * 100 / analyzed_total) if analyzed_total else 0,
        neutral_percentage=round(counts["neutral"] * 100 / analyzed_total) if analyzed_total else 0,
        negative_percentage=round(counts["negative"] * 100 / analyzed_total) if analyzed_total else 0,
        analysis_method="explainable_rules_with_multilingual_phrase_fallback",
        results=results,
    )


@app.get("/api/recommendations")
@staff_required
def recommendations():
    try:
        records, filters, notes = _selected_records(request.args, g.staff)
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 400
    payload = _analytics_payload(records, filters, notes, g.staff)
    suggestions = []
    advice = {
        "Teaching clarity": "Use a short worked example and check understanding after new concepts.",
        "Subject knowledge": "Invite specific questions and make supporting references available.",
        "Teaching pace": "Pause after difficult topics and leave time for questions.",
        "Student engagement": "Add a brief activity or discussion during class.",
        "Doubt clarification": "Set aside regular time to respond to questions and revisit unresolved doubts.",
        "Practical learning": "Connect concepts to a worked example, demonstration, or practical exercise.",
        "Assignments and assessment": "Clarify instructions and review workload, assessment criteria, and deadlines.",
        "Course organization": "Make the sequence, schedule, and course materials easier to follow.",
        "Learning environment": "Continue building a respectful and supportive classroom environment.",
        "Teaching effectiveness": "Ask students for a concrete example of what would make learning more effective.",
    }
    for item in payload["insights"]["improvement_areas"]:
        suggestions.append({"topic": item["aspect"], "mentions": item["mentions"], "suggestion": advice[item["aspect"]], "evidence": item["evidence"]})
    return jsonify(success=True, recommendations=suggestions, insights=payload["insights"], notes=notes)


@app.route("/api/admin/faculty", methods=["GET", "POST"])
@admin_required
def faculty_accounts():
    if request.method == "GET":
        rows = StaffAccount.query.filter_by(role="faculty").order_by(StaffAccount.email).all()
        return jsonify(success=True, accounts=[{"email": row.email, "faculty_key": row.faculty_key, "active": row.active} for row in rows])
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(success=False, message="Send account details as JSON."), 400
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    faculty_key = str(payload.get("faculty_key", "")).strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        return jsonify(success=False, message="Enter a valid faculty email address."), 400
    if len(password) < 12 or len(password) > 256:
        return jsonify(success=False, message="Choose a faculty password with at least 12 characters."), 400
    if not faculty_key or len(faculty_key) > 160:
        return jsonify(success=False, message="Enter the faculty name/key used on submissions."), 400
    if StaffAccount.query.filter(func.lower(StaffAccount.email) == email).first():
        return jsonify(success=False, message="An account with that email already exists."), 409
    account = StaffAccount(email=email, password_hash=generate_password_hash(password), role="faculty", faculty_key=faculty_key, active=True)
    db.session.add(account)
    db.session.commit()
    return jsonify(success=True, account={"email": account.email, "faculty_key": account.faculty_key, "active": account.active}), 201


@app.get("/api/report.pdf")
@staff_required
def pdf_report():
    try:
        records, filters, notes = _selected_records(request.args, g.staff)
    except ValueError as error:
        return jsonify(success=False, message=str(error)), 400
    payload = _analytics_payload(records, filters, notes, g.staff)
    try:
        from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
        from reportlab.graphics.shapes import Drawing
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, KeepTogether
        from xml.sax.saxutils import escape as xml_escape
    except ImportError:
        return jsonify(success=False, message="PDF support is unavailable. Install the reportlab dependency and restart."), 503

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm, topMargin=17 * mm, bottomMargin=17 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#183B56"), spaceAfter=6))
    styles.add(ParagraphStyle(name="SmallNote", parent=styles["BodyText"], fontSize=8, textColor=colors.HexColor("#526579"), leading=11))
    story = [Paragraph("AI Student Feedback Analytics", styles["ReportTitle"]), Paragraph("Academic feedback summary", styles["Heading2"]), Spacer(1, 4 * mm)]
    filter_text = " · ".join(f"{xml_escape(key.replace('_', ' ').title())}: {xml_escape(value)}" for key, value in filters.items()) or "No additional filters"
    story.extend([Paragraph(f"Data source: {payload['data_source_label']}", styles["BodyText"]), Paragraph(f"Filters: {filter_text}", styles["SmallNote"]), Spacer(1, 4 * mm)])
    for note in notes:
        story.extend([Paragraph(xml_escape(note), styles["SmallNote"]), Spacer(1, 2 * mm)])
    summary = [["Total", "Analyzed", "Positive", "Neutral", "Negative"], [str(payload["total"]), str(payload["sentiment_total"]), f"{payload['positive']} ({payload['positive_percentage']}%)", f"{payload['neutral']} ({payload['neutral_percentage']}%)", f"{payload['negative']} ({payload['negative_percentage']}%)"]]
    table = Table(summary, colWidths=[26 * mm, 30 * mm, 40 * mm, 40 * mm, 40 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183B56")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#CFD8E3")), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.extend([table, Spacer(1, 3 * mm)])
    if payload["unsupported_sentiment_count"]:
        story.append(Paragraph(f"{payload['unsupported_sentiment_count']} comments were excluded from sentiment percentages because the language could not be analyzed reliably.", styles["SmallNote"]))
    story.extend([Spacer(1, 3 * mm), Paragraph("Sentiment distribution", styles["Heading2"])])
    sentiment_chart = VerticalBarChart()
    sentiment_chart.x = 24
    sentiment_chart.y = 22
    sentiment_chart.height = 95
    sentiment_chart.width = 360
    sentiment_chart.data = [[payload["positive"], payload["neutral"], payload["negative"]]]
    sentiment_chart.categoryAxis.categoryNames = ["Positive", "Neutral", "Negative"]
    sentiment_chart.valueAxis.valueMin = 0
    sentiment_chart.valueAxis.valueMax = max(1, payload["total"])
    sentiment_chart.valueAxis.valueStep = max(1, payload["total"] // 5 or 1)
    sentiment_chart.bars[0].fillColor = colors.HexColor("#367B72")
    drawing = Drawing(410, 140)
    drawing.add(sentiment_chart)
    story.append(drawing)
    if payload["aspect_distribution"]:
        story.append(Paragraph("Aspect-wise sentiment", styles["Heading2"]))
        aspect_labels = list(payload["aspect_distribution"])
        aspect_chart = HorizontalBarChart()
        aspect_chart.x = 95
        aspect_chart.y = 24
        aspect_chart.width = 290
        aspect_chart.height = max(120, min(250, 17 * len(aspect_labels)))
        aspect_chart.data = [
            [payload["aspect_distribution"][name]["positive"] for name in aspect_labels],
            [payload["aspect_distribution"][name]["neutral"] for name in aspect_labels],
            [payload["aspect_distribution"][name]["negative"] for name in aspect_labels],
        ]
        aspect_chart.categoryAxis.categoryNames = aspect_labels
        aspect_chart.categoryAxis.labels.fontSize = 7
        aspect_chart.valueAxis.valueMin = 0
        aspect_chart.valueAxis.valueMax = max(1, max(sum(payload["aspect_distribution"][name].values()) for name in aspect_labels))
        aspect_chart.valueAxis.valueStep = max(1, aspect_chart.valueAxis.valueMax // 5 or 1)
        aspect_chart.bars[0].fillColor = colors.HexColor("#2a8178")
        aspect_chart.bars[1].fillColor = colors.HexColor("#a8b4c2")
        aspect_chart.bars[2].fillColor = colors.HexColor("#d65d5d")
        aspect_drawing = Drawing(410, aspect_chart.height + 55)
        aspect_drawing.add(aspect_chart)
        story.append(aspect_drawing)
        aspect_rows = [["Aspect", "Positive", "Neutral", "Negative"]]
        for aspect, counts in payload["aspect_distribution"].items():
            aspect_rows.append([aspect, str(counts["positive"]), str(counts["neutral"]), str(counts["negative"])])
        aspect_table = Table(aspect_rows, colWidths=[82 * mm, 30 * mm, 30 * mm, 30 * mm], repeatRows=1)
        aspect_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9F0F5")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CFD8E3")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.extend([aspect_table, Spacer(1, 5 * mm)])

    def add_insight_section(title, values):
        story.append(Paragraph(title, styles["Heading2"]))
        if not values:
            story.append(Paragraph("Insufficient feedback evidence for this section.", styles["SmallNote"]))
            return
        for item in values:
            block = [Paragraph(f"{item['aspect']} — {item['mentions']} mentions", styles["Heading3"])]
            for evidence in item["evidence"]:
                block.append(Paragraph(f'“{xml_escape(evidence[:420])}”', styles["SmallNote"]))
            story.append(KeepTogether(block))
    add_insight_section("Frequently mentioned strengths", payload["insights"]["strengths"])
    add_insight_section("Improvement areas", payload["insights"]["improvement_areas"])
    if payload["insights"]["trend"]:
        story.extend([Paragraph("Feedback trend", styles["Heading2"]), Paragraph(payload["insights"]["trend"]["message"], styles["BodyText"])])
    elif payload["data_source"] in {"live", "all"}:
        story.extend([Paragraph("Feedback trend", styles["Heading2"]), Paragraph("There is not enough timestamped data for a month-to-month comparison.", styles["SmallNote"])])
    story.extend([Spacer(1, 4 * mm), Paragraph("Automated language analysis is an estimate. Review the cited original feedback in context; do not use aggregate sentiment alone to rank or make disciplinary decisions about faculty.", styles["SmallNote"])])
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="student-feedback-report.pdf")


@app.get("/api/health")
def health():
    try:
        db.session.execute(db.select(1))
        return jsonify(status="ok", database="connected")
    except Exception:
        db.session.rollback()
        app.logger.exception("Database health check failed")
        return jsonify(status="error", database="unavailable"), 503


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(success=False, message="The submission is too large. Reduce the text or split it into smaller batches."), 413


if __name__ == "__main__":
    print("AI Student Feedback Analytics is available at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
