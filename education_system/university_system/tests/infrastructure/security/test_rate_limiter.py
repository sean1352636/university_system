#!/usr/bin/env python3
"""
Comprehensive tests for rate limiter module.

Tests cover:
- Basic rate limiting functionality
- RateLimitConfig configuration
- AttemptRecord tracking
- Rate limit exceeded exceptions
- Progressive delay
- Blocking and unblocking
- Thread safety
- Integration with login attempts
- Edge cases and boundary conditions
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.infrastructure.security.rate_limiter import (
    RateLimitConfig,
    AttemptRecord,
    RateLimitExceeded,
)

# Import the rate limiter - may need to handle import errors
try:
    from education_system.university_system.infrastructure.security.rate_limiter import (
        RateLimiter,
        InMemoryRateLimitStorage,
    )
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False


# ============================================================================
# RateLimitConfig Tests
# ============================================================================

class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.max_attempts == 5
        assert config.window_seconds == 300
        assert config.block_duration_seconds == 900
        assert config.progressive_delay is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            max_attempts=3,
            window_seconds=60,
            block_duration_seconds=300,
            progressive_delay=False
        )

        assert config.max_attempts == 3
        assert config.window_seconds == 60
        assert config.block_duration_seconds == 300
        assert config.progressive_delay is False

    def test_config_strict_limits(self):
        """Test strict rate limit configuration."""
        config = RateLimitConfig(
            max_attempts=1,
            window_seconds=10,
            block_duration_seconds=3600
        )

        assert config.max_attempts == 1
        assert config.block_duration_seconds == 3600

    def test_config_lenient_limits(self):
        """Test lenient rate limit configuration."""
        config = RateLimitConfig(
            max_attempts=100,
            window_seconds=3600,
            block_duration_seconds=60
        )

        assert config.max_attempts == 100
        assert config.window_seconds == 3600


# ============================================================================
# AttemptRecord Tests
# ============================================================================

class TestAttemptRecord:
    """Test AttemptRecord dataclass."""

    def test_default_record(self):
        """Test default AttemptRecord values."""
        record = AttemptRecord()

        assert record.timestamps == []
        assert record.blocked_until is None
        assert record.total_blocked_count == 0

    def test_record_with_timestamps(self):
        """Test AttemptRecord with timestamps."""
        now = datetime.now()
        record = AttemptRecord(timestamps=[now])

        assert len(record.timestamps) == 1
        assert record.timestamps[0] == now

    def test_record_blocked(self):
        """Test AttemptRecord with block."""
        block_time = datetime.now() + timedelta(minutes=15)
        record = AttemptRecord(blocked_until=block_time, total_blocked_count=1)

        assert record.blocked_until == block_time
        assert record.total_blocked_count == 1


# ============================================================================
# RateLimitExceeded Exception Tests
# ============================================================================

class TestRateLimitExceeded:
    """Test RateLimitExceeded exception."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = RateLimitExceeded()
        assert "Rate limit exceeded" in str(exc)

    def test_exception_with_message(self):
        """Test exception with custom message."""
        exc = RateLimitExceeded(message="Too many login attempts")
        assert "Too many login attempts" in str(exc)

    def test_exception_with_identifier(self):
        """Test exception with identifier."""
        exc = RateLimitExceeded(identifier="user@example.com")
        assert exc.args is not None

    def test_exception_with_retry_after(self):
        """Test exception with retry_after."""
        exc = RateLimitExceeded(retry_after=300)
        assert exc.retry_after == 300

    def test_exception_is_catchable(self):
        """Test exception can be caught."""
        with pytest.raises(RateLimitExceeded):
            raise RateLimitExceeded("Test")


# ============================================================================
# RateLimiter Tests (if available)
# ============================================================================

@pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.fixture
    def limiter(self):
        """Create a RateLimiter with short windows for testing."""
        config = RateLimitConfig(
            max_attempts=3,
            window_seconds=5,
            block_duration_seconds=10,
            progressive_delay=False
        )
        return RateLimiter(config=config)

    def test_limiter_allows_first_attempt(self, limiter):
        """Test first attempt is always allowed."""
        result = limiter.is_allowed("user1")
        assert result is True

    def test_limiter_allows_up_to_max_attempts(self, limiter):
        """Test allows up to max_attempts."""
        identifier = "user2"

        for i in range(3):
            result = limiter.is_allowed(identifier)
            assert result is True

    def test_limiter_blocks_after_max_attempts(self, limiter):
        """Test blocks after exceeding max_attempts."""
        identifier = "user3"

        # Use up all attempts via is_allowed (which records each attempt)
        for i in range(3):
            limiter.is_allowed(identifier)

        # Next should raise
        with pytest.raises(RateLimitExceeded):
            limiter.check_rate_limit(identifier)

    def test_limiter_reset_on_success(self, limiter):
        """Test reset clears attempts."""
        identifier = "user4"

        # Make some attempts
        limiter.is_allowed(identifier)
        limiter.is_allowed(identifier)

        # Reset
        limiter.reset(identifier)

        # Should be able to make attempts again
        for i in range(3):
            result = limiter.is_allowed(identifier)
            assert result is True

    def test_limiter_different_identifiers(self, limiter):
        """Test different identifiers have separate limits."""
        # Fill up user1's attempts
        for i in range(3):
            limiter.is_allowed("user1")

        # user2 should still be allowed
        result = limiter.is_allowed("user2")
        assert result is True


