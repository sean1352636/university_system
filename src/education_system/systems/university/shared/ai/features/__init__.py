"""
AI-Powered Features Service Module
"""

from education_system.systems.university.infrastructure.i18n import get_text, _

from education_system.systems.university.shared.ai.features.ai_features_core import (
    ChatbotManager, RecommendationEngine, AutoGradingManager,
    ContentSuggestionManager, SentimentAnalysisManager, PlagiarismDetectionManager
)

__all__ = [
    'ChatbotManager', 'RecommendationEngine', 'AutoGradingManager',
    'ContentSuggestionManager', 'SentimentAnalysisManager', 'PlagiarismDetectionManager'
]
