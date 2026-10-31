# AI Student Feedback Analytics

## Architecture found in the local workspace

The workspace originally contained a Flask application in `backend/app.py`, a static HTML/CSS/JavaScript frontend in `frontend/`, Chart.js dashboard pages, CSV datasets in `backend/data/`, and separate ML scripts and serialized artifacts in `ml/` and `backend/models/`. The live app read CSVs and exposed summaries through Flask routes; it did not have a database, stored student submissions, staff authentication, role checks, or a report generator. The sibling `cloud-cost-optimization/` folder is a separate project and is not part of this app.

The linked GitHub repository describes a newer version than the local files. This guide documents the local workspace after these changes; it does not claim that anything has been pushed or deployed.

## Existing project features retained

- Flask serves the home, feedback, dashboard, analytics, and predictions pages.
- The historical student feedback CSV and its category/sentiment labels remain available as a demo dataset.
- The original ML scripts, model artifacts, and Chart.js frontend remain in the workspace.
- The browser can still analyze text and the app still has interactive charts; staff pages now require a staff session.

The historical source is now **only** `backend/data/feedback.csv` (731 data rows at inspection). The processed CSVs contain derived copies of that source; they are not added as separate rows. The processed `final_feedback_analysis.csv` had 645 data rows. Historical rows have no academic metadata or reliable timestamps, so they are excluded from metadata and monthly comparisons. Emotion labels are shown only when present in the selected source.

## Improvements implemented

- Added phrase-level English sentiment with negation handling, mixed-opinion flags, heuristic scores, common spelling normalization, ten teaching aspects, and evidence excerpts from the original comment.
- Added limited Hindi and Telugu phrase lexicons. Unsupported or unrecognized language input is marked as unsupported rather than presented as a reliable neutral opinion. The live path is explainable rules, not a pretrained model and not a model trained on this dataset.
- Replaced the old teacher/email analysis form with an anonymous student submission form and optional department, academic year, semester, subject, section, and faculty fields.
- Added in-browser CSV, TSV, and TXT import. For CSV/TSV, the student selects the comment column; the source file and other columns are not uploaded. Limits are 100 comments per batch, 20,000 characters per comment, and 900 KB per selected file.
- Added persistent live submissions and staff accounts using SQLAlchemy. Batch UUIDs prevent an accidental retry from duplicating a batch.
- Added password-hashed staff sign-in, five failed attempts per account per 15-minute window, CSRF checks on state-changing requests, secure cookie settings, security headers, and administrator-only faculty account provisioning.
- Restricted raw feedback and staff analytics to signed-in staff. Faculty queries are limited to records whose faculty field matches their assigned faculty key. The historical demo dataset is not exposed to faculty accounts.
- Added explicit historical, live, and combined source selection, metadata filters, date filters, sentiment and aspect summaries, department/semester/subject comparisons, monthly live trends, evidence-based insights, and PDF reports.
- Added Vercel WSGI entry configuration and a production runtime dependency list. The production app requires a persistent PostgreSQL `DATABASE_URL`.

## Database and migration notes

Local submissions are stored in `backend/data/feedback_submissions.sqlite3`. The initial schema contains:

- `feedback_submissions`: anonymous comment text, academic metadata, analysis outputs, batch identifier, and UTC creation time.
- `staff_accounts`: normalized email, password hash, role, faculty key, and active status.
- `login_failures`: keyed hashes and timestamps used for temporary login throttling.

Historical CSV rows are not copied into the database. This keeps the demo source and live submissions separate and avoids double-counting.

Unsupported live-language comments remain in the total submission count, but are excluded from sentiment percentages and labeled “Not analyzed” in the staff comment list. Recognized Hindi/Telugu phrase matches are counted; aspect analysis is currently English-only.

The app checks same-named existing tables for required columns before startup, then uses `db.create_all()` to create missing tables. If an existing table is older, startup stops with the missing-column list before adding tables or changing rows. SQLAlchemy `create_all()` does **not** alter an existing table when a later release changes its columns. Back up SQLite/PostgreSQL before upgrades and apply an explicit schema migration for future column or constraint changes. Do not delete the database to upgrade it.

