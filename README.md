# AI Student Feedback Analytics

A Flask website for anonymous student feedback and teacher development insights. Students can submit feedback without an identity field; the app detects teaching aspects, sentiment, and evidence. Admin and faculty dashboards require sign-in. Faculty accounts are scoped to the matching faculty email/key.

## Run locally

1. Install Python 3.12 and dependencies: `python -m pip install -r requirements.txt`.
2. Set a local secret, for example in PowerShell: `$env:SECRET_KEY = "a-long-random-local-secret"`.
3. Start the Flask server from the repository root: `python backend/app.py`.
4. Open `http://127.0.0.1:5000`.

To enable teacher passwordless sign-in locally, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `PUBLIC_BASE_URL` before starting the server. Use SMTP port 587 with STARTTLS or port 465 with SSL; set `PUBLIC_BASE_URL=http://127.0.0.1:5000` for local use. Keep mail credentials out of Git. Faculty accounts must first be provisioned by an administrator. Teachers then sign in at `/teacher-login` using a one-time link sent to their registered university email; the link expires after 10 minutes.

Local use stores new feedback and one-time sign-in tokens in SQLite under `backend/data/feedback_submissions.sqlite3`. The historical CSV files, if present, support the original demo dashboard; they are excluded from Vercel deployments.

## Deploy to Vercel (free Hobby project)

This project has a root `app.py` Vercel entry point, a root `requirements.txt`, Python version configuration, and `vercel.json`. Vercel runs Flask as a serverless function. Connect this project to a GitHub repository from the Vercel dashboard and deploy it as a Python project; no build command or output directory is needed.

Before the first production deployment:

1. Create a PostgreSQL database using a provider that offers a free tier, such as Neon. Use its pooled connection string as `DATABASE_URL` (it should begin with `postgresql://` or `postgres://`). Vercel's old Postgres product is not provided; use an external database provider.
2. In Vercel Project Settings → Environment Variables, add `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `PUBLIC_BASE_URL` for Production. Set `PUBLIC_BASE_URL` to the deployed site URL and use a verified mail sender. Keep all credentials private. Use a unique random `SECRET_KEY` and an admin password of at least 12 characters. Do not commit these values or paste them into source files.
3. Redeploy after setting the variables. The first app start creates the required database tables and the initial administrator account. Later changes to `ADMIN_PASSWORD` do not reset an existing account; use the database/account administration process to change it.
4. Check `/api/health`; a successful deployment responds with `{"status":"ok","database":"connected",...}`. Open `/login` to sign into the staff dashboard. Students submit feedback at `/feedback`.
5. Create each faculty account by signing in as admin and sending a `POST` request to `/api/admin/users` with a JSON body containing `email`, `name`, `faculty_key`, and a password of at least 12 characters. Students can preview or submit comments without a password. The teacher email entered on the form is only a label for those comments; it does not connect to a college inbox or retrieve existing feedback. Set a faculty account's `faculty_key` to the exact teacher email used on submissions that account should be scoped to. Staff reports remain behind staff sign-in. This initial version has no staff account management screen.

Vercel Hobby is free and deployments can stay online without a 30-day trial expiry. It has monthly usage caps; exceeding them can pause the project until usage resets. Hobby is limited to personal, non-commercial use under Vercel's current terms, so confirm eligibility before using it as an official college service. Vercel also runs the Python app as serverless functions rather than an always-on server. The database is separate from Vercel and remains available subject to the database provider's free-plan limits and terms. Keep backups of submitted feedback.

## Security and privacy notes

The feedback form does not request a student identity, but free text can contain identifying details. Do not solicit names or sensitive information. The deployment provides password-based staff roles and faculty-level filtering, but it is still a prototype: it has no login rate limiting, staff account management UI, audit log, moderation workflow, or institutional privacy/security review. Do not use it for confidential or high-stakes decisions without that review.



## Teacher sign-in

The public feedback page does not require a password. Teachers use the separate `/teacher-login` page and receive a one-time link by email. Only faculty accounts already provisioned by an administrator can sign in. The link expires after 10 minutes, can be used once, and repeated requests are limited to one per minute per account. An email address alone never grants access to stored feedback.

## Analysis limits

Live analysis uses a small, transparent English phrase lexicon with sentence/clause splitting. It can misread negation, informal wording, sarcasm, mixed clauses, or unseen vocabulary. Confidence is a heuristic, not a calibrated probability. The insight page aggregates submitted feedback; it does not rank teachers or recommend disciplinary action. Included legacy ML models and scripts are not used by the live analysis path.

## Stack

Python, Flask, SQLAlchemy, PostgreSQL (hosted) or SQLite (local), HTML, CSS, JavaScript, and Chart.js.
