"""Services module for Social Matching."""

from education_system.systems.university.domain.pastoral.social_matching.services.social_matching_service import (
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
