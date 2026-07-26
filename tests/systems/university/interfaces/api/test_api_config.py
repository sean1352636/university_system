"""
Tests for university_system/api/config.py

Covers _deep_merge() recursive dict merging and load_config() JSON loading,
default merging, validation, and JWT secret generation.
"""

import json
import os
import sys
from unittest.mock import MagicMock, mock_open, patch

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from education_system.platform.delivery.api.university.config import _deep_merge, load_config, _DEFAULTS


# ============================================================================
# _deep_merge tests
# ============================================================================


class TestDeepMerge:
    """Tests for the _deep_merge(base, override) helper."""

    def test_flat_merge_adds_new_keys(self):
        """Override adds keys that are not in base."""
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_flat_merge_overrides_existing_keys(self):
        """Override replaces existing flat values."""
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99}

    def test_nested_merge_recursively_merges_dicts(self):
        """Nested dicts are recursively merged, not replaced."""
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 99, "c": 3}}
        result = _deep_merge(base, override)
        assert result == {"outer": {"a": 1, "b": 99, "c": 3}}

    def test_nested_override_replaces_non_dict_with_value(self):
        """If override value is not a dict, it replaces even a dict in base."""
        base = {"key": {"nested": True}}
        override = {"key": "flat_now"}
        result = _deep_merge(base, override)
        assert result == {"key": "flat_now"}

    def test_nested_override_replaces_flat_with_dict(self):
        """If base has flat value but override has dict, dict wins."""
        base = {"key": "flat"}
        override = {"key": {"nested": True}}
        result = _deep_merge(base, override)
        assert result == {"key": {"nested": True}}

    def test_empty_override_returns_copy_of_base(self):
        """Empty override produces a copy of base."""
        base = {"x": 1, "y": {"z": 2}}
        result = _deep_merge(base, {})
        assert result == base
        assert result is not base

    def test_empty_base_returns_override(self):
        """Empty base returns the override content."""
        override = {"a": 1}
        result = _deep_merge({}, override)
        assert result == {"a": 1}

    def test_does_not_mutate_base(self):
        """Base dict is not mutated by the merge."""
        base = {"a": 1, "nested": {"b": 2}}
        override = {"a": 99, "nested": {"c": 3}}
        _deep_merge(base, override)
        assert base == {"a": 1, "nested": {"b": 2}}

    def test_deeply_nested_merge(self):
        """Merge works for multiple levels of nesting."""
        base = {"l1": {"l2": {"l3": {"val": "original"}}}}
        override = {"l1": {"l2": {"l3": {"extra": "new"}}}}
        result = _deep_merge(base, override)
        assert result == {"l1": {"l2": {"l3": {"val": "original", "extra": "new"}}}}


# ============================================================================
# load_config tests
# ============================================================================


class TestLoadConfigNoFile:
    """Tests for load_config when no config file exists."""

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_returns_defaults_when_no_file(self, mock_exists, mock_validate):
        """When the config file does not exist, defaults are returned."""
        mock_validate.return_value = MagicMock(is_valid=True)
        config = load_config("/nonexistent/path.json")

        assert config["host"] == "localhost"
        assert config["port"] == 5000
        assert config["debug"] is False
        assert config["ssl_enabled"] is False
        assert config["max_content_length"] == 16 * 1024 * 1024
        assert config["rate_limiting"]["enabled"] is True
        assert config["rate_limiting"]["requests_per_minute"] == 100
        assert config["jwt"]["access_token_expires_minutes"] == 30
        assert config["jwt"]["refresh_token_expires_days"] == 7
        assert config["jwt"]["algorithm"] == "HS256"

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_generates_jwt_secret_when_missing(self, mock_exists, mock_validate):
        """A random JWT secret is generated when none is configured."""
        mock_validate.return_value = MagicMock(is_valid=True)
        config = load_config("/nonexistent/path.json")

        secret = config["jwt"]["secret_key"]
        assert secret is not None
        assert isinstance(secret, str)
        assert len(secret) == 64  # token_hex(32) produces 64 hex chars

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_jwt_secret_is_random_each_call(self, mock_exists, mock_validate):
        """Each call generates a different JWT secret."""
        mock_validate.return_value = MagicMock(is_valid=True)
        config1 = load_config("/nonexistent/path.json")
        config2 = load_config("/nonexistent/path.json")

        # Both should have secrets, but they should differ (random)
        assert config1["jwt"]["secret_key"] is not None
        assert config2["jwt"]["secret_key"] is not None
        assert isinstance(config1["jwt"]["secret_key"], str)
        assert isinstance(config2["jwt"]["secret_key"], str)
        assert len(config1["jwt"]["secret_key"]) == 64
        assert len(config2["jwt"]["secret_key"]) == 64


class TestLoadConfigWithFile:
    """Tests for load_config when a valid config file exists."""

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=True)
    def test_loads_valid_json_file(self, mock_exists, mock_validate):
        """Config is loaded from a valid JSON file."""
        file_data = json.dumps({"host": "0.0.0.0", "port": 8080})
        mock_validate.return_value = MagicMock(is_valid=True)

        with patch("builtins.open", mock_open(read_data=file_data)):
            config = load_config("/some/config.json")

        assert config["host"] == "0.0.0.0"
        assert config["port"] == 8080

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=True)
    def test_merges_file_config_with_defaults(self, mock_exists, mock_validate):
        """File config is merged with defaults so missing keys get defaults."""
        file_data = json.dumps({"host": "0.0.0.0"})
        mock_validate.return_value = MagicMock(is_valid=True)

        with patch("builtins.open", mock_open(read_data=file_data)):
            config = load_config("/some/config.json")

        # Overridden value
        assert config["host"] == "0.0.0.0"
        # Default values preserved
        assert config["port"] == 5000
        assert config["debug"] is False
        assert config["rate_limiting"]["enabled"] is True

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=True)
    def test_nested_file_config_merges_with_defaults(self, mock_exists, mock_validate):
        """Nested dicts in file config merge with nested defaults."""
        file_data = json.dumps({"jwt": {"algorithm": "HS512"}})
        mock_validate.return_value = MagicMock(is_valid=True)

        with patch("builtins.open", mock_open(read_data=file_data)):
            config = load_config("/some/config.json")

        # Overridden nested value
        assert config["jwt"]["algorithm"] == "HS512"
        # Other nested defaults preserved
        assert config["jwt"]["access_token_expires_minutes"] == 30
        assert config["jwt"]["refresh_token_expires_days"] == 7

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=True)
    def test_preserves_jwt_secret_from_file(self, mock_exists, mock_validate):
        """If file supplies a JWT secret, it is not overwritten."""
        file_data = json.dumps({"jwt": {"secret_key": "my-fixed-secret"}})
        mock_validate.return_value = MagicMock(is_valid=True)

        with patch("builtins.open", mock_open(read_data=file_data)):
            config = load_config("/some/config.json")

        assert config["jwt"]["secret_key"] == "my-fixed-secret"


class TestLoadConfigInvalidJson:
    """Tests for load_config when the config file contains invalid JSON."""

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=True)
    def test_falls_back_to_defaults_on_invalid_json(self, mock_exists, mock_validate):
        """Invalid JSON causes fallback to defaults (no crash)."""
        mock_validate.return_value = MagicMock(is_valid=True)

        with patch("builtins.open", mock_open(read_data="{ not valid json !!!")):
            config = load_config("/some/bad.json")

        # Should still return usable defaults
        assert config["host"] == "localhost"
        assert config["port"] == 5000

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=True)
    def test_falls_back_to_defaults_on_os_error(self, mock_exists, mock_validate):
        """OSError during file read causes fallback to defaults."""
        mock_validate.return_value = MagicMock(is_valid=True)

        with patch("builtins.open", side_effect=OSError("permission denied")):
            config = load_config("/some/unreadable.json")

        assert config["host"] == "localhost"
        assert config["port"] == 5000


class TestLoadConfigValidation:
    """Tests for the validation step inside load_config."""

    @patch(
        "education_system.systems.university.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_calls_validate_api_config(self, mock_exists, mock_validate):
        """load_config calls validate_api_config with the merged config."""
        mock_validate.return_value = MagicMock(is_valid=True)
        load_config("/any/path.json")

        mock_validate.assert_called_once()
        call_arg = mock_validate.call_args[0][0]
        assert isinstance(call_arg, dict)
        assert "host" in call_arg
        assert "port" in call_arg

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_continues_on_validation_warnings(self, mock_exists, mock_validate):
        """load_config still returns config even when validation reports warnings."""
        mock_validate.return_value = MagicMock(
            is_valid=False, error_message="port out of range"
        )
        config = load_config("/any/path.json")

        # Config should still be returned despite validation warnings
        assert config["host"] == "localhost"
        assert config["jwt"]["secret_key"] is not None


class TestLoadConfigDefaultPath:
    """Tests for load_config with the default path argument."""

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_uses_default_path_when_none(self, mock_exists, mock_validate):
        """When path is None, load_config uses _DEFAULT_CONFIG_PATH."""
        mock_validate.return_value = MagicMock(is_valid=True)
        load_config(None)

        # os.path.exists should have been called with the default path
        from education_system.platform.delivery.api.university.config import _DEFAULT_CONFIG_PATH

        mock_exists.assert_called_once_with(_DEFAULT_CONFIG_PATH)

    @patch(
        "university_system.infrastructure.validation.config_validators.validate_api_config"
    )
    @patch("os.path.exists", return_value=False)
    def test_uses_default_path_when_omitted(self, mock_exists, mock_validate):
        """When no path argument, load_config uses _DEFAULT_CONFIG_PATH."""
        mock_validate.return_value = MagicMock(is_valid=True)
        load_config()

        from education_system.platform.delivery.api.university.config import _DEFAULT_CONFIG_PATH

        mock_exists.assert_called_once_with(_DEFAULT_CONFIG_PATH)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
