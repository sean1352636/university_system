"""Browser-surface contract for the complete applicant-to-enrolment journey."""

from html.parser import HTMLParser
from pathlib import Path

from flask import Flask

from education_system.platform.delivery.api.university.routes.web_routes import (
    web_bp,
)

STATIC = (
    Path(__file__).resolve().parents[4]
    / "education_system/platform/delivery/api/university/static"
)


class JourneyBrowserParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = set()
        self.sections = set()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id"):
            self.forms.add(values["id"])
        if tag == "section" and values.get("id"):
            self.sections.add(values["id"])
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])


def test_browser_can_load_complete_applicant_to_enrolment_surface():
    app = Flask(__name__)
    app.register_blueprint(web_bp)

    response = app.test_client().get("/portal/journey")

    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    parser = JourneyBrowserParser()
    parser.feed(response.get_data(as_text=True))
    assert {
        "application-form",
        "load-application-form",
        "evidence-form",
        "registration-form",
        "module-form",
    } <= parser.forms
    assert {
        "application",
        "status",
        "evidence",
        "registration",
        "modules",
        "study",
        "finance",
        "support",
        "graduation",
    } <= parser.sections
    assert "/static/js/journey.js" in parser.scripts


def test_browser_script_connects_every_applicant_to_enrolment_step():
    script = (STATIC / "js/journey.js").read_text(encoding="utf-8")
    expected_calls = [
        "/api/admissions-crm/prospects",
        "/api/admissions/applications",
        "/choices",
        "/accept",
        "/conditions/",
        "/readiness",
        "/enrol",
        "/registrations",
        "/module-selections",
    ]

    assert all(fragment in script for fragment in expected_calls)
    assert 'sessionStorage.setItem("journey_student_id"' in script
    assert 'message("Student record and annual registration completed."' in script
