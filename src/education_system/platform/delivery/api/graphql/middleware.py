"""GraphQL middleware / extensions for the education system.

Three ``SchemaExtension`` subclasses that plug into the Strawberry extensions
mechanism (``strawberry.Schema(extensions=[...])``)::

- ``DepthLimitMiddleware`` — thin wrapper around Strawberry's built-in
  ``QueryDepthLimiter``; exposed here so callers only need to import from
  this module.

- ``AuthMiddleware``       — validates a JWT from the ``Authorization`` header
  and injects ``user_info`` into ``info.context`` for every request.

- ``RateLimitMiddleware``  — per-user token-bucket rate limiting.  State is
  kept in process memory (sufficient for single-process deployments).  For
  multi-process deployments replace ``_buckets`` with a Redis backend.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Optional

from strawberry.extensions import QueryDepthLimiter, SchemaExtension

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Depth limit (re-export wrapper around Strawberry's built-in)
# ---------------------------------------------------------------------------

def DepthLimitMiddleware(max_depth: int = 10) -> QueryDepthLimiter:  # noqa: N802
    """Return a ``QueryDepthLimiter`` capped at *max_depth* levels.

    Named ``DepthLimitMiddleware`` for consistency with the rest of the
    module, but it returns Strawberry's built-in validator class instance.
    """
    return QueryDepthLimiter(max_depth=max_depth)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class AuthMiddleware(SchemaExtension):
    """Extract a JWT from ``Authorization: Bearer <token>`` and inject
    decoded user info into ``info.context["user_info"]``.

    If no token is present the request is still allowed through; individual
    resolvers should check ``info.context.get("user_info")`` when they need
    an authenticated caller.
    """

    def __init__(
        self,
        jwt_secret: Optional[str] = None,
        algorithm: str = "HS256",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._secret = jwt_secret or os.getenv("JWT_SECRET_KEY", "")
        self._algorithm = algorithm

    # ------------------------------------------------------------------
    # SchemaExtension hook – runs once per GraphQL operation
    # ------------------------------------------------------------------

    def on_operation(self):  # type: ignore[override]
        """Decode the JWT before the operation executes."""
        request = self._get_request()
        token = self._extract_token(request)
        user_info: Optional[dict] = None
        if token and self._secret:
            user_info = self._decode_token(token)

        ctx = self.execution_context.context
        if isinstance(ctx, dict):
            ctx.setdefault("user_info", user_info)

        yield  # execution happens here

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_request(self):
        ctx = self.execution_context.context
        if isinstance(ctx, dict):
            return ctx.get("request")
        return getattr(ctx, "request", None)

    @staticmethod
    def _extract_token(request) -> Optional[str]:
        if request is None:
            return None
        auth: str = ""
        if hasattr(request, "headers"):
            auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def _decode_token(self, token: str) -> Optional[dict]:
        try:
            import jwt  # PyJWT — already in requirements.txt
            return jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"verify_exp": True},
            )
        except Exception as exc:
            logger.debug("GraphQL JWT decode failed: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------

class RateLimitMiddleware(SchemaExtension):
    """Per-user token-bucket rate limiter for GraphQL operations.

    Parameters
    ----------
    max_tokens:
        Maximum burst size (default 60 requests).
    refill_seconds:
        Window over which tokens refill to *max_tokens* (default 60 s).
    """

    # Shared across all instances/requests in the same process
    _buckets: dict[str, list] = {}

    def __init__(
        self,
        max_tokens: int = 60,
        refill_seconds: float = 60.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._max = max_tokens
        self._refill = refill_seconds

    # ------------------------------------------------------------------
    # SchemaExtension hook
    # ------------------------------------------------------------------

    def on_operation(self):  # type: ignore[override]
        identity = self._identity()
        if not self._check_and_consume(identity):
            from strawberry.types import ExecutionResult  # noqa: F401
            raise PermissionError(
                "GraphQL rate limit exceeded. Please slow down your requests."
            )
        yield  # execution happens here

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _identity(self) -> str:
        ctx = self.execution_context.context
        ctx_dict = ctx if isinstance(ctx, dict) else {}
        user_info = ctx_dict.get("user_info") or {}
        if user_info:
            return str(user_info.get("sub") or user_info.get("username") or "anon")
        request = ctx_dict.get("request")
        if request is not None:
            if hasattr(request, "remote_addr"):
                return str(request.remote_addr)
            if hasattr(request, "client"):
                host = getattr(request.client, "host", "unknown")
                return str(host)
        return "anon"

    def _check_and_consume(self, identity: str) -> bool:
        now = time.monotonic()
        if identity not in RateLimitMiddleware._buckets:
            RateLimitMiddleware._buckets[identity] = [self._max - 1, now]
            return True

        tokens, last = RateLimitMiddleware._buckets[identity]
        elapsed = now - last
        tokens = min(self._max, tokens + elapsed * (self._max / self._refill))
        last = now

        if tokens >= 1.0:
            RateLimitMiddleware._buckets[identity] = [tokens - 1, last]
            return True

        RateLimitMiddleware._buckets[identity] = [tokens, last]
        return False
