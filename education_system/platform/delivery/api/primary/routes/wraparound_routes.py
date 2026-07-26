"""REST API for Primary Wraparound Care (breakfast / after-school clubs)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

wraparound_bp = Blueprint("pri_wraparound", __name__, url_prefix="/api/wraparound")


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
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.systems.primary.domain.operations.daily_care.wraparound import (
        wraparound as data,
    )
    return data


def _bad_request(exc):
    return jsonify({"error": str(exc)}), 400


# --- Sessions -------------------------------------------------------------

@wraparound_bp.route("/sessions", methods=["GET"])
@wraparound_bp.route("/sessions/", methods=["GET"])
@_token_required
def list_sessions():
    data = _data()
    session_type = request.args.get("session_type")
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    try:
        rows = data.list_sessions(session_type=session_type, active_only=active_only)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@wraparound_bp.route("/sessions/<int:session_id>", methods=["GET"])
@_token_required
def get_session(session_id):
    data = _data()
    rec = data.get_session(session_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@wraparound_bp.route("/sessions", methods=["POST"])
@wraparound_bp.route("/sessions/", methods=["POST"])
@_token_required
def create_session():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_session(payload)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify(_dump(rec)), 201


@wraparound_bp.route("/sessions/<int:session_id>", methods=["PUT"])
@_token_required
def update_session(session_id):
    data = _data()
    if data.get_session(session_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_session(session_id, payload)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify(_dump(rec))


@wraparound_bp.route("/sessions/<int:session_id>/toggle", methods=["POST"])
@_token_required
def toggle_session(session_id):
    data = _data()
    if data.get_session(session_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.toggle_session_active(session_id)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify(_dump(rec))


@wraparound_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@_token_required
def delete_session(session_id):
    data = _data()
    if not data.delete_session(session_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "session_id": session_id})


@wraparound_bp.route("/sessions/<int:session_id>/summary", methods=["GET"])
@_token_required
def session_summary(session_id):
    data = _data()
    if data.get_session(session_id) is None:
        return jsonify({"error": "Not found"}), 404
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    try:
        result = data.session_summary(
            session_id, from_date=from_date, to_date=to_date)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify(_dump(result))


@wraparound_bp.route("/sessions/<int:session_id>/register", methods=["GET"])
@_token_required
def day_register(session_id):
    data = _data()
    date = request.args.get("date", "")
    try:
        rows = data.day_register(session_id, date)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify({"items": _dump(rows), "count": len(rows)})


# --- Attendance -----------------------------------------------------------

@wraparound_bp.route("/attendance", methods=["GET"])
@wraparound_bp.route("/attendance/", methods=["GET"])
@_token_required
def list_attendance():
    data = _data()
    sid = request.args.get("session_id")
    try:
        session_id = int(sid) if sid not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "session_id must be an integer"}), 400
    try:
        rows = data.list_attendance(
            session_id=session_id,
            pupil_id=request.args.get("pupil_id"),
            from_date=request.args.get("from_date"),
            to_date=request.args.get("to_date"),
            status=request.args.get("status"),
        )
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@wraparound_bp.route("/attendance/<int:attendance_id>", methods=["GET"])
@_token_required
def get_attendance(attendance_id):
    data = _data()
    rec = data.get_attendance(attendance_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@wraparound_bp.route("/attendance", methods=["POST"])
@wraparound_bp.route("/attendance/", methods=["POST"])
@_token_required
def book_attendance():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.book(payload)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify(_dump(rec)), 201


@wraparound_bp.route("/attendance/<int:attendance_id>/status", methods=["PUT"])
@_token_required
def set_attendance_status(attendance_id):
    data = _data()
    if data.get_attendance(attendance_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()
    try:
        rec = data.set_attendance_status(attendance_id, status)
    except data.ValidationError as exc:
        return _bad_request(exc)
    return jsonify(_dump(rec))


@wraparound_bp.route("/attendance/<int:attendance_id>", methods=["DELETE"])
@_token_required
def delete_attendance(attendance_id):
    data = _data()
    if not data.delete_attendance(attendance_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "attendance_id": attendance_id})


# --- Aggregate ------------------------------------------------------------

@wraparound_bp.route("/counts", methods=["GET"])
@_token_required
def counts():
    data = _data()
    return jsonify(_dump(data.counts()))
