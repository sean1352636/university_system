"""JSON e-mail templates (domain.operations.communications.messages.email_templates).

``send_from_template`` only writes a Sent row to the messages log; ``smtplib``
is made to raise so any real send attempt would fail the test.
"""

from __future__ import annotations

import json
import smtplib

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.communications.messages import (
    email_templates as ET,
)
from education_system.systems.primary.domain.operations.communications.messages import (
    messages as M,
)


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("tried to open a real SMTP connection")
    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)


def _templates(monkeypatch, tmp_path, **files):
    """Point the template folder at *tmp_path* holding *files* (name → dict|str)."""
    for name, content in files.items():
        text = content if isinstance(content, str) else json.dumps(content)
        (tmp_path / f"{name}.json").write_text(text, encoding="utf-8")
    monkeypatch.setattr(ET.paths, "PRIMARY_EMAIL_TEMPLATES_DIR", tmp_path)


WELCOME = {
    "subject": "  Welcome to {{system_name}}, {{first_name}}  ",
    "body": "Hi {{ first_name }}, your class is {{class_name}}.",
    "from_name": "{{school}} Admissions",
    "from_address": "admissions@primary.sch.uk",
}


# ── render ──────────────────────────────────────────────────────────

def test_render_substitutes_known_tokens():
    assert ET.render("Hi {{name}} ({{ age }})", {"name": "Ada", "age": 7}) == "Hi Ada (7)"


def test_render_leaves_unknown_and_none_tokens_in_place():
    assert ET.render("{{a}} {{b}} {{c}}", {"a": "x", "b": None}) == "x {{b}} {{c}}"


def test_render_ignores_text_without_tokens():
    assert ET.render("{single} {{9bad}}", {"single": 1, "9bad": 2}) == "{single} {{9bad}}"


# ── load ────────────────────────────────────────────────────────────

def test_load_template_parses_json(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path, welcome=WELCOME)
    assert ET.load_template("welcome") == WELCOME


def test_missing_template_raises(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path)
    with pytest.raises(ET.TemplateError, match="Email template not found"):
        ET.load_template("nope")


def test_invalid_json_raises(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path, broken="{not json")
    with pytest.raises(ET.TemplateError, match="broken is not valid JSON"):
        ET.load_template("broken")


# ── send_from_template ──────────────────────────────────────────────

def test_send_logs_a_sent_message(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path, welcome=WELCOME)
    p = P.create_pupil({"first_name": "Ada", "last_name": "L", "year_group": "R",
                        "date_of_birth": "2021-01-01"})
    m = ET.send_from_template("welcome", {"system_name": "Oak Primary", "first_name": "Ada",
                                          "class_name": "Robins", "school": "Oak"},
                              to_name="Mrs L", to_address="Parent@Home.Test",
                              student_id=p.pupil_id)
    assert m.status == "Sent" and m.direction == "Outgoing"
    assert m.subject == "Welcome to Oak Primary, Ada"
    assert m.body == "Hi Ada, your class is Robins."
    assert m.from_name == "Oak Admissions"
    assert m.from_address == "admissions@primary.sch.uk"
    assert m.to_name == "Mrs L" and m.to_address == "parent@home.test"
    assert m.student_id == p.pupil_id
    assert m.channel == "Email" and m.category == "General" and m.priority == "Normal"
    assert m.tags == "template:welcome"
    assert m.sent_at is not None
    assert M.list_messages(sent_only=True) == [m]


def test_template_can_set_channel_category_priority(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path, club={"subject": "Club", "body": "Chess on Tue",
                                            "channel": "Portal", "category": "Clubs",
                                            "priority": "High"})
    m = ET.send_from_template("club", {})
    assert (m.channel, m.category, m.priority) == ("Portal", "Clubs", "High")
    assert m.from_name is None and m.from_address is None


def test_missing_context_leaves_tokens_visible(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path, welcome=WELCOME)
    m = ET.send_from_template("welcome", {"first_name": "Ada"})
    assert m.subject == "Welcome to {{system_name}}, Ada"
    assert "{{class_name}}" in m.body


def test_invalid_rendered_payload_is_refused_and_not_logged(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path, welcome=WELCOME,
               bad_cat={"subject": "s", "body": "b", "category": "Careers"},
               empty={"subject": "", "body": "b"})
    with pytest.raises(M.ValidationError, match="To address is not a valid email"):
        ET.send_from_template("welcome", {}, to_address="not an email")
    with pytest.raises(M.ValidationError, match="Category must be one of"):
        ET.send_from_template("bad_cat", {})
    with pytest.raises(M.ValidationError, match="Subject is required"):
        ET.send_from_template("empty", {})
    with pytest.raises(M.ValidationError, match="No student with id 0000000"):
        ET.send_from_template("welcome", {}, student_id="0000000")
    assert M.list_messages() == []


def test_missing_template_sends_nothing(monkeypatch, tmp_path):
    _templates(monkeypatch, tmp_path)
    with pytest.raises(ET.TemplateError):
        ET.send_from_template("welcome", {})
    assert M.list_messages() == []
