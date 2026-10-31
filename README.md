# AI Student Feedback Analytics

A Flask website for anonymous student course feedback and evidence-backed teaching analytics.

## Features

- **Anonymous Student Feedback**: Clean submission interface collecting course feedback without requesting student names or emails.
- **Client-Side CSV/TSV/TXT Import**: Secure in-browser file reading allowing students to import batches up to 100 comments.
- **Explainable Aspect & Sentiment Analysis**: Rule-based NLP detecting 10 core teaching aspects with quote excerpts, negation handling, mixed-sentiment detection, and support for English, Hindi, and Telugu phrases.
- **Role-Based Access Control**: Secure staff authentication for administrators and faculty accounts with PBKDF2 hashing, login rate limiting, and CSRF protection.
- **Faculty-Scoped Insights**: Faculty accounts automatically see only feedback submitted for their assigned classes; historical demo data is excluded.
- **Executive PDF Reports**: Dynamic report generator producing downloadable PDF summaries with charts and student quote excerpts.
- **Dual Database Support**: Seamless operation on local SQLite during development and managed PostgreSQL in production via SQLAlchemy.

## Run Locally (Windows)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
$env:SECRET_KEY = "a-long-random-local-secret"
$env:ADMIN_EMAIL = "admin@example.edu"
$env:ADMIN_PASSWORD = "AdminPassword123!"
python backend\app.py
```

Then open `http://127.0.0.1:5000` in your browser.

## Deploy to Vercel

1. Connect this repository to Vercel.
2. In Project Settings → Environment Variables, configure:
   - `DATABASE_URL`: Connection string to persistent PostgreSQL database.
   - `SECRET_KEY`: A unique, secure random string.
   - `ADMIN_EMAIL`: Initial administrator login email.
   - `ADMIN_PASSWORD`: Initial administrator password (12+ characters).
3. Deploy. Production deployments automatically initialize the database tables and provision the initial administrator account.
