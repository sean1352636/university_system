"""REST API for Primary Attendance."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

attendance_bp = Blueprint("pri_attendance", __name__, url_prefix="/api/attendance")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.systems.primary.domain.academics.attendance import (
        attendance as data,
    )
    return data


# ---------------------------------------------------------------------------
# List / query
# ---------------------------------------------------------------------------
@attendance_bp.route("", methods=["GET"])
@attendance_bp.route("/", methods=["GET"])
@_token_required
def list_attendance():
    """List attendance records, filtered by date or pupil.

    Query params:
      - date=YYYY-MM-DD [&session=AM|PM]   -> records for that date
      - pupil_id=... [&date_from=..&date_to=..] -> records for that pupil
    """
    data = _data()
    date_iso = request.args.get("date")
    pupil_id = request.args.get("pupil_id")
    try:
        if pupil_id:
            rows = data.list_for_pupil(
                pupil_id,
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
            )
        elif date_iso:
            rows = data.list_for_date(
                date_iso, session=request.args.get("session")
            )
        else:
            return jsonify(
                {"error": "Provide either 'date' or 'pupil_id' query param"}
            ), 400
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@attendance_bp.route("/<int:record_id>", methods=["GET"])
@_token_required
def get_attendance(record_id: int):
    data = _data()
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Attendance record not found"}), 404
    return jsonify(_dump(rec))


# ---------------------------------------------------------------------------
# Create (upsert mark for a single pupil/date/session)
# ---------------------------------------------------------------------------
@attendance_bp.route("", methods=["POST"])
@attendance_bp.route("/", methods=["POST"])
@_token_required
def create_attendance():
    data = _data()
    body = request.get_json(silent=True) or {}
    try:
        rec = data.record_mark(
            pupil_id=body.get("pupil_id"),
            date_iso=body.get("date") or body.get("date_iso"),
            session=body.get("session"),
            mark=body.get("mark"),
            notes=body.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


# ---------------------------------------------------------------------------
# Bulk create
# ---------------------------------------------------------------------------
@attendance_bp.route("/bulk", methods=["POST"])
@_token_required
def bulk_attendance():
    data = _data()
    body = request.get_json(silent=True) or {}
    marks = body.get("marks")
    if not isinstance(marks, dict):
        return jsonify({"error": "'marks' must be an object mapping pupil_id->mark"}), 400
    try:
        result = data.bulk_record(
            date_iso=body.get("date") or body.get("date_iso"),
            session=body.get("session"),
            marks=marks,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"results": {pid: _dump(v) for pid, v in result.items()}}), 201


# ---------------------------------------------------------------------------
# Update (re-record an existing record's mark; upsert via record_mark)
# ---------------------------------------------------------------------------
@attendance_bp.route("/<int:record_id>", methods=["PUT"])
@_token_required
def update_attendance(record_id: int):
    data = _data()
    existing = data.get_record(record_id)
    if existing is None:
        return jsonify({"error": "Attendance record not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        rec = data.record_mark(
            pupil_id=body.get("pupil_id", existing.pupil_id),
            date_iso=body.get("date", body.get("date_iso", existing.date)),
            session=body.get("session", existing.session),
            mark=body.get("mark", existing.mark),
            notes=body.get("notes", existing.notes),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@attendance_bp.route("/<int:record_id>", methods=["DELETE"])
@_token_required
def delete_attendance(record_id: int):
    data = _data()
    if not data.delete_record(record_id):
        return jsonify({"error": "Attendance record not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------
@attendance_bp.route("/summary/daily", methods=["GET"])
@_token_required
def daily_summary():
    data = _data()
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"error": "'date' query param is required"}), 400
    try:
        return jsonify(_dump(data.daily_summary(date_iso)))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@attendance_bp.route("/summary/pupil/<pupil_id>", methods=["GET"])
@_token_required
def pupil_summary(pupil_id: str):
    data = _data()
    try:
        summary = data.pupil_summary(
            pupil_id,
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(summary))
