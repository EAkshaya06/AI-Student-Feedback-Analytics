from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import pandas as pd
import os
import json
import re
import hashlib
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from functools import wraps
from datetime import datetime, timezone, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
try:
    from backend.storage import engine, submissions, users, teacher_login_tokens, fetch_submissions
except ModuleNotFoundError:
    from storage import engine, submissions, users, teacher_login_tokens, fetch_submissions
try:
    from backend.services.aspect_analysis import analyze as analyze_text
except ModuleNotFoundError:
    from services.aspect_analysis import analyze as analyze_text

app = Flask(__name__)
IS_PRODUCTION = (os.environ.get("APP_ENV", "").lower() == "production"
                 or os.environ.get("VERCEL") == "1"
                 or os.environ.get("RENDER") == "true")
app.secret_key = os.environ.get("SECRET_KEY") or (None if IS_PRODUCTION else os.urandom(32))
if IS_PRODUCTION and not app.secret_key:
    raise RuntimeError("SECRET_KEY must be set in production.")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=IS_PRODUCTION, PERMANENT_SESSION_LIFETIME=8 * 60 * 60)
allowed_origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()]
if allowed_origins:
    CORS(app, origins=allowed_origins)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "backend", "data")

FEEDBACK_FILE = os.path.join(
    DATA_DIR,
    "feedback.csv"
)

CLEANED_FILE = os.path.join(
    DATA_DIR,
    "cleaned_feedback.csv"
)

FINAL_FILE = os.path.join(
    DATA_DIR,
    "final_feedback_analysis.csv"
)

EMOTION_FILE = os.path.join(
    DATA_DIR,
    "emotion_feedback.csv"
)

RECOMMENDATION_FILE = os.path.join(
    DATA_DIR,
    "recommendations.txt"
)
def saved_submissions(faculty_key=None):
    return fetch_submissions(faculty_key)

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    from sqlalchemy import select
    with engine.connect() as connection:
        return connection.execute(select(users).where(users.c.id == user_id, users.c.active.is_(True))).mappings().first()

