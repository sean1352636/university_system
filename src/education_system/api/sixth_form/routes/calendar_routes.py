"""REST API for the Sixth Form Calendar.

Mounted by the unified server under ``/api/v1/sixthform/calendar``:

* GET    /                       — filtered event list
* POST   /                       — create an event
* GET    /<id>                   — one event
* PUT    /<id>                   — update
* POST   /<id>/status            — change status
* DELETE /<id>                   — archive (soft delete)
* GET    /day/<date>             — one day's events
* GET    /week/<date>            — the Mon–Sun week containing a date
* GET    /summary                — counts
* GET    /<id>/bookings          — the attendance list
* POST   /<id>/bookings          — book (waitlists when full)
* DELETE /<id>/bookings/<person> — cancel a booking
* GET    /portal/parent          — the parent portal feed
* GET    /portal/student/<id>    — a student's feed
* GET    /feed.ics               — the ICS subscription

Auth follows :mod:`academic_year_routes`: everything requires a
token except the ``.ics`` feed, which Outlook and Google fetch with
no header support — it is gated by an opaque ``token`` query string
(``SIXTHFORM_CALENDAR_FEED_TOKEN``) and serves only what the given
viewer kind may see, never Confidential rows.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import hmac
import os

from flask import Blueprint, Response, g, jsonify, request

from education_system.api.sixth_form import access_gate

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("sf_calendar", __name__,
                        url_prefix="/api/calendar")


def _token_required(view):
    view = access_gate.gate(view)
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


# ── Lazy domain imports (kept out of module import time) ──────────

def _data():
    from education_system.systems.sixth_form.domain.academics.calendar import (
        calendar as data,
    )
    return data


def _bookings():
    from education_system.systems.sixth_form.domain.academics.calendar import (
        calendar_bookings,
    )
    return calendar_bookings


def _governance():
    from education_system.systems.sixth_form.domain.academics.calendar import (
        calendar_governance,
    )
    return calendar_governance


def _portal():
    from education_system.systems.sixth_form.domain.academics.calendar import (
        calendar_portal,
    )
    return calendar_portal


def _ics():
    from education_system.systems.sixth_form.domain.academics.calendar import (
        calendar_ics,
    )
    return calendar_ics


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _actor() -> str | None:
    user = getattr(g, "current_user", None) or {}
    return user.get("sub") or user.get("username")


_BOOL_KEYS = ("overlapping", "upcoming_only", "include_deleted")
_STR_KEYS = ("event_type", "audience", "status", "location_like",
             "organiser_like", "title_like", "text_like",
             "department", "visibility", "date_from", "date_to")


# ── Events ────────────────────────────────────────────────────────

@calendar_bp.route("", methods=["GET"])
@calendar_bp.route("/", methods=["GET"])
@_token_required
def list_events():
    data = _data()
    kwargs = {}
    for key in _STR_KEYS:
        val = request.args.get(key)
        if val is not None:
            kwargs[key] = val
    for key in _BOOL_KEYS:
        val = request.args.get(key)
        if val is not None:
            kwargs[key] = val.lower() in ("1", "true", "yes")
    limit = request.args.get("limit")
    if limit is not None:
        try:
            kwargs["limit"] = int(limit)
        except ValueError:
            return jsonify({"error": "limit must be a number"}), 400
    try:
        rows = data.list_events(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@calendar_bp.route("", methods=["POST"])
@calendar_bp.route("/", methods=["POST"])
@_token_required
def create_event():
    data = _data()
    governance = _governance()
    payload = request.get_json(silent=True) or {}
    try:
        event = governance.audited_create(payload, actor=_actor())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(event)), 201


@calendar_bp.route("/<int:event_id>", methods=["GET"])
@_token_required
def get_event(event_id: int):
    data = _data()
    event = data.get_event(event_id)
    if event is None:
        return jsonify({"error": f"No event #{event_id}"}), 404
    return jsonify(_dump(event))


@calendar_bp.route("/<int:event_id>", methods=["PUT", "PATCH"])
@_token_required
def update_event(event_id: int):
    data = _data()
    governance = _governance()
    payload = request.get_json(silent=True) or {}
    try:
        event = governance.audited_update(event_id, payload,
                                          actor=_actor())
    except data.ValidationError as exc:
        code = 404 if "No event" in str(exc) else 400
        return jsonify({"error": str(exc)}), code
    return jsonify(_dump(event))


@calendar_bp.route("/<int:event_id>/status", methods=["POST"])
@_token_required
def set_status(event_id: int):
    data = _data()
    governance = _governance()
    payload = request.get_json(silent=True) or {}
    status = payload.get("status", "")
    try:
        event = governance.audited_set_status(
            event_id, status, actor=_actor(),
            reason=payload.get("reason"))
    except data.ValidationError as exc:
        code = 404 if "No event" in str(exc) else 400
        return jsonify({"error": str(exc)}), code
    return jsonify(_dump(event))


@calendar_bp.route("/<int:event_id>", methods=["DELETE"])
@_token_required
def archive_event(event_id: int):
    """Archive, not destroy — restore via the GUI/CLI archive."""
    governance = _governance()
    done = governance.audited_archive(event_id, actor=_actor())
    if not done:
        return jsonify({"error": f"No event #{event_id}"}), 404
    return jsonify({"archived": event_id})


# ── Reads by shape ────────────────────────────────────────────────

@calendar_bp.route("/day/<date_iso>", methods=["GET"])
@_token_required
def day(date_iso: str):
    data = _data()
    try:
        rows = data.events_on(date_iso)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"date": date_iso, "items": _dump(rows),
                    "count": len(rows)})


@calendar_bp.route("/week/<date_iso>", methods=["GET"])
@_token_required
def week(date_iso: str):
    data = _data()
    try:
        rows = data.events_in_week(date_iso)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"anchor": date_iso, "items": _dump(rows),
                    "count": len(rows)})


@calendar_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    kwargs = {}
    window = request.args.get("upcoming_window_days")
    if window is not None:
        try:
            kwargs["upcoming_window_days"] = int(window)
        except ValueError:
            return jsonify({"error": "upcoming_window_days must "
                                     "be a number"}), 400
    return jsonify(_dump(data.summary(**kwargs)))


# ── Bookings ──────────────────────────────────────────────────────

@calendar_bp.route("/<int:event_id>/bookings", methods=["GET"])
@_token_required
def list_bookings(event_id: int):
    data = _data()
    bookings = _bookings()
    try:
        summ = bookings.booking_summary(event_id)
        rows = bookings.attendance_list(event_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"summary": _dump(summ), "items": _dump(rows)})


@calendar_bp.route("/<int:event_id>/bookings", methods=["POST"])
@_token_required
def book(event_id: int):
    data = _data()
    bookings = _bookings()
    payload = request.get_json(silent=True) or {}
    try:
        got = bookings.book(
            event_id, payload.get("person", ""),
            person_name=payload.get("person_name"),
            note=payload.get("note"))
    except data.ValidationError as exc:
        code = 404 if "No event" in str(exc) else 400
        return jsonify({"error": str(exc)}), code
    return jsonify(_dump(got)), 201


@calendar_bp.route("/<int:event_id>/bookings/<person>",
                   methods=["DELETE"])
@_token_required
def cancel_booking(event_id: int, person: str):
    data = _data()
    bookings = _bookings()
    try:
        got = bookings.cancel(event_id, person)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(got))


# ── Portal feeds ──────────────────────────────────────────────────

@calendar_bp.route("/portal/parent", methods=["GET"])
@_token_required
def parent_feed():
    portal = _portal()
    feed = portal.feed_for_parent()
    return jsonify(feed.to_dict())


@calendar_bp.route("/portal/student/<student_id>", methods=["GET"])
@_token_required
def student_feed(student_id: str):
    data = _data()
    portal = _portal()
    try:
        feed = portal.feed_for_student(student_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(feed.to_dict())


# ── The ICS subscription ──────────────────────────────────────────

@calendar_bp.route("/feed.ics", methods=["GET"])
def ics_feed():
    """The standing subscription URL for Outlook/Google.

    No auth header (calendar clients cannot send one) — gated by an
    opaque ``token`` query string instead, and never serves
    Confidential events regardless of the viewer parameter.
    """
    expected = os.environ.get("SIXTHFORM_CALENDAR_FEED_TOKEN")
    if not expected or not hmac.compare_digest(
            request.args.get("token") or "", expected):
        return jsonify({"error": "Unauthorized"}), 401
    data = _data()
    ics = _ics()
    viewer = request.args.get("viewer", "public")
    # A URL parameter must not be able to claim staff eyes.
    if viewer not in ("public", "parent", "student"):
        viewer = "public"
    try:
        text = ics.feed(viewer=viewer,
                        audience=request.args.get("audience"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return Response(
        text, mimetype="text/calendar",
        headers={"Content-Disposition":
                 'attachment; filename="sixthform.ics"'})
