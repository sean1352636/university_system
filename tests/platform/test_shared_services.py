"""Tests for shared services added in v8.57.0-v8.58.0.

Tests: ConsentService, WebhookService, AuditService, PasswordResetService,
       OfflineSyncService, EarlyWarningService.
"""

import os
import sqlite3
import tempfile
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def auth_db(tmp_path):
    """Create a temporary auth database with schema."""
    db_path = str(tmp_path / "auth.db")
    from education_system.platform.identity.auth.schema import initialise_auth_db
    initialise_auth_db(db_path)
    return db_path


# ── ConsentService ────────────────────────────────────────────────────


class TestConsentService:
    def test_grant_consent(self, auth_db):
        from education_system.platform.governance.gdpr.consent_service import ConsentService
        svc = ConsentService(auth_db)
        # Need a user first
        conn = sqlite3.connect(auth_db)
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            ("testuser", "hash", "Test User"),
        )
        conn.commit()
        conn.close()

        record_id = svc.grant_consent(1, "data_processing", ip_address="127.0.0.1")
        assert record_id > 0

    def test_withdraw_consent(self, auth_db):
        from education_system.platform.governance.gdpr.consent_service import ConsentService
        svc = ConsentService(auth_db)
        conn = sqlite3.connect(auth_db)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("testuser", "hash"),
        )
        conn.commit()
        conn.close()

        svc.grant_consent(1, "marketing")
        assert svc.has_consent(1, "marketing") is True
        svc.withdraw_consent(1, "marketing")
        assert svc.has_consent(1, "marketing") is False

    def test_get_consent_summary(self, auth_db):
        from education_system.platform.governance.gdpr.consent_service import ConsentService, CONSENT_TYPES
        svc = ConsentService(auth_db)
        conn = sqlite3.connect(auth_db)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("testuser", "hash"),
        )
        conn.commit()
        conn.close()

        summary = svc.get_consent_summary(1)
        assert len(summary) == len(CONSENT_TYPES)
        assert all(not v["granted"] for v in summary.values())

    def test_bulk_grant(self, auth_db):
        from education_system.platform.governance.gdpr.consent_service import ConsentService
        svc = ConsentService(auth_db)
        conn = sqlite3.connect(auth_db)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("testuser", "hash"),
        )
        conn.commit()
        conn.close()

        count = svc.bulk_grant(1, ["data_processing", "email_communications"])
        assert count == 2
        assert svc.has_consent(1, "data_processing")
        assert svc.has_consent(1, "email_communications")

    def test_export_consent_history(self, auth_db):
        from education_system.platform.governance.gdpr.consent_service import ConsentService
        svc = ConsentService(auth_db)
        conn = sqlite3.connect(auth_db)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("testuser", "hash"),
        )
        conn.commit()
        conn.close()

        svc.grant_consent(1, "data_processing")
        svc.withdraw_consent(1, "data_processing")
        history = svc.export_consent_history(1)
        assert len(history) >= 1


# ── WebhookService ────────────────────────────────────────────────────


class TestWebhookService:
    def test_subscribe(self, tmp_db):
        from education_system.platform.integrations.webhooks.webhook_service import WebhookService
        svc = WebhookService(tmp_db)
        sub_id = svc.subscribe(
            url="https://example.com/hook",
            event_types=["student.enrolled"],
            description="Test webhook",
        )
        assert sub_id > 0

    def test_unsubscribe(self, tmp_db):
        from education_system.platform.integrations.webhooks.webhook_service import WebhookService
        svc = WebhookService(tmp_db)
        sub_id = svc.subscribe(url="https://example.com/hook")
        assert svc.unsubscribe(sub_id) is True

    def test_list_subscriptions(self, tmp_db):
        from education_system.platform.integrations.webhooks.webhook_service import WebhookService
        svc = WebhookService(tmp_db)
        svc.subscribe(url="https://a.com/hook", system_key="sixth_form")
        svc.subscribe(url="https://b.com/hook", system_key="university")
        subs = svc.list_subscriptions()
        assert len(subs) == 2

    def test_list_subscriptions_by_system(self, tmp_db):
        from education_system.platform.integrations.webhooks.webhook_service import WebhookService
        svc = WebhookService(tmp_db)
        svc.subscribe(url="https://a.com/hook", system_key="sixth_form")
        svc.subscribe(url="https://b.com/hook", system_key="university")
        subs = svc.list_subscriptions(system_key="sixth_form")
        assert len(subs) >= 1

    def test_dispatch_queues_deliveries(self, tmp_db):
        from education_system.platform.integrations.webhooks.webhook_service import WebhookService
        svc = WebhookService(tmp_db)
        svc.subscribe(url="https://example.com/hook", event_types=["test.event"])
        count = svc.dispatch("test.event", {"data": "hello"})
        assert count == 1

    def test_get_recent_deliveries(self, tmp_db):
        from education_system.platform.integrations.webhooks.webhook_service import WebhookService
        svc = WebhookService(tmp_db)
        svc.subscribe(url="https://example.com/hook", event_types=["*"])
        svc.dispatch("test.event", {"data": "hello"})
        import time
        time.sleep(0.2)  # Let background thread queue
        deliveries = svc.get_recent_deliveries(limit=10)
        assert isinstance(deliveries, list)


# ── AuditService ──────────────────────────────────────────────────────


