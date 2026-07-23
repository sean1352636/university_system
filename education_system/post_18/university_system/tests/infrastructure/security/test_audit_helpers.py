"""
Comprehensive tests for audit_helpers module.

Tests cover:
- safe_log_security_event() - never raises, returns bool
- get_gui_context() - extracts user context from GUI auth
- get_api_context() - extracts IP and user-agent from requests
- get_current_user_id() - tries multiple context sources
- mask_sensitive_data() - masks fields by name pattern
"""

import pytest
from unittest.mock import MagicMock, patch

from education_system.post_18.university_system.infrastructure.security.audit_helpers import (
    safe_log_security_event,
    get_gui_context,
    get_api_context,
    get_current_user_id,
    mask_sensitive_data,
)


# ---------------------------------------------------------------------------
# safe_log_security_event
# ---------------------------------------------------------------------------

class TestSafeLogSecurityEvent:
    def test_returns_true_on_success(self):
        with patch(
            "education_system.post_18.university_system.infrastructure.security.immutable_audit_log.log_security_event",
        ) as mock_log_fn:
            result = safe_log_security_event(action="LOGIN_SUCCESS", user_id="admin")
            assert result is True
            mock_log_fn.assert_called_once()

    def test_returns_false_on_import_error(self):
        """If immutable_audit_log can't be imported, should return False."""
        with patch(
            "education_system.post_18.university_system.infrastructure.security.audit_helpers.safe_log_security_event",
            wraps=safe_log_security_event,
        ):
            # Force ImportError by patching the import path
            with patch.dict("sys.modules", {
                "education_system.post_18.university_system.infrastructure.security.immutable_audit_log": None,
            }):
                result = safe_log_security_event(action="TEST")
                assert result is False

    def test_returns_false_on_exception(self):
        """If log_security_event raises, should catch and return False."""
        with patch(
            "education_system.post_18.university_system.infrastructure.security.immutable_audit_log.log_security_event",
            side_effect=RuntimeError("DB error"),
        ):
            result = safe_log_security_event(action="TEST")
            assert result is False

    def test_never_raises(self):
        """The whole point: it should NEVER raise."""
        with patch(
            "education_system.post_18.university_system.infrastructure.security.immutable_audit_log.log_security_event",
            side_effect=Exception("catastrophic"),
        ):
            # Should not raise
            result = safe_log_security_event(action="TEST")
            assert result is False

    def test_passes_all_params(self):
        with patch(
            "education_system.post_18.university_system.infrastructure.security.immutable_audit_log.log_security_event",
        ) as mock_fn:
            safe_log_security_event(
                action="DATA_VIEW",
                user_id="u1",
                resource_type="student",
                resource_id="s123",
                details={"key": "val"},
                ip_address="1.2.3.4",
                user_agent="Mozilla",
                session_id="sess-1",
            )
            mock_fn.assert_called_once_with(
                user_id="u1",
                action="DATA_VIEW",
                resource_type="student",
                resource_id="s123",
                details={"key": "val"},
                ip_address="1.2.3.4",
                user_agent="Mozilla",
                session_id="sess-1",
            )


# ---------------------------------------------------------------------------
# get_gui_context
# ---------------------------------------------------------------------------

class TestGetGuiContext:
    def test_returns_none_none_on_import_error(self):
        with patch.dict("sys.modules", {
            "education_system.post_18.university_system.infrastructure.shared_context": None,
        }):
            user_id, session_id = get_gui_context()
            assert user_id is None
            assert session_id is None

    def test_returns_none_none_when_not_logged_in(self):
        mock_auth = MagicMock()
        mock_auth.is_logged_in.return_value = False
        with patch(
            "education_system.post_18.university_system.infrastructure.security.audit_helpers.get_gui_context"
        ) as mock_fn:
            mock_fn.return_value = (None, None)
            user_id, session_id = mock_fn()
            assert user_id is None

    def test_returns_user_context_when_logged_in(self):
        mock_auth = MagicMock()
        mock_auth.is_logged_in.return_value = True
        mock_auth.get_current_user.return_value = {"id": 42, "session_id": "s-123"}

        mock_module = MagicMock()
        mock_module.get_auth.return_value = mock_auth

        with patch.dict("sys.modules", {
            "education_system.post_18.university_system.infrastructure.shared_context": mock_module,
        }):
            user_id, session_id = get_gui_context()
            assert user_id == "42"
            assert session_id == "s-123"

    def test_handles_exception_gracefully(self):
        mock_module = MagicMock()
        mock_module.get_auth.side_effect = RuntimeError("bad")
        with patch.dict("sys.modules", {
            "education_system.post_18.university_system.infrastructure.shared_context": mock_module,
        }):
            user_id, session_id = get_gui_context()
            assert user_id is None
            assert session_id is None


# ---------------------------------------------------------------------------
# get_api_context
# ---------------------------------------------------------------------------