def require_roles(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                if request.path.startswith("/api/"):
                    return jsonify({"success":False,"message":"Please sign in to continue."}), 401
                return redirect(url_for("login_page", next=request.path))
            if user["role"] not in roles:
                return jsonify({"success":False,"message":"You do not have access to this page."}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorate

def bootstrap_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if IS_PRODUCTION and (not email or len(password) < 12):
        raise RuntimeError("Set ADMIN_EMAIL and an ADMIN_PASSWORD of at least 12 characters in production.")
    if email and password:
        from sqlalchemy import insert, select
        with engine.begin() as connection:
            exists = connection.execute(select(users.c.id).where(users.c.email == email)).first()
            if not exists:
                connection.execute(insert(users).values(email=email, display_name="University Admin",
                    password_hash=generate_password_hash(password), role="admin", active=True))

bootstrap_admin()


# =========================================================
# LOAD DATA
# =========================================================

def load_data():

    # Prefer final analysis file
    if os.path.exists(FINAL_FILE):
        print("Loading:", FINAL_FILE)
        return pd.read_csv(FINAL_FILE)

    # Deployment packages the public historical dataset with frontend assets.
    packaged_final = os.path.join(FRONTEND_DIR, "data", "final_feedback_analysis.csv")
    if os.path.exists(packaged_final):
        print("Loading:", packaged_final)
        return pd.read_csv(packaged_final)

    # Otherwise use emotion analysis
    if os.path.exists(EMOTION_FILE):
        print("Loading:", EMOTION_FILE)
        return pd.read_csv(EMOTION_FILE)

    # Otherwise cleaned data
    if os.path.exists(CLEANED_FILE):
        print("Loading:", CLEANED_FILE)
        return pd.read_csv(CLEANED_FILE)

    # Finally raw data
    if os.path.exists(FEEDBACK_FILE):
        print("Loading:", FEEDBACK_FILE)
        return pd.read_csv(FEEDBACK_FILE)

    return pd.DataFrame()


# =========================================================
# NORMALIZE DATA
# =========================================================

def normalize_data(df):

    if df.empty:
        return df

    # Find feedback text column
    if "text" in df.columns:
        df["feedback_text"] = df["text"].fillna("").astype(str)

    elif "cleaned_text" in df.columns:
        df["feedback_text"] = (
            df["cleaned_text"]
            .fillna("")
            .astype(str)
        )

    elif "feedback" in df.columns:
        df["feedback_text"] = (
            df["feedback"]
            .fillna("")
            .astype(str)
        )

    else:
        df["feedback_text"] = ""

    # Normalize sentiment
    if "sentiment" in df.columns:

        df["sentiment"] = (
            df["sentiment"]
            .fillna("neutral")
            .astype(str)
            .str.lower()
            .str.strip()
        )

    elif "predicted_sentiment" in df.columns:

        df["sentiment"] = (
            df["predicted_sentiment"]
            .fillna("neutral")
            .astype(str)
            .str.lower()
            .str.strip()
        )

    else:
        df["sentiment"] = "neutral"

    # Normalize category
    if "category" in df.columns:

        df["category"] = (
            df["category"]
            .fillna("unknown")
            .astype(str)
            .str.lower()
            .str.strip()
        )

    else:
        df["category"] = "unknown"

    # Normalize emotion
    if "emotion" not in df.columns:
        df["emotion"] = "Neutral"

    df["emotion"] = (
        df["emotion"]
        .fillna("Neutral")
        .astype(str)
        .str.strip()
    )

    return df


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        FRONTEND_DIR,
        "index.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    return send_from_directory(
        FRONTEND_DIR,
        "dashboard.html"
    )


# =========================================================
# FEEDBACK PAGE
# =========================================================

@app.route("/feedback")
def feedback_page():

    return send_from_directory(
        FRONTEND_DIR,
        "feedback.html"
    )


# =========================================================
# ANALYSIS PAGE
# =========================================================

@app.route("/analysis")
def analysis_page():

    return send_from_directory(
        FRONTEND_DIR,
        "analysis.html"
    )


# =========================================================
# PREDICTIONS PAGE
# =========================================================

@app.route("/predictions")
def predictions_page():

    return send_from_directory(
        FRONTEND_DIR,
        "predictions.html"
    )


# =========================================================
# CSS
# =========================================================

@app.route("/css/<path:filename>")
def css_files(filename):

    return send_from_directory(
        os.path.join(FRONTEND_DIR, "css"),
        filename
    )


# =========================================================
# JAVASCRIPT
# =========================================================

@app.route("/js/<path:filename>")
def js_files(filename):

    return send_from_directory(
        os.path.join(FRONTEND_DIR, "js"),
        filename
    )


# =========================================================
# API - FEEDBACK
# =========================================================

@app.route("/insights")
@require_roles("admin", "faculty")
def insights_page():
    return send_from_directory(FRONTEND_DIR, "insights.html")

@app.route("/login")
def login_page():
    if current_user():
        return redirect(url_for("insights_page"))
    return send_from_directory(FRONTEND_DIR, "login.html")

@app.route("/teacher-login")
def teacher_login_page():
    user = current_user()
    if user:
        return redirect(url_for("insights_page"))
    return send_from_directory(FRONTEND_DIR, "teacher-login.html")


@app.route("/api/auth/login", methods=["POST"])
def login():
    from sqlalchemy import select
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success":False,"message":"Invalid email or password."}), 400
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not isinstance(password, str) or len(email) > 254 or len(password) > 256:
        return jsonify({"success":False,"message":"Invalid email or password."}), 400
    with engine.connect() as connection:
        user = connection.execute(select(users).where(users.c.email == email, users.c.active.is_(True))).mappings().first()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"success":False,"message":"Invalid email or password."}), 401
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    return jsonify({"success":True,"user":{"name":user["display_name"],"role":user["role"]}})

def _send_teacher_signin_email(address, signin_url):
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured.")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    message = EmailMessage()
    message["Subject"] = "Your teacher sign-in link"
    message["From"] = sender
    message["To"] = address
    message.set_content(
        "Use this one-time link to sign in to Teacher Feedback Intelligence. "
        "It expires in 10 minutes and can only be used once.\n\n"
        + signin_url
        + "\n\nIf you did not request this link, you can ignore this email."
    )
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=15) as mail:
            if username:
                mail.login(username, password)
            mail.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as mail:
            mail.ehlo()
            mail.starttls(context=ssl.create_default_context())
            mail.ehlo()
            if username:
                mail.login(username, password)
            mail.send_message(message)


