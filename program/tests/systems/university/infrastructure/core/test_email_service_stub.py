"""Tests for modules.shared.utils.email_service (stub)."""
from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.utils import email_service as es


@pytest.fixture(autouse=True)
def reset_queues():
    """Clear in-memory queues between tests to avoid leakage."""
    es.email_queue.clear()
    es.scheduled_jobs.clear()
    es.worker_threads.clear()
    yield
    es.email_queue.clear()
    es.scheduled_jobs.clear()
    es.worker_threads.clear()


class TestEmailTemplate:
    def test_has_expected_values(self):
        assert es.EmailTemplate.REGISTRATION_CONFIRMATION.value \
            == "user_management/registration_confirmation"
        assert es.EmailTemplate.PASSWORD_RESET.value == "password_reset"

    def test_all_values_are_strings(self):
        for member in es.EmailTemplate:
            assert isinstance(member.value, str)
            assert member.value  # non-empty


class TestStubBehavior:
    @pytest.fixture(autouse=True)
    def force_stub(self, monkeypatch):
        """Disable real-service delegation so we test the stub path."""
        monkeypatch.setattr(es, "_REAL_EMAIL_SERVICE_AVAILABLE", False)


class TestSendEmailQueueing(TestStubBehavior):
    def test_send_email_appends_immediate(self):
        es.send_email("to@x", subject="hi")
        assert len(es.email_queue) == 1
        assert es.email_queue[0]["type"] == "immediate"
        assert es.email_queue[0]["args"] == ("to@x",)
        assert es.email_queue[0]["kwargs"] == {"subject": "hi"}

    def test_send_email_db_only_appends(self):
        es.send_email_db_only("to@x")
        assert es.email_queue[0]["type"] == "db_only"

    def test_queue_email_appends_queued(self):
        es.queue_email("to@x")
        assert es.email_queue[0]["type"] == "queued"

    def test_queue_template_email_delegates_to_queue(self):
        es.queue_template_email("to@x")
        assert es.email_queue[0]["type"] == "queued"

    def test_send_template_email_delegates_to_send(self):
        es.send_template_email("to@x")
        assert es.email_queue[0]["type"] == "immediate"

    def test_send_email_as_user_delegates(self):
        es.send_email_as_user("to@x")
        assert es.email_queue[0]["type"] == "immediate"

    def test_send_email_as_system_delegates(self):
        es.send_email_as_system("to@x")
        assert es.email_queue[0]["type"] == "immediate"


class TestStoredEmails(TestStubBehavior):
    def test_get_stored_emails_returns_copy(self):
        es.send_email("a@x")
        stored = es.get_stored_emails()
        assert len(stored) == 1
        stored.clear()  # mutating the returned list must not affect internal state
        assert len(es.email_queue) == 1

    def test_clear_stored_emails(self):
        es.send_email("a@x")
        es.clear_stored_emails()
        assert es.email_queue == []


class TestSchedule(TestStubBehavior):
    def test_schedule_send_appends_job(self):
        es.schedule_send("a@x", when="tomorrow")
        assert len(es.scheduled_jobs) == 1
        job, when = es.scheduled_jobs[0]
        assert job["args"] == ("a@x",)
        assert job["kwargs"] == {"when": "tomorrow"}


class TestNoOpHelpers(TestStubBehavior):
    def test_safe_log_email(self):
        assert es.safe_log_email("anything") is None

    def test_fix_inbox_display_issue(self):
        assert es.fix_inbox_display_issue() is None

    def test_generate_system_username(self):
        assert es.generate_system_username() == "system"

    def test_get_appropriate_sender_id(self):
        assert es.get_appropriate_sender_id() == "system"

    def test_worker_lifecycle_noops(self):
        # All worker functions are no-ops in stub
        assert es.email_worker() is None
        assert es.start_email_workers() is None
        assert es.start_workers() is None  # backward-compat alias
        assert es.stop_email_workers() is None
        assert es.stop_workers() is None  # backward-compat alias

    def test_scheduler_helpers_noops(self):
        assert es.process_scheduled_emails() is None
        assert es.ensure_scheduler_running() is None
        assert es.run_scheduler() is None
        assert es.update_scheduled_email_status() is None

    def test_bulk_and_wait_noops(self):
        assert es.send_bulk(["a@x"]) is None
        assert es.wait_for_email_queue() is None

    def test_delete_stored_email(self):
        assert es.delete_stored_email(1) is None


class TestDelegateToRealService:
    def test_delegate_calls_real_when_available(self):
        # Create a fake real service with a recorded method
        class _Fake:
            def __init__(self):
                self.called = False
            def send_email(self, *a, **kw):
                self.called = True
                return "real_result"
        fake = _Fake()
        with patch.object(es, "_REAL_EMAIL_SERVICE_AVAILABLE", True), \
             patch.object(es, "_real_email_service", fake):
            result = es.send_email("to@x")
        assert result == "real_result"
        assert fake.called

    def test_delegate_returns_none_when_method_missing(self):
        with patch.object(es, "_REAL_EMAIL_SERVICE_AVAILABLE", True), \
             patch.object(es, "_real_email_service", object()):
            # Real service lacks send_email; should fall through to stub queue
            result = es.send_email("to@x")
        # Stub path appends to queue and returns None
        assert result is None
