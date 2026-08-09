"""Single source of truth for HTTP security headers and browser isolation.

Every Flask app in the platform registers this rather than hand-rolling its own
``after_request`` block. Previously each app had a slightly different header
set — the unified server sent CSP and HSTS but no ``Permissions-Policy``, the
university API repeated most of it, and the portal blueprints set their own
per-route CSP with no shared floor — which meant a new blueprint could silently
ship with weaker isolation than its neighbours.

What is enforced here:

* **CSP** with ``frame-ancestors``, ``base-uri`` and ``form-action``. The API
  default is the maximally restrictive ``default-src 'none'``, since a JSON
  endpoint should never load a resource. HTML routes opt into a looser
  document policy via :func:`document_csp`.
* **HSTS** outside development, with ``includeSubDomains`` and ``preload``.
* **X-Content-Type-Options: nosniff** so a mis-typed response is not sniffed
  into script.
* **Referrer-Policy** so a URL carrying a student or case identifier is not
  leaked to third-party hosts.
* **Permissions-Policy** denying camera, microphone, geolocation, payment,
  USB/serial/HID, and the other powerful features this platform never uses.
* **Cross-origin isolation** — COOP and CORP — so a malicious opener or
  embedder cannot reach into a portal window.
* **Banner suppression** — the ``Server`` header is flattened so the exact
  Werkzeug/Python build is not advertised to scanners.

It also refuses to let an app boot in production with debug or propagated
tracebacks enabled: a stack trace in a response body leaks file paths, SQL and
config, so the check is a startup failure rather than a warning.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, Response

logger = logging.getLogger(__name__)

__all__ = [
    "DEV_ENVIRONMENTS",
    "PERMISSIONS_POLICY",
    "API_CSP",
    "is_development",
    "document_csp",
    "apply_security_headers",
    "register_security_headers",
]

#: ``APP_ENV`` values that count as non-production. Anything else — including
#: an unset ``APP_ENV`` — is treated as production, so the strict path is the
#: default and a misconfigured deployment fails safe rather than open.
DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})

#: Powerful browser features the platform never uses. Denying them means a
#: successful XSS cannot silently turn on a webcam or read a location.
PERMISSIONS_POLICY = ", ".join(
    f"{feature}=()"
    for feature in (
        "accelerometer", "ambient-light-sensor", "autoplay", "battery",
        "camera", "display-capture", "document-domain", "encrypted-media",
        "fullscreen", "geolocation", "gyroscope", "hid", "idle-detection",
        "local-fonts", "magnetometer", "microphone", "midi", "payment",
        "picture-in-picture", "publickey-credentials-get", "screen-wake-lock",
        "serial", "usb", "web-share", "xr-spatial-tracking",
    )
)

#: CSP for JSON/API responses. An API response has no legitimate reason to
#: load or execute anything, so everything is denied.
API_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "sandbox"
)

_HSTS = "max-age=31536000; includeSubDomains; preload"


def is_development() -> bool:
    """True when ``APP_ENV`` names a non-production environment."""
    return os.getenv("APP_ENV", "production").strip().lower() in DEV_ENVIRONMENTS


def document_csp(
    *,
    allow_inline_styles: bool = False,
    frame_ancestors: str = "'none'",
    extra_img_src: str = "data:",
    connect_src: str = "'self'",
) -> str:
    """Build a CSP for an HTML document route.

    Scripts are always ``'self'`` — never ``'unsafe-inline'`` or
    ``'unsafe-eval'``, which would defeat the policy entirely. Inline *styles*
    can be opted into for pages that still carry ``style=`` attributes, but
    that is a migration crutch and the parameter exists so those pages are
    greppable.

    Args:
        allow_inline_styles: Permit ``style-src 'unsafe-inline'``.
        frame_ancestors: Who may frame this page. ``'none'`` unless the page is
            deliberately embeddable, in which case use ``'self'``.
        extra_img_src: Additional ``img-src`` sources beyond ``'self'``.
        connect_src: Where the page may make XHR/fetch/WebSocket calls.
    """
    style_src = "'self' 'unsafe-inline'" if allow_inline_styles else "'self'"
    return "; ".join(
        (
            "default-src 'self'",
            "script-src 'self'",
            f"style-src {style_src}",
            f"img-src 'self' {extra_img_src}".strip(),
            "font-src 'self' data:",
            f"connect-src {connect_src}",
            "object-src 'none'",
            "media-src 'self'",
            f"frame-ancestors {frame_ancestors}",
            "frame-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "upgrade-insecure-requests",
        )
    )


def apply_security_headers(response: Response, *, development: bool | None = None) -> Response:
    """Apply the platform header floor to a single response.

    Routes that need a looser CSP set ``response._custom_csp = True`` (and
    their own ``Content-Security-Policy``) before this runs; every *other*
    header is applied unconditionally, so a route can relax its content policy
    without accidentally dropping nosniff, Referrer-Policy or HSTS along with
    it. That coupling is exactly what the old per-app blocks got wrong.
    """
    dev = is_development() if development is None else development

    if not getattr(response, "_custom_csp", False):
        # Pick the policy from what is actually being sent rather than assuming
        # every response is JSON. API_CSP includes `sandbox` and
        # `default-src 'none'`, which would blank any HTML page that had not
        # remembered to opt out — so an HTML response gets the document policy
        # by default and only non-documents get the locked-down one.
        content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type in ("text/html", "application/xhtml+xml"):
            response.headers["Content-Security-Policy"] = document_csp()
        else:
            response.headers["Content-Security-Policy"] = API_CSP

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = PERMISSIONS_POLICY

    # X-Frame-Options is redundant next to frame-ancestors on modern browsers
    # but is still honoured by older ones, so both are sent. A route that has
    # deliberately set SAMEORIGIN (the embeddable portal shell) keeps it.
    response.headers.setdefault("X-Frame-Options", "DENY")

    # Cross-origin isolation: COOP severs the window.opener relationship so a
    # page that opened us cannot script our window; CORP stops other origins
    # embedding our responses as subresources.
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

    if not dev:
        response.headers["Strict-Transport-Security"] = _HSTS

    # Do not advertise the exact server build to scanners.
    response.headers["Server"] = "education-system"
    response.headers.pop("X-Powered-By", None)

    return response


def register_security_headers(app: Flask, *, enforce_no_debug: bool = True) -> None:
    """Install the header policy and the production debug guard on ``app``.

    Args:
        app: The Flask app to harden.
        enforce_no_debug: Raise at startup if the app would serve tracebacks in
            production. Only pass ``False`` from a test that is deliberately
            constructing a debug app.

    Raises:
        RuntimeError: in production, if debug mode or exception propagation is
            enabled — either would render a full stack trace into the response.
    """
    dev = is_development()

    if enforce_no_debug and not dev:
        if app.debug or app.config.get("DEBUG"):
            raise RuntimeError(
                "Flask debug mode is enabled but APP_ENV is production. The "
                "debugger serves stack traces and an interactive console to "
                "anyone who can reach the app. Unset FLASK_DEBUG/DEBUG."
            )
        if app.config.get("PROPAGATE_EXCEPTIONS"):
            raise RuntimeError(
                "PROPAGATE_EXCEPTIONS is enabled in production; unhandled "
                "errors would return a traceback instead of a generic 500."
            )
        if app.config.get("TRAP_HTTP_EXCEPTIONS"):
            raise RuntimeError("TRAP_HTTP_EXCEPTIONS must be off in production.")
        # Explicit: never expose the interactive debugger even if something
        # downstream flips DEBUG later in the boot sequence.
        app.config["PROPAGATE_EXCEPTIONS"] = False
        app.config["EXPLAIN_TEMPLATE_LOADING"] = False

    # Cookie flags belong with the header policy — they are the same decision.
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    if not dev:
        app.config.setdefault("SESSION_COOKIE_SECURE", True)

    @app.after_request
    def _security_headers(response: Response) -> Response:
        return apply_security_headers(response, development=dev)

    if dev:
        logger.warning(
            "APP_ENV is a development environment: HSTS is not being sent and "
            "session cookies are not marked Secure."
        )
