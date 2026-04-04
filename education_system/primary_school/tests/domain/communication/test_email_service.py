"""Tests for the EmailService in the Primary School system."""

import pytest


class TestSendEmail:
    """Tests for sending (logging) emails."""

    def test_send_email_returns_dict(self, email_service):
        """Sending an email returns a dict with id and status."""
        result = email_service.send_email(
            to_address="parent@example.com",
            subject="Attendance Alert",
            body="Your child was absent today.",
            from_address="office@school.local",
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert result["status"] == "Logged"

    def test_send_email_persists(self, email_service):
        """Sent email appears in get_sent_emails results."""
        email_service.send_email(
            to_address="parent@example.com",
            subject="Newsletter",
            body="March newsletter attached.",
            from_address="office@school.local",
        )
        emails = email_service.get_sent_emails()
        assert len(emails) == 1
        assert emails[0]["subject"] == "Newsletter"
        assert emails[0]["to_address"] == "parent@example.com"

    def test_send_email_without_from_address(self, email_service):
        """Sending without a from_address stores None."""
        result = email_service.send_email(
            to_address="staff@school.local",
            subject="Reminder",
            body="Staff meeting at 3pm.",
        )
        emails = email_service.get_sent_emails()
        match = [e for e in emails if e["id"] == result["id"]]
        assert len(match) == 1
        assert match[0]["from_address"] is None

    def test_send_multiple_emails(self, email_service):
        """Multiple emails are stored independently."""
        email_service.send_email(
            to_address="a@example.com", subject="S1", body="B1")
        email_service.send_email(
            to_address="b@example.com", subject="S2", body="B2")
        emails = email_service.get_sent_emails()
        assert len(emails) == 2


class TestGetSentEmails:
    """Tests for retrieving sent emails."""

    def test_get_sent_emails_empty_db(self, email_service):
        """Querying an empty database returns an empty list."""
        assert email_service.get_sent_emails() == []

    def test_get_sent_emails_all_fields(self, email_service):
        """Retrieved email includes body, status, and sent_at."""
        email_service.send_email(
            to_address="parent@example.com",
            subject="Test",
            body="Body content",
            from_address="admin@school.local",
        )
        emails = email_service.get_sent_emails()
        assert emails[0]["body"] == "Body content"
        assert emails[0]["status"] == "Logged"
        assert emails[0]["sent_at"] is not None

    def test_email_fields_preserved_exactly(self, email_service):
        """Subject and body with special characters are stored verbatim."""
        email_service.send_email(
            to_address="parent@example.com",
            subject="RE: Pupil's Report (2026)",
            body="Please see attached <report>.",
        )
        emails = email_service.get_sent_emails()
        assert emails[0]["subject"] == "RE: Pupil's Report (2026)"
        assert emails[0]["body"] == "Please see attached <report>."
