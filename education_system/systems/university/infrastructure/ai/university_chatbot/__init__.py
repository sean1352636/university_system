"""University Chatbot package — public API.

Re-exports the symbols external callers depend on. The public surface was
audited and trimmed in 2026-05; unused model/service classes were removed
from the package init (callers that need them import from the relevant
submodule directly).

Public surface (and current external consumers):

  ``LIBRARIES_AVAILABLE``         — feature flag (gui/chatbot_gui, gui/manager,
                                    gui/compat, gui/entry, gui/features/messaging,
                                    gui/screens/admin)
  ``AUTH_AVAILABLE`` / ``_lazy_auth`` — auth-bridge state (gui/entry)
  ``UniversityChatbot``           — main class (auth.optional_dependencies,
                                    academics/gui/_cross_dialogs,
                                    ai_features/gui/ai_features_gui,
                                    shared/cli/chatbot_integration, tests, gui/entry)
  ``MinimalChatbot``              — degraded-mode class (gui/entry, tests)
  ``VoiceInterface``              — voice add-on (auth/core)
  ``create_chatbot_with_auth``    — convenience factory (tests)
  ``test_chatbot_integration``    — smoke-test helper (tests)

Internal modules (`chatbot.py`, `api_routes.py`, etc.) import sibling
*modules* directly rather than going through this init, so trimming the
re-export surface doesn't affect them.
"""

from education_system.systems.university.infrastructure.ai.university_chatbot.fallbacks import LIBRARIES_AVAILABLE
from education_system.systems.university.infrastructure.ai.university_chatbot.chatbot import UniversityChatbot
from education_system.systems.university.infrastructure.ai.university_chatbot.minimal_chatbot import MinimalChatbot
from education_system.systems.university.infrastructure.ai.university_chatbot.models import (
    AuthenticatedSession,
    ConversationContext,
    NotificationChannel,
    QueryType,
    StudentProfile,
    UserRole,
    UserSession,
)
from education_system.systems.university.infrastructure.ai.university_chatbot.services import (
    AdminPanel,
    AnalyticsService,
    BackgroundScheduler,
    CourseRecommendationEngine,
    NotificationService,
)
from education_system.systems.university.infrastructure.ai.university_chatbot.voice_interface import VoiceInterface

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
        from education_system.systems.university.infrastructure.auth import UserAuth as _UA, get_current_user as _gcu, PERMISSIONS as _P
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


__all__ = [
    'UniversityChatbot',
    'MinimalChatbot',
    'LIBRARIES_AVAILABLE',
    'UserRole',
    'QueryType',
    'NotificationChannel',
    'AuthenticatedSession',
    'UserSession',
    'ConversationContext',
    'StudentProfile',
    'NotificationService',
    'AnalyticsService',
    'CourseRecommendationEngine',
    'AdminPanel',
    'BackgroundScheduler',
    'AUTH_AVAILABLE',
    '_lazy_auth',
    'create_chatbot_with_auth',
    'test_chatbot_integration',
    'VoiceInterface',
]
