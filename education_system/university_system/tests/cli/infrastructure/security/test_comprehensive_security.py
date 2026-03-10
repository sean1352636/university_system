#!/usr/bin/env python3
"""
Comprehensive tests for all security managers in comprehensive_security.py

Tests:
- APISecurityManager: API key management and rate limiting
- PasswordSecurityManager: Password strength and compromise checking
- SecurityAuditManager: Security event logging and compliance reports
- DataLossPreventionManager: Bulk export controls and PII detection
- IncidentResponseManager: Security incident handling
- VulnerabilityScanner: SQL injection and XSS detection
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.infrastructure.security.comprehensive_security import (
    APISecurityManager,
    PasswordSecurityManager,
    SecurityAuditManager,
    DataLossPreventionManager,
    IncidentResponseManager,
    VulnerabilityScanner
)
from education_system.university_system.infrastructure.security.init_security_tables import init_security_tables

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize security tables
    init_security_tables(path)

    yield path

    # Cleanup
    if os.path.exists(path):
        os.remove(path)

# ============================================================================
# APISecurityManager Tests
# ============================================================================

class TestAPISecurityManager:
    """Test API security and rate limiting"""

    def test_create_api_key_success(self, test_db):
        """Test successful API key creation"""
        manager = APISecurityManager(test_db)

        result = manager.create_api_key(
            user_id=1,
            key_name="Test Key",
            permissions=["read:students", "write:grades"],
            rate_limit=1000,
            expires_days=365
        )

        assert result['success'] is True
        assert 'api_key' in result
        assert result['api_key'].startswith('uni_')
        assert result['key_name'] == "Test Key"
        assert 'expires_at' in result

    def test_validate_api_key_valid(self, test_db):
        """Test validation of valid API key"""
        manager = APISecurityManager(test_db)

        # Create key
        create_result = manager.create_api_key(1, "Test", ["read:all"])
        api_key = create_result['api_key']

        # Validate key
        validate_result = manager.validate_api_key(api_key)

        assert validate_result['valid'] is True
        assert validate_result['user_id'] == 1
        assert 'read:all' in validate_result['permissions']

    def test_validate_api_key_invalid(self, test_db):
        """Test validation of invalid API key"""
        manager = APISecurityManager(test_db)

        result = manager.validate_api_key("invalid_key_12345")

        assert result['valid'] is False
        assert result['reason'] == 'Invalid API key'

    def test_validate_api_key_expired(self, test_db):
        """Test validation of expired API key"""
        manager = APISecurityManager(test_db)

        # Create key with past expiration
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        import hashlib
        api_key = "uni_test_expired"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        expired_date = datetime.now() - timedelta(days=1)
        cursor.execute("""
            INSERT INTO api_keys (user_id, key_hash, key_name, permissions, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (1, key_hash, "Expired", '["test"]', expired_date))
        conn.commit()
        conn.close()

        result = manager.validate_api_key(api_key)

        assert result['valid'] is False
        assert result['reason'] == 'API key expired'

    def test_check_rate_limit_allowed(self, test_db):
        """Test rate limiting allows request under limit"""
        manager = APISecurityManager(test_db)

        result = manager.check_rate_limit(
            identifier="user_123",
            identifier_type="user",
            endpoint="/api/students",
            limit=1000
        )

        assert result['allowed'] is True
        assert result['remaining'] == 999
        assert 'reset_at' in result

    def test_check_rate_limit_exceeded(self, test_db):
        """Test rate limiting blocks request over limit"""
        manager = APISecurityManager(test_db)

        # Make 5 requests with limit of 5
        for i in range(5):
            manager.check_rate_limit("user_123", "user", "/api/test", limit=5)

        # 6th request should be blocked
        result = manager.check_rate_limit("user_123", "user", "/api/test", limit=5)

        assert result['allowed'] is False
        assert result['reason'] == 'Rate limit exceeded'
        assert result['limit'] == 5

    def test_check_rate_limit_window_reset(self, test_db):
        """Test rate limit resets after window expires"""
        manager = APISecurityManager(test_db)

        # Make initial request
        manager.check_rate_limit("user_456", "user", "/api/test", limit=10)

        # Manually expire the window
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        old_time = datetime.now() - timedelta(hours=2)
        cursor.execute("""
            UPDATE api_rate_limits
            SET window_start = ?, request_count = 10
            WHERE identifier = ?
        """, (old_time, "user_456"))
        conn.commit()
        conn.close()

        # Next request should reset counter
        result = manager.check_rate_limit("user_456", "user", "/api/test", limit=10)

        assert result['allowed'] is True
        assert result['remaining'] == 9

