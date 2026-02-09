"""
Cache Manager for the University System.

Provides a thread-safe in-memory caching layer with TTL support,
automatic cleanup, and statistics tracking.

Example usage:
    >>> from university_system.infrastructure.cache import CacheManager, cached
    >>>
    >>> # Direct cache usage
    >>> cache = CacheManager(default_ttl=300)
    >>> cache.set('user:123', user_data)
    >>> user = cache.get('user:123')
    >>>
    >>> # Decorator usage
    >>> @cached(ttl=60, namespace='students')
    ... def get_student(student_id: int):
    ...     return fetch_student_from_db(student_id)

Future Enhancement: Redis integration for distributed caching
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Represents a cached value with metadata."""
    value: Any
    expiry: float
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    tags: Set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return time.time() >= self.expiry

    def access(self) -> Any:
        """Record an access and return the value."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired: int = 0
    total_items: int = 0
    memory_estimate_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate the cache hit rate as a percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'expired': self.expired,
            'total_items': self.total_items,
            'hit_rate_percent': round(self.hit_rate, 2),
            'memory_estimate_bytes': self.memory_estimate_bytes,
        }


class CacheManager:
    """
    Thread-safe in-memory cache with TTL support and automatic cleanup.

    Features:
    - Time-to-live (TTL) for automatic expiration
    - Tag-based cache invalidation
    - Namespace support for key organization
    - Statistics tracking for performance monitoring
    - Automatic cleanup of expired entries
    - LRU-style eviction when max_size is reached

    Example usage:
        >>> cache = CacheManager(default_ttl=300, max_size=1000)
        >>>
        >>> # Basic operations
        >>> cache.set('key', 'value')
        >>> value = cache.get('key')
        >>>
        >>> # With TTL override
        >>> cache.set('session:123', session_data, ttl=3600)
        >>>
        >>> # With tags for group invalidation
        >>> cache.set('student:123', student, tags={'students', 'active'})
        >>> cache.invalidate_tag('students')  # Removes all tagged entries
    """

    def __init__(
        self,
        default_ttl: int = 300,
        max_size: int = 10000,
        cleanup_interval: int = 60,
        namespace: str = '',
    ):
        """
        Initialize the cache manager.

        Args:
            default_ttl: Default time-to-live in seconds (default: 300)
            max_size: Maximum number of entries in cache (default: 10000)
            cleanup_interval: Interval for automatic cleanup in seconds (default: 60)
            namespace: Optional namespace prefix for all keys
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._namespace = namespace
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._last_cleanup = time.time()
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> set of keys

        logger.info(
            f"CacheManager initialized: namespace='{namespace}', "
            f"default_ttl={default_ttl}s, max_size={max_size}"
        )

    def _make_key(self, key: str) -> str:
        """Create a namespaced key."""
        if self._namespace:
            return f"{self._namespace}:{key}"
        return key

    def _cleanup_expired(self) -> None:
        """Remove expired entries from the cache."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                self._remove_entry(key)
                self._stats.expired += 1

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

            self._last_cleanup = now

    def _remove_entry(self, key: str) -> None:
        """Remove an entry and update tag index."""
        if key in self._cache:
            entry = self._cache[key]
            # Remove from tag index
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)
                    if not self._tag_index[tag]:
                        del self._tag_index[tag]
            del self._cache[key]
            self._stats.total_items = len(self._cache)

    def _evict_lru(self) -> None:
        """Evict least recently used entries if cache is full."""
        if len(self._cache) < self._max_size:
            return

        # Sort by last accessed time and remove oldest
        entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )

        # Remove bottom 10% of entries
        evict_count = max(1, len(entries) // 10)
        for key, _ in entries[:evict_count]:
            self._remove_entry(key)
            self._stats.evictions += 1

        logger.debug(f"Evicted {evict_count} LRU cache entries")

    def get(self, key: str, default: T = None) -> Optional[Union[Any, T]]:
        """
        Get a value from the cache.

        Args:
            key: The cache key
            default: Default value if key not found or expired

        Returns:
            The cached value or default if not found/expired
        """
        self._cleanup_expired()

        full_key = self._make_key(key)

        with self._lock:
            entry = self._cache.get(full_key)

            if entry is None:
                self._stats.misses += 1
                return default

            if entry.is_expired():
                self._remove_entry(full_key)
                self._stats.misses += 1
                self._stats.expired += 1
                return default

            self._stats.hits += 1
            return entry.access()

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """
        Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Optional TTL override in seconds
            tags: Optional set of tags for group invalidation
        """
        self._cleanup_expired()

        full_key = self._make_key(key)
        expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
        entry_tags = tags or set()

        with self._lock:
            # Remove old entry if exists (to update tag index)
            if full_key in self._cache:
                self._remove_entry(full_key)

            # Evict if necessary
            self._evict_lru()

            # Create new entry
            self._cache[full_key] = CacheEntry(
                value=value,
                expiry=expiry,
                tags=entry_tags,
            )

            # Update tag index
            for tag in entry_tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(full_key)

            self._stats.total_items = len(self._cache)
            logger.debug(f"Cache set: key={full_key}, ttl={ttl or self._default_ttl}s")

    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: The cache key to delete

        Returns:
            True if the key existed and was deleted, False otherwise
        """
        full_key = self._make_key(key)

        with self._lock:
            if full_key in self._cache:
                self._remove_entry(full_key)
                logger.debug(f"Cache delete: key={full_key}")
                return True
            return False

    def exists(self, key: str) -> bool:
        """
        Check if a key exists and is not expired.

        Args:
            key: The cache key to check

        Returns:
            True if key exists and is valid, False otherwise
        """
        full_key = self._make_key(key)

        with self._lock:
            entry = self._cache.get(full_key)
            if entry is None:
                return False
            if entry.is_expired():
                self._remove_entry(full_key)
                return False
            return True

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> T:
        """
        Get a value from cache, or compute and store it if not present.

        Args:
            key: The cache key
            factory: Callable to produce the value if not cached
            ttl: Optional TTL override
            tags: Optional tags for the entry

        Returns:
            The cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value

        # Compute new value
        value = factory()
        self.set(key, value, ttl=ttl, tags=tags)
        return value

    def invalidate_tag(self, tag: str) -> int:
        """
        Invalidate all cache entries with the given tag.

        Args:
            tag: The tag to invalidate

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if tag not in self._tag_index:
                return 0

            keys_to_remove = list(self._tag_index[tag])
            for key in keys_to_remove:
                self._remove_entry(key)

            count = len(keys_to_remove)
            logger.info(f"Cache invalidated tag '{tag}': {count} entries removed")
            return count

    def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate all cache entries in a namespace.

        Args:
            namespace: The namespace prefix to invalidate

        Returns:
            Number of entries invalidated
        """
        prefix = f"{namespace}:"

        with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(prefix)
            ]

            for key in keys_to_remove:
                self._remove_entry(key)

            count = len(keys_to_remove)
            logger.info(f"Cache invalidated namespace '{namespace}': {count} entries removed")
            return count

    def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._tag_index.clear()
            self._stats.total_items = 0
            logger.info(f"Cache cleared: {count} entries removed")
            return count

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object with current statistics
        """
        with self._lock:
            self._stats.total_items = len(self._cache)
            # Rough memory estimate
            self._stats.memory_estimate_bytes = sum(
                len(str(k)) + len(str(v.value))
                for k, v in self._cache.items()
            )
            return self._stats

    def get_keys(self, pattern: str = '*') -> List[str]:
        """
        Get all keys matching a pattern.

        Args:
            pattern: Simple pattern with * wildcard support

        Returns:
            List of matching keys (without namespace prefix)
        """
        with self._lock:
            if pattern == '*':
                keys = list(self._cache.keys())
            else:
                # Simple pattern matching
                import fnmatch
                keys = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]

            # Remove namespace prefix from keys
            if self._namespace:
                prefix = f"{self._namespace}:"
                keys = [k[len(prefix):] if k.startswith(prefix) else k for k in keys]

            return keys

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get the remaining TTL for a key in seconds.

        Args:
            key: The cache key

        Returns:
            Remaining TTL in seconds, or None if key doesn't exist
        """
        full_key = self._make_key(key)

        with self._lock:
            entry = self._cache.get(full_key)
            if entry is None or entry.is_expired():
                return None
            return max(0, int(entry.expiry - time.time()))

    def touch(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Update the TTL for a key without changing its value.

        Args:
            key: The cache key
            ttl: New TTL in seconds (uses default if not specified)

        Returns:
            True if key exists and was updated, False otherwise
        """
        full_key = self._make_key(key)

        with self._lock:
            entry = self._cache.get(full_key)
            if entry is None or entry.is_expired():
                return False

            entry.expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
            return True


