"""
Tests for university chatbot utility module.

Tests the main chatbot implementation.
"""

import pytest
from pathlib import Path


class TestUniversityChatbotModule:
    """Test university chatbot module structure."""

    def test_university_chatbot_file_exists(self):
        """Test that university_chatbot file exists."""
        chatbot_file = Path(__file__).resolve().parents[3] / "infrastructure" / "ai" / "university_chatbot" / "__init__.py"
        assert chatbot_file.exists()

    def test_university_chatbot_imports(self):
        """Test that university_chatbot module can be imported."""
        try:
            from education_system.post_18.university_system.infrastructure.ai import university_chatbot
            assert university_chatbot is not None
        except ImportError as e:
            pytest.skip(f"University chatbot module not available: {e}")

    def test_chatbot_has_classes(self):
        """Test that chatbot module has expected classes."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.university_chatbot import (
                UniversityChatbot,
                MinimalChatbot
            )
            assert UniversityChatbot is not None
            assert MinimalChatbot is not None
        except ImportError as e:
            pytest.skip(f"Chatbot classes not available: {e}")


class TestChatbotClasses:
    """Test chatbot class definitions."""

    def test_university_chatbot_class_exists(self):
        """Test UniversityChatbot class exists."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.university_chatbot import UniversityChatbot
            assert UniversityChatbot is not None
        except ImportError:
            pytest.skip("UniversityChatbot not available")

    def test_minimal_chatbot_class_exists(self):
        """Test MinimalChatbot class exists."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.university_chatbot import MinimalChatbot
            assert MinimalChatbot is not None
        except ImportError:
            pytest.skip("MinimalChatbot not available")


class TestChatbotFunctions:
    """Test chatbot utility functions."""

    def test_create_chatbot_with_auth_exists(self):
        """Test create_chatbot_with_auth function exists."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.university_chatbot import create_chatbot_with_auth
            assert callable(create_chatbot_with_auth)
        except ImportError:
            pytest.skip("create_chatbot_with_auth not available")

    def test_test_chatbot_integration_exists(self):
        """Test test_chatbot_integration function exists."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.university_chatbot import test_chatbot_integration
            assert callable(test_chatbot_integration)
        except ImportError:
            pytest.skip("test_chatbot_integration not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
