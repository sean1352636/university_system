from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

STATIC = (
    Path(__file__).resolve().parents[4]
    / "education_system/platform/delivery/api/university/static"
)


class JourneyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.labels_for: set[str] = set()
        self.controls: list[dict[str, str | None]] = []
        self.landmarks: set[str] = set()
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "label" and values.get("for"):
            self.labels_for.add(values["for"])
        if tag in {"input", "select", "textarea", "button"}:
            self.controls.append({"tag": tag, **values})
        if tag in {"header", "nav", "main"}:
            self.landmarks.add(tag)


def test_journey_has_accessible_structure_and_names() -> None:
    parser = JourneyParser()
    parser.feed((STATIC / "journey.html").read_text(encoding="utf-8"))

    assert parser.lang == "en"
    assert parser.landmarks == {"header", "nav", "main"}
    assert "main" in parser.ids
    assert all(
        control["tag"] == "button"
        or control.get("aria-label")
        or control.get("name")
        or control.get("id") in parser.labels_for
        for control in parser.controls
    )


def test_mobile_focus_contrast_and_reduced_motion_rules_exist() -> None:
    css = (STATIC / "css/journey.css").read_text(encoding="utf-8")
    assert ":focus" in css
    assert "@media (max-width:" in css
    assert "prefers-reduced-motion" in css
    assert "--focus: #ffbf47" in css


def test_journey_uses_no_inline_script_or_event_handlers() -> None:
    html = (STATIC / "journey.html").read_text(encoding="utf-8").lower()
    assert "<script>" not in html
    assert " onclick=" not in html
    assert " onsubmit=" not in html
