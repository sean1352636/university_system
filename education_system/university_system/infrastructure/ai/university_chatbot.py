"""
Compatibility shim for ``university_system.infrastructure.ai.university_chatbot``.

Re‑exports symbols from ``university_system.utils.ai.university_chatbot``.
"""
# Explicit imports instead of wildcard to improve code clarity and security
from education_system.university_system.utils.ai.university_chatbot import (
    LIBRARIES_AVAILABLE,
    AUTH_AVAILABLE,
    UserAuth,
    get_current_user,
    VoiceInterface,
    UserRole,
    QueryType,
    NotificationChannel,
    AuthenticatedSession,
    UserSession,
    ConversationContext,
    StudentProfile,
    create_chatbot_with_auth,
    test_chatbot_integration,
    MinimalChatbot,
    UniversityChatbot,
    NotificationService,
    AnalyticsService,
    CourseRecommendationEngine,
    AdminPanel,
    BackgroundScheduler,
)

# Define what gets exported when someone imports from this module
__all__ = [
    'LIBRARIES_AVAILABLE',
    'AUTH_AVAILABLE',
    'UserAuth',
    'get_current_user',
    'VoiceInterface',
    'UserRole',
    'QueryType',
    'NotificationChannel',
    'AuthenticatedSession',
    'UserSession',
    'ConversationContext',
    'StudentProfile',
    'create_chatbot_with_auth',
    'test_chatbot_integration',
    'MinimalChatbot',
    'UniversityChatbot',
    'NotificationService',
    'AnalyticsService',
    'CourseRecommendationEngine',
    'AdminPanel',
    'BackgroundScheduler',
]
