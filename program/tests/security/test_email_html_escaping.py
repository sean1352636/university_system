"""Email templates must HTML-escape context in the HTML body (task 18)."""

from __future__ import annotations

import pytest

from education_system.platform.integrations.email import email_templates as ET

pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def _probe_template():
    if hasattr(ET, "register_template"):
        ET.register_template(
            "xss_probe",
            subject="Hi $user_name",
            body="Hello $user_name visit $login_url",
            html_body='<p>Hello $user_name</p><a href="$login_url">go</a>',
        )
    yield


def test_html_body_escapes_markup():
    subj, body, html = ET.render_template(
        "xss_probe",
        user_name="<img src=x onerror=alert(1)>",
        login_url="https://ex.com/a?b=1&c=2",
    )
    # HTML body must neutralise injected markup.
    assert "<img" not in html
    assert "&lt;img" in html
    # URL is escaped for HTML context (& -> &amp;) but remains a working link.
    assert "https://ex.com/a?b=1&amp;c=2" in html


def test_plain_text_is_not_escaped():
    subj, body, html = ET.render_template("xss_probe", user_name="<b>", login_url="x")
    # text/plain parts should carry the raw value, not HTML entities.
    assert "<b>" in subj
    assert "<b>" in body


def test_html_suffixed_keys_are_trusted():
    if not hasattr(ET, "register_template"):
        pytest.skip("register_template unavailable")
    ET.register_template(
        "html_suffix_probe",
        subject="s",
        body="b",
        html_body="$snippet_html",
    )
    _, _, html = ET.render_template("html_suffix_probe", snippet_html="<b>bold</b>")
    assert "<b>bold</b>" in html  # explicitly-safe HTML passes through