# Global cache registry
_cache_registry: Dict[str, CacheManager] = {}
_registry_lock = threading.Lock()


def get_cache(name: str = 'default', **kwargs) -> CacheManager:
    """
    Get or create a named cache instance.

    Args:
        name: Name of the cache
        **kwargs: Arguments passed to CacheManager if creating new

    Returns:
        CacheManager instance
    """
    with _registry_lock:
        if name not in _cache_registry:
            _cache_registry[name] = CacheManager(namespace=name, **kwargs)
        return _cache_registry[name]


def clear_all_caches() -> Dict[str, int]:
    """
    Clear all registered caches.

    Returns:
        Dictionary of cache names to number of entries cleared
    """
    results = {}
    with _registry_lock:
        for name, cache in _cache_registry.items():
            results[name] = cache.clear()
    logger.info(f"Cleared all caches: {results}")
    return results


# Pre-configured cache instances for common use cases
default_cache = CacheManager(
    default_ttl=300,  # 5 minutes
    max_size=10000,
    namespace='default',
)

student_cache = CacheManager(
    default_ttl=600,  # 10 minutes
    max_size=5000,
    namespace='students',
)

course_cache = CacheManager(
    default_ttl=3600,  # 1 hour (courses change less frequently)
    max_size=2000,
    namespace='courses',
)


