"""
Caching Layer

Provides LRU cache with TTL for frequently accessed data.
Reduces database load and improves response times.
"""

import time
import logging
from functools import wraps
from typing import Any, Optional, Dict, Callable
from collections import OrderedDict
from threading import RLock

logger = logging.getLogger(__name__)


class CacheManager:
    """
    LRU cache with TTL (Time To Live) support.

    Features:
    - Configurable max size
    - Time-based expiration
    - Cache statistics
    - Thread-safe operations
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize cache manager.

        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default time-to-live in seconds (0 = no expiration)
        """
        self._cache: OrderedDict = OrderedDict()
        self._lock = RLock()
        self._max_size = max_size
        self._default_ttl = default_ttl

        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Returns None if key not found or expired.
        """
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None

            value, expiry = self._cache[key]

            # Check expiration
            if expiry and time.time() > expiry:
                # Expired - remove it
                del self._cache[key]
                self._stats['misses'] += 1
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._stats['hits'] += 1

            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default, 0 = no expiration)
        """
        with self._lock:
            # Calculate expiry time
            if ttl is None:
                ttl = self._default_ttl

            expiry = time.time() + ttl if ttl > 0 else None

            # Add/update item
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)
            self._stats['sets'] += 1

            # Evict oldest if over limit
            if len(self._cache) > self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats['evictions'] += 1

    def delete(self, key: str):
        """Delete specific key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """Clear all cached items"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0

            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'sets': self._stats['sets'],
                'evictions': self._stats['evictions'],
                'hit_rate_percent': round(hit_rate, 2),
                'total_requests': total_requests,
            }

    def cleanup_expired(self) -> int:
        """Remove expired items from cache"""
        with self._lock:
            now = time.time()
            expired_keys = []

            for key, (value, expiry) in self._cache.items():
                if expiry and now > expiry:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)


# Global cache manager
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance"""
    global _cache_manager

    if _cache_manager is None:
        _cache_manager = CacheManager()

    return _cache_manager


def cached(ttl: int = 300, key_func: Optional[Callable] = None):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds (0 = no expiration)
        key_func: Optional function to generate cache key from args/kwargs
                  Default: uses function name + str(args) + str(kwargs)

    Usage:
        @cached(ttl=60)
        def get_student_gpa(student_id):
            # Expensive calculation
            return calculated_gpa

        @cached(ttl=300, key_func=lambda student_id: f"gpa:{student_id}")
        def get_student_gpa(student_id):
            return calculated_gpa
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                cache_key = f"{func.__module__}.{func.__name__}:{args}:{kwargs}"

            # Try to get from cache
            cache = get_cache_manager()
            cached_value = cache.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Cache miss - compute value
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl)

            return result

        # Add cache invalidation method to function
        def invalidate(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__module__}.{func.__name__}:{args}:{kwargs}"

            cache = get_cache_manager()
            cache.delete(cache_key)

        wrapper.invalidate = invalidate

        return wrapper
    return decorator


def invalidate_cache(pattern: Optional[str] = None):
    """
    Invalidate cache entries.

    Args:
        pattern: If provided, only clear keys matching pattern (simple startswith check)
                 If None, clears entire cache
    """
    cache = get_cache_manager()

    if pattern is None:
        cache.clear()
    else:
        # Clear matching keys
        with cache._lock:
            keys_to_delete = [
                key for key in cache._cache.keys()
                if key.startswith(pattern)
            ]

            for key in keys_to_delete:
                cache.delete(key)

        logger.info(f"Invalidated {len(keys_to_delete)} cache entries matching '{pattern}'")


# Example usage functions for common cached operations

@cached(ttl=600)  # Cache for 10 minutes
def get_student_gpa(student_id: int) -> float:
    """Calculate and cache student GPA"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT AVG(grade)
            FROM grades
            WHERE student_id = ?
        """, (student_id,))

        result = cursor.fetchone()
        return float(result[0]) if result and result[0] else 0.0


@cached(ttl=1800, key_func=lambda course_id: f"course_enrollment:{course_id}")
def get_course_enrollment_count(course_id: int) -> int:
    """Get cached course enrollment count"""
    from education_system.post_18.university_system.infrastructure.database.db import get_connection

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT COUNT(*)
            FROM enrollments
            WHERE course_id = ?
        """, (course_id,))

        result = cursor.fetchone()
        return int(result[0]) if result else 0
