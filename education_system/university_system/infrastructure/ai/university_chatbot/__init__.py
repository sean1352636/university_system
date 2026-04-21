"""University Chatbot package.

Re-exports all public symbols so that existing imports like
``from education_system.university_system.infrastructure.ai.university_chatbot import UniversityChatbot``
continue to work unchanged.
"""

from education_system.university_system.infrastructure.ai.university_chatbot.chatbot import UniversityChatbot
from education_system.university_system.infrastructure.ai.university_chatbot.minimal_chatbot import MinimalChatbot
from education_system.university_system.infrastructure.ai.university_chatbot.fallbacks import LIBRARIES_AVAILABLE
from education_system.university_system.infrastructure.ai.university_chatbot.models import (
    AuthenticatedSession,
    ConversationContext,
    NotificationChannel,
    QueryType,
    StudentProfile,
    UserRole,
    UserSession,
)
from education_system.university_system.infrastructure.ai.university_chatbot.voice_interface import VoiceInterface
from education_system.university_system.infrastructure.ai.university_chatbot.services import (
    AdminPanel,
    AnalyticsService,
    BackgroundScheduler,
    CourseRecommendationEngine,
    NotificationService,
)

# Lazy auth guard — kept at package level for backward compat
AUTH_AVAILABLE = False

class UserAuth:  # type: ignore
    """Placeholder class for UserAuth. Will be replaced by _lazy_auth() if auth module is available."""

def get_current_user():  # type: ignore
    return None

PERMISSIONS = {}  # type: ignore

def _lazy_auth():
    """Import auth lazily to avoid circular imports with user_authentication."""
    global UserAuth, get_current_user, PERMISSIONS, AUTH_AVAILABLE
    if AUTH_AVAILABLE:
        return
    try:
        from education_system.university_system.infrastructure.auth import UserAuth as _UA, get_current_user as _gcu, PERMISSIONS as _P
        UserAuth = _UA
        get_current_user = _gcu
        PERMISSIONS = _P
        AUTH_AVAILABLE = True
    except Exception:
        AUTH_AVAILABLE = False


def create_chatbot_with_auth(auth_system, db_path=None):
    """Factory function to create chatbot with authentication"""
    chatbot = UniversityChatbot(db_path=db_path)
    chatbot.set_auth_system(auth_system)
    return chatbot


def test_chatbot_integration(auth_system):
    """Test chatbot integration with authentication system"""
    print("Testing chatbot integration...")

    try:
        chatbot = create_chatbot_with_auth(auth_system)

        test_message = "Hello, this is a test"
        response = chatbot.process_message(test_message, "test_user", session_id="test_session")

        if response:
            print("✅ Chatbot integration test passed")
            return True
        else:
            print("❌ Chatbot integration test failed")
            return False

    except Exception as e:
        print(f"❌ Chatbot integration test failed: {e}")
        return False


def setup_enhanced_api_routes(chatbot):
    """Enhanced API routes setup"""
    chatbot.setup_api_routes()


__all__ = [
    'UniversityChatbot',
    'MinimalChatbot',
    'LIBRARIES_AVAILABLE',
    'AUTH_AVAILABLE',
    'UserAuth',
    'get_current_user',
    'PERMISSIONS',
    '_lazy_auth',
    'create_chatbot_with_auth',
    'test_chatbot_integration',
    'setup_enhanced_api_routes',
    'AuthenticatedSession',
    'ConversationContext',
    'NotificationChannel',
    'QueryType',
    'StudentProfile',
    'UserRole',
    'UserSession',
    'VoiceInterface',
    'AdminPanel',
    'AnalyticsService',
    'BackgroundScheduler',
    'CourseRecommendationEngine',
    'NotificationService',
]
