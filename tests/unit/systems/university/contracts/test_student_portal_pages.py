from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import Flask

from education_system.systems.university.interfaces.api.routes.web_routes import (
    web_bp,
)

STATIC = (
    Path(__file__).resolve().parents[5]
    / "education_system/platform/delivery/api/university/static"
)

PAGES = ("timetable", "submissions", "fees", "support", "graduation")


class AccessiblePageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = None
        self.ids = set()
        self.labels = set()
        self.controls = []
        self.landmarks = set()
        self.skip_link = False
        self.current_page = False
        self.title = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        if tag == "title":
            self.title = True
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "label" and values.get("for"):
            self.labels.add(values["for"])
        if tag in {"input", "select", "textarea", "button"}:
            self.controls.append((tag, values))
        if tag in {"header", "nav", "main"}:
            self.landmarks.add(tag)
        if tag == "a" and values.get("href") == "#main":
            self.skip_link = True
        if values.get("aria-current") == "page":
            self.current_page = True


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(web_bp)
    return app.test_client()


@pytest.mark.parametrize("page", PAGES)
def test_student_task_page_is_served_and_accessible(client, page):
    response = client.get(f"/portal/student/{page}")

    assert response.status_code == 200
    assert response.content_type == "text/html; charset=utf-8"
    parser = AccessiblePageParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.lang == "en"
    assert parser.title
    assert parser.landmarks == {"header", "nav", "main"}
    assert parser.skip_link
    assert parser.current_page
    assert all(
        tag == "button"
        or attrs.get("aria-label")
        or attrs.get("id") in parser.labels
        for tag, attrs in parser.controls
    )


def test_unknown_student_page_is_not_exposed(client):
    assert client.get("/portal/student/private-notes").status_code == 404


def test_shared_wcag_22_rules_cover_focus_errors_contrast_and_preferences():
    css = (STATIC / "css/journey.css").read_text(encoding="utf-8")

    assert ":focus-visible" in css
    assert "--focus: #ffbf47" in css
    assert '[aria-invalid="true"]' in css
    assert "min-height: 2.75rem" in css
    assert "prefers-reduced-motion" in css
    assert "forced-colors: active" in css


def test_form_errors_are_announced_and_focus_the_invalid_control():
    script = (STATIC / "js/student_pages.js").read_text(encoding="utf-8")

    assert 'setAttribute("aria-invalid", "true")' in script
    assert "invalid.focus()" in script
    assert "message.focus()" in script