def cached(
    ttl: Optional[int] = None,
    namespace: str = 'default',
    tags: Optional[Set[str]] = None,
    key_builder: Optional[Callable[..., str]] = None,
    cache_none: bool = False,
):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds (uses cache default if not specified)
        namespace: Cache namespace to use
        tags: Tags to apply to cached entries
        key_builder: Custom function to build cache key from args/kwargs
        cache_none: Whether to cache None return values

    Example:
        >>> @cached(ttl=60, namespace='students')
        ... def get_student(student_id: int):
        ...     return fetch_student_from_db(student_id)
        >>>
        >>> # With custom key builder
        >>> @cached(key_builder=lambda self, id: f"user:{id}")
        ... def get_user(self, user_id: int):
        ...     return self.db.fetch_user(user_id)
    """
    cache = get_cache(namespace)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key: function name + args hash
                key_parts = [func.__module__, func.__name__]
                if args:
                    key_parts.append(str(args))
                if kwargs:
                    key_parts.append(str(sorted(kwargs.items())))
                key_str = ':'.join(key_parts)
                cache_key = hashlib.md5(key_str.encode()).hexdigest()

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Call function
            result = func(*args, **kwargs)

            # Cache result
            if result is not None or cache_none:
                cache.set(cache_key, result, ttl=ttl, tags=tags)

            return result

        # Add cache control methods to the wrapper
        wrapper.cache_clear = lambda: cache.invalidate_namespace(namespace)
        wrapper.cache_info = lambda: cache.get_stats().to_dict()

        return wrapper
    return decorator


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
