"""The private calendar feed a student or member of staff subscribes to
from Outlook or Google Calendar.

``GET /calendar/feed/<token>.ics`` returns the iCalendar behind the link
(``calendar_events.feed_ics``): the published key dates, the events the
person may see and their own timetable. Calendar apps cannot sign in, so
the route is unauthenticated; the token is random, only its hash is stored,
the person can turn it off, and requests are rate limited per IP. Fetching
records when the feed was last used, so the request commits.

Mounted under ``/api/v1/university``, which is where
``calendar_events.feed_url`` points.
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response

from education_system.platform.delivery.api.rate_limiter import rate_limiter
from education_system.systems.university.application.academic_calendar import (
    events as calendar_events,
)
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

calendar_feed_bp = Blueprint("calendar_feed", __name__, url_prefix="/api/calendar")


@calendar_feed_bp.route("/feed/<token>.ics", methods=["GET"])
@rate_limiter.limit("30/minute")
def feed(token: str):
    """The person's calendar as iCalendar, or 404 for a dead link."""
    conn = get_connection(row_factory=False)
    try:
        text = calendar_events.feed_ics(conn, token[:200])
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("calendar feed failed")
        return Response("The calendar could not be built. Try again later.\n", status=500,
                        mimetype="text/plain")
    finally:
        conn.close()
    if text is None:
        return Response("This calendar link is not valid or has been turned off.\n",
                        status=404, mimetype="text/plain")
    response = Response(text, status=200, mimetype="text/calendar")
    response.headers["Cache-Control"] = "private, max-age=900"
    response.headers["X-Robots-Tag"] = "noindex"
    return response
