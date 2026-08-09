"""Behavioural tests for provider and email-boundary failures."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, Mock, patch

import pytest
from hypothesis import given, strategies as st

from education_system.systems.university.infrastructure.email.smtp import (
    EmailService,
    SMTPClient,
    SMTPConfig,
)


@pytest.fixture
def smtp_client():
    return SMTPClient(
        SMTPConfig(
            smtp_server="smtp.test",
            smtp_port=587,
            sender_email="noreply@test.invalid",
            sender_name="Test System",
            use_tls=True,
        )
    )


def test_invalid_attachment_is_rejected_before_provider_call(smtp_client, tmp_path):
    provider = MagicMock()
    with patch("education_system.systems.university.infrastructure.email.smtp.smtplib.SMTP", provider):
        assert smtp_client.send(
            "person@example.com",
            "Subject",
            "Body",
            attachments=str(tmp_path / "missing.pdf"),
        ) is False
    provider.assert_not_called()


def test_provider_throttling_is_reported_as_failure(smtp_client):
    provider = MagicMock()
    provider.return_value.__enter__.return_value.sendmail.side_effect = RuntimeError(
        "provider throttled request"
    )
    with patch("education_system.systems.university.infrastructure.email.smtp.smtplib.SMTP", provider):
        assert smtp_client.send("person@example.com", "Subject", "Body") is False


def test_audit_or_email_log_failure_does_not_duplicate_provider_delivery():
    smtp = Mock()
    smtp.send.return_value = True
    log_email = Mock(side_effect=OSError("audit store unavailable"))
    metrics = Mock()
    service = EmailService(smtp, log_email_func=log_email, log_metrics_func=metrics)

    assert service.send_and_log("person@example.com", "Subject", "Body") is True
    smtp.send.assert_called_once()
    log_email.assert_called_once()
    metrics.assert_called_once_with("sent")


def test_partial_batch_failure_isolated_by_provider_calls(smtp_client):
    provider = MagicMock()
    server = provider.return_value.__enter__.return_value
    server.sendmail.side_effect = [None, RuntimeError("temporary provider failure"), None]
    with patch("education_system.systems.university.infrastructure.email.smtp.smtplib.SMTP", provider):
        results = [
            smtp_client.send(f"person{i}@example.com", "Subject", "Body")
            for i in range(3)
        ]

    assert results == [True, False, True]
    assert server.sendmail.call_count == 3


@given(st.text(min_size=1, max_size=80))
def test_header_validation_rejects_all_generated_crlf_values(value):
    """Generated Unicode/header input must never permit header injection."""
    if "\r" in value or "\n" in value:
        with pytest.raises(ValueError):
            SMTPClient._validate_email_header(value)
    else:
        assert SMTPClient._validate_email_header(value) == value


def test_concurrent_provider_calls_are_not_dropped_or_duplicated():
    smtp = Mock()
    smtp.send.return_value = True
    service = EmailService(smtp)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda i: service.send_and_log(
                    f"person{i}@example.com", "Subject", "Body"
                ),
                range(32),
            )
        )

    assert results == [True] * 32
    assert smtp.send.call_count == 32
