"""Web portal routes: serves the single-page application UI."""

from __future__ import annotations

import os

from flask import Blueprint, make_response, send_from_directory

web_bp = Blueprint("web", __name__)

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def _send_index():
    """Read and return the index.html with appropriate headers."""
    response = make_response(send_from_directory(_STATIC_DIR, "index.html"))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    # Override CSP so the portal page can load its own static JS/CSS.
    response._custom_csp = True
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self';"
    )
    # Allow framing within same origin for the portal
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@web_bp.route("/portal")
@web_bp.route("/portal/")
def portal():
    """Serve the web portal single-page application."""
    return _send_index()
