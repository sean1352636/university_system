"""
Rate Limiting for the University System.

Provides configurable rate limiting to protect against brute force attacks
and API abuse. Supports multiple limiting strategies.

Supports both in-memory and Redis-based distributed rate limiting.
Redis is used automatically when REDIS_URL environment variable is set.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any

from education_system.university_system.infrastructure.exceptions import UniversitySystemError

logger = logging.getLogger(__name__)

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Import security alerting for real-time notifications
try:
    from education_system.university_system.infrastructure.security.security_alerts import (
        alert_brute_force_attempt,
    )
    SECURITY_ALERTS_AVAILABLE = True
except ImportError:
    SECURITY_ALERTS_AVAILABLE = False

# Try to import redis for distributed rate limiting
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RateLimitExceeded(UniversitySystemError):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        identifier: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if identifier:
            details['identifier'] = identifier
        if retry_after:
            details['retry_after_seconds'] = retry_after
        kwargs['details'] = details
        kwargs.pop('code', None)
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", **kwargs)
        self.retry_after = retry_after


@dataclass
class RateLimitConfig:
    """Configuration for a rate limiter."""
    max_attempts: int = 5
    window_seconds: int = 300  # 5 minutes
    block_duration_seconds: int = 900  # 15 minutes after exceeded
    progressive_delay: bool = True  # Increase delay with each attempt


@dataclass
class AttemptRecord:
    """Record of attempts for an identifier."""
    timestamps: list = field(default_factory=list)
    blocked_until: Optional[datetime] = None
    total_blocked_count: int = 0


class InMemoryRateLimitStorage:
    """In-memory storage backend for rate limiting."""

    def __init__(self):
        self._attempts: Dict[str, list] = defaultdict(list)
        self._blocks: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def record_attempt(self, identifier: str) -> None:
        with self._lock:
            self._attempts[identifier].append(datetime.now())

    def get_attempts(self, identifier: str, window_seconds: int = 300) -> list:
        with self._lock:
            cutoff = datetime.now() - timedelta(seconds=window_seconds)
            attempts = self._attempts[identifier]
            attempts[:] = [ts for ts in attempts if ts > cutoff]
            return list(attempts)

    def clear_attempts(self, identifier: str) -> None:
        with self._lock:
            self._attempts[identifier] = []
            self._blocks.pop(identifier, None)

    def is_blocked(self, identifier: str) -> bool:
        with self._lock:
            blocked_until = self._blocks.get(identifier)
            if blocked_until is None:
                return False
            if blocked_until > datetime.now():
                return True
            del self._blocks[identifier]
            return False

    def set_block(self, identifier: str, block_until: datetime) -> None:
        with self._lock:
            self._blocks[identifier] = block_until


class RedisRateLimitStorage:
    """
    Redis-backed storage for distributed rate limiting.

    Uses Redis sorted sets for tracking attempts and simple keys for blocks.
    """

    def __init__(self, redis_url: str = None, key_prefix: str = "ratelimit"):
        """
        Initialize Redis storage.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all Redis keys
        """
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis package not installed")

        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.key_prefix = key_prefix
        self._redis: Optional[redis.Redis] = None
        self._connect()

    def _connect(self) -> bool:
        """Establish Redis connection."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self._redis.ping()
            logger.info(f"Rate limiter connected to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            self._redis = None
            return False

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if self._redis is None:
            return False
        try:
            self._redis.ping()
            return True
        except Exception:
            return False

    def _attempts_key(self, identifier: str) -> str:
        """Get Redis key for attempts."""
        return f"{self.key_prefix}:attempts:{identifier}"

    def _block_key(self, identifier: str) -> str:
        """Get Redis key for block status."""
        return f"{self.key_prefix}:blocked:{identifier}"

    def _block_count_key(self, identifier: str) -> str:
        """Get Redis key for block count."""
        return f"{self.key_prefix}:block_count:{identifier}"

    def get_attempts_in_window(self, identifier: str, window_seconds: int) -> int:
        """Get number of attempts within window."""
        if not self.is_connected:
            return 0

        key = self._attempts_key(identifier)
        now = time.time()
        window_start = now - window_seconds

        try:
            # Remove old entries and count
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = pipe.execute()
            return results[1]
        except Exception as e:
            logger.error(f"Redis error getting attempts: {e}")
            return 0

    def record_attempt(self, identifier: str, window_seconds: int) -> None:
        """Record an attempt."""
        if not self.is_connected:
            return

        key = self._attempts_key(identifier)
        now = time.time()
        member = f"{now}:{os.urandom(4).hex()}"

        try:
            pipe = self._redis.pipeline()
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds + 60)
            pipe.execute()
        except Exception as e:
            logger.error(f"Redis error recording attempt: {e}")

    def is_blocked(self, identifier: str) -> bool:
        """Check if identifier is blocked."""
        if not self.is_connected:
            return False

        try:
            blocked_until = self._redis.get(self._block_key(identifier))
            if blocked_until:
                if float(blocked_until) > time.time():
                    return True
                # Block expired, clean up
                self._redis.delete(self._block_key(identifier))
            return False
        except Exception as e:
            logger.error(f"Redis error checking block: {e}")
            return False

    def get_blocked_until(self, identifier: str) -> Optional[datetime]:
        """Get block expiration time."""
        if not self.is_connected:
            return None

        try:
            blocked_until = self._redis.get(self._block_key(identifier))
            if blocked_until:
                ts = float(blocked_until)
                if ts > time.time():
                    return datetime.fromtimestamp(ts)
            return None
        except Exception as e:
            logger.error(f"Redis error getting block time: {e}")
            return None

    def set_blocked(self, identifier: str, block_duration_seconds: int) -> None:
        """Block an identifier."""
        if not self.is_connected:
            return

        try:
            blocked_until = time.time() + block_duration_seconds
            pipe = self._redis.pipeline()
            pipe.set(self._block_key(identifier), blocked_until)
            pipe.expire(self._block_key(identifier), block_duration_seconds + 60)
            pipe.incr(self._block_count_key(identifier))
            pipe.execute()
            logger.warning(f"Rate limit: {identifier} blocked for {block_duration_seconds}s")
        except Exception as e:
            logger.error(f"Redis error setting block: {e}")

    def get_total_blocked_count(self, identifier: str) -> int:
        """Get total times identifier has been blocked."""
        if not self.is_connected:
            return 0

        try:
            count = self._redis.get(self._block_count_key(identifier))
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Redis error getting block count: {e}")
            return 0

    def reset(self, identifier: str) -> None:
        """Reset rate limit for identifier."""
        if not self.is_connected:
            return

        try:
            pipe = self._redis.pipeline()
            pipe.delete(self._attempts_key(identifier))
            pipe.delete(self._block_key(identifier))
            pipe.execute()
            logger.info(f"Rate limit reset for {identifier}")
        except Exception as e:
            logger.error(f"Redis error resetting: {e}")

    def clear_attempts(self, identifier: str) -> None:
        """Clear attempt history but keep block status."""
        if not self.is_connected:
            return

        try:
            self._redis.delete(self._attempts_key(identifier))
        except Exception as e:
            logger.error(f"Redis error clearing attempts: {e}")


