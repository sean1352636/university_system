"""Tests for shared.security.rate_limiter — PersistentRateLimiter."""

import pytest

from education_system.shared.security.rate_limiter import PersistentRateLimiter


@pytest.fixture
def limiter(tmp_path):
    """Fresh rate limiter with its own DB."""
    return PersistentRateLimiter(db_path=str(tmp_path / "rate.db"))


class TestCheckRateLimit:
    """Test check_rate_limit allowing and blocking requests."""

    def test_first_request_allowed(self, limiter):
        allowed, retry = limiter.check_rate_limit("user:1", max_requests=5, window_seconds=60)
        assert allowed is True
        assert retry == 0

    def test_within_limit(self, limiter):
        for _ in range(3):
            allowed, _ = limiter.check_rate_limit("user:2", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_exceeds_limit(self, limiter):
        key = "user:flood"
        for _ in range(5):
            limiter.check_rate_limit(key, max_requests=5, window_seconds=60)

        allowed, retry = limiter.check_rate_limit(key, max_requests=5, window_seconds=60)
        assert allowed is False
        assert retry >= 1

    def test_different_keys_independent(self, limiter):
        for _ in range(5):
            limiter.check_rate_limit("key_a", max_requests=5, window_seconds=60)

        # key_b should still be allowed
        allowed, _ = limiter.check_rate_limit("key_b", max_requests=5, window_seconds=60)
        assert allowed is True


class TestReset:
    """Test reset clears the limit for a key."""

    def test_reset_allows_again(self, limiter):
        key = "user:reset"
        for _ in range(5):
            limiter.check_rate_limit(key, max_requests=5, window_seconds=60)

        # Should be blocked
        allowed, _ = limiter.check_rate_limit(key, max_requests=5, window_seconds=60)
        assert allowed is False

        # Reset and retry
        limiter.reset(key)
        allowed, _ = limiter.check_rate_limit(key, max_requests=5, window_seconds=60)
        assert allowed is True


class TestCleanupExpired:
    """Test cleanup_expired removes old entries."""

    def test_cleanup_does_not_error(self, limiter):
        limiter.check_rate_limit("user:x", max_requests=10, window_seconds=60)
        limiter.cleanup_expired(max_age_seconds=0)  # expire everything

        # After cleanup, should be allowed again
        allowed, _ = limiter.check_rate_limit("user:x", max_requests=1, window_seconds=60)
        assert allowed is True
