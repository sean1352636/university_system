"""
AI-Powered Features Service Module
"""

from education_system.university_system.core.i18n import get_text, _

from education_system.university_system.modules.shared.services.ai_features.ai_features_core import (
    ChatbotManager, RecommendationEngine, AutoGradingManager,
    ContentSuggestionManager, SentimentAnalysisManager, PlagiarismDetectionManager
)

__all__ = [
    'ChatbotManager', 'RecommendationEngine', 'AutoGradingManager',
    'ContentSuggestionManager', 'SentimentAnalysisManager', 'PlagiarismDetectionManager'
]
