#!/usr/bin/env python3
"""
Comprehensive tests for infrastructure validation - Config Validators module.

Tests validate_email_config, validate_api_config, and validate_sms_config
for required fields, type checking, range validation, and enum validation.
"""

import pytest

from education_system.university_system.infrastructure.validation.config_validators import (
    validate_email_config,
    validate_api_config,
    validate_sms_config,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_email_config():
    """Minimal valid email configuration."""
    return {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "sender_email": "noreply@example.com",
    }


@pytest.fixture
def full_email_config(valid_email_config):
    """Full email configuration with all optional keys."""
    return {
        **valid_email_config,
        "use_tls": True,
        "max_retries": 3,
        "send_delay": 1.5,
        "log_level": "INFO",
        "attachment_size_limit": 10_000_000,
    }


@pytest.fixture
def valid_api_config():
    """Minimal valid API configuration."""
    return {
        "host": "0.0.0.0",
        "port": 5000,
    }


@pytest.fixture
def full_api_config(valid_api_config):
    """Full API configuration with all optional keys."""
    return {
        **valid_api_config,
        "debug": False,
        "ssl_enabled": True,
        "rate_limiting": {
            "enabled": True,
            "requests_per_minute": 60,
        },
        "max_content_length": 16_777_216,
        "jwt": {
            "algorithm": "HS256",
        },
    }


# ===========================================================================
# validate_email_config
# ===========================================================================

class TestValidateEmailConfig:
    """Tests for validate_email_config."""

    # --- valid configs ---

    def test_minimal_valid(self, valid_email_config):
        result = validate_email_config(valid_email_config)
        assert result.is_valid, f"Unexpected errors: {result.errors}"
        assert result.field == "email_config"

    def test_full_valid(self, full_email_config):
        result = validate_email_config(full_email_config)
        assert result.is_valid, f"Unexpected errors: {result.errors}"

    def test_value_is_original_config(self, valid_email_config):
        result = validate_email_config(valid_email_config)
        assert result.value is valid_email_config

    # --- missing required keys ---

    def test_missing_smtp_server(self, valid_email_config):
        del valid_email_config["smtp_server"]
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("smtp_server" in e for e in result.errors)

    def test_missing_smtp_port(self, valid_email_config):
        del valid_email_config["smtp_port"]
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("smtp_port" in e for e in result.errors)

    def test_missing_sender_email(self, valid_email_config):
        del valid_email_config["sender_email"]
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("sender_email" in e for e in result.errors)

    def test_empty_config(self):
        result = validate_email_config({})
        assert not result.is_valid
        assert len(result.errors) >= 3  # All 3 required keys missing

    # --- wrong types for required keys ---

    def test_smtp_server_wrong_type(self, valid_email_config):
        valid_email_config["smtp_server"] = 123
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("smtp_server" in e and "str" in e for e in result.errors)

    def test_smtp_port_wrong_type(self, valid_email_config):
        valid_email_config["smtp_port"] = "587"
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("smtp_port" in e and "int" in e for e in result.errors)

    def test_sender_email_wrong_type(self, valid_email_config):
        valid_email_config["sender_email"] = 42
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("sender_email" in e and "str" in e for e in result.errors)

    # --- smtp_port range ---

    def test_smtp_port_zero(self, valid_email_config):
        valid_email_config["smtp_port"] = 0
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("smtp_port" in e for e in result.errors)

    def test_smtp_port_negative(self, valid_email_config):
        valid_email_config["smtp_port"] = -1
        result = validate_email_config(valid_email_config)
        assert not result.is_valid

    def test_smtp_port_above_max(self, valid_email_config):
        valid_email_config["smtp_port"] = 65536
        result = validate_email_config(valid_email_config)
        assert not result.is_valid

    def test_smtp_port_boundary_min(self, valid_email_config):
        valid_email_config["smtp_port"] = 1
        result = validate_email_config(valid_email_config)
        assert result.is_valid

    def test_smtp_port_boundary_max(self, valid_email_config):
        valid_email_config["smtp_port"] = 65535
        result = validate_email_config(valid_email_config)
        assert result.is_valid

    # --- sender_email validation ---

    def test_invalid_sender_email(self, valid_email_config):
        valid_email_config["sender_email"] = "not-an-email"
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("sender_email" in e and "valid email" in e for e in result.errors)

    def test_valid_sender_email_formats(self, valid_email_config):
        for email in ["a@b.com", "user+tag@domain.org", "test.user@sub.domain.co.uk"]:
            valid_email_config["sender_email"] = email
            result = validate_email_config(valid_email_config)
            assert result.is_valid, f"Expected valid for email {email!r}: {result.errors}"

    # --- optional: use_tls ---

    def test_use_tls_valid(self, valid_email_config):
        valid_email_config["use_tls"] = True
        assert validate_email_config(valid_email_config).is_valid
        valid_email_config["use_tls"] = False
        assert validate_email_config(valid_email_config).is_valid

    def test_use_tls_wrong_type(self, valid_email_config):
        valid_email_config["use_tls"] = "yes"
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("use_tls" in e and "bool" in e for e in result.errors)

    # --- optional: max_retries ---

    def test_max_retries_valid(self, valid_email_config):
        valid_email_config["max_retries"] = 0
        assert validate_email_config(valid_email_config).is_valid
        valid_email_config["max_retries"] = 5
        assert validate_email_config(valid_email_config).is_valid

    def test_max_retries_negative(self, valid_email_config):
        valid_email_config["max_retries"] = -1
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("max_retries" in e and ">= 0" in e for e in result.errors)

    def test_max_retries_wrong_type(self, valid_email_config):
        valid_email_config["max_retries"] = 3.5
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("max_retries" in e and "int" in e for e in result.errors)

    # --- optional: send_delay ---

    def test_send_delay_valid_int(self, valid_email_config):
        valid_email_config["send_delay"] = 0
        assert validate_email_config(valid_email_config).is_valid

    def test_send_delay_valid_float(self, valid_email_config):
        valid_email_config["send_delay"] = 1.5
        assert validate_email_config(valid_email_config).is_valid

    def test_send_delay_negative(self, valid_email_config):
        valid_email_config["send_delay"] = -0.5
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("send_delay" in e and ">= 0" in e for e in result.errors)

    def test_send_delay_wrong_type(self, valid_email_config):
        valid_email_config["send_delay"] = "fast"
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("send_delay" in e and "number" in e for e in result.errors)

    # --- optional: log_level ---

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_log_level_valid(self, valid_email_config, level):
        valid_email_config["log_level"] = level
        assert validate_email_config(valid_email_config).is_valid

    def test_log_level_invalid(self, valid_email_config):
        valid_email_config["log_level"] = "TRACE"
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("log_level" in e for e in result.errors)

    def test_log_level_wrong_type(self, valid_email_config):
        valid_email_config["log_level"] = 42
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("log_level" in e and "str" in e for e in result.errors)

    def test_log_level_case_sensitive_input(self, valid_email_config):
        # The validator does v.upper(), so "info" should work
        valid_email_config["log_level"] = "info"
        result = validate_email_config(valid_email_config)
        assert result.is_valid

    # --- optional: attachment_size_limit ---

    def test_attachment_size_limit_valid(self, valid_email_config):
        valid_email_config["attachment_size_limit"] = 1024
        assert validate_email_config(valid_email_config).is_valid

    def test_attachment_size_limit_zero(self, valid_email_config):
        valid_email_config["attachment_size_limit"] = 0
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("attachment_size_limit" in e and "> 0" in e for e in result.errors)

    def test_attachment_size_limit_negative(self, valid_email_config):
        valid_email_config["attachment_size_limit"] = -100
        result = validate_email_config(valid_email_config)
        assert not result.is_valid

    def test_attachment_size_limit_wrong_type(self, valid_email_config):
        valid_email_config["attachment_size_limit"] = 10.5
        result = validate_email_config(valid_email_config)
        assert not result.is_valid
        assert any("attachment_size_limit" in e and "int" in e for e in result.errors)

    # --- extra keys are silently ignored ---

    def test_extra_keys_ignored(self, valid_email_config):
        valid_email_config["unknown_key"] = "anything"
        result = validate_email_config(valid_email_config)
        assert result.is_valid


# ===========================================================================
# validate_api_config
# ===========================================================================

class TestValidateApiConfig:
    """Tests for validate_api_config."""

    # --- valid configs ---

    def test_minimal_valid(self, valid_api_config):
        result = validate_api_config(valid_api_config)
        assert result.is_valid, f"Unexpected errors: {result.errors}"
        assert result.field == "api_config"

    def test_full_valid(self, full_api_config):
        result = validate_api_config(full_api_config)
        assert result.is_valid, f"Unexpected errors: {result.errors}"

    def test_value_is_original_config(self, valid_api_config):
        result = validate_api_config(valid_api_config)
        assert result.value is valid_api_config

    # --- missing required keys ---

    def test_missing_host(self, valid_api_config):
        del valid_api_config["host"]
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("host" in e for e in result.errors)

    def test_missing_port(self, valid_api_config):
        del valid_api_config["port"]
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("port" in e for e in result.errors)

    def test_empty_config(self):
        result = validate_api_config({})
        assert not result.is_valid
        assert len(result.errors) >= 2

    # --- wrong types for required keys ---

    def test_host_wrong_type(self, valid_api_config):
        valid_api_config["host"] = 127
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("host" in e and "str" in e for e in result.errors)

    def test_port_wrong_type(self, valid_api_config):
        valid_api_config["port"] = "5000"
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("port" in e and "int" in e for e in result.errors)

    # --- port range ---

    def test_port_zero(self, valid_api_config):
        valid_api_config["port"] = 0
        result = validate_api_config(valid_api_config)
        assert not result.is_valid

    def test_port_negative(self, valid_api_config):
        valid_api_config["port"] = -1
        result = validate_api_config(valid_api_config)
        assert not result.is_valid

    def test_port_above_max(self, valid_api_config):
        valid_api_config["port"] = 65536
        result = validate_api_config(valid_api_config)
        assert not result.is_valid

    def test_port_boundary_min(self, valid_api_config):
        valid_api_config["port"] = 1
        assert validate_api_config(valid_api_config).is_valid

    def test_port_boundary_max(self, valid_api_config):
        valid_api_config["port"] = 65535
        assert validate_api_config(valid_api_config).is_valid

    def test_port_common_values(self, valid_api_config):
        for port in [80, 443, 5000, 8080, 8443]:
            valid_api_config["port"] = port
            assert validate_api_config(valid_api_config).is_valid

    # --- optional: debug / ssl_enabled ---

    def test_debug_valid(self, valid_api_config):
        valid_api_config["debug"] = True
        assert validate_api_config(valid_api_config).is_valid
        valid_api_config["debug"] = False
        assert validate_api_config(valid_api_config).is_valid

    def test_debug_wrong_type(self, valid_api_config):
        valid_api_config["debug"] = 1
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("debug" in e and "bool" in e for e in result.errors)

    def test_ssl_enabled_valid(self, valid_api_config):
        valid_api_config["ssl_enabled"] = True
        assert validate_api_config(valid_api_config).is_valid

    def test_ssl_enabled_wrong_type(self, valid_api_config):
        valid_api_config["ssl_enabled"] = "true"
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("ssl_enabled" in e and "bool" in e for e in result.errors)

    # --- optional: rate_limiting ---

    def test_rate_limiting_valid(self, valid_api_config):
        valid_api_config["rate_limiting"] = {
            "enabled": True,
            "requests_per_minute": 60,
        }
        assert validate_api_config(valid_api_config).is_valid

    def test_rate_limiting_wrong_type(self, valid_api_config):
        valid_api_config["rate_limiting"] = "on"
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("rate_limiting" in e and "dict" in e for e in result.errors)

    def test_rate_limiting_enabled_wrong_type(self, valid_api_config):
        valid_api_config["rate_limiting"] = {"enabled": "yes"}
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("rate_limiting.enabled" in e for e in result.errors)

    def test_rate_limiting_rpm_wrong_type(self, valid_api_config):
        valid_api_config["rate_limiting"] = {"requests_per_minute": "sixty"}
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("requests_per_minute" in e for e in result.errors)

    def test_rate_limiting_rpm_zero(self, valid_api_config):
        valid_api_config["rate_limiting"] = {"requests_per_minute": 0}
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("requests_per_minute" in e and "> 0" in e for e in result.errors)

    def test_rate_limiting_rpm_negative(self, valid_api_config):
        valid_api_config["rate_limiting"] = {"requests_per_minute": -10}
        result = validate_api_config(valid_api_config)
        assert not result.is_valid

    def test_rate_limiting_empty_dict(self, valid_api_config):
        valid_api_config["rate_limiting"] = {}
        assert validate_api_config(valid_api_config).is_valid

    # --- optional: max_content_length ---

    def test_max_content_length_valid(self, valid_api_config):
        valid_api_config["max_content_length"] = 16_777_216
        assert validate_api_config(valid_api_config).is_valid

    def test_max_content_length_zero(self, valid_api_config):
        valid_api_config["max_content_length"] = 0
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("max_content_length" in e and "> 0" in e for e in result.errors)

    def test_max_content_length_negative(self, valid_api_config):
        valid_api_config["max_content_length"] = -1
        result = validate_api_config(valid_api_config)
        assert not result.is_valid

    def test_max_content_length_wrong_type(self, valid_api_config):
        valid_api_config["max_content_length"] = 16.5
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("max_content_length" in e and "int" in e for e in result.errors)

    # --- optional: jwt ---

    def test_jwt_valid(self, valid_api_config):
        valid_api_config["jwt"] = {"algorithm": "HS256"}
        assert validate_api_config(valid_api_config).is_valid

    @pytest.mark.parametrize("algo", ["HS256", "HS384", "HS512"])
    def test_jwt_all_valid_algorithms(self, valid_api_config, algo):
        valid_api_config["jwt"] = {"algorithm": algo}
        assert validate_api_config(valid_api_config).is_valid

    def test_jwt_invalid_algorithm(self, valid_api_config):
        valid_api_config["jwt"] = {"algorithm": "RS256"}
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("jwt.algorithm" in e for e in result.errors)

    def test_jwt_algorithm_wrong_type(self, valid_api_config):
        valid_api_config["jwt"] = {"algorithm": 256}
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("jwt.algorithm" in e and "str" in e for e in result.errors)

    def test_jwt_wrong_type(self, valid_api_config):
        valid_api_config["jwt"] = "HS256"
        result = validate_api_config(valid_api_config)
        assert not result.is_valid
        assert any("jwt" in e and "dict" in e for e in result.errors)

    def test_jwt_empty_dict(self, valid_api_config):
        valid_api_config["jwt"] = {}
        assert validate_api_config(valid_api_config).is_valid

    # --- extra keys ignored ---

    def test_extra_keys_ignored(self, valid_api_config):
        valid_api_config["custom_setting"] = "anything"
        assert validate_api_config(valid_api_config).is_valid


# ===========================================================================
# validate_sms_config
# ===========================================================================

class TestValidateSmsConfig:
    """Tests for validate_sms_config."""

    def test_empty_config_valid(self):
        result = validate_sms_config({})
        assert result.is_valid
        assert result.field == "sms_config"

    @pytest.mark.parametrize("provider", ["twilio", "aws_sns", "email_gateway", "mock"])
    def test_valid_primary_providers(self, provider):
        result = validate_sms_config({"primary_provider": provider})
        assert result.is_valid, f"Expected valid for provider {provider!r}: {result.errors}"

    @pytest.mark.parametrize("provider", ["twilio", "aws_sns", "email_gateway", "mock"])
    def test_valid_fallback_providers(self, provider):
        result = validate_sms_config({"fallback_provider": provider})
        assert result.is_valid

    def test_both_providers_valid(self):
        config = {
            "primary_provider": "twilio",
            "fallback_provider": "aws_sns",
        }
        result = validate_sms_config(config)
        assert result.is_valid

    def test_null_fallback_accepted(self):
        config = {"fallback_provider": None}
        result = validate_sms_config(config)
        assert result.is_valid

    def test_null_primary_accepted(self):
        config = {"primary_provider": None}
        result = validate_sms_config(config)
        assert result.is_valid

    def test_invalid_primary_provider(self):
        result = validate_sms_config({"primary_provider": "vonage"})
        assert not result.is_valid
        assert any("primary_provider" in e for e in result.errors)

    def test_invalid_fallback_provider(self):
        result = validate_sms_config({"fallback_provider": "unknown"})
        assert not result.is_valid
        assert any("fallback_provider" in e for e in result.errors)

    def test_primary_provider_wrong_type(self):
        result = validate_sms_config({"primary_provider": 123})
        assert not result.is_valid
        assert any("primary_provider" in e and "str" in e for e in result.errors)

    def test_fallback_provider_wrong_type(self):
        result = validate_sms_config({"fallback_provider": True})
        assert not result.is_valid
        assert any("fallback_provider" in e and "str" in e for e in result.errors)

    def test_value_is_original_config(self):
        config = {"primary_provider": "twilio"}
        result = validate_sms_config(config)
        assert result.value is config

    def test_extra_keys_ignored(self):
        config = {
            "primary_provider": "twilio",
            "api_key": "secret123",
            "region": "us-east-1",
        }
        result = validate_sms_config(config)
        assert result.is_valid

    def test_multiple_errors_collected(self):
        config = {
            "primary_provider": "invalid1",
            "fallback_provider": "invalid2",
        }
        result = validate_sms_config(config)
        assert not result.is_valid
        assert len(result.errors) == 2


# ===========================================================================
# Cross-cutting / integration tests
# ===========================================================================

class TestConfigValidatorIntegration:
    """Cross-cutting tests that verify common behaviour across config validators."""

    def test_all_validators_return_validation_result(
        self, valid_email_config, valid_api_config
    ):
        from education_system.university_system.infrastructure.validation.validators import ValidationResult
        assert isinstance(validate_email_config(valid_email_config), ValidationResult)
        assert isinstance(validate_api_config(valid_api_config), ValidationResult)
        assert isinstance(validate_sms_config({}), ValidationResult)

    def test_all_validators_set_field_name(
        self, valid_email_config, valid_api_config
    ):
        assert validate_email_config(valid_email_config).field == "email_config"
        assert validate_api_config(valid_api_config).field == "api_config"
        assert validate_sms_config({}).field == "sms_config"

    def test_raise_if_invalid_works_on_config_results(self):
        result = validate_email_config({})
        assert not result.is_valid
        from education_system.university_system.infrastructure.validation.validators import ValidationError
        with pytest.raises(ValidationError):
            result.raise_if_invalid()

    def test_bool_conversion_on_results(self, valid_email_config):
        assert bool(validate_email_config(valid_email_config)) is True
        assert bool(validate_email_config({})) is False
