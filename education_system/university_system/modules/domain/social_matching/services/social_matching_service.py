"""
Social Matching Service - Interest-based social connection platform.

Features:
- Interest-based matching with compatibility scoring
- Study abroad buddy finder
- Intramural sports team formation
- Club recommendation engine
- Social activity suggestions
- Personality-based matching
- Privacy controls
"""

from .constants import (
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES,
    GROUP_SIZE_PREFERENCES,
    ACTIVITY_LEVELS,
)
from .interests import InterestMixin
from .personality import PersonalityMixin
from .privacy import PrivacyMixin
from .matching import MatchingMixin
from .buddy_requests import BuddyRequestMixin
from .teams import TeamMixin
from .clubs import ClubMixin
from .activities import ActivityMixin
from .statistics import StatisticsMixin


class SocialMatchingService(
    InterestMixin,
    PersonalityMixin,
    PrivacyMixin,
    MatchingMixin,
    BuddyRequestMixin,
    TeamMixin,
    ClubMixin,
    ActivityMixin,
    StatisticsMixin,
):
    """Service for managing interest-based social matching and connections."""

    def __init__(self):
        """Initialize the social matching service."""
        from education_system.university_system.modules.domain.social_matching.database.db_init import (
            initialize_social_matching_tables
        )
        initialize_social_matching_tables()
