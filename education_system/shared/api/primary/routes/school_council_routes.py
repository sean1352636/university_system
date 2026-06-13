"""REST API for Primary School Council."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

school_council_bp = Blueprint("pri_school_council", __name__, url_prefix="/api/school-council")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
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


def _bool(value) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on")


# ── Members ──────────────────────────────────────────────────────

@school_council_bp.route("/members", methods=["GET"])
@school_council_bp.route("/members/", methods=["GET"])
@_token_required
def list_members():
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    rows = data.list_members(
        student_id=request.args.get("student_id"),
        role=request.args.get("role"),
        status=request.args.get("status"),
        active_only=_bool(request.args.get("active_only", "")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@school_council_bp.route("/members/<int:member_id>", methods=["GET"])
@_token_required
def get_member(member_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    row = data.get_member(member_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@school_council_bp.route("/members", methods=["POST"])
@school_council_bp.route("/members/", methods=["POST"])
@_token_required
def create_member():
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_member(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@school_council_bp.route("/members/<int:member_id>", methods=["PUT"])
@_token_required
def update_member(member_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    if data.get_member(member_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_member(member_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@school_council_bp.route("/members/<int:member_id>", methods=["DELETE"])
@_token_required
def delete_member(member_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    if not data.delete_member(member_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Meetings ─────────────────────────────────────────────────────

@school_council_bp.route("/meetings", methods=["GET"])
@school_council_bp.route("/meetings/", methods=["GET"])
@_token_required
def list_meetings():
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    rows = data.list_meetings(
        meeting_type=request.args.get("meeting_type"),
        status=request.args.get("status"),
        upcoming_only=_bool(request.args.get("upcoming_only", "")),
        chair_like=request.args.get("chair_like"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@school_council_bp.route("/meetings/<int:meeting_id>", methods=["GET"])
@_token_required
def get_meeting(meeting_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    row = data.get_meeting(meeting_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@school_council_bp.route("/meetings", methods=["POST"])
@school_council_bp.route("/meetings/", methods=["POST"])
@_token_required
def create_meeting():
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_meeting(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@school_council_bp.route("/meetings/<int:meeting_id>", methods=["PUT"])
@_token_required
def update_meeting(meeting_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    if data.get_meeting(meeting_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_meeting(meeting_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@school_council_bp.route("/meetings/<int:meeting_id>", methods=["DELETE"])
@_token_required
def delete_meeting(meeting_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    if not data.delete_meeting(meeting_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Motions ──────────────────────────────────────────────────────

@school_council_bp.route("/motions", methods=["GET"])
@school_council_bp.route("/motions/", methods=["GET"])
@_token_required
def list_motions():
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    meeting_id = request.args.get("meeting_id", type=int)
    rows = data.list_motions(
        meeting_id=meeting_id,
        outcome=request.args.get("outcome"),
        pending_only=_bool(request.args.get("pending_only", "")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@school_council_bp.route("/motions/<int:motion_id>", methods=["GET"])
@_token_required
def get_motion(motion_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    row = data.get_motion(motion_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@school_council_bp.route("/meetings/<int:meeting_id>/motions", methods=["POST"])
@_token_required
def add_motion(meeting_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.add_motion(meeting_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@school_council_bp.route("/motions/<int:motion_id>", methods=["PUT"])
@_token_required
def update_motion(motion_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    if data.get_motion(motion_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_motion(motion_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@school_council_bp.route("/motions/<int:motion_id>", methods=["DELETE"])
@_token_required
def delete_motion(motion_id: int):
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    if not data.delete_motion(motion_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Summary ───────────────────────────────────────────────────────

@school_council_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.school_council import (
        school_council as data,
    )
    return jsonify(_dump(data.summary()))
