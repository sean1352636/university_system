"""REST API for Nursery Attendance Report + register.

Exposes the daily register (list/upsert) and aggregated attendance reporting.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

attendance_report_bp = Blueprint("nsy_attendance_report", __name__, url_prefix="/api/attendance-report")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


@attendance_report_bp.route("", methods=["GET"])
@attendance_report_bp.route("/", methods=["GET"])
@_token_required
def list_register():
    """Register rows for a single date. Requires ?date=YYYY-MM-DD."""
    from education_system.nursery_system.modules.domain.attendance_report import (
        attendance_report as data,
    )
    attend_date = request.args.get("date")
    if not attend_date:
        attend_date = data.default_range()[1]  # today
    try:
        rows = data.list_for_date(attend_date)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows), "date": attend_date})


@attendance_report_bp.route("/children", methods=["GET"])
@_token_required
def list_children():
    """Active children eligible for the register: (pupil_id, name, room)."""
    from education_system.nursery_system.modules.domain.attendance_report import (
        attendance_report as data,
    )
    rows = [
        {"pupil_id": pid, "name": name, "room": room}
        for pid, name, room in data.active_children()
    ]
    return jsonify({"items": rows, "count": len(rows)})


@attendance_report_bp.route("", methods=["POST"])
@attendance_report_bp.route("/", methods=["POST"])
@_token_required
def mark_register():
    """UPSERT a register row for a child-date-session."""
    from education_system.nursery_system.modules.domain.attendance_report import (
        attendance_report as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        data.mark_attendance(
            payload.get("pupil_id"),
            payload.get("attend_date"),
            payload.get("status"),
            session=payload.get("session", "all-day"),
            arrival_time=payload.get("arrival_time"),
            departure_time=payload.get("departure_time"),
            absence_reason=payload.get("absence_reason"),
            notes=payload.get("notes"),
            room=payload.get("room"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok"}), 201


@attendance_report_bp.route("/report", methods=["GET"])
@_token_required
def attendance_report_summary():
    """Aggregated attendance rates over a date range. ?date_from&date_to&room."""
    from education_system.nursery_system.modules.domain.attendance_report import (
        attendance_report as data,
    )
    lo, hi = data.default_range()
    date_from = request.args.get("date_from", lo)
    date_to = request.args.get("date_to", hi)
    room = request.args.get("room")
    try:
        rep = data.report(date_from, date_to, room=room)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rep))


@attendance_report_bp.route("/export", methods=["POST"])
@_token_required
def export_register():
    """Write the per-child breakdown to CSV; return path + row count."""
    from education_system.nursery_system.modules.domain.attendance_report import (
        attendance_report as data,
    )
    payload = request.get_json(silent=True) or {}
    lo, hi = data.default_range()
    try:
        result = data.export_csv(
            payload.get("date_from", lo),
            payload.get("date_to", hi),
            room=payload.get("room"),
            path=payload.get("path"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(_dump(result)), 201
