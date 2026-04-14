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

from education_system.university_system.modules.domain.student_affairs.social_matching.services.constants import (
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES,
    GROUP_SIZE_PREFERENCES,
    ACTIVITY_LEVELS,
)
from education_system.university_system.modules.domain.student_affairs.social_matching.services.interests import InterestMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.personality import PersonalityMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.privacy import PrivacyMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.matching import MatchingMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.buddy_requests import BuddyRequestMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.teams import TeamMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.clubs import ClubMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.activities import ActivityMixin
from education_system.university_system.modules.domain.student_affairs.social_matching.services.statistics import StatisticsMixin


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
        from education_system.university_system.modules.domain.student_affairs.social_matching.database.db_init import (
            initialize_social_matching_tables
        )
        initialize_social_matching_tables()
