"""API version constants and legacy path handling.

``API_VERSION`` was a bare string in the app factory, which meant the
version appeared in f-strings scattered across registration, the OpenAPI
spec and the docs blueprint. Anything that needs to know the version now
asks here.

Legacy redirects exist because the pre-unification apps served
``/api/<thing>`` with no version segment, and older clients still do.
:func:`legacy_redirect_rules` turns those into permanent redirects rather
than 404s.
"""

from __future__ import annotations

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

#: Versions still answered. Add here before removing a prefix, so a
#: deprecation is a two-step change rather than a break.
SUPPORTED_VERSIONS = (API_VERSION,)


def versioned(path: str = "") -> str:
    """``versioned("/university")`` -> ``"/api/v1/university"``."""
    if not path:
        return API_PREFIX
    return API_PREFIX + ("" if path.startswith("/") else "/") + path


def reprefix(url_prefix: str | None, system: str) -> str:
    """Rewrite a blueprint's own prefix into the versioned system space.

    ``"/api/students"`` + ``"university"`` -> ``"/api/v1/university/students"``.
    Blueprints are written to be mountable standalone, so they carry a
    bare ``/api/...`` prefix; mounting is what adds the version and the
    system segment.
    """
    if url_prefix and url_prefix.startswith("/api"):
        return f"{API_PREFIX}/{system}" + url_prefix[4:]
    return f"{API_PREFIX}/{system}{url_prefix or ''}"


def legacy_redirect_rules() -> dict[str, str]:
    """Unversioned path -> versioned path, for permanent redirects."""
    return {
        "/api/auth": versioned("/auth"),
        "/api/health": versioned("/health"),
        "/api/docs": versioned("/docs"),
    }


__all__ = ["API_VERSION", "API_PREFIX", "SUPPORTED_VERSIONS",
           "versioned", "reprefix", "legacy_redirect_rules"]
