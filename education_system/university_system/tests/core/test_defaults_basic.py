"""Tests for university_system.core.defaults."""
import importlib

import pytest

from education_system.university_system.core import defaults


@pytest.fixture
def fresh_defaults(monkeypatch):
    """Reload `defaults` so module-level env-var reads happen in test."""
    monkeypatch.setenv("UNIVERSITY_NAME", "Test University")
    monkeypatch.setenv("UNIVERSITY_EMAIL_DOMAIN", "test.edu")
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", "test_admin")
    yield importlib.reload(defaults)
    importlib.reload(defaults)  # restore real values


class TestEnvHelpers:
    def test_get_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("__NEVER_SET_X__", raising=False)
        assert defaults._get_env("__NEVER_SET_X__", "fallback") == "fallback"

    def test_get_env_uses_env(self, monkeypatch):
        monkeypatch.setenv("__TEST_VAR__", "set")
        assert defaults._get_env("__TEST_VAR__", "fallback") == "set"

    def test_get_env_int_parses(self, monkeypatch):
        monkeypatch.setenv("__TEST_INT__", "42")
        assert defaults._get_env_int("__TEST_INT__", 0) == 42

    def test_get_env_int_falls_back_on_bad_value(self, monkeypatch):
        monkeypatch.setenv("__TEST_INT__", "abc")
        assert defaults._get_env_int("__TEST_INT__", 99) == 99


class TestGenerateRandomPassword:
    def test_default_length(self):
        pw = defaults._generate_random_password()
        assert len(pw) == 16

    def test_custom_length(self):
        assert len(defaults._generate_random_password(24)) == 24

    def test_each_call_unique(self):
        passwords = {defaults._generate_random_password() for _ in range(10)}
        assert len(passwords) == 10


class TestRequirePasswordEnv:
    def test_uses_env_when_set(self, monkeypatch):
        monkeypatch.setenv("__PW_TEST__", "secret123")
        assert defaults._require_password_env("__PW_TEST__", "test_role") == "secret123"

    def test_generates_when_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("__NEVER_PW__", raising=False)
        # Clear any leftover generated passwords from previous tests
        defaults._generated_passwords.clear()
        result = defaults._require_password_env("__NEVER_PW__", "test_role_xyz")
        assert isinstance(result, str)
        assert len(result) == 16
        assert defaults._generated_passwords.get("test_role_xyz") == result
        defaults._generated_passwords.clear()


class TestPrintGeneratedPasswords:
    def test_silent_when_empty(self, capsys):
        defaults._generated_passwords.clear()
        defaults.print_generated_passwords()
        out = capsys.readouterr().out
        assert out == ""

    def test_prints_and_clears(self, capsys):
        defaults._generated_passwords["admin"] = "secretvalue123"
        defaults.print_generated_passwords()
        out = capsys.readouterr().out
        assert "DEFAULT_ADMIN_PASSWORD" in out
        # Cleared after printing
        assert defaults._generated_passwords == {}


class TestFallbackEmails:
    def test_admin_context(self):
        assert defaults.get_fallback_email("admin") == defaults.SYSTEM_ADMIN_EMAIL

    def test_support_context(self):
        assert defaults.get_fallback_email("support") == defaults.SYSTEM_SUPPORT_EMAIL

    def test_noreply_context(self):
        assert defaults.get_fallback_email("noreply") == defaults.UNIVERSITY_NOREPLY_EMAIL

    def test_unknown_falls_back_to_admin(self):
        assert defaults.get_fallback_email("mystery") == defaults.SYSTEM_ADMIN_EMAIL


class TestUserDataHelpers:
    def test_default_student_data_keys(self):
        d = defaults.get_default_student_data()
        assert set(d.keys()) == {"student_id", "username", "email",
                                  "first_name", "last_name", "password"}

    def test_default_admin_data_keys(self):
        d = defaults.get_default_admin_data()
        assert set(d.keys()) == {"username", "email", "first_name", "last_name", "password"}

    def test_get_admin_email_returns_system_admin(self):
        assert defaults.get_admin_email() == defaults.SYSTEM_ADMIN_EMAIL


class TestEnvOverrides:
    def test_env_overrides_module_constants(self, fresh_defaults):
        assert fresh_defaults.UNIVERSITY_NAME == "Test University"
        assert fresh_defaults.UNIVERSITY_EMAIL_DOMAIN == "test.edu"
        assert fresh_defaults.DEFAULT_ADMIN_USERNAME == "test_admin"
        assert fresh_defaults.UNIVERSITY_NOREPLY_EMAIL.endswith("@test.edu")


class TestDemoMode:
    def test_demo_mode_is_bool(self):
        assert isinstance(defaults.DEMO_MODE, bool)
