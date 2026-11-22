"""Public graduation checks for employers: is this award genuine, and the
graduate's shared transcript.

Both GETs are unauthenticated by design — an employer has no account — so
they say only what the certificate itself says, and both are rate limited
per IP, below the global default, to blunt guessing:

* ``GET /graduation/verify/<reference>`` — a certificate number or the
  verification code printed with the award (``graduation_conferral.verify``);
* ``GET /graduation/transcript/<token>`` — the frozen transcript behind a
  share link the graduate created (``graduation_transcripts.open_share``);
  opening it is counted, so the request commits.

Mounted under ``/api/v1/university``, which is where
``graduation_transcripts.share_url`` points.
"""

from __future__ import annotations

import html
import logging

from flask import Blueprint, Response, jsonify

from education_system.platform.delivery.api.rate_limiter import rate_limiter
from education_system.systems.university.application.graduation import (
    conferral as graduation_conferral,
)
from education_system.systems.university.application.graduation import (
    transcripts as graduation_transcripts,
)
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

graduation_bp = Blueprint("graduation_public", __name__, url_prefix="/api/graduation")

_GONE = ("withdrawn", "expired", "no longer current", "under review", "no longer valid")


@graduation_bp.route("/verify/<path:reference>", methods=["GET"])
@rate_limiter.limit("30/minute")
def verify(reference: str):
    """Check a certificate number or verification code."""
    conn = get_connection(row_factory=False)
    try:
        result = graduation_conferral.verify(conn, reference[:80])
        conn.commit()           # ensure() may create the graduation tables
    finally:
        conn.close()
    return jsonify(result), (200 if result.get("valid") or result.get("status") else 404)


def _page(title: str, message: str, status: int) -> Response:
    body = (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}"
            f"</title></head><body><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
            "</body></html>")
    return Response(body, status=status, mimetype="text/html")


@graduation_bp.route("/transcript/<token>", methods=["GET"])
@rate_limiter.limit("20/minute")
def transcript(token: str):
    """The shared transcript snapshot, or why it cannot be shown."""
    conn = get_connection(row_factory=False)
    try:
        result = graduation_transcripts.open_share(conn, token[:200])
        conn.commit()           # the opening is counted
    except Exception:
        conn.rollback()
        logger.exception("transcript share could not be opened")
        return _page("Transcript unavailable", "Please try again later.", 500)
    finally:
        conn.close()
    if not result.get("ok"):
        message = result.get("message") or "This link is not valid."
        gone = any(word in message for word in _GONE)
        return _page("Transcript unavailable", message, 410 if gone else 404)
    response = Response(result["html"], status=200, mimetype="text/html")
    response.headers["X-Transcript-SHA256"] = result["sha256"]
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


__all__ = ["graduation_bp"]
