"""Database module for Social Matching."""

from university_system.modules.domain.social_matching.database.db_init import (
    initialize_social_matching_tables,
    seed_sample_data
)

__all__ = ['initialize_social_matching_tables', 'seed_sample_data']
