"""
Cache Infrastructure Package.

Provides caching functionality including:
- In-memory cache with TTL support
- Thread-safe operations
- Cache statistics and metrics
- Function caching decorators
- Namespace/tag support for cache invalidation
"""

from university_system.infrastructure.cache.cache_manager import (
    CacheManager,
    CacheEntry,
    CacheStats,
    cached,
    get_cache,
    default_cache,
    student_cache,
    course_cache,
    clear_all_caches,
)

__all__ = [
    'CacheManager',
    'CacheEntry',
    'CacheStats',
    'cached',
    'get_cache',
    'default_cache',
    'student_cache',
    'course_cache',
    'clear_all_caches',
]