@app.route("/api/auth/teacher-link", methods=["POST"])
def request_teacher_signin_link():
    from sqlalchemy import delete, insert, select
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Enter a valid university email address."}), 400
    email = str(data.get("email", "")).strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        return jsonify({"success": False, "message": "Enter a valid university email address."}), 400
    if not os.environ.get("SMTP_HOST") or not os.environ.get("SMTP_FROM"):
        return jsonify({"success": False, "message": "Passwordless email sign-in is not configured yet. Ask the administrator to configure the mail settings."}), 503

    now = datetime.now(timezone.utc)
    raw_token = None
    with engine.begin() as connection:
        user = connection.execute(select(users).where(
            users.c.email == email,
            users.c.role == "faculty",
            users.c.active.is_(True)
        )).mappings().first()
        if user:
            cooldown_after = (now - timedelta(seconds=60)).isoformat()
            recently_sent = connection.execute(select(teacher_login_tokens.c.token_hash).where(
                teacher_login_tokens.c.user_id == user["id"],
                teacher_login_tokens.c.created_at >= cooldown_after
            )).first()
            if not recently_sent:
                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                connection.execute(delete(teacher_login_tokens).where(
                    teacher_login_tokens.c.user_id == user["id"]
                ))
                connection.execute(insert(teacher_login_tokens).values(
                    token_hash=token_hash,
                    user_id=user["id"],
                    created_at=now.isoformat(),
                    expires_at=(now + timedelta(minutes=10)).isoformat(),
                    used_at=None
                ))

    if raw_token:
        base_url = os.environ.get("PUBLIC_BASE_URL", request.url_root).rstrip("/")
        signin_url = base_url + "/teacher-login?token=" + raw_token
        try:
            _send_teacher_signin_email(email, signin_url)
        except Exception:
            app.logger.exception("Could not send passwordless teacher sign-in email")
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            from sqlalchemy import delete
            with engine.begin() as connection:
                connection.execute(delete(teacher_login_tokens).where(
                    teacher_login_tokens.c.token_hash == token_hash
                ))

    return jsonify({
        "success": True,
        "message": "If a pre-registered faculty account uses that email, a sign-in link will be sent. Check the inbox; the link expires in 10 minutes."
    })


