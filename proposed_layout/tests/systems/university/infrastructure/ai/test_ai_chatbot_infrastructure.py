"""
Tests for AI chatbot infrastructure module.

This tests the compatibility shim that re-exports chatbot functionality
from utils.ai.university_chatbot.
"""

import pytest
from education_system.systems.university.infrastructure.ai import university_chatbot


class TestChatbotExports:
    """Test that chatbot symbols are properly exported."""

    def test_libraries_available_exported(self):
        """Test LIBRARIES_AVAILABLE is exported."""
        assert hasattr(university_chatbot, 'LIBRARIES_AVAILABLE')

    def test_auth_available_exported(self):
        """Test AUTH_AVAILABLE is exported."""
        assert hasattr(university_chatbot, 'AUTH_AVAILABLE')

    def test_user_auth_exported(self):
        """Test UserAuth is exported."""
        assert hasattr(university_chatbot, 'UserAuth')

    def test_get_current_user_exported(self):
        """Test get_current_user is exported."""
        assert hasattr(university_chatbot, 'get_current_user')

    def test_voice_interface_exported(self):
        """Test VoiceInterface is exported."""
        assert hasattr(university_chatbot, 'VoiceInterface')

    def test_user_role_exported(self):
        """Test UserRole is exported."""
        assert hasattr(university_chatbot, 'UserRole')

    def test_query_type_exported(self):
        """Test QueryType is exported."""
        assert hasattr(university_chatbot, 'QueryType')

    def test_notification_channel_exported(self):
        """Test NotificationChannel is exported."""
        assert hasattr(university_chatbot, 'NotificationChannel')

    def test_authenticated_session_exported(self):
        """Test AuthenticatedSession is exported."""
        assert hasattr(university_chatbot, 'AuthenticatedSession')

    def test_user_session_exported(self):
        """Test UserSession is exported."""
        assert hasattr(university_chatbot, 'UserSession')

    def test_conversation_context_exported(self):
        """Test ConversationContext is exported."""
        assert hasattr(university_chatbot, 'ConversationContext')

    def test_student_profile_exported(self):
        """Test StudentProfile is exported."""
        assert hasattr(university_chatbot, 'StudentProfile')

    def test_create_chatbot_with_auth_exported(self):
        """Test create_chatbot_with_auth is exported."""
        assert hasattr(university_chatbot, 'create_chatbot_with_auth')

    def test_test_chatbot_integration_exported(self):
        """Test test_chatbot_integration is exported."""
        assert hasattr(university_chatbot, 'test_chatbot_integration')

    def test_minimal_chatbot_exported(self):
        """Test MinimalChatbot is exported."""
        assert hasattr(university_chatbot, 'MinimalChatbot')

    def test_university_chatbot_exported(self):
        """Test UniversityChatbot is exported."""
        assert hasattr(university_chatbot, 'UniversityChatbot')

    def test_notification_service_exported(self):
        """Test NotificationService is exported."""
        assert hasattr(university_chatbot, 'NotificationService')

    def test_analytics_service_exported(self):
        """Test AnalyticsService is exported."""
        assert hasattr(university_chatbot, 'AnalyticsService')

    def test_course_recommendation_engine_exported(self):
        """Test CourseRecommendationEngine is exported."""
        assert hasattr(university_chatbot, 'CourseRecommendationEngine')

    def test_admin_panel_exported(self):
        """Test AdminPanel is exported."""
        assert hasattr(university_chatbot, 'AdminPanel')

    def test_background_scheduler_exported(self):
        """Test BackgroundScheduler is exported."""
        assert hasattr(university_chatbot, 'BackgroundScheduler')


class TestModuleAll:
    """Test __all__ exports."""

    def test_all_exports_defined(self):
        """Test that all items in __all__ are actually defined."""
        # Handle case where module might not have __all__
        if hasattr(university_chatbot, '__all__'):
            for name in university_chatbot.__all__:
                assert hasattr(university_chatbot, name), f"{name} in __all__ but not defined"
        else:
            # If no __all__, just verify the module has some attributes
            assert len(dir(university_chatbot)) > 0

    def test_all_essential_exports(self):
        """Test that essential exports are available."""
        essential = [
            'UniversityChatbot',
            'MinimalChatbot',
            'UserAuth',
            'create_chatbot_with_auth',
        ]

        # Check if __all__ exists, otherwise just check attributes exist
        for name in essential:
            assert hasattr(university_chatbot, name), f"Essential {name} not available"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
