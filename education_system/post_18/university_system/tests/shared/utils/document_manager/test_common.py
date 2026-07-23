"""Tests for document_manager._common"""
from unittest.mock import MagicMock, patch

from education_system.post_18.university_system.modules.shared.utils.document_manager import (
    _common,
)
from education_system.post_18.university_system.modules.shared.utils import document_manager as dm_pkg


def test_get_connection_falls_through_to_base():
    """If no override is set on the package, the wrapper uses the base."""
    with patch.object(_common, "_base_get_connection") as base:
        base.return_value = "real_conn"
        # Temporarily clear the package-level alias so the wrapper is forced
        # to use the base.
        original = dm_pkg.get_connection
        try:
            dm_pkg.get_connection = _common.get_connection  # same identity
            result = _common.get_connection("a", "b", k=1)
            base.assert_called_once_with("a", "b", k=1)
            assert result == "real_conn"
        finally:
            dm_pkg.get_connection = original


def test_get_connection_routes_to_package_override(monkeypatch):
    """When the package exposes a different callable, the wrapper uses it."""
    sentinel = MagicMock(return_value="overridden")
    monkeypatch.setattr(dm_pkg, "get_connection", sentinel)
    out = _common.get_connection("foo")
    sentinel.assert_called_once_with("foo")
    assert out == "overridden"


def test_get_current_user_and_set_auth_instance_exposed():
    """The module re-exports auth helpers used by mixin code."""
    assert callable(_common.get_current_user)
    assert callable(_common.set_auth_instance)


def test_log_event_fallback_when_email_unavailable(monkeypatch, capsys):
    """If the email subsystem is missing, log_event becomes a print fallback.
    We just verify the bound name is callable and accepts (level, message).
    """
    _common.log_event("info", "hello")  # no exception
