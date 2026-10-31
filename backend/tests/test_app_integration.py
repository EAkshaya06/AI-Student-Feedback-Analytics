"""Runtime smoke tests for Flask routes, persistence, access control, and reports."""

from __future__ import annotations

import importlib
import os
import unittest
import uuid
from pathlib import Path


_project_root = Path(__file__).resolve().parents[2]
_database_path = _project_root / "backend" / "data" / f"runtime-tests-{uuid.uuid4().hex}.sqlite3"
os.environ.pop("VERCEL", None)
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"
os.environ["SECRET_KEY"] = "runtime-test-secret-key-that-is-never-used-outside-tests"
os.environ["ADMIN_EMAIL"] = "runtime-admin@example.edu"
os.environ["ADMIN_PASSWORD"] = "Runtime-Only-Admin-Passphrase-123!"
os.environ["COOKIE_SECURE"] = "0"

app_module = importlib.import_module("backend.app")
app = app_module.app
db = app_module.db
app.config.update(TESTING=True)


def csrf_token(client) -> str:
    response = client.get("/api/session")
    if response.status_code != 200:
        raise AssertionError(f"Unable to create session: {response.status_code}")
    return response.get_json()["csrf_token"]


def login(client, email: str, password: str):
    return client.post(
        "/api/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_token(client)},
    )


class FlaskRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def tearDown(self):
        with app.app_context():
            db.session.remove()

    def submit(self, comment: str, **metadata):
        return self.client.post(
            "/api/feedback",
            json={"batch_id": str(uuid.uuid4()), "comments": [comment], "metadata": metadata},
            headers={"X-CSRF-Token": csrf_token(self.client)},
        )

    def test_health_pages_and_staff_routes(self):
        self.assertEqual(self.client.get("/api/health").get_json()["database"], "connected")
        feedback_page = self.client.get("/feedback")
        self.assertEqual(feedback_page.status_code, 200)
        feedback_page.close()
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.assertEqual(self.client.get("/api/analytics").status_code, 401)
        self.assertEqual(self.client.get("/api/feedback").status_code, 401)

    def test_submission_is_saved_once_and_requires_staff_for_raw_reads(self):
        batch_id = str(uuid.uuid4())
        payload = {
            "batch_id": batch_id,
            "comments": ["The instructor explains concepts clearly with practical examples."],
            "metadata": {"department": "Computer Science", "semester": "2"},
        }
        token = csrf_token(self.client)
        blocked = self.client.post("/api/feedback", json=payload)
        self.assertEqual(blocked.status_code, 400)

        created = self.client.post("/api/feedback", json=payload, headers={"X-CSRF-Token": token})
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        self.assertTrue(created.get_json()["stored"])
        self.assertEqual(created.get_json()["count"], 1)

        duplicate = self.client.post(
            "/api/feedback",
            json={**payload, "comments": ["different text must not be returned"]},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["duplicate_batch"])
        self.assertEqual(duplicate.get_json()["results"], [])
        self.assertEqual(self.client.get("/api/feedback?source=live").status_code, 401)

        authenticated = login(self.client, "runtime-admin@example.edu", "Runtime-Only-Admin-Passphrase-123!")
        self.assertEqual(authenticated.status_code, 200, authenticated.get_data(as_text=True))
        self.assertEqual(authenticated.get_json()["role"], "admin")
        records = self.client.get("/api/feedback?source=live&limit=100").get_json()["data"]
        matches = [row for row in records if row["batch_id"] == batch_id]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["department"], "Computer Science")
        self.assertIn("batch_id", matches[0])
        analytics = self.client.get("/api/analytics?source=live&department=Computer%20Science")
        self.assertEqual(analytics.status_code, 200, analytics.get_data(as_text=True))
        self.assertGreaterEqual(analytics.get_json()["total"], 1)

    def test_faculty_scope_and_pdf_report(self):
        admin_login = login(self.client, "runtime-admin@example.edu", "Runtime-Only-Admin-Passphrase-123!")
        self.assertEqual(admin_login.status_code, 200)
        faculty_key = f"Faculty-{uuid.uuid4().hex[:10]}"
        faculty_email = f"faculty-{uuid.uuid4().hex[:10]}@example.edu"
        provision = self.client.post(
            "/api/admin/faculty",
            json={"email": faculty_email, "password": "Faculty-Only-Passphrase-123!", "faculty_key": faculty_key},
            headers={"X-CSRF-Token": admin_login.get_json()["csrf_token"]},
        )
        self.assertEqual(provision.status_code, 201, provision.get_data(as_text=True))

        own = self.submit("The class uses helpful examples.", faculty=faculty_key)
        self.assertEqual(own.status_code, 201, own.get_data(as_text=True))
        other = self.submit("The pace is difficult to follow.", faculty="Someone Else")
        self.assertEqual(other.status_code, 201, other.get_data(as_text=True))

        faculty_login = login(self.client, faculty_email, "Faculty-Only-Passphrase-123!")
        self.assertEqual(faculty_login.status_code, 200, faculty_login.get_data(as_text=True))
        results = self.client.get("/api/feedback?source=all&limit=1000").get_json()["data"]
        self.assertTrue(results)
        self.assertTrue(all(row["faculty"].casefold() == faculty_key.casefold() for row in results))
        self.assertTrue(all(row["source"] == "live" for row in results))
        analytics = self.client.get("/api/analytics?source=all")
        self.assertEqual(analytics.status_code, 200, analytics.get_data(as_text=True))
        self.assertEqual(analytics.get_json()["filter_options"]["faculty"], [faculty_key])

        report = self.client.get("/api/report.pdf?source=live")
        response_detail = report.get_data()[:500].decode("utf-8", errors="replace")
        self.assertEqual(report.status_code, 200, response_detail)
        self.assertTrue(report.data.startswith(b"%PDF"))
        self.assertIn("application/pdf", report.content_type)

    def test_submission_validation_and_analyzer_endpoint(self):
        token = csrf_token(self.client)
        too_many = self.client.post(
            "/api/feedback",
            json={"comments": ["ok"] * 101},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(too_many.status_code, 400)

        analyzed = self.client.post(
            "/api/analyze",
            json={"comments": ["The teacher is very good.", "शिक्षक बहुत अच्छी तरह समझाते हैं।"]},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(analyzed.status_code, 200, analyzed.get_data(as_text=True))
        self.assertEqual(analyzed.get_json()["total"], 2)
        self.assertEqual(analyzed.get_json()["sentiment_total"], 2)


def tearDownModule():
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    _database_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
