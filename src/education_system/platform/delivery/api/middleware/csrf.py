"""CSRF protection for cookie-authenticated requests.

A thin wrapper over the shared implementation in
``platform/governance/security``. It lives here so the app factory pulls
every middleware from one package and in one declared order — see
:mod:`.__init__`.

Scope: only requests that authenticate by cookie need this. A request
carrying ``Authorization: Bearer`` is not vulnerable to CSRF, because a
browser will not attach that header cross-origin on its own — and
demanding a token from API clients that already send a bearer would
break every one of them for no gain. Safe methods are exempt by
definition.
"""

from __future__ import annotations

import logging

from flask import g, jsonify, request

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_HEADER = "X-CSRF-Token"

#: Paths that must work before a token can exist.
EXEMPT_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/refresh",
                   "/api/v1/health", "/portal", "/static")


def _shared_validator():
    """The project's CSRF implementation, if it is available."""
    try:
        from education_system.platform.governance.security import csrf as _csrf
        return _csrf
    except Exception:
        return None


def _is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def register_csrf(app, *, enabled: bool = True) -> None:
    """Attach the CSRF check to *app*."""
    if not enabled:
        logger.info("CSRF protection disabled by configuration")
        return

    shared = _shared_validator()

    @app.before_request
    def _check_csrf():
        if request.method in SAFE_METHODS or _is_exempt(request.path):
            return None
        # Bearer-authenticated calls are not browser-driven; requiring a
        # CSRF token from them would break API clients without adding
        # protection.
        if request.headers.get("Authorization", "").startswith("Bearer "):
            return None
        if not request.cookies:
            return None   # nothing ambient to forge with

        token = request.headers.get(CSRF_HEADER) or request.form.get("csrf_token")
        if shared is not None and hasattr(shared, "validate_token"):
            try:
                if shared.validate_token(token):
                    return None
            except Exception:
                logger.warning("CSRF validation raised; treating as invalid",
                               exc_info=True)
        elif token and token == request.cookies.get("csrf_token"):
            # Double-submit fallback when the shared module is absent.
            return None

        logger.warning("CSRF rejected for %s %s from %s",
                       request.method, request.path, request.remote_addr)
        return jsonify({"error": "CSRF token missing or invalid"}), 403

    logger.info("CSRF protection enabled (shared implementation: %s)",
                "yes" if shared else "double-submit fallback")


__all__ = ["register_csrf", "CSRF_HEADER", "SAFE_METHODS", "EXEMPT_PREFIXES"]
