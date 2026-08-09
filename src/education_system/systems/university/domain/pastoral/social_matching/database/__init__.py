"""Database module for Social Matching."""

from education_system.systems.university.domain.pastoral.social_matching.database.db_init import (
    initialize_social_matching_tables,
    seed_sample_data
)

__all__ = ['initialize_social_matching_tables', 'seed_sample_data']