class TestAuditService:
    def test_log_entry(self, tmp_db):
        from education_system.platform.governance.audit.audit_service import AuditService
        svc = AuditService(tmp_db)
        entry_id = svc.log("user.login", system_key="university", user_id=1, username="admin")
        assert entry_id > 0

    def test_log_security_event(self, tmp_db):
        from education_system.platform.governance.audit.audit_service import AuditService
        svc = AuditService(tmp_db)
        entry_id = svc.log_security("failed_login", system_key="sixth_form", username="attacker")
        assert entry_id > 0

    def test_query_by_system(self, tmp_db):
        from education_system.platform.governance.audit.audit_service import AuditService
        svc = AuditService(tmp_db)
        svc.log("action1", system_key="sixth_form")
        svc.log("action2", system_key="university")
        results = svc.query(system_key="sixth_form")
        assert len(results) == 1
        assert results[0]["system_key"] == "sixth_form"

    def test_verify_integrity(self, tmp_db):
        from education_system.platform.governance.audit.audit_service import AuditService
        svc = AuditService(tmp_db)
        entry_id = svc.log("test.action", system_key="shared")
        assert svc.verify_integrity(entry_id) is True

    def test_get_stats(self, tmp_db):
        from education_system.platform.governance.audit.audit_service import AuditService
        svc = AuditService(tmp_db)
        svc.log("a", system_key="shared")
        svc.log("b", system_key="shared", severity="security")
        stats = svc.get_stats()
        assert stats["total"] >= 2


# ── PasswordResetService ──────────────────────────────────────────────


class TestPasswordResetService:
    def test_request_reset_unknown_email(self, auth_db):
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        svc = PasswordResetService(auth_db)
        result = svc.request_reset("nobody@example.com")
        assert result["sent"] is True
        assert "token" not in result  # Should not reveal token for unknown email

    def test_request_and_validate_token(self, auth_db):
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        from education_system.platform.identity.auth.password_manager import hash_password
        svc = PasswordResetService(auth_db)

        # Create a user
        conn = sqlite3.connect(auth_db)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            ("resetuser", hash_password("OldPass@12345"), "reset@test.com"),
        )
        conn.commit()
        conn.close()

        result = svc.request_reset("reset@test.com")
        assert "token" in result

        info = svc.validate_token(result["token"])
        assert info["username"] == "resetuser"

    def test_reset_password(self, auth_db):
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        from education_system.platform.identity.auth.password_manager import hash_password
        svc = PasswordResetService(auth_db)

        conn = sqlite3.connect(auth_db)
        conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            ("resetuser2", hash_password("OldPass@12345"), "reset2@test.com"),
        )
        conn.commit()
        conn.close()

        result = svc.request_reset("reset2@test.com")
        success = svc.reset_password(result["token"], "NewSecure@Pass789")
        assert success is True

    def test_reset_with_invalid_token(self, auth_db):
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        from education_system.platform.identity.auth.exceptions import AuthError
        svc = PasswordResetService(auth_db)
        with pytest.raises(AuthError):
            svc.reset_password("invalid-token", "NewPass@12345")


# ── OfflineSyncService ────────────────────────────────────────────────


class TestOfflineSyncService:
    def test_cache_set_get(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        svc.cache_set("students:1", {"name": "Alice"}, "university", "student")
        result = svc.cache_get("students:1")
        assert result == {"name": "Alice"}

    def test_cache_miss(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        assert svc.cache_get("nonexistent") is None

    def test_cache_invalidate(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        svc.cache_set("key1", {"a": 1}, "sixth_form", "course")
        svc.cache_invalidate(cache_key="key1")
        assert svc.cache_get("key1") is None

    def test_queue_mutation(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        mid = svc.queue_mutation("create", "student", "university", {"name": "Bob"})
        assert mid > 0

    def test_get_pending_mutations(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        svc.queue_mutation("create", "student", "university", {"name": "Alice"})
        svc.queue_mutation("update", "student", "sixth_form", {"name": "Bob"})
        pending = svc.get_pending_mutations()
        assert len(pending) == 2

    def test_mark_synced(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        mid = svc.queue_mutation("create", "student", "university", {"name": "Alice"})
        svc.mark_synced(mid)
        pending = svc.get_pending_mutations()
        assert len(pending) == 0

    def test_sync_status(self, tmp_db):
        from education_system.platform.features.offline.sync_service import OfflineSyncService
        svc = OfflineSyncService(tmp_db)
        svc.queue_mutation("create", "student", "university", {"x": 1})
        status = svc.get_sync_status()
        assert status["pending_mutations"] == 1
        assert status["conflicts"] == 0


# ── EarlyWarningService ──────────────────────────────────────────────


class TestEarlyWarningService:
    def test_assess_unknown_system(self):
        from education_system.platform.features.analytics.early_warning import EarlyWarningService
        svc = EarlyWarningService(db_paths={"test": "/nonexistent.db"})
        result = svc.assess_student_risk("S001", "unknown")
        assert "error" in result

    def test_assess_missing_db(self):
        from education_system.platform.features.analytics.early_warning import EarlyWarningService
        svc = EarlyWarningService(db_paths={"test": "/nonexistent.db"})
        result = svc.assess_student_risk("S001", "test")
        assert "error" in result

    def test_risk_thresholds(self):
        from education_system.platform.features.analytics.early_warning import EarlyWarningService
        svc = EarlyWarningService()
        assert svc.RISK_THRESHOLDS["low"] < svc.RISK_THRESHOLDS["critical"]

    def test_recommendations_generated(self):
        from education_system.platform.features.analytics.early_warning import EarlyWarningService
        svc = EarlyWarningService()
        factors = {
            "attendance": {"score": 0.8, "weight": 0.35},
            "grades": {"score": 0.8, "weight": 0.30},
            "assignments": {"score": 0.6, "weight": 0.20},
            "behaviour": {"score": 0.6, "weight": 0.15},
        }
        recs = svc._generate_recommendations(factors, "high")
        assert len(recs) > 0
        assert any("case conference" in r.lower() for r in recs)