## Environment variables

Required for an initial staff login:

- `ADMIN_EMAIL`: administrator login email.
- `ADMIN_PASSWORD`: initial administrator password, at least 12 characters. It is hashed before storage. Changing this variable later does not reset an existing account.
- `SECRET_KEY`: a long, unique random Flask signing key.

Optional locally:

- `DATABASE_URL`: omit to use local SQLite; set a PostgreSQL URL to use PostgreSQL. `postgres://` is normalized to the psycopg driver.
- `COOKIE_SECURE=1`: use only when local HTTPS is enabled. Vercel sessions automatically use secure cookies.
- `PORT`: local Flask port; defaults to 5000.
- `FLASK_DEBUG=1`: enables Flask debug mode for local development only.

On Vercel, `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` are required. Use a persistent PostgreSQL provider; do not rely on SQLite in a serverless function. Store values in the hosting provider's environment-variable settings, not in source files or `.env` files.

## Run locally on Windows

Install Python 3.12 or newer, then from PowerShell at the project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
$env:SECRET_KEY = "replace-with-a-long-random-secret"
$env:ADMIN_EMAIL = "admin@your-college.edu"
$env:ADMIN_PASSWORD = "replace-with-a-unique-password-of-12-or-more-characters"
python backend\app.py
```

Open `http://127.0.0.1:5000`. The database tables and initial admin account are created on first startup. `START_PROJECT.bat` remains available when the environment variables are already set.

## Deploy to Vercel

The repository root now exposes `app.py`, `requirements.txt`, `.python-version`, and `vercel.json`. Set the four required production variables above, with `DATABASE_URL` pointing to persistent PostgreSQL, then deploy through the Vercel project workflow. Confirm `/api/health`, `/login`, student submission, and authorized staff report download after deployment. Do not deploy with SQLite or with a default/temporary secret.

The function excludes the unrelated cloud-cost project, ML training directory, serialized models, and derived CSV copies from its bundle. It keeps the frontend and canonical historical CSV. The deployed project has not been built or deployed in this workspace.

## Verification performed

- Seventeen `unittest` checks passed: eight NLP examples, four Flask runtime integration checks, and five frontend/API security contract checks. Runtime coverage includes database health, anonymous submission and idempotent retry, staff sign-in, admin faculty provisioning, faculty scoping, analytics access, input validation, and PDF generation.
- The browser-side CSV/TSV parser passed checks for quoted commas, escaped quotes, TSV columns, and malformed quote rejection.
- JavaScript syntax checks passed for the shared API helper, login, feedback import/submission, dashboard, analytics, and predictions scripts.
- Python AST parsing passed for the Flask app, SQLAlchemy models, and analysis engine. `vercel.json` parsed successfully.
- The dependencies in `backend\requirements.txt` were installed in the project `.venv` and the test suite was rerun there. A rendered browser/mobile check remains unverified: Windows browser automation stopped because it could not confidently identify the active browser URL. The integration tests above ran against a temporary SQLite database and removed it afterward.

## Current limitations

- Hindi and Telugu handling is a small phrase lexicon, not general multilingual NLP. Aspect tagging currently supports English only. Unrecognized phrases are explicitly flagged.
- Sentiment scores are directional heuristics, not calibrated probabilities. No model evaluation metrics are claimed.
- The workspace's existing TF-IDF/Logistic Regression artifacts and training scripts remain, but are not loaded by the live analyzer. Their current provenance and evaluation were not independently verified, so they were not used to produce new live predictions.
- Historical CSV rows lack dates, academic metadata, faculty scope, and reliable emotion labels; the app does not invent these values.
- No SMTP or one-time email-link flow existed in the local workspace. The new local faculty workflow uses administrator-provisioned passwords.
- Anonymity means no name or student email is requested or stored by this form; students can still identify themselves inside free text.
- The local workspace and the linked GitHub branch differ. No external changes were made, and no production deployment or GitHub push was performed.
