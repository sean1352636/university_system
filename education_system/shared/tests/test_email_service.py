"""Tests for EmailService (no SMTP server required)."""

import pytest

from education_system.shared.email.email_service import EmailService, EmailMessage


# ── EmailMessage dataclass ───────────────────────────────────────────

def test_email_message_defaults():
    msg = EmailMessage(to="user@example.com", subject="Hi", body="Hello")
    assert msg.to == "user@example.com"
    assert msg.cc is None
    assert msg.bcc is None
    assert msg.html_body is None
    assert msg.headers == {}


def test_email_message_all_recipients():
    msg = EmailMessage(
        to="a@b.com", subject="s", body="b",
        cc=["c@d.com"], bcc=["e@f.com", "g@h.com"],
    )
    recipients = msg.all_recipients()
    assert recipients == ["a@b.com", "c@d.com", "e@f.com", "g@h.com"]


# ── validate_email ───────────────────────────────────────────────────

@pytest.mark.parametrize("addr", [
    "user@example.com",
    "first.last@domain.co.uk",
    "a+tag@sub.domain.org",
    "digits123@test.io",
])
def test_validate_email_valid(addr):
    assert EmailService.validate_email(addr) is True


@pytest.mark.parametrize("addr", [
    "",
    "plaintext",
    "@no-local.com",
    "no-domain@",
    "spaces in@addr.com",
    "missing@tld.",
    "double@@at.com",
])
def test_validate_email_invalid(addr):
    assert EmailService.validate_email(addr) is False


# ── is_configured ────────────────────────────────────────────────────

def _empty_config():
    return {
        "smtp_server": "", "smtp_port": 587, "use_tls": True,
        "smtp_username": "", "smtp_password": "",
        "sender_email": "", "sender_name": "Test",
    }


def test_unconfigured_service(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                "SMTP_FROM", "SMTP_FROM_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        "education_system.shared.email.email_service.load_email_config", _empty_config,
    )

    svc = EmailService(smtp_host="", smtp_user="", smtp_password="")
    assert svc.is_configured is False


def test_configured_service(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                "SMTP_FROM", "SMTP_FROM_NAME"):
        monkeypatch.delenv(var, raising=False)

    svc = EmailService(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="secret",
    )
    assert svc.is_configured is True


# ── send_email without SMTP ──────────────────────────────────────────

def test_send_email_unconfigured(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                "SMTP_FROM", "SMTP_FROM_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        "education_system.shared.email.email_service.load_email_config", _empty_config,
    )

    svc = EmailService(smtp_host="", smtp_user="", smtp_password="")
    result = svc.send_email("dest@example.com", "Test", "Body")
    assert result["success"] is False
    assert "not configured" in result["error"].lower()


# ── send_bulk_email no recipients ────────────────────────────────────

def test_send_bulk_no_recipients(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                "SMTP_FROM", "SMTP_FROM_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        "education_system.shared.email.email_service.load_email_config", _empty_config,
    )

    svc = EmailService(smtp_host="", smtp_user="", smtp_password="")
    result = svc.send_bulk_email([], "Subject", "Body")
    assert result["success"] is False
    assert result["sent"] == 0


# ── header injection prevention ──────────────────────────────────────

def test_validate_header_rejects_newlines():
    from education_system.shared.email.email_service import EmailError
    with pytest.raises(EmailError):
        EmailService._validate_header("value\r\nBcc: attacker@evil.com")
