"""Tests for ConsentService (GDPR consent tracking)."""

import sqlite3
import pytest


@pytest.fixture
def consent_db(tmp_path):
    """Create a temporary auth-like DB with a users table."""
    db_path = str(tmp_path / "consent_auth.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT ''
        )"""
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        ("testuser", "hash", "Test User"),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def svc(consent_db):
    from education_system.platform.governance.gdpr.consent_service import ConsentService
    return ConsentService(consent_db)


class TestGrantAndWithdraw:
    def test_grant_consent_returns_id(self, svc):
        record_id = svc.grant_consent(1, "data_processing", ip_address="127.0.0.1",
                                       source="web", version="2.0")
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_has_consent_after_grant(self, svc):
        svc.grant_consent(1, "photo_internal")
        assert svc.has_consent(1, "photo_internal") is True

    def test_has_consent_false_before_grant(self, svc):
        assert svc.has_consent(1, "email_communications") is False

    def test_withdraw_consent(self, svc):
        svc.grant_consent(1, "marketing", ip_address="10.0.0.1")
        assert svc.has_consent(1, "marketing") is True
        result = svc.withdraw_consent(1, "marketing", ip_address="10.0.0.2")
        assert result is True
        assert svc.has_consent(1, "marketing") is False

    def test_withdraw_nonexistent_returns_false(self, svc):
        assert svc.withdraw_consent(1, "biometric_data") is False

    def test_regrant_after_withdraw(self, svc):
        svc.grant_consent(1, "sms_communications")
        svc.withdraw_consent(1, "sms_communications")
        rid = svc.grant_consent(1, "sms_communications")
        assert isinstance(rid, int)
        assert svc.has_consent(1, "sms_communications") is True


class TestBulkGrant:
    def test_bulk_grant_multiple_types(self, svc):
        types = ["data_processing", "photo_internal", "email_communications"]
        count = svc.bulk_grant(1, types, ip_address="192.168.1.1", source="registration")
        assert count == 3
        for ct in types:
            assert svc.has_consent(1, ct) is True

    def test_bulk_grant_returns_count(self, svc):
        count = svc.bulk_grant(1, ["cookies_analytics", "cookies_functional"])
        assert count == 2


class TestQueryAndExport:
    def test_get_user_consents(self, svc):
        svc.grant_consent(1, "data_processing")
        svc.grant_consent(1, "photo_external")
        consents = svc.get_user_consents(1)
        assert len(consents) == 2
        types = {c["consent_type"] for c in consents}
        assert types == {"data_processing", "photo_external"}

    def test_get_consent_summary(self, svc):
        svc.grant_consent(1, "data_processing")
        summary = svc.get_consent_summary(1)
        assert summary["data_processing"]["granted"] is True
        assert summary["marketing"]["granted"] is False

    def test_export_consent_history_chronological(self, svc):
        svc.grant_consent(1, "data_processing")
        svc.grant_consent(1, "marketing")
        svc.withdraw_consent(1, "marketing")
        history = svc.export_consent_history(1)
        assert len(history) >= 2
        # Verify chronological order
        dates = [h["created_at"] for h in history]
        assert dates == sorted(dates)

    def test_export_includes_withdrawn_records(self, svc):
        svc.grant_consent(1, "research")
        svc.withdraw_consent(1, "research")
        history = svc.export_consent_history(1)
        research = [h for h in history if h["consent_type"] == "research"]
        assert len(research) == 1
        assert research[0]["granted"] == 0
        assert research[0]["withdrawn_at"] is not None
