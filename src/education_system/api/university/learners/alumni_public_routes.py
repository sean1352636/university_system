"""The public unsubscribe link printed in alumni newsletters.

``GET /alumni/unsubscribe/<token>`` withdraws newsletter consent for the
alumnus the token was issued to (``alumni_comms.unsubscribe``). It is
unauthenticated by design — the reader is following a link in an e-mail —
and rate limited per IP. The token is random and only its hash is stored.

Mounted under ``/api/v1/university``, which is where
``alumni_comms.unsubscribe_url`` points.
"""

from __future__ import annotations

import html
import logging

from flask import Blueprint, Response

from education_system.platform.delivery.api.rate_limiter import rate_limiter
from education_system.systems.university.application.alumni import comms as alumni_comms
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

alumni_public_bp = Blueprint("alumni_public", __name__, url_prefix="/api/alumni")


def _page(title: str, message: str, status: int) -> Response:
    body = (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}"
            f"</title></head><body><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
            "</body></html>")
    response = Response(body, status=status, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@alumni_public_bp.route("/unsubscribe/<token>", methods=["GET"])
@rate_limiter.limit("20/minute")
def unsubscribe(token: str):
    """Stop alumni newsletters for whoever this link was sent to."""
    conn = get_connection(row_factory=False)
    try:
        result = alumni_comms.unsubscribe(conn, token[:200])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("alumni unsubscribe failed")
        return _page("Something went wrong", "Please try again later.", 500)
    finally:
        conn.close()
    if not result.get("ok"):
        return _page("Link not recognised", result.get("message") or "This link is not valid.",
                     404)
    return _page("Unsubscribed", result["message"], 200)