@app.route("/api/auth/teacher-link/verify", methods=["POST"])
def verify_teacher_signin_link():
    from sqlalchemy import select, update
    data = request.get_json(silent=True) or {}
    token = data.get("token", "") if isinstance(data, dict) else ""
    if not isinstance(token, str) or len(token) > 200:
        return jsonify({"success": False, "message": "This sign-in link is invalid or has expired."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        link = connection.execute(select(teacher_login_tokens).where(
            teacher_login_tokens.c.token_hash == token_hash,
            teacher_login_tokens.c.used_at.is_(None)
        )).mappings().first()
        if not link:
            return jsonify({"success": False, "message": "This sign-in link is invalid, expired, or already used."}), 401
        if datetime.fromisoformat(link["expires_at"]) <= now:
            return jsonify({"success": False, "message": "This sign-in link has expired. Request a new one."}), 401
        user = connection.execute(select(users).where(
            users.c.id == link["user_id"],
            users.c.role == "faculty",
            users.c.active.is_(True)
        )).mappings().first()
        if not user:
            return jsonify({"success": False, "message": "This sign-in link is invalid or has expired."}), 401
        changed = connection.execute(update(teacher_login_tokens).where(
            teacher_login_tokens.c.token_hash == token_hash,
            teacher_login_tokens.c.used_at.is_(None)
        ).values(used_at=now.isoformat()))
        if changed.rowcount != 1:
            return jsonify({"success": False, "message": "This sign-in link has already been used."}), 401
        user_id = user["id"]
        display_name = user["display_name"]
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    return jsonify({"success": True, "user": {"name": display_name, "role": "faculty"}})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success":True})

@app.route("/api/auth/me")
def auth_me():
    user = current_user()
    if not user:
        return jsonify({"success":False}), 401
    return jsonify({"success":True,"user":{"name":user["display_name"],"role":user["role"]}})

@app.route("/api/admin/users", methods=["POST"])
@require_roles("admin")
def create_faculty_user():
    from sqlalchemy import insert, select
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success":False,"message":"Invalid account details."}), 400
    email = str(data.get("email", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    faculty_key = str(data.get("faculty_key", "")).strip()
    password = data.get("password", "")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(name) > 160 or not name or not faculty_key or len(faculty_key) > 160 or not isinstance(password, str) or len(password) < 12 or len(password) > 256:
        return jsonify({"success":False,"message":"Provide a valid email, name, faculty key, and password with at least 12 characters."}), 400
    with engine.begin() as connection:
        if connection.execute(select(users.c.id).where(users.c.email == email)).first():
            return jsonify({"success":False,"message":"An account with that email already exists."}), 409
        connection.execute(insert(users).values(email=email, display_name=name,
            password_hash=generate_password_hash(password), role="faculty", faculty_key=faculty_key, active=True))
    return jsonify({"success":True,"message":"Faculty account created."}), 201

@app.route("/api/public-dataset")
def public_dataset():
    """Read-only historical dataset for the public project dashboard."""
    df = normalize_data(load_data())
    if df.empty:
        return jsonify({"success": True, "total": 0, "data": [], "sentiment": {}, "emotion": {}, "category": {}, "sentiment_by_category": {}})
    sentiment = df["sentiment"].value_counts().to_dict()
    total = len(df)
    cross = pd.crosstab(df["category"], df["sentiment"]).fillna(0)
    return jsonify({
        "success": True, "total": total,
        "positive": int(sentiment.get("positive", 0)),
        "neutral": int(sentiment.get("neutral", 0)),
        "negative": int(sentiment.get("negative", 0)),
        "positive_percentage": round(sentiment.get("positive", 0) / total * 100, 2),
        "neutral_percentage": round(sentiment.get("neutral", 0) / total * 100, 2),
        "negative_percentage": round(sentiment.get("negative", 0) / total * 100, 2),
        "sentiment": sentiment,
        "emotion": df["emotion"].value_counts().to_dict(),
        "category": df["category"].value_counts().to_dict(),
        "sentiment_by_category": {str(k): v.to_dict() for k, v in cross.iterrows()},
        "data": df.to_dict(orient="records")
    })


@app.route("/api/feedback")
@require_roles("admin")
def get_feedback():

    df = normalize_data(load_data())
    records = df.to_dict(orient="records") if not df.empty else []
    for row in saved_submissions():
        result = json.loads(row["analysis_json"])
        records.insert(0, {"text": row["feedback_text"], "feedback_text": row["feedback_text"],
            "sentiment": result["sentiment"], "category": ", ".join(a["aspect"] for a in result["aspects"]) or "Unclassified",
            "emotion": "Not analyzed", "created_at": row["created_at"], "department": row["department"],
            "course": row["course"], "faculty": row["faculty"], "anonymous": bool(row["anonymous"]), "analysis": result})

    return jsonify({
        "success": True,
        "count": len(records),
        "data": records
    })


# =========================================================
# API - ANALYTICS
# =========================================================

@app.route("/api/analytics")
@require_roles("admin")
def analytics():

    df = normalize_data(load_data())

    if df.empty:
        df = pd.DataFrame(columns=["sentiment", "emotion", "category"])

    submissions = saved_submissions()
    total = len(df) + len(submissions)

    # Sentiment counts
    sentiment_counts = (
        df["sentiment"]
        .value_counts()
        .to_dict()
    )
    for row in submissions:
        label = json.loads(row["analysis_json"])["sentiment"]
        sentiment_counts[label] = sentiment_counts.get(label, 0) + 1

    positive = sentiment_counts.get(
        "positive",
        0
    )

    neutral = sentiment_counts.get(
        "neutral",
        0
    )

    negative = sentiment_counts.get(
        "negative",
        0
    )

    # Percentages
    positive_percentage = positive / total * 100 if total else 0

    neutral_percentage = neutral / total * 100 if total else 0

    negative_percentage = negative / total * 100 if total else 0

    # Emotion
    emotion_counts = (
        df["emotion"]
        .value_counts()
        .to_dict()
    )

    # Category
    category_counts = (
        df["category"]
        .value_counts()
        .to_dict()
    )
    for row in submissions:
        for aspect in json.loads(row["analysis_json"])["aspects"]:
            key = aspect["aspect"].lower()
            category_counts[key] = category_counts.get(key, 0) + 1

    # Sentiment by category
    sentiment_by_category = pd.crosstab(
        df["category"],
        df["sentiment"]
    ).fillna(0)

    sentiment_category = {}

    for category in sentiment_by_category.index:

        sentiment_category[
            category
        ] = sentiment_by_category.loc[
            category
        ].to_dict()

    return jsonify({

        "success": True,

        "total": total,

        "positive": positive,

        "neutral": neutral,

        "negative": negative,

        "positive_percentage": round(
            positive_percentage,
            2
        ),

        "neutral_percentage": round(
            neutral_percentage,
            2
        ),

        "negative_percentage": round(
            negative_percentage,
            2
        ),

        "sentiment": sentiment_counts,

        "emotion": emotion_counts,

        "category": category_counts,

        "sentiment_by_category":
            sentiment_category,
        "mixed": sentiment_counts.get("mixed", 0),
        "stored_submissions": len(submissions)

    })


# =========================================================
# API - ANALYZE NEW FEEDBACK
# =========================================================

def _feedback_comments(data):
    raw_comments = data.get("comments")
    if raw_comments is None:
        raw_comments = [data.get("text", "")]
    if isinstance(raw_comments, str):
        raw_comments = raw_comments.splitlines()
    if not isinstance(raw_comments, list):
        return None, "Feedback comments must be a list of text entries."
    comments = [item.strip() for item in raw_comments if isinstance(item, str) and item.strip()]
    if not comments:
        return None, "Please enter at least one student feedback comment."
    if len(comments) > 25:
        return None, "Please analyze up to 25 comments at a time."
    if any(len(item) > 5000 for item in comments) or sum(map(len, comments)) > 20000:
        return None, "Keep each comment under 5,000 characters and the total under 20,000 characters."
    return comments, None


def _analyze_feedback_batch(comments):
    results = [analyze_text(comment) for comment in comments]
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
    aspect_groups = {}
    for result in results:
        label = result.get("sentiment", "neutral")
        sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
        for aspect in result.get("aspects", []):
            group = aspect_groups.setdefault(aspect["aspect"], {
                "labels": [], "evidence": [], "confidence": []
            })
            group["labels"].append(aspect.get("sentiment", "neutral"))
            group["evidence"].extend(aspect.get("evidence", []))
            group["confidence"].append(aspect.get("confidence", 0))
    overall = (
        "mixed" if sentiment_counts["mixed"] or (sentiment_counts["positive"] and sentiment_counts["negative"])
        else "positive" if sentiment_counts["positive"]
        else "negative" if sentiment_counts["negative"]
        else "neutral"
    )
    aspects = []
    for name, group in aspect_groups.items():
        labels = group["labels"]
        positive = labels.count("positive")
        negative = labels.count("negative")
        if "mixed" in labels or (positive and negative):
            sentiment = "mixed"
        elif "improvement" in labels:
            sentiment = "improvement"
        elif positive:
            sentiment = "positive"
        elif negative:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        aspects.append({
            "aspect": name,
            "sentiment": sentiment,
            "confidence": round(sum(group["confidence"]) / len(group["confidence"]), 2),
            "evidence": list(dict.fromkeys(group["evidence"]))[:8],
            "mentions": len(labels)
        })
    detailed_results = [
        {"feedback": comment, **result}
        for comment, result in zip(comments, results)
    ]
    return {
        "sentiment": overall,
        "confidence": round(sum(item.get("confidence", 0) for item in results) / len(results), 2),
        "aspects": aspects,
        "results": detailed_results,
        "sentiment_counts": sentiment_counts,
        "total": len(comments),
        "strengths": sorted({aspect for item in results for aspect in item.get("strengths", [])}),
        "improvements": sorted({aspect for item in results for aspect in item.get("improvements", [])}),
        "suggestions": sorted({aspect for item in results for aspect in item.get("suggestions", [])}),
        "concerns": sorted({aspect for item in results for aspect in item.get("concerns", [])}),
        "method": "Aggregated explainable sentence and phrase rules"
    }


@app.route("/api/analyze", methods=["POST"])
def analyze_feedback():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Feedback must be sent as a JSON object."}), 400
    comments, error = _feedback_comments(data)
    if error:
        return jsonify({"success": False, "message": error}), 400
    teacher_email = str(data.get("teacher_email", "")).strip().lower()
    if teacher_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", teacher_email):
        return jsonify({"success": False, "message": "Enter a valid teacher college email address."}), 400
    result = _analyze_feedback_batch(comments)
    result.update({"success": True, "teacher_email": teacher_email})
    return jsonify(result)


@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    from sqlalchemy import insert
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Feedback must be sent as a JSON object."}), 400
    comments, error = _feedback_comments(data)
    if error:
        return jsonify({"success": False, "message": error}), 400
    teacher_email = str(data.get("teacher_email", "")).strip().lower()
    if teacher_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", teacher_email):
        return jsonify({"success": False, "message": "Enter a valid teacher college email address."}), 400
    fields = [str(data.get(k, "")).strip()[:160] for k in ("department", "course")]
    faculty_name = str(data.get("faculty", "")).strip()[:160]
    faculty_label = teacher_email or faculty_name
    analyses = [analyze_text(comment) for comment in comments]
    report = _analyze_feedback_batch(comments)
    submission_ids = []
    with engine.begin() as connection:
        for comment, analysis in zip(comments, analyses):
            result = connection.execute(insert(submissions).values(
                created_at=datetime.now(timezone.utc).isoformat(),
                feedback_text=comment,
                department=fields[0],
                course=fields[1],
                faculty=faculty_label,
                anonymous=True,
                analysis_json=json.dumps(analysis)
            ))
            submission_ids.append(result.inserted_primary_key[0])
    return jsonify({
        "success": True,
        "submission_ids": submission_ids,
        "analysis": report,
        "message": f"Thank you. {len(comments)} comment(s) were stored without student identity."
    }), 201

@app.route("/api/insights")
@require_roles("admin", "faculty")
def insight_center():
    user = current_user()
    faculty_key = None if user["role"] == "admin" else (user["faculty_key"] or "")
    submissions = saved_submissions(faculty_key)
    summary = {}
    suggestion_evidence = set()
    for row in submissions:
        result = json.loads(row["analysis_json"])
        for aspect in result["aspects"]:
            bucket = summary.setdefault(aspect["aspect"], {"mentions":0,"positive":0,"negative":0,"neutral":0,"mixed":0,"improvement":0})
            bucket["mentions"] += 1
            bucket[aspect["sentiment"]] = bucket.get(aspect["sentiment"], 0) + 1
            if any(word in " ".join(aspect["evidence"]).lower() for word in ("more", "should", "need", "could", "suggest", "wish")):
                suggestion_evidence.add(aspect["aspect"])
    return jsonify({"success":True,"stored_feedback_count":len(submissions),"aspects":summary,
        "strengths":sorted([k for k,v in summary.items() if v["positive"] > v["negative"] + v["improvement"]], key=lambda k: -summary[k]["mentions"]),
        "improvement_areas":sorted([k for k,v in summary.items() if v["negative"] + v["improvement"] > 0], key=lambda k: -(summary[k]["negative"] + summary[k]["improvement"])),
        "student_suggestions":sorted(suggestion_evidence, key=lambda k: -summary[k]["mentions"]),
        "method":"Aggregated from actual submitted feedback; explainable aspect evidence"})


# =========================================================
# API - RECOMMENDATIONS
# =========================================================

@app.route("/api/recommendations")
@require_roles("admin")
def recommendations():

    if os.path.exists(
        RECOMMENDATION_FILE
    ):

        with open(
            RECOMMENDATION_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            recommendations_list = [
                line.strip()
                for line in file
                if line.strip()
            ]

        return jsonify({

            "success": True,

            "recommendations":
                recommendations_list

        })

    return jsonify({

        "success": True,

        "recommendations": []

    })


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/api/health")
def health():
    from sqlalchemy import func, select
    try:
        with engine.connect() as connection:
            count = connection.execute(select(func.count()).select_from(submissions)).scalar_one()
        return jsonify({"status":"ok","database":"connected","stored_submissions":count})
    except Exception:
        app.logger.exception("Health check database failure")
        return jsonify({"status":"unavailable"}), 503


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    print("\n======================================")
    print("AI STUDENT FEEDBACK ANALYTICS")
    print("FLASK SERVER")
    print("======================================")

    print("\nData directory:")
    print(DATA_DIR)

    df = load_data()

    print(
        "\nRecords loaded:",
        len(df)
    )

    if not df.empty:

        print(
            "Columns:",
            list(df.columns)
        )

    print(
        "\nServer running at:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print(
        "======================================\n"
    )

    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=5000,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )
