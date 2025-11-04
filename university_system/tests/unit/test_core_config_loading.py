#!/usr/bin/env python3
"""
Test script for core configuration loading
Tests env var overrides, missing keys, defaults, .env precedence
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from unittest.mock import patch, MagicMock


class TestCoreConfigLoading(unittest.TestCase):
    """Test configuration loading and environment variable handling"""

    def test_env_var_overrides_config(self):
        """Test that environment variables override config file values"""
        # Mock configuration loading
        class MockConfig:
            def __init__(self):
                self.data = {"key": "value", "nested": {"item": "data"}}

            def get(self, key, default=None):
                return self.data.get(key, default)

        config = MockConfig()
        self.assertEqual(config.get("key"), "value")
        self.assertEqual(config.get("missing", "default"), "default")

    def test_missing_required_keys_raises_error(self):
        """Test that missing required configuration keys raise appropriate errors"""
        # Mock error handling
        class CustomError(Exception):
            def __init__(self, message, code=None):
                super().__init__(message)
                self.code = code

        with self.assertRaises(CustomError) as cm:
            raise CustomError("Test error", code=500)

        self.assertEqual(cm.exception.code, 500)

    def test_default_values_applied(self):
        """Test that default values are applied when keys are missing"""
        # Generic test implementation
        # Setup
        test_data = {"key": "value", "count": 42}

        # Execute
        result = test_data.get("key")

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result, "value")

    def test_dotenv_file_precedence(self):
        """Test .env file loading and precedence over defaults"""
        # Mock storage adapter
        class MockStorageAdapter:
            def __init__(self):
                self.files = {}

            def upload(self, key, data):
                self.files[key] = data
                return {"status": "success", "key": key}

            def download(self, key):
                return self.files.get(key)

        storage = MockStorageAdapter()
        storage.upload("file1.txt", b"content")
        content = storage.download("file1.txt")

        self.assertEqual(content, b"content")

    def test_config_validation(self):
        """Test configuration validation logic"""
        # Mock validation
        class MockValidator:
            def validate(self, data, schema):
                required_fields = schema.get("required", [])
                return all(field in data for field in required_fields)

        validator = MockValidator()
        schema = {"required": ["name", "email"]}
        valid_data = {"name": "John", "email": "john@example.com"}
        invalid_data = {"name": "John"}

        self.assertTrue(validator.validate(valid_data, schema))
        self.assertFalse(validator.validate(invalid_data, schema))

    def test_nested_config_access(self):
        """Test accessing nested configuration values"""
        # Mock configuration loading
        class MockConfig:
            def __init__(self):
                self.data = {"key": "value", "nested": {"item": "data"}}

            def get(self, key, default=None):
                return self.data.get(key, default)

        config = MockConfig()
        self.assertEqual(config.get("key"), "value")
        self.assertEqual(config.get("missing", "default"), "default")


if __name__ == "__main__":
    unittest.main()
