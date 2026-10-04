from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import pandas as pd
import os
import json
import re
from functools import wraps
from datetime import datetime, timezone
from werkzeug.security import check_password_hash, generate_password_hash
try:
    from backend.storage import engine, submissions, users, fetch_submissions
except ModuleNotFoundError:
    from storage import engine, submissions, users, fetch_submissions
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
@require_roles("admin")
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
@require_roles("admin")
def analysis_page():

    return send_from_directory(
        FRONTEND_DIR,
        "analysis.html"
    )


# =========================================================
# PREDICTIONS PAGE
# =========================================================

@app.route("/predictions")
@require_roles("admin")
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

@app.route(
    "/api/analyze",
    methods=["POST"]
)
def analyze_feedback():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Feedback must be sent as a JSON object."}), 400
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"success": False, "message": "Please enter feedback."}), 400
    if len(text) > 5000:
        return jsonify({"success": False, "message": "Feedback must be 5,000 characters or fewer."}), 400
    result = analyze_text(text)
    result.update({"success": True, "feedback": text})
    return jsonify(result)

@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    from sqlalchemy import insert
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Feedback must be sent as a JSON object."}), 400
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"success": False, "message": "Please enter feedback."}), 400
    if len(text) > 5000:
        return jsonify({"success": False, "message": "Feedback must be 5,000 characters or fewer."}), 400
    analysis = analyze_text(text)
    fields = [str(data.get(k, "")).strip()[:160] for k in ("department", "course", "faculty")]
    # Identity fields are intentionally neither requested nor stored in this flow.
    with engine.begin() as connection:
        result = connection.execute(insert(submissions).values(created_at=datetime.now(timezone.utc).isoformat(),
            feedback_text=text.strip(), department=fields[0], course=fields[1], faculty=fields[2],
            anonymous=True, analysis_json=json.dumps(analysis)))
        submission_id = result.inserted_primary_key[0]
    return jsonify({"success": True, "submission_id": submission_id, "analysis": analysis,
        "message": "Thank you. Your feedback was stored without student identity."}), 201

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
