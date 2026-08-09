"""Tests for simple_activity_logger.security"""
from education_system.systems.university.infrastructure.utils.activity_logger.security import (
    PIIDetector, SecurityMonitor,
)


class TestPIIDetector:
    def setup_method(self):
        self.d = PIIDetector()

    def test_masks_email(self):
        out = self.d.detect_and_mask("contact me at alice@example.com")
        assert "alice@example.com" not in out
        assert "*" in out

    def test_masks_phone_ssn_card_ip(self):
        text = "call 555-123-4567 ssn 123-45-6789 card 4111-1111-1111-1111 ip 10.0.0.1"
        out = self.d.detect_and_mask(text)
        for token in ["555-123-4567", "123-45-6789", "4111-1111-1111-1111", "10.0.0.1"]:
            assert token not in out

    def test_non_string_passthrough(self):
        assert self.d.detect_and_mask(12345) == 12345

    def test_custom_mask_char(self):
        out = self.d.detect_and_mask("alice@example.com", mask_char="#")
        assert "#" in out and "*" not in out


class TestSecurityMonitor:
    def test_check_failed_login_threshold(self):
        m = SecurityMonitor({"max_failed_attempts": 3, "lockout_window": 15})
        assert m.check_failed_login("u", "1.2.3.4") is False
        assert m.check_failed_login("u", "1.2.3.4") is False
        assert m.check_failed_login("u", "1.2.3.4") is True
        assert "1.2.3.4" in m.suspicious_ips

    def test_get_failed_attempts_count(self):
        m = SecurityMonitor({"max_failed_attempts": 5, "lockout_window": 15})
        m.check_failed_login("u", "ip")
        m.check_failed_login("u", "ip")
        assert m.get_failed_attempts_count("u", "ip") == 2
        assert m.get_failed_attempts_count("other", "ip") == 0

    def test_reset_failed_attempts(self):
        m = SecurityMonitor({"max_failed_attempts": 5})
        m.check_failed_login("u", "ip")
        m.reset_failed_attempts("u", "ip")
        assert m.get_failed_attempts_count("u", "ip") == 0
        m.reset_failed_attempts("u", "ip")  # idempotent

    def test_add_remove_suspicious_ip(self):
        m = SecurityMonitor({})
        m.add_suspicious_ip("9.9.9.9")
        assert "9.9.9.9" in m.suspicious_ips
        m.remove_suspicious_ip("9.9.9.9")
        assert "9.9.9.9" not in m.suspicious_ips
        m.remove_suspicious_ip("9.9.9.9")  # discard is idempotent

    def test_is_suspicious_activity_by_ip(self, make_log_entry):
        m = SecurityMonitor({})
        m.add_suspicious_ip("127.0.0.1")
        entry = make_log_entry(ip_address="127.0.0.1")
        assert m.is_suspicious_activity(entry) is True

    def test_privilege_escalation(self, make_log_entry):
        m = SecurityMonitor({"sensitive_actions": ["delete"], "privileged_roles": ["admin"]})
        non_admin = make_log_entry(action="delete", role="user", ip_address="2.2.2.2")
        assert m.is_suspicious_activity(non_admin) is True
        admin = make_log_entry(action="delete", role="admin", ip_address="2.2.2.2")
        assert m.is_suspicious_activity(admin) is False

    def test_rate_limiting(self, make_log_entry):
        m = SecurityMonitor({"max_requests_per_minute": 2})
        entry = make_log_entry(user_id="u", action="x", ip_address="3.3.3.3")
        assert m.is_suspicious_activity(entry) is False
        m.is_suspicious_activity(entry)
        # third call should breach the rate limit
        assert m.is_suspicious_activity(entry) is True
