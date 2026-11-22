"""The branded HTML version of outgoing e-mail: what the text becomes, that it
is escaped, and that the plain-text part is untouched."""

from __future__ import annotations

import pytest

from education_system.systems.university.infrastructure.email import html_layout, smtp

BRAND = {"name": "Teesside University", "tagline": "Inspiring success",
         "primary": "#112233", "secondary": "#445566", "accent": "#778899",
         "footer": "University Management System"}


@pytest.fixture(autouse=True)
def fixed_brand(monkeypatch):
    """No database: the brand and the on/off setting are given."""
    html_layout.clear_cache()
    monkeypatch.setattr(html_layout, "branding", lambda: html_layout._clean(BRAND))
    monkeypatch.setattr(html_layout, "enabled", lambda: True)
    monkeypatch.setattr(html_layout, "logo", lambda: None)
    yield
    html_layout.clear_cache()


def _parts(message):
    return {p.get_content_type(): p.get_payload(decode=True).decode(p.get_content_charset())
            for p in message.walk() if not p.is_multipart()}


def _build(body, subject="Hello", **kwargs):
    return smtp.build_message(subject=subject, body=body, from_header="a@x.test",
                              to_header="b@x.test", **kwargs)


# ── the message ─────────────────────────────────────────────────────────


def test_plain_text_goes_out_with_a_branded_html_version():
    message = _build("Dear Asha,\n\nYour essay is due.\n\nBest regards,\nExam Office")
    assert message.get_content_subtype() == "alternative"
    parts = _parts(message)
    assert parts["text/plain"] == "Dear Asha,\n\nYour essay is due.\n\nBest regards,\nExam Office"
    page = parts["text/html"]
    assert "Teesside University" in page and "#112233" in page and "Inspiring success" in page


def test_turned_off_sends_plain_text_only(monkeypatch):
    monkeypatch.setattr(html_layout, "enabled", lambda: False)
    message = _build("Just text")
    assert list(_parts(message)) == ["text/plain"]


def test_styled_false_overrides_the_setting():
    assert list(_parts(_build("Just text", styled=False))) == ["text/plain"]


