# AI Student Feedback Analytics

A Flask website for anonymous student feedback and teacher development insights. Students can submit feedback without an identity field; the app detects teaching aspects, sentiment, and evidence. Admin and faculty dashboards require sign-in. Faculty accounts are scoped to the matching faculty name/key.

## Run locally

1. Install Python 3.12 and dependencies: `python -m pip install -r requirements.txt`.
2. Set a local secret, for example in PowerShell: `$env:SECRET_KEY = "a-long-random-local-secret"`.
3. Start the Flask server from the repository root: `python backend/app.py`.
4. Open `http://127.0.0.1:5000`.

Local use stores new feedback in SQLite under `backend/data/feedback_submissions.sqlite3`. The historical CSV files, if present, support the original demo dashboard; they are excluded from Vercel deployments.

## Deploy to Vercel (free Hobby project)

This project has a root `app.py` Vercel entry point, a root `requirements.txt`, Python version configuration, and `vercel.json`. Vercel runs Flask as a serverless function. Connect this project to a GitHub repository from the Vercel dashboard and deploy it as a Python project; no build command or output directory is needed.

Before the first production deployment:

1. Create a PostgreSQL database using a provider that offers a free tier, such as Neon. Use its pooled connection string as `DATABASE_URL` (it should begin with `postgresql://` or `postgres://`). Vercel's old Postgres product is not provided; use an external database provider.
2. In Vercel Project Settings → Environment Variables, add `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` for Production. Use a unique random `SECRET_KEY` and an admin password of at least 12 characters. Do not commit these values or paste them into source files.
3. Redeploy after setting the variables. The first app start creates the required database tables and the initial administrator account. Later changes to `ADMIN_PASSWORD` do not reset an existing account; use the database/account administration process to change it.
4. Check `/api/health`; a successful deployment responds with `{"status":"ok","database":"connected",...}`. Open `/login` to sign into the staff dashboard. Students submit feedback at `/feedback`.
5. Create each faculty account by signing in as admin and sending a `POST` request to `/api/admin/users` with a JSON body containing `email`, `name`, `faculty_key`, and a password of at least 12 characters. The faculty key must exactly match the name entered in the student feedback form. This initial version has no staff account management screen.

Vercel Hobby is free and deployments can stay online without a 30-day trial expiry. It has monthly usage caps; exceeding them can pause the project until usage resets. Hobby is limited to personal, non-commercial use under Vercel's current terms, so confirm eligibility before using it as an official college service. Vercel also runs the Python app as serverless functions rather than an always-on server. The database is separate from Vercel and remains available subject to the database provider's free-plan limits and terms. Keep backups of submitted feedback.

## Security and privacy notes

The feedback form does not request a student identity, but free text can contain identifying details. Do not solicit names or sensitive information. The deployment provides password-based staff roles and faculty-level filtering, but it is still a prototype: it has no login rate limiting, staff account management UI, audit log, moderation workflow, or institutional privacy/security review. Do not use it for confidential or high-stakes decisions without that review.

## Analysis limits

Live analysis uses a small, transparent English phrase lexicon with sentence/clause splitting. It can misread negation, informal wording, sarcasm, mixed clauses, or unseen vocabulary. Confidence is a heuristic, not a calibrated probability. The insight page aggregates submitted feedback; it does not rank teachers or recommend disciplinary action. Included legacy ML models and scripts are not used by the live analysis path.

## Stack

Python, Flask, SQLAlchemy, PostgreSQL (hosted) or SQLite (local), HTML, CSS, JavaScript, and Chart.js.
