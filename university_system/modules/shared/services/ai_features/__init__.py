"""
AI-Powered Features Service Module
"""

from .ai_features_core import (
    ChatbotManager, RecommendationEngine, AutoGradingManager,
    ContentSuggestionManager, SentimentAnalysisManager, PlagiarismDetectionManager
)

__all__ = [
    'ChatbotManager', 'RecommendationEngine', 'AutoGradingManager',
    'ContentSuggestionManager', 'SentimentAnalysisManager', 'PlagiarismDetectionManager'
]