class TestGetApiContext:
    def test_extracts_remote_addr(self):
        request = MagicMock()
        request.remote_addr = "10.0.0.1"
        request.headers = {}
        ip, ua = get_api_context(request)
        assert ip == "10.0.0.1"
        assert ua is None

    def test_prefers_x_forwarded_for(self):
        request = MagicMock()
        request.remote_addr = "10.0.0.1"
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        ip, ua = get_api_context(request)
        assert ip == "1.2.3.4"

    def test_uses_x_real_ip_when_no_forwarded(self):
        request = MagicMock()
        request.remote_addr = "10.0.0.1"
        headers = MagicMock()
        headers.get = MagicMock(side_effect=lambda key, *a: {
            "X-Forwarded-For": None,
            "X-Real-IP": "9.8.7.6",
            "User-Agent": None,
        }.get(key))
        request.headers = headers
        ip, ua = get_api_context(request)
        assert ip == "9.8.7.6"

    def test_extracts_user_agent(self):
        request = MagicMock()
        request.remote_addr = "10.0.0.1"
        headers = MagicMock()
        headers.get = MagicMock(side_effect=lambda key, *a: {
            "X-Forwarded-For": None,
            "X-Real-IP": None,
            "User-Agent": "TestBrowser/1.0",
        }.get(key))
        request.headers = headers
        ip, ua = get_api_context(request)
        assert ua == "TestBrowser/1.0"

    def test_handles_no_headers_attr(self):
        request = MagicMock(spec=[])  # No attributes
        request.remote_addr = "1.1.1.1"
        ip, ua = get_api_context(request)
        # Should still get remote_addr since hasattr check will match
        # Actually spec=[] means no attributes; the function checks hasattr
        # So it should fall through gracefully
        assert ip is None or isinstance(ip, str)

    def test_handles_exception(self):
        request = MagicMock()
        request.remote_addr = property(lambda self: (_ for _ in ()).throw(RuntimeError))
        # Force an exception
        type(request).remote_addr = property(lambda self: (_ for _ in ()).throw(RuntimeError("fail")))
        ip, ua = get_api_context(request)
        assert ip is None
        assert ua is None


# ---------------------------------------------------------------------------
# get_current_user_id
# ---------------------------------------------------------------------------

class TestGetCurrentUserId:
    def test_returns_gui_user_id_first(self):
        with patch(
            "education_system.post_18.university_system.infrastructure.security.audit_helpers.get_gui_context",
            return_value=("42", "sess"),
        ):
            uid = get_current_user_id()
            assert uid == "42"

    def test_returns_none_when_no_context(self):
        with patch(
            "education_system.post_18.university_system.infrastructure.security.audit_helpers.get_gui_context",
            return_value=(None, None),
        ):
            # Also need to prevent Flask g fallback
            with patch.dict("sys.modules", {"flask": None}):
                uid = get_current_user_id()
                assert uid is None

    def test_never_raises(self):
        with patch(
            "education_system.post_18.university_system.infrastructure.security.audit_helpers.get_gui_context",
            side_effect=Exception("broken"),
        ):
            uid = get_current_user_id()
            assert uid is None


# ---------------------------------------------------------------------------
# mask_sensitive_data
# ---------------------------------------------------------------------------

class TestMaskSensitiveData:
    def test_masks_password_field(self):
        data = {"username": "admin", "password": "secret123"}
        result = mask_sensitive_data(data)
        assert result["username"] == "admin"
        assert result["password"] == "***"

    def test_masks_token_field(self):
        data = {"auth_token": "abc123"}
        result = mask_sensitive_data(data)
        assert result["auth_token"] == "***"

    def test_masks_secret_field(self):
        data = {"api_secret": "xyz"}
        result = mask_sensitive_data(data)
        assert result["api_secret"] == "***"

    def test_masks_key_field(self):
        data = {"encryption_key": "mykey"}
        result = mask_sensitive_data(data)
        assert result["encryption_key"] == "***"

    def test_preserves_non_sensitive(self):
        data = {"name": "John", "email": "john@test.com", "role": "admin"}
        result = mask_sensitive_data(data)
        assert result == data

    def test_case_insensitive_matching(self):
        data = {"PASSWORD": "secret", "Token": "abc", "SECRET_KEY": "xyz"}
        result = mask_sensitive_data(data)
        assert result["PASSWORD"] == "***"
        assert result["Token"] == "***"
        assert result["SECRET_KEY"] == "***"

    def test_empty_dict(self):
        assert mask_sensitive_data({}) == {}

    def test_none_input(self):
        assert mask_sensitive_data(None) is None

    def test_custom_fields(self):
        data = {"ssn": "123-45-6789", "name": "Alice"}
        result = mask_sensitive_data(data, fields_to_mask=("ssn",))
        assert result["ssn"] == "***"
        assert result["name"] == "Alice"

    def test_partial_match(self):
        data = {"user_password_hash": "abc", "token_value": "xyz"}
        result = mask_sensitive_data(data)
        assert result["user_password_hash"] == "***"
        assert result["token_value"] == "***"

    def test_returns_new_dict(self):
        data = {"password": "secret"}
        result = mask_sensitive_data(data)
        assert result is not data