def _get_redis_storage() -> Optional[RedisRateLimitStorage]:
    """Get Redis storage if available and configured."""
    if not REDIS_AVAILABLE:
        return None

    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        return None

    try:
        storage = RedisRateLimitStorage(redis_url)
        if storage.is_connected:
            return storage
    except Exception as e:
        logger.warning(f"Could not initialize Redis rate limit storage: {e}")

    return None


# Global Redis storage instance (initialized lazily)
_redis_storage: Optional[RedisRateLimitStorage] = None
_redis_storage_checked = False


def get_redis_storage() -> Optional[RedisRateLimitStorage]:
    """Get the global Redis storage instance."""
    global _redis_storage, _redis_storage_checked

    if not _redis_storage_checked:
        _redis_storage = _get_redis_storage()
        _redis_storage_checked = True

    return _redis_storage


class RateLimiter:
    """
    Thread-safe rate limiter with configurable windows and blocking.

    Example usage:
        >>> limiter = RateLimiter(max_attempts=5, window_seconds=300)
        >>>
        >>> # Check if action is allowed
        >>> if limiter.is_allowed("user@example.com"):
        ...     # Proceed with action
        ...     pass
        >>> else:
        ...     raise RateLimitExceeded("Too many attempts")
        >>>
        >>> # Or use check_rate_limit which raises automatically
        >>> limiter.check_rate_limit("user@example.com")  # Raises if exceeded
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        block_duration_seconds: int = 900,
        progressive_delay: bool = True,
        cleanup_interval: int = 3600,
        use_redis: bool = None,
        redis_key_prefix: str = "security_ratelimit",
        config: Optional[RateLimitConfig] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            max_attempts: Maximum allowed attempts within the window
            window_seconds: Time window in seconds for counting attempts
            block_duration_seconds: How long to block after limit exceeded
            progressive_delay: Whether to apply increasing delays
            cleanup_interval: Interval for cleaning old records (seconds)
            use_redis: Use Redis for distributed rate limiting (auto-detect if None)
            redis_key_prefix: Prefix for Redis keys when using distributed mode
            config: Optional RateLimitConfig to override individual parameters
        """
        if config is not None:
            max_attempts = config.max_attempts
            window_seconds = config.window_seconds
            block_duration_seconds = config.block_duration_seconds
            progressive_delay = config.progressive_delay
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_duration_seconds = block_duration_seconds
        self.progressive_delay = progressive_delay
        self.cleanup_interval = cleanup_interval
        self.redis_key_prefix = redis_key_prefix

        # In-memory storage (always available as fallback)
        self._attempts: Dict[str, AttemptRecord] = defaultdict(AttemptRecord)
        self._lock = threading.RLock()
        self._last_cleanup = time.time()

        # Redis storage (optional, for distributed rate limiting)
        self._redis_storage: Optional[RedisRateLimitStorage] = None
        if use_redis is True or (use_redis is None and os.getenv('REDIS_URL')):
            self._redis_storage = get_redis_storage()
            if self._redis_storage:
                self._redis_storage.key_prefix = redis_key_prefix

        storage_type = "Redis" if self._redis_storage else "in-memory"
        logger.info(
            f"RateLimiter initialized ({storage_type}): max_attempts={max_attempts}, "
            f"window={window_seconds}s, block_duration={block_duration_seconds}s"
        )

    @property
    def is_distributed(self) -> bool:
        """Check if using distributed (Redis) storage."""
        return self._redis_storage is not None and self._redis_storage.is_connected

    def _cleanup_old_records(self) -> None:
        """Remove expired records to prevent memory growth."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return

        with self._lock:
            cutoff = datetime.now() - timedelta(seconds=self.window_seconds * 2)
            identifiers_to_remove = []

            for identifier, record in self._attempts.items():
                # Remove if no recent attempts and not currently blocked
                if record.blocked_until and record.blocked_until < datetime.now():
                    record.blocked_until = None

                if not record.timestamps and not record.blocked_until:
                    identifiers_to_remove.append(identifier)
                else:
                    # Clean old timestamps
                    record.timestamps = [
                        ts for ts in record.timestamps
                        if ts > cutoff
                    ]
                    if not record.timestamps and not record.blocked_until:
                        identifiers_to_remove.append(identifier)

            for identifier in identifiers_to_remove:
                del self._attempts[identifier]

            if identifiers_to_remove:
                logger.debug(f"Cleaned up {len(identifiers_to_remove)} expired rate limit records")

            self._last_cleanup = now

    def _get_attempts_in_window(self, identifier: str) -> int:
        """Get the number of attempts within the current window."""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        record = self._attempts[identifier]

        # Clean old timestamps
        record.timestamps = [ts for ts in record.timestamps if ts > cutoff]

        return len(record.timestamps)

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if an action is allowed for the given identifier.

        This method records the attempt if allowed.
        Uses Redis for distributed rate limiting if available.

        Args:
            identifier: Unique identifier (e.g., username, IP address)

        Returns:
            True if action is allowed, False if rate limited
        """
        # Use Redis if available
        if self._redis_storage and self._redis_storage.is_connected:
            return self._is_allowed_redis(identifier)

        # Fall back to in-memory
        return self._is_allowed_memory(identifier)

    def _is_allowed_redis(self, identifier: str) -> bool:
        """Check rate limit using Redis storage."""
        # Check if currently blocked
        if self._redis_storage.is_blocked(identifier):
            blocked_until = self._redis_storage.get_blocked_until(identifier)
            logger.warning(f"Rate limit: {identifier} is blocked until {blocked_until}")
            return False

        # Count recent attempts
        attempts = self._redis_storage.get_attempts_in_window(identifier, self.window_seconds)

        if attempts >= self.max_attempts:
            # Block the identifier
            self._redis_storage.set_blocked(identifier, self.block_duration_seconds)
            logger.warning(
                f"Rate limit exceeded for {identifier}: "
                f"{attempts} attempts, blocked for {self.block_duration_seconds}s"
            )

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.RATE_LIMIT_HIT,
                    user_id=identifier,
                    resource_type='rate_limit',
                    details={
                        'attempts': attempts,
                        'max_attempts': self.max_attempts,
                        'window_seconds': self.window_seconds
                    }
                )
                safe_log_security_event(
                    action=AuditAction.IP_BLOCKED,
                    user_id=identifier,
                    resource_type='rate_limit',
                    details={
                        'block_duration_seconds': self.block_duration_seconds,
                        'reason': 'rate_limit_exceeded'
                    }
                )

            # Send real-time security alert for potential brute force
            if SECURITY_ALERTS_AVAILABLE:
                alert_brute_force_attempt(
                    identifier=identifier,
                    ip_address=identifier,
                    attempts=attempts,
                    window_minutes=self.window_seconds // 60
                )

            return False

        # Record this attempt
        self._redis_storage.record_attempt(identifier, self.window_seconds)
        return True

    def _is_allowed_memory(self, identifier: str) -> bool:
        """Check rate limit using in-memory storage."""
        self._cleanup_old_records()

        with self._lock:
            record = self._attempts[identifier]
            now = datetime.now()

            # Check if currently blocked
            if record.blocked_until and record.blocked_until > now:
                logger.warning(
                    f"Rate limit: {identifier} is blocked until {record.blocked_until}"
                )
                return False
            elif record.blocked_until:
                # Block has expired, reset
                record.blocked_until = None
                record.timestamps = []

            # Count recent attempts
            attempts = self._get_attempts_in_window(identifier)

            if attempts >= self.max_attempts:
                # Block the identifier
                record.blocked_until = now + timedelta(seconds=self.block_duration_seconds)
                record.total_blocked_count += 1
                logger.warning(
                    f"Rate limit exceeded for {identifier}: "
                    f"{attempts} attempts, blocked until {record.blocked_until}"
                )

                # Immutable audit log for compliance
                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        action=AuditAction.RATE_LIMIT_HIT,
                        user_id=identifier,
                        resource_type='rate_limit',
                        details={
                            'attempts': attempts,
                            'max_attempts': self.max_attempts,
                            'window_seconds': self.window_seconds
                        }
                    )
                    safe_log_security_event(
                        action=AuditAction.IP_BLOCKED,
                        user_id=identifier,
                        resource_type='rate_limit',
                        details={
                            'block_duration_seconds': self.block_duration_seconds,
                            'blocked_until': record.blocked_until.isoformat(),
                            'total_blocked_count': record.total_blocked_count,
                            'reason': 'rate_limit_exceeded'
                        }
                    )

                # Send real-time security alert for potential brute force
                if SECURITY_ALERTS_AVAILABLE:
                    alert_brute_force_attempt(
                        identifier=identifier,
                        ip_address=identifier,
                        attempts=attempts,
                        window_minutes=self.window_seconds // 60
                    )

                return False

            # Record this attempt
            record.timestamps.append(now)
            return True

    def check_rate_limit(self, identifier: str) -> None:
        """
        Check rate limit and raise exception if exceeded.

        Args:
            identifier: Unique identifier (e.g., username, IP address)

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if not self.is_allowed(identifier):
            retry_after = self.get_block_time_remaining(identifier)

            raise RateLimitExceeded(
                f"Too many attempts. Please try again in {retry_after} seconds.",
                identifier=identifier,
                retry_after=retry_after
            )

    def get_remaining_attempts(self, identifier: str) -> int:
        """
        Get the number of remaining attempts for an identifier.

        Args:
            identifier: Unique identifier

        Returns:
            Number of remaining attempts (0 if blocked)
        """
        # Use Redis if available
        if self._redis_storage and self._redis_storage.is_connected:
            if self._redis_storage.is_blocked(identifier):
                return 0
            attempts = self._redis_storage.get_attempts_in_window(identifier, self.window_seconds)
            return max(0, self.max_attempts - attempts)

        # Fall back to in-memory
        with self._lock:
            record = self._attempts[identifier]

            if record.blocked_until and record.blocked_until > datetime.now():
                return 0

            attempts = self._get_attempts_in_window(identifier)
            return max(0, self.max_attempts - attempts)

    def get_block_time_remaining(self, identifier: str) -> Optional[int]:
        """
        Get remaining block time in seconds.

        Args:
            identifier: Unique identifier

        Returns:
            Seconds remaining on block, or None if not blocked
        """
        # Use Redis if available
        if self._redis_storage and self._redis_storage.is_connected:
            blocked_until = self._redis_storage.get_blocked_until(identifier)
            if blocked_until:
                remaining = (blocked_until - datetime.now()).total_seconds()
                return max(0, int(remaining)) if remaining > 0 else None
            return None

        # Fall back to in-memory
        with self._lock:
            record = self._attempts[identifier]

            if not record.blocked_until:
                return None

            remaining = (record.blocked_until - datetime.now()).total_seconds()
            return max(0, int(remaining)) if remaining > 0 else None

    def reset(self, identifier: str) -> None:
        """
        Reset rate limit for an identifier.

        Args:
            identifier: Unique identifier to reset
        """
        # Reset in Redis if available
        if self._redis_storage and self._redis_storage.is_connected:
            self._redis_storage.reset(identifier)

        # Also reset in-memory
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]
                logger.info(f"Rate limit reset for {identifier}")

    def record_attempt(self, identifier: str) -> None:
        """Record a single attempt without checking the limit.

        This is useful when the calling code handles the allow/block logic
        itself and just needs to track that an attempt was made.
        """
        with self._lock:
            self._attempts[identifier].timestamps.append(datetime.now())

    def get_delay(self, identifier: str) -> Optional[float]:
        """Get progressive delay for the identifier based on attempt count.

        Returns None or 0 if progressive delay is disabled.
        """
        if not self.progressive_delay:
            return None

        with self._lock:
            attempts = self._get_attempts_in_window(identifier)
            if attempts <= 1:
                return None
            # Exponential backoff: 0.5 * 2^(attempts-2)
            return min(0.5 * (2 ** (attempts - 2)), 30.0)

    def reset_all(self) -> None:
        """Reset all rate limits."""
        with self._lock:
            self._attempts.clear()
            logger.info("All rate limits reset")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            now = datetime.now()
            blocked_count = sum(
                1 for r in self._attempts.values()
                if r.blocked_until and r.blocked_until > now
            )

            return {
                'tracked_identifiers': len(self._attempts),
                'currently_blocked': blocked_count,
                'config': {
                    'max_attempts': self.max_attempts,
                    'window_seconds': self.window_seconds,
                    'block_duration_seconds': self.block_duration_seconds,
                }
            }


# Pre-configured rate limiters for common use cases
# These automatically use Redis when REDIS_URL is set
login_limiter = RateLimiter(
    max_attempts=5,
    window_seconds=300,  # 5 minutes
    block_duration_seconds=900,  # 15 minutes
    redis_key_prefix="security:login",
)

api_limiter = RateLimiter(
    max_attempts=100,
    window_seconds=60,  # 1 minute
    block_duration_seconds=60,
    redis_key_prefix="security:api",
)

password_reset_limiter = RateLimiter(
    max_attempts=3,
    window_seconds=3600,  # 1 hour
    block_duration_seconds=3600,
    redis_key_prefix="security:password_reset",
)


def rate_limit(limiter: RateLimiter, key_func: Callable[..., str] = None):
    """
    Decorator to apply rate limiting to a function.

    Args:
        limiter: RateLimiter instance to use
        key_func: Function to extract identifier from args/kwargs
                  Default uses first argument as identifier

    Example:
        >>> @rate_limit(login_limiter, key_func=lambda username, **kwargs: username)
        ... def login(username, password):
        ...     # Login logic
        ...     pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if key_func:
                identifier = key_func(*args, **kwargs)
            elif args:
                identifier = str(args[0])
            else:
                identifier = "default"

            limiter.check_rate_limit(identifier)
            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


__all__ = [
    'RateLimiter',
    'RateLimitExceeded',
    'RateLimitConfig',
    'RedisRateLimitStorage',
    'get_redis_storage',
    'rate_limit',
    'login_limiter',
    'api_limiter',
    'password_reset_limiter',
]
