"""Tests for simple_activity_logger.security."""
from education_system.systems.university.infrastructure.utils.activity_logger.security import (
    PIIDetector,
    SecurityMonitor,
)
from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


def _entry(**overrides):
    base = dict(
        timestamp="2026-05-28 10:00:00.000",
        user_id="u1", username="alice", role="user",
        action="read", module="m", details="d",
        status="success", log_level="INFO",
        session_id="s", ip_address="1.2.3.4",
        user_agent="UA", request_size=0, response_size=0,
        processing_time=0.0, geolocation={}, security_level="LOW",
        trace_id="t",
    )
    base.update(overrides)
    return LogEntry(**base)


class TestPIIDetector:
    def setup_method(self):
        self.det = PIIDetector()

    def test_masks_email(self):
        out = self.det.detect_and_mask("contact alice@example.com today")
        assert "alice@example.com" not in out
        assert "*" in out

    def test_masks_ssn(self):
        out = self.det.detect_and_mask("ssn 123-45-6789 here")
        assert "123-45-6789" not in out

    def test_masks_credit_card(self):
        out = self.det.detect_and_mask("card 4111 1111 1111 1111 stored")
        assert "4111" not in out

    def test_masks_ip(self):
        out = self.det.detect_and_mask("from 10.0.0.5 logged in")
        assert "10.0.0.5" not in out

    def test_masks_phone(self):
        out = self.det.detect_and_mask("call 555-123-4567")
        assert "555-123-4567" not in out

    def test_non_string_passthrough(self):
        assert self.det.detect_and_mask(42) == 42
        assert self.det.detect_and_mask(None) is None

    def test_no_pii_unchanged(self):
        text = "this has no PII at all"
        assert self.det.detect_and_mask(text) == text


class TestSecurityMonitorFailedLogin:
    def test_below_threshold_returns_false(self):
        sm = SecurityMonitor({"max_failed_attempts": 3, "lockout_window": 15})
        assert sm.check_failed_login("u", "1.1.1.1") is False
        assert sm.check_failed_login("u", "1.1.1.1") is False

    def test_at_threshold_returns_true_and_marks_ip(self):
        sm = SecurityMonitor({"max_failed_attempts": 3, "lockout_window": 15})
        sm.check_failed_login("u", "1.1.1.1")
        sm.check_failed_login("u", "1.1.1.1")
        assert sm.check_failed_login("u", "1.1.1.1") is True
        assert "1.1.1.1" in sm.suspicious_ips

    def test_get_failed_attempts_count(self):
        sm = SecurityMonitor({"max_failed_attempts": 10, "lockout_window": 15})
        sm.check_failed_login("u", "1.1.1.1")
        sm.check_failed_login("u", "1.1.1.1")
        assert sm.get_failed_attempts_count("u", "1.1.1.1") == 2

    def test_reset_failed_attempts(self):
        sm = SecurityMonitor({"max_failed_attempts": 5, "lockout_window": 15})
        sm.check_failed_login("u", "1.1.1.1")
        sm.reset_failed_attempts("u", "1.1.1.1")
        assert sm.get_failed_attempts_count("u", "1.1.1.1") == 0


class TestSecurityMonitorSuspiciousActivity:
    def test_suspicious_ip_flagged(self):
        sm = SecurityMonitor({})
        sm.add_suspicious_ip("1.2.3.4")
        assert sm.is_suspicious_activity(_entry(ip_address="1.2.3.4")) is True

    def test_remove_suspicious_ip(self):
        sm = SecurityMonitor({})
        sm.add_suspicious_ip("1.2.3.4")
        sm.remove_suspicious_ip("1.2.3.4")
        assert sm.is_suspicious_activity(_entry(ip_address="1.2.3.4")) is False

    def test_privilege_escalation_detected(self):
        sm = SecurityMonitor({
            "sensitive_actions": ["delete"],
            "privileged_roles": ["admin"],
        })
        assert sm.is_suspicious_activity(_entry(action="delete", role="user")) is True

    def test_privileged_role_can_perform_sensitive_action(self):
        sm = SecurityMonitor({
            "sensitive_actions": ["delete"],
            "privileged_roles": ["admin"],
            "max_requests_per_minute": 100,
        })
        assert sm.is_suspicious_activity(_entry(action="delete", role="admin")) is False

    def test_rate_limit_violation(self):
        sm = SecurityMonitor({"max_requests_per_minute": 2})
        e = _entry(action="read", role="admin")
        sm.is_suspicious_activity(e)
        sm.is_suspicious_activity(e)
        # Third call within a minute exceeds the limit
        assert sm.is_suspicious_activity(e) is True