# ============================================================================
# PasswordSecurityManager Tests
# ============================================================================

class TestPasswordSecurityManager:
    """Test password security features"""

    def test_calculate_password_strength_weak(self, test_db):
        """Test weak password detection"""
        manager = PasswordSecurityManager(test_db)

        result = manager.calculate_password_strength("abc123")

        assert result['strength'] in ['weak', 'fair']
        assert result['score'] < 60
        assert len(result['feedback']) > 0

    def test_calculate_password_strength_strong(self, test_db):
        """Test strong password detection"""
        manager = PasswordSecurityManager(test_db)

        result = manager.calculate_password_strength("MyStr0ng!P@ssw0rd#2024")

        assert result['strength'] in ['good', 'strong']
        assert result['score'] >= 60

    def test_password_strength_common_patterns(self, test_db):
        """Test detection of common patterns"""
        manager = PasswordSecurityManager(test_db)

        result = manager.calculate_password_strength("password123")

        assert result['score'] < 50
        assert any('common' in fb.lower() for fb in result['feedback'])

    def test_password_strength_sequential(self, test_db):
        """Test detection of sequential characters"""
        manager = PasswordSecurityManager(test_db)

        result = manager.calculate_password_strength("abc12345xyz")

        feedback_str = ' '.join(result['feedback']).lower()
        assert 'sequential' in feedback_str or result['score'] < 70

    def test_password_strength_repeated(self, test_db):
        """Test detection of repeated characters"""
        manager = PasswordSecurityManager(test_db)

        result = manager.calculate_password_strength("aaabbbccc")

        feedback_str = ' '.join(result['feedback']).lower()
        assert 'repeat' in feedback_str or result['score'] < 60

    @patch('requests.get')
    def test_check_compromised_password_safe(self, mock_get, test_db):
        """Test password not found in breaches"""
        manager = PasswordSecurityManager(test_db)

        # Mock API response with no match
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "AAAAA:123\nBBBBB:456\nCCCCC:789"
        mock_get.return_value = mock_response

        result = manager.check_compromised_password("SafeP@ssw0rd!")

        assert result['compromised'] is False
        assert 'not found' in result['message'].lower()

    @patch('requests.get')
    def test_check_compromised_password_found(self, mock_get, test_db):
        """Test password found in breaches"""
        manager = PasswordSecurityManager(test_db)

        # Create predictable hash
        import hashlib
        password = "password123"
        sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()
        suffix = sha1_hash[5:]

        # Mock API response with match
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = f"{suffix}:12345"
        mock_get.return_value = mock_response

        result = manager.check_compromised_password(password)

        assert result['compromised'] is True
        assert result['count'] == 12345

    def test_add_to_password_history(self, test_db):
        """Test adding password to history"""
        manager = PasswordSecurityManager(test_db)

        # Add password to history
        manager.add_to_password_history(1, "hash1")
        manager.add_to_password_history(1, "hash2")

        # Verify in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM password_history WHERE user_id = 1")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 2

    def test_password_history_limit(self, test_db):
        """Test password history keeps only last 5"""
        manager = PasswordSecurityManager(test_db)

        # Add 7 passwords
        for i in range(7):
            manager.add_to_password_history(1, f"hash{i}")

        # Should only keep last 5
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM password_history WHERE user_id = 1")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5

    def test_check_password_reuse(self, test_db):
        """Test password reuse detection"""
        manager = PasswordSecurityManager(test_db)

        # Add password to history
        manager.add_to_password_history(1, "hash123")

        # Check if reused
        is_reused = manager.check_password_reuse(1, "hash123")
        assert is_reused is True

        # Check new password
        is_new = manager.check_password_reuse(1, "hash456")
        assert is_new is False

# ============================================================================
# SecurityAuditManager Tests
# ============================================================================

