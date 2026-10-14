"""A rate-limiter DB error must fail closed, not disable protection (task 5)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.security


def test_db_error_treats_key_as_limited():
    from education_system.platform.identity.auth.rate_limit_store import (
        PersistentRateLimiter,
    )

    limiter = PersistentRateLimiter()

    class _BoomConn:
        def execute(self, *a, **k):
            raise RuntimeError("db locked")

        def commit(self):
            pass

        def close(self):
            pass

    with patch.object(limiter, "_conn", return_value=_BoomConn()):
        # is_limited True == request is throttled/denied — the fail-closed
        # direction. The old code returned False here (unlimited attempts).
        assert limiter.is_limited("login:bob", limit=5, window=60) is True
