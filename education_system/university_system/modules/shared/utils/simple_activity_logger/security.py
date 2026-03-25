import re
from datetime import datetime, timedelta
from typing import Dict, Any

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import LogEntry


class PIIDetector:
    """Detect and mask personally identifiable information"""

    def __init__(self):
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
            'ip_address': re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
        }

    def detect_and_mask(self, text: str, mask_char: str = '*') -> str:
        """Detect and mask PII in text"""
        if not isinstance(text, str):
            return text

        masked_text = text
        for pii_type, pattern in self.patterns.items():
            def mask_match(match):
                return mask_char * len(match.group())
            masked_text = pattern.sub(mask_match, masked_text)

        return masked_text


class SecurityMonitor:
    """Monitor for suspicious activities and security threats"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.failed_attempts = {}
        self.suspicious_ips = set()
        self.rate_limits = {}

    def check_failed_login(self, user_id: str, ip_address: str) -> bool:
        """Track failed login attempts"""
        key = f"{user_id}:{ip_address}"
        now = datetime.now()

        if key not in self.failed_attempts:
            self.failed_attempts[key] = []

        # Clean old attempts
        cutoff = now - timedelta(minutes=self.config.get('lockout_window', 15))
        self.failed_attempts[key] = [
            attempt for attempt in self.failed_attempts[key]
            if attempt > cutoff
        ]

        # Add current attempt
        self.failed_attempts[key].append(now)

        # Check if exceeded threshold
        max_attempts = self.config.get('max_failed_attempts', 5)
        if len(self.failed_attempts[key]) >= max_attempts:
            self.suspicious_ips.add(ip_address)
            return True

        return False

    def is_suspicious_activity(self, log_entry: LogEntry) -> bool:
        """Analyze log entry for suspicious patterns"""
        # Check IP reputation
        if log_entry.ip_address in self.suspicious_ips:
            return True

        # Check for unusual access patterns
        if self._check_rate_limiting(log_entry):
            return True

        # Check for privilege escalation attempts
        if self._check_privilege_escalation(log_entry):
            return True

        return False

    def _check_rate_limiting(self, log_entry: LogEntry) -> bool:
        """Check for rate limiting violations"""
        key = f"{log_entry.user_id}:{log_entry.action}"
        now = datetime.now()

        if key not in self.rate_limits:
            self.rate_limits[key] = []

        # Clean old requests
        cutoff = now - timedelta(minutes=1)
        self.rate_limits[key] = [
            req_time for req_time in self.rate_limits[key]
            if req_time > cutoff
        ]

        # Add current request
        self.rate_limits[key].append(now)

        # Check rate limit
        max_requests = self.config.get('max_requests_per_minute', 100)
        return len(self.rate_limits[key]) > max_requests

    def _check_privilege_escalation(self, log_entry: LogEntry) -> bool:
        """Check for potential privilege escalation"""
        sensitive_actions = self.config.get('sensitive_actions', [
            'delete', 'modify_permissions', 'create_admin', 'export_data'
        ])

        if log_entry.action in sensitive_actions:
            if log_entry.role not in self.config.get('privileged_roles', ['admin', 'superuser']):
                return True

        return False

    def add_suspicious_ip(self, ip_address: str):
        """Manually add IP to suspicious list"""
        self.suspicious_ips.add(ip_address)

    def remove_suspicious_ip(self, ip_address: str):
        """Remove IP from suspicious list"""
        self.suspicious_ips.discard(ip_address)

    def get_failed_attempts_count(self, user_id: str, ip_address: str) -> int:
        """Get current failed attempts count for user/IP combination"""
        key = f"{user_id}:{ip_address}"
        if key not in self.failed_attempts:
            return 0

        now = datetime.now()
        cutoff = now - timedelta(minutes=self.config.get('lockout_window', 15))

        # Clean old attempts and return count
        self.failed_attempts[key] = [
            attempt for attempt in self.failed_attempts[key]
            if attempt > cutoff
        ]

        return len(self.failed_attempts[key])

    def reset_failed_attempts(self, user_id: str, ip_address: str):
        """Reset failed attempts for user/IP combination"""
        key = f"{user_id}:{ip_address}"
        if key in self.failed_attempts:
            del self.failed_attempts[key]
