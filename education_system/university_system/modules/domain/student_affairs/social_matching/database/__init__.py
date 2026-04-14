"""Database module for Social Matching."""

from education_system.university_system.modules.domain.student_affairs.social_matching.database.db_init import (
    initialize_social_matching_tables,
    seed_sample_data
)

__all__ = ['initialize_social_matching_tables', 'seed_sample_data']
