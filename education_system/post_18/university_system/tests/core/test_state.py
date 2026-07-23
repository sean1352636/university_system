"""Tests for university_system.modules.shared.utils.state."""
from education_system.post_18.university_system.modules.shared.utils import state


class TestAuthInstance:
    def setup_method(self):
        state.reset_state()

    def test_set_and_get_auth(self):
        marker = object()
        state.set_auth(marker)
        assert state.get_auth() is marker

    def test_default_auth_is_none(self):
        assert state.get_auth() is None


class TestConfig:
    def setup_method(self):
        state.reset_state()

    def test_set_and_get_config(self):
        state.set_config("debug", True)
        assert state.get_config("debug") is True

    def test_get_config_default(self):
        assert state.get_config("missing", "fallback") == "fallback"

    def test_get_config_missing_returns_none(self):
        assert state.get_config("missing") is None


class TestAppState:
    def setup_method(self):
        state.reset_state()

    def test_not_initialized_by_default(self):
        assert state.is_initialized() is False

    def test_initialize_marks_state(self):
        state.initialize_state()
        assert state.is_initialized() is True

    def test_reset_clears_initialization(self):
        state.initialize_state()
        state.reset_state()
        assert state.is_initialized() is False
