import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE_SCRIPTS = {
    "login.js": "login.html",
    "feedback.js": "feedback.html",
    "dashboard.js": "dashboard.html",
    "analysis.js": "analysis.html",
    "prediction.js": "predictions.html",
}


class FrontendContractTests(unittest.TestCase):
    def test_script_dom_ids_exist_on_their_page(self):
        for script_name, page_name in PAGE_SCRIPTS.items():
            with self.subTest(script=script_name):
                script = (ROOT / "frontend" / "js" / script_name).read_text(encoding="utf-8")
                page = (ROOT / "frontend" / page_name).read_text(encoding="utf-8")
                referenced = set(re.findall(r"getElementById\([\"']([^\"']+)", script))
                available = set(re.findall(r"\bid=[\"']([^\"']+)", page))
                self.assertFalse(referenced - available, f"Missing page IDs: {sorted(referenced - available)}")

    def test_frontend_has_no_inline_event_handlers(self):
        for page in (ROOT / "frontend").glob("*.html"):
            with self.subTest(page=page.name):
                self.assertIsNone(re.search(r"\son[a-z]+\s*=", page.read_text(encoding="utf-8"), re.IGNORECASE))

    def test_expected_api_routes_are_registered(self):
        app_source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")
        routes = set(re.findall(r"@app\.(?:get|post)\([\"']([^\"']+)", app_source))
        routes.update(re.findall(r"@app\.route\([\"']([^\"']+)", app_source))
        for endpoint in (
            "/api/session", "/api/login", "/api/logout", "/api/feedback", "/api/analyze",
            "/api/analytics", "/api/recommendations", "/api/admin/faculty", "/api/report.pdf", "/api/health",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, routes)

    def test_staff_and_admin_routes_have_access_checks(self):
        source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")
        for route, decorator in (
            ("/api/analytics", "@staff_required"),
            ("/api/recommendations", "@staff_required"),
            ("/api/report.pdf", "@staff_required"),
            ("/api/admin/faculty", "@admin_required"),
        ):
            with self.subTest(route=route):
                start = source.index(f'@app.get("{route}")') if route != "/api/admin/faculty" else source.index(f'@app.route("{route}"')
                section = source[start:source.index("\ndef ", start)]
                self.assertIn(decorator, section)
        feedback_start = source.index('@app.route("/api/feedback"')
        feedback_end = source.index("\ndef analyze_feedback", feedback_start)
        feedback_section = source[feedback_start:feedback_end]
        self.assertIn('session.get("staff_email")', feedback_section)

    def test_mutating_routes_use_the_csrf_guard(self):
        source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")
        guard = source[source.index("def protect_state_changes"):source.index("\ndef staff_required")]
        self.assertIn('request.method in {"POST", "PUT", "PATCH", "DELETE"}', guard)
        self.assertIn("hmac.compare_digest", guard)


if __name__ == "__main__":
    unittest.main()
