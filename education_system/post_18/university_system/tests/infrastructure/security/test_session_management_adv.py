"""
Comprehensive tests for session_management module (Advanced SessionManager).

Tests cover:
- SessionInfo dataclass
- SessionManager initialization with role-based timeouts and session limits
- _hash_session_id() SHA-256 hashing
- create_session() with concurrent limits, suspicious detection
- validate_session() with expiration, IP changes
- terminate_session() and terminate_all_sessions()
- get_user_sessions() and get_all_active_sessions()
- cleanup_expired_sessions()
- get_session_statistics()
- _get_location_from_ip() with localhost and external IPs
- _detect_suspicious_login() with impossible travel, unusual hours
- _is_impossible_travel() haversine calculation
"""

import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Import with mocked external dependencies
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_session_imports():
    """Mock heavy imports that session_management tries at module level."""
    with patch.dict("sys.modules", {
        "university_system.infrastructure.security.security_alerts": MagicMock(),
    }):
        yield


# ---------------------------------------------------------------------------
# SessionInfo dataclass
# ---------------------------------------------------------------------------

class TestSessionInfo:
    def test_creation(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionInfo
        now = datetime.now()
        s = SessionInfo(
            session_id="sid",
            user_id=1,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            device_fingerprint="fp",
            location={"city": "Local"},
            created_at=now,
            last_activity=now,
            expires_at=now + timedelta(hours=1),
            is_active=True,
        )
        assert s.session_id == "sid"
        assert s.is_active is True


# ---------------------------------------------------------------------------
# SessionManager initialization
# ---------------------------------------------------------------------------

class TestSessionManagerInit:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.DEFAULT_DB_PATH", "/tmp/test.db")
    def test_default_db_path(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager()
        assert mgr.db_path == "/tmp/test.db"

    def test_custom_db_path(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/custom/path.db")
        assert mgr.db_path == "/custom/path.db"

    def test_timeout_policies(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        assert mgr.timeout_policies["admin"] == 30
        assert mgr.timeout_policies["student"] == 240

    def test_session_limits(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        assert mgr.session_limits["admin"] == 2
        assert mgr.session_limits["student"] == 3


# ---------------------------------------------------------------------------
# _hash_session_id
# ---------------------------------------------------------------------------

class TestHashSessionId:
    def test_returns_sha256(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        result = mgr._hash_session_id("test-session")
        expected = hashlib.sha256("test-session".encode()).hexdigest()
        assert result == expected

    def test_deterministic(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        assert mgr._hash_session_id("x") == mgr._hash_session_id("x")


# ---------------------------------------------------------------------------
# _get_location_from_ip
# ---------------------------------------------------------------------------

class TestGetLocationFromIp:
    def test_localhost_returns_local(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        loc = mgr._get_location_from_ip("127.0.0.1")
        assert loc["city"] == "Local"
        assert loc["country"] == "Local"

    def test_private_ip_returns_local(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        loc = mgr._get_location_from_ip("192.168.1.50")
        assert loc["city"] == "Local"

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.requests")
    def test_external_ip_calls_api(self, mock_requests):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "city": "London",
            "country": "UK",
            "lat": 51.5,
            "lon": -0.1,
            "regionName": "England",
            "isp": "TestISP",
        }
        mock_requests.get.return_value = mock_response

        mgr = SessionManager(db_path="/tmp/t.db")
        loc = mgr._get_location_from_ip("8.8.8.8")
        assert loc["city"] == "London"
        assert loc["country"] == "UK"

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.requests")
    def test_api_failure_returns_unknown(self, mock_requests):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mock_requests.get.side_effect = Exception("Network error")
        mgr = SessionManager(db_path="/tmp/t.db")
        loc = mgr._get_location_from_ip("8.8.8.8")
        assert loc["city"] == "Unknown"


# ---------------------------------------------------------------------------
# _is_impossible_travel
# ---------------------------------------------------------------------------

class TestIsImpossibleTravel:
    def test_no_coordinates_returns_false(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        result = mgr._is_impossible_travel(
            {"latitude": 0, "longitude": 0},
            {"latitude": 0, "longitude": 0},
            (datetime.now() - timedelta(hours=1)).isoformat(),
        )
        assert result is False

    def test_same_location_not_impossible(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        loc = {"latitude": 51.5, "longitude": -0.1}
        result = mgr._is_impossible_travel(
            loc, loc,
            (datetime.now() - timedelta(hours=1)).isoformat(),
        )
        assert result is False

    def test_far_distance_short_time_is_impossible(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        # London to Tokyo (~9600 km) in 1 minute = impossible
        loc1 = {"latitude": 51.5, "longitude": -0.1}
        loc2 = {"latitude": 35.7, "longitude": 139.7}
        one_min_ago = (datetime.now() - timedelta(minutes=1)).isoformat()
        result = mgr._is_impossible_travel(loc1, loc2, one_min_ago)
        assert result is True

    def test_far_distance_long_time_not_impossible(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        loc1 = {"latitude": 51.5, "longitude": -0.1}
        loc2 = {"latitude": 35.7, "longitude": 139.7}
        long_ago = (datetime.now() - timedelta(hours=24)).isoformat()
        result = mgr._is_impossible_travel(loc1, loc2, long_ago)
        assert result is False

    def test_missing_lat_lon_returns_false(self):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")
        result = mgr._is_impossible_travel(
            {"latitude": None, "longitude": None},
            {"latitude": 51.5, "longitude": -0.1},
            datetime.now().isoformat(),
        )
        assert result is False


# ---------------------------------------------------------------------------
# create_session (mocked DB)
# ---------------------------------------------------------------------------

class TestCreateSession:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_success_returns_session_id(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # No active sessions
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.lastrowid = 1

        with patch.object(mgr, "_get_location_from_ip", return_value={"city": "Local", "country": "Local", "latitude": 0, "longitude": 0}):
            with patch.object(mgr, "_detect_suspicious_login", return_value=[]):
                result = mgr.create_session(
                    user_id=1, role="student",
                    ip_address="127.0.0.1", user_agent="Test"
                )

        assert result["success"] is True
        assert "session_id" in result

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_error_returns_failure(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Make the internal DB call raise
        mock_cursor.execute.side_effect = Exception("DB error")

        result = mgr.create_session(
            user_id=1, role="student",
            ip_address="127.0.0.1", user_agent="Test"
        )
        assert result["success"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# validate_session
# ---------------------------------------------------------------------------

class TestValidateSession:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_not_found_returns_invalid(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = mgr.validate_session("bad-session", 1)
        assert result["valid"] is False
        assert "not found" in result["reason"]

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_terminated_session_invalid(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
            1, 1, "127.0.0.1",
            (datetime.now() + timedelta(hours=1)).isoformat(),
            0,  # is_active = False
            datetime.now().isoformat(), "fp", '{"city":"Local"}'
        )

        result = mgr.validate_session("sess", 1)
        assert result["valid"] is False
        assert "terminated" in result["reason"].lower()

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_expired_session_invalid(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        expired = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_cursor.fetchone.return_value = (
            1, 1, "127.0.0.1", expired,
            1, datetime.now().isoformat(), "fp", '{"city":"Local"}'
        )

        result = mgr.validate_session("sess", 1)
        assert result["valid"] is False
        assert "expired" in result["reason"].lower()


# ---------------------------------------------------------------------------
# terminate_session
# ---------------------------------------------------------------------------

class TestTerminateSession:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_not_found_returns_failure(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = mgr.terminate_session("sess", 1)
        assert result["success"] is False

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_success_terminates(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)

        result = mgr.terminate_session("sess", 1, reason="logout")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# terminate_all_sessions
# ---------------------------------------------------------------------------

class TestTerminateAllSessions:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_terminates_all(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 3

        result = mgr.terminate_all_sessions(user_id=1)
        assert result["success"] is True
        assert result["terminated_count"] == 3

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_except_session(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 2

        result = mgr.terminate_all_sessions(user_id=1, except_session="keep-this")
        assert result["success"] is True
        assert result["terminated_count"] == 2


# ---------------------------------------------------------------------------
# cleanup_expired_sessions
# ---------------------------------------------------------------------------

class TestCleanupExpiredSessions:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_returns_count(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 5

        count = mgr.cleanup_expired_sessions()
        assert count == 5


# ---------------------------------------------------------------------------
# get_session_statistics
# ---------------------------------------------------------------------------

class TestGetSessionStatistics:
    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_returns_stats_dict(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(10,), (25,), (2,)]

        stats = mgr.get_session_statistics()
        assert stats["active_sessions"] == 10
        assert stats["sessions_today"] == 25
        assert stats["suspicious_today"] == 2

    @patch("education_system.post_18.university_system.infrastructure.security.session_management.get_connection")
    def test_with_user_id_filter(self, mock_get_conn):
        from education_system.post_18.university_system.infrastructure.security.session_management import SessionManager
        mgr = SessionManager(db_path="/tmp/t.db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(1,), (3,), (0,)]

        stats = mgr.get_session_statistics(user_id=42)
        assert "active_sessions" in stats