def test_a_broken_layout_never_stops_the_email(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("layout bug")
    monkeypatch.setattr(html_layout, "render", boom)
    assert list(_parts(_build("Still delivered"))) == ["text/plain"]


def test_html_fragment_is_framed_and_full_documents_are_left_alone():
    framed = _parts(_build("<p>Hello <b>there</b></p>"))["text/html"]
    assert "<p>Hello <b>there</b></p>" in framed and "Teesside University" in framed
    document = "<!DOCTYPE html><html><body><p>Mine</p></body></html>"
    assert _parts(_build(document))["text/html"] == document


def test_explicit_html_body_is_used_as_given():
    parts = _parts(_build("text", html_body="<p>given</p>"))
    assert parts["text/html"] == "<p>given</p>"


# ── what the text becomes ───────────────────────────────────────────────


def test_markup_in_text_is_escaped_everywhere():
    page = html_layout.render('<script>alert(1)</script>',
                              'Name: <img src=x onerror=alert(1)>\nRef: "a"&b\n\n<b>hi</b>',
                              BRAND)
    assert "<script>" not in page and "<img" not in page and "<b>hi</b>" not in page
    assert "&lt;script&gt;" in page and "&lt;img" in page


def test_underlined_lines_become_headings():
    body = html_layout.text_to_html("Results\n=======\n\nNext steps\n----------\nRead on.", BRAND)
    assert "<h2" in body and ">Results</h2>" in body
    assert "<h3" in body and ">Next steps</h3>" in body and "Read on." in body


def test_bullets_and_numbers_become_lists():
    body = html_layout.text_to_html("• one\n• two\n\n1. first\n2. second", BRAND)
    assert body.count("<li") == 4 and "<ul" in body and "<ol" in body


def test_lead_in_line_then_bullets():
    body = html_layout.text_to_html("Before you submit:\n- check\n- upload", BRAND)
    assert "Before you submit" in body and body.count("<li") == 2


def test_label_value_lines_become_a_details_table():
    body = html_layout.text_to_html("Assignment: Essay\nDue: 2026-11-04 23:59", BRAND)
    assert "<table" in body and ">Assignment</td>" in body and ">2026-11-04 23:59</td>" in body


def test_rules_around_details_divide_them_from_the_text():
    body = html_layout.text_to_html(
        "Schedule Details:\n━━━━━━━━━━\nCourse: ACC\nTime: 09:00\n━━━━━━━━━━\nAsk us.", BRAND)
    assert ">Schedule Details</h2>" in body and "━" not in body
    assert ">Course</td>" in body and body.index("<table") < body.index("Ask us.")


def test_a_single_label_line_stays_a_sentence():
    body = html_layout.text_to_html("Note: the library closes early.", BRAND)
    assert "<table" not in body and "<p" in body


def test_aligned_columns_become_a_table():
    report = "Code   Title          Mark\nCS1    Computing      72\nCS2    Maths          65"
    body = html_layout.text_to_html(report, BRAND)
    assert "<pre" not in body and ">Computing</td>" in body and ">Mark</th>" in body


def test_links_and_addresses_are_clickable():
    body = html_layout.text_to_html("See https://example.ac.uk/a?b=1&c=2. Or mail x@uni.test",
                                    BRAND)
    assert 'href="https://example.ac.uk/a?b=1&amp;c=2"' in body
    assert 'href="mailto:x@uni.test"' in body


def test_closing_becomes_a_signature():
    body = html_layout.text_to_html("Hello.\n\nKind regards,\nAdmissions Office", BRAND)
    assert "border-top" in body.split("Hello.")[1] and "Admissions Office" in body


def test_bad_colours_fall_back_to_the_defaults():
    brand = html_layout._clean({**BRAND, "primary": "red;background:url(x)"})
    assert brand["primary"] == html_layout.DEFAULT_BRAND["primary"]


def test_empty_brand_fields_keep_the_defaults():
    brand = html_layout._clean({"name": "", "primary": ""})
    assert brand["name"] == html_layout.DEFAULT_BRAND["name"]
    assert brand["primary"] == html_layout.DEFAULT_BRAND["primary"]


def test_column_report_becomes_a_table_even_when_a_name_overruns():
    report = ("ALL DEPARTMENTS\nDepartment           Courses    Students\n"
              "School of Computing  5          17\nSchool of Engineering 3          0")
    body = html_layout.text_to_html(report, BRAND)
    assert "<pre" not in body and body.count("<tr>") == 3
    assert ">School of Engineering</td>" in body and ">ALL DEPARTMENTS</h3>" in body


def test_columns_that_cannot_be_read_stay_fixed_width():
    report = "Code   Title   Mark\nCS1    Computing  72   extra   x\nCS2    Maths"
    assert "<pre" in html_layout.text_to_html(report, BRAND)


def test_header_underlined_with_a_rule_heads_the_table():
    report = ("COURSES BY DEPARTMENT:\nDepartment           Courses    Students\n"
              "----------------------------------------\n"
              "School of Computing  4          17\nBusiness School      4          3")
    body = html_layout.text_to_html(report, BRAND)
    assert ">Department</th>" in body and ">School of Computing</td>" in body
    assert ">COURSES BY DEPARTMENT</h3>" in body and "----" not in body


def test_single_spaced_header_and_a_closing_note():
    report = ("Code Name Credits\nACC-1      Financial Accounting      20\n"
              "ACC-2      Taxation      20\n… (344 more lines in the attachment)")
    body = html_layout.text_to_html(report, BRAND)
    assert ">Code</th>" in body and ">Taxation</td>" in body
    assert 'colspan="3"' in body and "344 more lines" in body


def test_single_spaced_header_over_a_rule():
    report = ("Code Name Credits\n------------------\nACC-1      Financial Accounting      20\n"
              "ACC-2      Taxation      20")
    body = html_layout.text_to_html(report, BRAND)
    assert ">Code</th>" in body and ">Credits</th>" in body and "<h3" not in body


def test_an_underlined_title_is_still_a_heading():
    body = html_layout.text_to_html("Results\n-------\nYou passed every module.", BRAND)
    assert ">Results</h3>" in body and "<table" not in body


# ── logo ────────────────────────────────────────────────────────────────


@pytest.fixture
def crown(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    path = tmp_path / "logo.png"
    Image.new("RGBA", (512, 256), (220, 180, 60, 255)).save(path)
    return path


def test_logo_is_scaled_for_the_header(crown):
    picture = html_layout.load_logo(crown)
    assert picture["subtype"] == "png" and (picture["width"], picture["height"]) == (96, 48)
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(picture["data"])).size == (192, 96)


def test_logo_travels_with_the_page(monkeypatch, crown):
    monkeypatch.setattr(html_layout, "logo", lambda: html_layout.load_logo(crown))
    message = _build("Dear Asha,\n\nHello.")
    assert message.get_content_subtype() == "alternative"
    plain, related = message.get_payload()
    assert plain.get_content_type() == "text/plain"
    assert related.get_content_type() == "multipart/related"
    page, image = related.get_payload()
    assert 'src="cid:institution-logo"' in page.get_payload(decode=True).decode()
    assert image["Content-ID"] == "<institution-logo>" and image.get_content_type() == "image/png"


def test_no_logo_keeps_the_simple_message():
    plain, page = _build("Hello").get_payload()
    assert page.get_content_type() == "text/html" and "cid:" not in page.get_payload(decode=True).decode()


def test_logo_with_an_attachment_stays_inside_the_body(monkeypatch, crown, tmp_path):
    monkeypatch.setattr(html_layout, "logo", lambda: html_layout.load_logo(crown))
    attached = tmp_path / "report.txt"
    attached.write_text("data")
    sent = {}

    class Server:
        def __init__(self, *_a, **_k): pass
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def starttls(self, *_a, **_k): pass
        def ehlo(self, *_a, **_k): pass
        def login(self, *_a, **_k): pass
        def send_message(self, msg, *_a, **_k): sent["msg"] = msg
        def sendmail(self, _f, _t, raw, *_a, **_k): sent["raw"] = raw

    monkeypatch.setattr(smtp.smtplib, "SMTP", Server)
    client = smtp.SMTPClient(smtp.SMTPConfig(smtp_server="s", smtp_port=25, sender_email="a@x.test",
                                             sender_name="Uni", use_tls=False,
                                             use_authentication=False))
    client.send_or_raise("b@x.test", "Report", "See attached.", attachments=str(attached))
    import email
    msg = sent.get("msg") or email.message_from_string(sent["raw"])
    assert msg.get_content_subtype() == "mixed"
    body, file_part = msg.get_payload()
    assert body.get_content_subtype() == "alternative"
    assert file_part.get_filename() == "report.txt"


def test_unreadable_logo_is_skipped(tmp_path):
    bad = tmp_path / "logo.png"
    bad.write_text("not an image")
    html_layout.clear_cache()
    import education_system.systems.university.infrastructure.email.html_layout as layout
    original = layout._logo_file
    layout._logo_file = lambda: bad
    try:
        assert layout._load_logo() is None
    finally:
        layout._logo_file = original


def test_logo_alt_text_is_the_institution_name():
    page = html_layout.render("S", "Hi", BRAND, image={"src": "cid:x", "width": 48, "height": 48})
    assert 'alt="Teesside University"' in page and 'src="cid:x"' in page
