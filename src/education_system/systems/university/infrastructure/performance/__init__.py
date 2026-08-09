"""
Performance Optimization Infrastructure

Provides caching, query optimization, and background job management.
"""

from education_system.systems.university.infrastructure.performance.cache import (
    CacheManager,
    get_cache_manager,
    cached,
    invalidate_cache,
)

__all__ = [
    # Caching
    'CacheManager',
    'get_cache_manager',
    'cached',
    'invalidate_cache',
]