class TestSecurityAuditManager:
    """Test security audit and compliance"""

    def test_log_security_event(self, test_db):
        """Test logging security events"""
        manager = SecurityAuditManager(test_db)

        manager.log_security_event(
            user_id=1,
            event_type='failed_login',
            details={'reason': 'invalid_password'},
            severity='high',
            ip_address='192.168.1.100'
        )

        # Verify in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM security_events WHERE user_id = 1")
        event = cursor.fetchone()
        conn.close()

        assert event is not None
        assert 'failed_login' in str(event)

    def test_log_data_access(self, test_db):
        """Test logging data access"""
        manager = SecurityAuditManager(test_db)

        manager.log_data_access(
            user_id=1,
            resource_type='student',
            resource_id=100,
            action='view',
            ip_address='10.0.0.1'
        )

        # Verify in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM data_access_log WHERE user_id = 1")
        log = cursor.fetchone()
        conn.close()

        assert log is not None

    def test_log_permission_change(self, test_db):
        """Test logging permission changes"""
        manager = SecurityAuditManager(test_db)

        manager.log_permission_change(
            changed_by=1,
            target_user_id=2,
            permission_name='view_grades',
            action='granted',
            reason='Promoted to instructor'
        )

        # Verify in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM permission_changes_log WHERE target_user_id = 2")
        log = cursor.fetchone()
        conn.close()

        assert log is not None

    def test_generate_compliance_report(self, test_db):
        """Test compliance report generation"""
        manager = SecurityAuditManager(test_db)

        # Add some test data
        manager.log_security_event(1, 'failed_login', {}, 'medium')
        manager.log_data_access(1, 'student', 100, 'view')

        # Generate report
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        report = manager.generate_compliance_report(start_date, end_date, 'ferpa')

        assert report['report_type'] == 'ferpa'
        assert 'data_access' in report
        assert 'security_events' in report
        assert 'failed_logins' in report

# ============================================================================
# DataLossPreventionManager Tests
# ============================================================================

class TestDataLossPreventionManager:
    """Test data loss prevention"""

    def test_request_bulk_export_approved(self, test_db):
        """Test bulk export auto-approved under threshold"""
        manager = DataLossPreventionManager(test_db)

        result = manager.request_bulk_export(
            user_id=1,
            export_type='csv',
            resource_type='student',
            record_count=50,  # Under threshold of 100
            ip_address='192.168.1.1'
        )

        assert result['approved'] is True
        assert result['reason'] == 'Under threshold'

    def test_request_bulk_export_requires_approval(self, test_db):
        """Test bulk export requires approval over threshold"""
        manager = DataLossPreventionManager(test_db)

        result = manager.request_bulk_export(
            user_id=1,
            export_type='csv',
            resource_type='student',
            record_count=200,  # Over threshold of 100
            ip_address='192.168.1.1'
        )

        assert result['approved'] is False
        assert result['requires_approval'] is True
        assert 'threshold' in result['reason'].lower()

    def test_detect_pii_ssn(self, test_db):
        """Test SSN detection in text"""
        manager = DataLossPreventionManager(test_db)

        text = "My SSN is 123-45-6789 and my friend's is 987-65-4321"
        pii_found = manager.detect_pii_in_text(text)

        assert len(pii_found) > 0
        assert any(item['type'] == 'SSN' for item in pii_found)

    def test_detect_pii_email(self, test_db):
        """Test email detection in text"""
        manager = DataLossPreventionManager(test_db)

        text = "Contact me at john.doe@example.com or jane@test.org"
        pii_found = manager.detect_pii_in_text(text)

        email_item = next((item for item in pii_found if item['type'] == 'Email'), None)
        assert email_item is not None
        assert email_item['count'] >= 2

    def test_detect_pii_phone(self, test_db):
        """Test phone number detection"""
        manager = DataLossPreventionManager(test_db)

        text = "Call 555-123-4567 or 555.987.6543"
        pii_found = manager.detect_pii_in_text(text)

        phone_item = next((item for item in pii_found if item['type'] == 'Phone'), None)
        assert phone_item is not None

    def test_detect_pii_credit_card(self, test_db):
        """Test credit card detection"""
        manager = DataLossPreventionManager(test_db)

        text = "My card is 1234-5678-9012-3456"
        pii_found = manager.detect_pii_in_text(text)

        assert any(item['type'] == 'Credit Card' for item in pii_found)

# ============================================================================
# IncidentResponseManager Tests
# ============================================================================

class TestIncidentResponseManager:
    """Test incident response system"""

    def test_create_incident(self, test_db):
        """Test creating security incident"""
        manager = IncidentResponseManager(test_db)

        result = manager.create_incident(
            incident_type='data_breach',
            severity='critical',
            description='Unauthorized access detected',
            detected_by=1,
            affected_users=[1, 2, 3]
        )

        assert result['success'] is True
        assert 'incident_id' in result
        assert result['status'] == 'open'

    def test_log_incident_action(self, test_db):
        """Test logging incident response actions"""
        manager = IncidentResponseManager(test_db)

        # Create incident first
        incident = manager.create_incident('breach', 'high', 'Test', 1)
        incident_id = incident['incident_id']

        # Log action
        manager.log_incident_action(
            incident_id=incident_id,
            action_type='investigation',
            action_details={'findings': 'No data leaked'},
            performed_by=1
        )

        # Verify in database
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incident_response_actions WHERE incident_id = ?", (incident_id,))
        action = cursor.fetchone()
        conn.close()

        assert action is not None