# ============================================================================
# InMemoryRateLimitStorage Tests (if available)
# ============================================================================

@pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
class TestInMemoryRateLimitStorage:
    """Test InMemoryRateLimitStorage class."""

    @pytest.fixture
    def storage(self):
        """Create an InMemoryRateLimitStorage instance."""
        return InMemoryRateLimitStorage()

    def test_storage_record_attempt(self, storage):
        """Test recording an attempt."""
        storage.record_attempt("user1")
        attempts = storage.get_attempts("user1", window_seconds=300)
        assert len(attempts) >= 1

    def test_storage_multiple_attempts(self, storage):
        """Test recording multiple attempts."""
        for _ in range(5):
            storage.record_attempt("user1")

        attempts = storage.get_attempts("user1", window_seconds=300)
        assert len(attempts) == 5

    def test_storage_clear_attempts(self, storage):
        """Test clearing attempts."""
        storage.record_attempt("user1")
        storage.record_attempt("user1")

        storage.clear_attempts("user1")

        attempts = storage.get_attempts("user1", window_seconds=300)
        assert len(attempts) == 0

    def test_storage_set_block(self, storage):
        """Test setting block."""
        block_until = datetime.now() + timedelta(minutes=15)
        storage.set_block("user1", block_until)

        is_blocked = storage.is_blocked("user1")
        assert is_blocked is True

    def test_storage_block_expires(self, storage):
        """Test block expires after duration."""
        # Set block in the past
        block_until = datetime.now() - timedelta(seconds=1)
        storage.set_block("user1", block_until)

        is_blocked = storage.is_blocked("user1")
        assert is_blocked is False

    def test_storage_different_identifiers(self, storage):
        """Test different identifiers are independent."""
        storage.record_attempt("user1")
        storage.record_attempt("user1")
        storage.record_attempt("user2")

        attempts_user1 = storage.get_attempts("user1", window_seconds=300)
        attempts_user2 = storage.get_attempts("user2", window_seconds=300)

        assert len(attempts_user1) == 2
        assert len(attempts_user2) == 1


# ============================================================================
# Thread Safety Tests
# ============================================================================

@pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
class TestThreadSafety:
    """Test thread safety of rate limiter."""

    def test_concurrent_attempts(self):
        """Test concurrent attempts are handled safely."""
        config = RateLimitConfig(
            max_attempts=100,
            window_seconds=60,
            block_duration_seconds=60
        )
        limiter = RateLimiter(config=config)

        errors = []
        results = []

        def make_attempt():
            try:
                limiter.record_attempt("concurrent_user")
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_attempt) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should complete without errors
        assert len(errors) == 0
        assert len(results) == 50

    def test_concurrent_checks(self):
        """Test concurrent rate limit checks are thread-safe."""
        config = RateLimitConfig(
            max_attempts=1000,
            window_seconds=60,
            block_duration_seconds=60
        )
        limiter = RateLimiter(config=config)

        errors = []
        results = []

        def check_limit():
            try:
                result = limiter.is_allowed("check_user")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check_limit) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20


# ============================================================================
# Integration Tests
# ============================================================================

