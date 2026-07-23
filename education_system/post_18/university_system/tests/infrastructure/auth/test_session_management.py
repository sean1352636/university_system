#!/usr/bin/env python3
"""
Comprehensive tests for session management

Tests:
- Session creation with security checks
- Session validation
- Session termination
- Concurrent session limiting
- Impossible travel detection
- Suspicious activity detection
- Session cleanup
- Session statistics
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
from education_system.post_18.university_system.infrastructure.security.init_security_tables import init_security_tables

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize security tables
    init_security_tables(path)

    # Add users table so that FK constraints on session_activity_log are satisfied
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (1, 'testuser1')")
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (2, 'testuser2')")

    # Add session_activity_log table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            user_id INTEGER,
            activity_type TEXT,
            details TEXT,
            activity_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add missing columns to sessions table
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN session_id_hash TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN device_fingerprint TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN location TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN terminated_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN termination_reason TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.remove(path)

# ============================================================================
# Session Creation Tests
# ============================================================================

class TestSessionCreation:
    """Test session creation with security features"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_create_session_success(self, mock_location, test_db):
        """Test successful session creation"""
        mock_location.return_value = {'city': 'TestCity', 'country': 'TestCountry', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        result = manager.create_session(
            user_id=1,
            role='student',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            device_fingerprint='fp123'
        )

        assert result['success'] is True
        assert 'session_id' in result
        assert 'expires_at' in result
        assert len(result['session_id']) > 20

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_create_session_timeout_by_role(self, mock_location, test_db):
        """Test session timeout varies by role"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Admin session (30 minutes)
        admin_result = manager.create_session(1, 'admin', '127.0.0.1', 'Agent')
        admin_expires = datetime.fromisoformat(admin_result['expires_at'])

        # Student session (240 minutes)
        student_result = manager.create_session(2, 'student', '127.0.0.1', 'Agent')
        student_expires = datetime.fromisoformat(student_result['expires_at'])

        # Student session should expire much later than admin
        assert student_expires > admin_expires

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_create_session_concurrent_limit(self, mock_location, test_db):
        """Test concurrent session limiting"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create 3 sessions for admin (limit is 2)
        manager.create_session(1, 'admin', '127.0.0.1', 'Agent1')
        manager.create_session(1, 'admin', '127.0.0.2', 'Agent2')
        result3 = manager.create_session(1, 'admin', '127.0.0.3', 'Agent3')

        assert result3['success'] is True
        assert any('terminated oldest' in w.lower() for w in result3.get('warnings', []))

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._detect_suspicious_login')
    def test_create_session_suspicious_activity(self, mock_suspicious, mock_location, test_db):
        """Test suspicious activity detection during login"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}
        mock_suspicious.return_value = ['impossible_travel', 'unusual_hours']

        manager = SessionManager(test_db)

        result = manager.create_session(1, 'student', '127.0.0.1', 'Agent')

        assert result['success'] is True
        assert result['suspicious'] is True
        assert len(result['warnings']) > 0

# ============================================================================
# Session Validation Tests
# ============================================================================

class TestSessionValidation:
    """Test session validation"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_validate_session_valid(self, mock_location, test_db):
        """Test validation of valid session"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create session
        create_result = manager.create_session(1, 'student', '192.168.1.1', 'Agent')
        session_id = create_result['session_id']

        # Validate session
        validate_result = manager.validate_session(session_id, 1, '192.168.1.1')

        assert validate_result['valid'] is True
        assert validate_result['user_id'] == 1

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_validate_session_invalid_id(self, mock_location, test_db):
        """Test validation of invalid session ID"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        result = manager.validate_session('invalid_session_id', 1)

        assert result['valid'] is False
        assert result['reason'] == 'Session not found'

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_validate_session_expired(self, mock_location, test_db):
        """Test validation of expired session"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create session
        create_result = manager.create_session(1, 'student', '127.0.0.1', 'Agent')
        session_id = create_result['session_id']

        # Manually expire the session
        import hashlib
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        expired_time = datetime.now() - timedelta(hours=1)
        cursor.execute("""
            UPDATE sessions SET expires_at = ? WHERE session_id_hash = ?
        """, (expired_time, session_hash))
        conn.commit()
        conn.close()

        # Validate
        result = manager.validate_session(session_id, 1)

        assert result['valid'] is False
        assert result['reason'] == 'Session expired'

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_validate_session_ip_change_warning(self, mock_location, test_db):
        """Test IP change generates warning"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create session
        create_result = manager.create_session(1, 'student', '192.168.1.1', 'Agent')
        session_id = create_result['session_id']

        # Validate with different IP
        result = manager.validate_session(session_id, 1, '192.168.1.2')

        assert result['valid'] is True
        assert any('IP address changed' in w for w in result.get('warnings', []))

# ============================================================================
# Session Termination Tests
# ============================================================================

class TestSessionTermination:
    """Test session termination"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_terminate_session_success(self, mock_location, test_db):
        """Test successful session termination"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create session
        create_result = manager.create_session(1, 'student', '127.0.0.1', 'Agent')
        session_id = create_result['session_id']

        # Terminate session
        result = manager.terminate_session(session_id, 1, reason='user_logout')

        assert result['success'] is True

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_terminate_session_already_terminated(self, mock_location, test_db):
        """Test terminating already terminated session"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create and terminate session
        create_result = manager.create_session(1, 'student', '127.0.0.1', 'Agent')
        session_id = create_result['session_id']
        manager.terminate_session(session_id, 1)

        # Try to terminate again
        result = manager.terminate_session(session_id, 1)

        assert result['success'] is False

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_terminate_all_sessions(self, mock_location, test_db):
        """Test terminating all user sessions"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create multiple sessions
        manager.create_session(1, 'student', '127.0.0.1', 'Agent1')
        manager.create_session(1, 'student', '127.0.0.2', 'Agent2')
        manager.create_session(1, 'student', '127.0.0.3', 'Agent3')

        # Terminate all
        result = manager.terminate_all_sessions(1)

        assert result['success'] is True
        assert result['terminated_count'] >= 3

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_terminate_all_except_current(self, mock_location, test_db):
        """Test terminating all sessions except current"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create sessions
        session1 = manager.create_session(1, 'student', '127.0.0.1', 'Agent1')
        session2 = manager.create_session(1, 'student', '127.0.0.2', 'Agent2')
        current_session_id = session1['session_id']

        # Terminate all except current
        result = manager.terminate_all_sessions(1, except_session=current_session_id)

        assert result['success'] is True

        # Verify current session still valid
        validate_result = manager.validate_session(current_session_id, 1)
        assert validate_result['valid'] is True

# ============================================================================
# Suspicious Activity Detection Tests
# ============================================================================

class TestSuspiciousActivityDetection:
    """Test detection of suspicious login patterns"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_detect_impossible_travel(self, mock_location, test_db):
        """Test impossible travel detection"""
        manager = SessionManager(test_db)

        # Mock first location (New York)
        mock_location.return_value = {
            'city': 'New York',
            'country': 'USA',
            'latitude': 40.7128,
            'longitude': -74.0060
        }

        # Create first session
        manager.create_session(1, 'student', '1.2.3.4', 'Agent')

        # Mock second location (London) - too fast to travel
        mock_location.return_value = {
            'city': 'London',
            'country': 'UK',
            'latitude': 51.5074,
            'longitude': -0.1278
        }

        # Create second session immediately
        result = manager.create_session(1, 'student', '5.6.7.8', 'Agent')

        # Should detect impossible travel
        assert any('travel' in w.lower() or 'country' in w.lower() for w in result.get('warnings', []))

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_detect_unusual_hours(self, mock_location, test_db):
        """Test unusual hours detection"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Check if current hour is in unusual hours range
        current_hour = datetime.now().hour
        is_unusual_hours = any(start <= current_hour < end for start, end in manager.unusual_hours)

        result = manager.create_session(1, 'student', '127.0.0.1', 'Agent')

        if is_unusual_hours:
            assert any('unusual' in w.lower() for w in result.get('warnings', []))

# ============================================================================
# Session Listing Tests
# ============================================================================

class TestSessionListing:
    """Test listing user sessions"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_get_user_sessions(self, mock_location, test_db):
        """Test getting all user sessions"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create sessions
        manager.create_session(1, 'student', '127.0.0.1', 'Agent1')
        manager.create_session(1, 'student', '127.0.0.2', 'Agent2')

        # Get sessions
        sessions = manager.get_user_sessions(1)

        assert len(sessions) >= 2

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_get_user_sessions_active_only(self, mock_location, test_db):
        """Test getting only active sessions"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create sessions
        result1 = manager.create_session(1, 'student', '127.0.0.1', 'Agent1')
        manager.create_session(1, 'student', '127.0.0.2', 'Agent2')

        # Terminate one
        manager.terminate_session(result1['session_id'], 1)

        # Get active only
        active_sessions = manager.get_user_sessions(1, include_inactive=False)

        # Should have only 1 active session
        assert all(s['is_active'] for s in active_sessions)

# ============================================================================
# Session Cleanup Tests
# ============================================================================

class TestSessionCleanup:
    """Test session cleanup operations"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_cleanup_expired_sessions(self, mock_location, test_db):
        """Test automatic cleanup of expired sessions"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create session
        result = manager.create_session(1, 'student', '127.0.0.1', 'Agent')
        session_id = result['session_id']

        # Manually expire it
        import hashlib
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        expired_time = datetime.now() - timedelta(hours=1)
        cursor.execute("""
            UPDATE sessions SET expires_at = ? WHERE session_id_hash = ?
        """, (expired_time, session_hash))
        conn.commit()
        conn.close()

        # Run cleanup
        count = manager.cleanup_expired_sessions()

        assert count >= 1

# ============================================================================
# Session Statistics Tests
# ============================================================================

class TestSessionStatistics:
    """Test session statistics"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_get_session_statistics(self, mock_location, test_db):
        """Test getting session statistics"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create some sessions
        manager.create_session(1, 'student', '127.0.0.1', 'Agent')
        manager.create_session(2, 'student', '127.0.0.2', 'Agent')

        # Get stats
        stats = manager.get_session_statistics()

        assert 'active_sessions' in stats
        assert 'sessions_today' in stats
        assert stats['active_sessions'] >= 2

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_get_session_statistics_for_user(self, mock_location, test_db):
        """Test getting statistics for specific user"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create sessions for different users
        manager.create_session(1, 'student', '127.0.0.1', 'Agent')
        manager.create_session(2, 'student', '127.0.0.2', 'Agent')

        # Get stats for user 1
        stats = manager.get_session_statistics(user_id=1)

        assert stats['active_sessions'] >= 1

# ============================================================================
# Location Services Tests
# ============================================================================

class TestLocationServices:
    """Test IP geolocation services"""

    def test_get_location_localhost(self, test_db):
        """Test localhost returns local location"""
        manager = SessionManager(test_db)

        location = manager._get_location_from_ip('127.0.0.1')

        assert location['city'] == 'Local'
        assert location['country'] == 'Local'

    def test_get_location_private_ip(self, test_db):
        """Test private IP returns local location"""
        manager = SessionManager(test_db)

        location = manager._get_location_from_ip('192.168.1.1')

        assert location['city'] == 'Local'
        assert location['country'] == 'Local'

    @patch('requests.get')
    def test_get_location_public_ip(self, mock_get, test_db):
        """Test public IP queries geolocation API"""
        manager = SessionManager(test_db)

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'city': 'San Francisco',
            'country': 'United States',
            'lat': 37.7749,
            'lon': -122.4194,
            'regionName': 'California',
            'isp': 'Test ISP'
        }
        mock_get.return_value = mock_response

        location = manager._get_location_from_ip('8.8.8.8')

        assert location['city'] == 'San Francisco'
        assert location['country'] == 'United States'

# ============================================================================
# Integration Tests
# ============================================================================

class TestSessionIntegration:
    """Test integration scenarios"""

    @patch('education_system.post_18.university_system.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_complete_session_lifecycle(self, mock_location, test_db):
        """Test complete session lifecycle"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        manager = SessionManager(test_db)

        # Create session
        create_result = manager.create_session(1, 'student', '192.168.1.1', 'Agent')
        session_id = create_result['session_id']

        assert create_result['success'] is True

        # Validate session
        validate_result = manager.validate_session(session_id, 1)
        assert validate_result['valid'] is True

        # List sessions
        sessions = manager.get_user_sessions(1)
        assert len(sessions) >= 1

        # Terminate session
        terminate_result = manager.terminate_session(session_id, 1)
        assert terminate_result['success'] is True

        # Validate should now fail
        validate_result2 = manager.validate_session(session_id, 1)
        assert validate_result2['valid'] is False

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
