"""
Social Matching Module - Interest-based social connection platform.

This module provides a comprehensive social matching system for students to connect
based on shared interests, hobbies, and activities.

Features:
- Interest-based matching with compatibility scoring
- Study abroad buddy finder
- Intramural sports team formation
- Club recommendation engine
- Social activity suggestions
- Personality-based matching
- Privacy controls
"""

from university_system.modules.domain.social_matching.services.social_matching_service import (
    SocialMatchingService,
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES,
    GROUP_SIZE_PREFERENCES,
    ACTIVITY_LEVELS
)

__all__ = [
    'SocialMatchingService',
    'INTEREST_CATEGORIES',
    'PERSONALITY_TYPES',
    'GROUP_SIZE_PREFERENCES',
    'ACTIVITY_LEVELS'
]

__version__ = '1.0.0'