# ============================================================================
# VulnerabilityScanner Tests
# ============================================================================

class TestVulnerabilityScanner:
    """Test vulnerability scanning"""

    def test_scan_sql_injection_safe(self, test_db):
        """Test safe query passes SQL injection scan"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_sql_injection("SELECT * FROM students WHERE id = ?")

        assert result['vulnerable'] is False
        assert len(result['vulnerabilities']) == 0

    def test_scan_sql_injection_vulnerable_or(self, test_db):
        """Test detection of OR-based SQL injection"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_sql_injection("SELECT * FROM users WHERE id = 1 OR 1=1")

        assert result['vulnerable'] is True
        assert any(v['type'] == 'SQL Injection' for v in result['vulnerabilities'])

    def test_scan_sql_injection_vulnerable_union(self, test_db):
        """Test detection of UNION-based SQL injection"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_sql_injection("SELECT * FROM users UNION SELECT * FROM passwords")

        assert result['vulnerable'] is True

    def test_scan_sql_injection_vulnerable_drop(self, test_db):
        """Test detection of DROP TABLE attack"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_sql_injection("'; DROP TABLE students; --")

        assert result['vulnerable'] is True

    def test_scan_xss_safe(self, test_db):
        """Test safe input passes XSS scan"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_xss("Hello, this is normal text!")

        assert result['vulnerable'] is False

    def test_scan_xss_script_tag(self, test_db):
        """Test detection of script tag XSS"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_xss("<script>alert('XSS')</script>")

        assert result['vulnerable'] is True
        assert any(v['type'] == 'XSS' for v in result['vulnerabilities'])

    def test_scan_xss_javascript_protocol(self, test_db):
        """Test detection of javascript: protocol XSS"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_xss("<a href='javascript:alert(1)'>Click</a>")

        assert result['vulnerable'] is True

    def test_scan_xss_event_handler(self, test_db):
        """Test detection of event handler XSS"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_xss("<img src=x onerror='alert(1)'>")

        assert result['vulnerable'] is True

    def test_scan_xss_iframe(self, test_db):
        """Test detection of iframe XSS"""
        scanner = VulnerabilityScanner(test_db)

        result = scanner.scan_xss("<iframe src='http://evil.com'></iframe>")

        assert result['vulnerable'] is True

# ============================================================================
# Integration Tests
# ============================================================================

class TestSecurityIntegration:
    """Test integration between security components"""

    def test_api_key_with_rate_limiting(self, test_db):
        """Test API key validation with rate limiting"""
        api_mgr = APISecurityManager(test_db)

        # Create API key
        create_result = api_mgr.create_api_key(1, "Test", ["read:all"], rate_limit=5)
        api_key = create_result['api_key']

        # Validate key
        validate_result = api_mgr.validate_api_key(api_key)
        assert validate_result['valid'] is True

        # Check rate limit with the key
        for i in range(5):
            rate_result = api_mgr.check_rate_limit(
                identifier=validate_result['key_id'],
                identifier_type='api_key',
                endpoint='/api/test',
                limit=validate_result['rate_limit']
            )
            assert rate_result['allowed'] is True

        # 6th request should fail
        rate_result = api_mgr.check_rate_limit(
            identifier=validate_result['key_id'],
            identifier_type='api_key',
            endpoint='/api/test',
            limit=validate_result['rate_limit']
        )
        assert rate_result['allowed'] is False

    def test_security_audit_trail(self, test_db):
        """Test complete security audit trail"""
        audit_mgr = SecurityAuditManager(test_db)

        # Log various events
        audit_mgr.log_security_event(1, 'login', {}, 'low')
        audit_mgr.log_data_access(1, 'student', 100, 'view')
        audit_mgr.log_permission_change(1, 2, 'admin', 'granted')

        # Generate report
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now() + timedelta(hours=1)
        report = audit_mgr.generate_compliance_report(start, end)

        assert len(report['data_access']) > 0
        assert report['permission_changes'] > 0

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