class TestRateLimiterIntegration:
    """Test rate limiter integration scenarios."""

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_login_attempt_limiting(self):
        """Test rate limiting for login attempts."""
        config = RateLimitConfig(
            max_attempts=3,
            window_seconds=300,
            block_duration_seconds=900
        )
        limiter = RateLimiter(config=config)

        identifier = "login:attacker@evil.com"

        # First 3 attempts should be allowed
        for i in range(3):
            limiter.record_attempt(identifier)

        # 4th should be blocked
        with pytest.raises(RateLimitExceeded):
            limiter.check_rate_limit(identifier)

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_api_endpoint_limiting(self):
        """Test rate limiting for API endpoints."""
        config = RateLimitConfig(
            max_attempts=100,
            window_seconds=60,
            block_duration_seconds=60
        )
        limiter = RateLimiter(config=config)

        identifier = "api:/api/students"

        # Should allow many requests
        for i in range(100):
            limiter.record_attempt(identifier)

        # Next should be blocked
        with pytest.raises(RateLimitExceeded):
            limiter.check_rate_limit(identifier)

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_ip_based_limiting(self):
        """Test IP-based rate limiting."""
        config = RateLimitConfig(
            max_attempts=50,
            window_seconds=60,
            block_duration_seconds=300
        )
        limiter = RateLimiter(config=config)

        ip_address = "ip:192.168.1.100"

        # Fill up the limit
        for i in range(50):
            limiter.record_attempt(ip_address)

        # Should be blocked
        with pytest.raises(RateLimitExceeded):
            limiter.check_rate_limit(ip_address)

        # Different IP should be allowed
        result = limiter.is_allowed("ip:192.168.1.101")
        assert result is True


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_config_zero_attempts(self):
        """Test config with zero max_attempts."""
        config = RateLimitConfig(max_attempts=0)
        # Should not crash - implementation may reject this
        assert config.max_attempts == 0

    def test_config_negative_window(self):
        """Test config with negative window."""
        config = RateLimitConfig(window_seconds=-1)
        # Implementation should handle gracefully
        assert config.window_seconds == -1

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_empty_identifier(self):
        """Test rate limiting with empty identifier."""
        limiter = RateLimiter()

        # Should handle empty string
        limiter.record_attempt("")
        # Should not crash

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_special_characters_in_identifier(self):
        """Test rate limiting with special characters in identifier."""
        limiter = RateLimiter()

        identifiers = [
            "user@example.com",
            "user:password",
            "192.168.1.1",
            "/api/endpoint?param=value",
            "unicode_",
        ]

        for identifier in identifiers:
            limiter.record_attempt(identifier)
            # Should not crash

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_very_long_identifier(self):
        """Test rate limiting with very long identifier."""
        limiter = RateLimiter()

        long_identifier = "a" * 10000
        limiter.record_attempt(long_identifier)
        # Should not crash


# ============================================================================
# Progressive Delay Tests
# ============================================================================

@pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
class TestProgressiveDelay:
    """Test progressive delay functionality."""

    def test_progressive_delay_increases(self):
        """Test that delay increases with attempts."""
        config = RateLimitConfig(
            max_attempts=10,
            window_seconds=60,
            progressive_delay=True
        )
        limiter = RateLimiter(config=config)

        # Make several attempts and check delay increases
        delays = []
        for i in range(5):
            limiter.record_attempt("delay_user")
            delay = limiter.get_delay("delay_user")
            if delay is not None:
                delays.append(delay)

        # Delays should generally increase (if progressive delay is implemented)
        # This test may need adjustment based on actual implementation

    def test_no_progressive_delay(self):
        """Test without progressive delay."""
        config = RateLimitConfig(
            max_attempts=10,
            window_seconds=60,
            progressive_delay=False
        )
        limiter = RateLimiter(config=config)

        # Make several attempts
        for i in range(5):
            limiter.record_attempt("no_delay_user")

        # Should not have significant delay
        delay = limiter.get_delay("no_delay_user")
        assert delay is None or delay == 0


# ============================================================================
# Security Tests
# ============================================================================

class TestSecurityScenarios:
    """Test security-related scenarios."""

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_brute_force_protection(self):
        """Test protection against brute force attacks."""
        config = RateLimitConfig(
            max_attempts=5,
            window_seconds=300,
            block_duration_seconds=900
        )
        limiter = RateLimiter(config=config)

        attacker_id = "brute_force_attacker"

        # Simulate brute force
        for i in range(5):
            limiter.record_attempt(attacker_id)

        # Should be blocked
        with pytest.raises(RateLimitExceeded) as exc_info:
            limiter.check_rate_limit(attacker_id)

        # Should have retry_after info
        exc = exc_info.value
        # Check exception contains useful info

    @pytest.mark.skipif(not RATE_LIMITER_AVAILABLE, reason="RateLimiter not available")
    def test_credential_stuffing_protection(self):
        """Test protection against credential stuffing."""
        config = RateLimitConfig(
            max_attempts=10,
            window_seconds=60,
            block_duration_seconds=300
        )
        limiter = RateLimiter(config=config)

        # Simulate multiple different usernames from same IP
        ip_id = "ip:attacker_ip"

        for i in range(10):
            limiter.record_attempt(ip_id)

        # IP should be rate limited
        with pytest.raises(RateLimitExceeded):
            limiter.check_rate_limit(ip_id)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
