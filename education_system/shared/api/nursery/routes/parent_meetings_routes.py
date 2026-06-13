"""REST API for Nursery Parent Meetings.

Exposes CRUD over scheduled parent/staff meetings plus pupil and staff choice
lists used when scheduling.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

parent_meetings_bp = Blueprint("nsy_parent_meetings", __name__, url_prefix="/api/parent-meetings")


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


@parent_meetings_bp.route("", methods=["GET"])
@parent_meetings_bp.route("/", methods=["GET"])
@_token_required
def list_meetings():
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_meetings(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@parent_meetings_bp.route("/<meeting_id>", methods=["GET"])
@_token_required
def get_meeting(meeting_id):
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    meeting = data.get_meeting(meeting_id)
    if meeting is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(meeting))


@parent_meetings_bp.route("", methods=["POST"])
@parent_meetings_bp.route("/", methods=["POST"])
@_token_required
def create_meeting():
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    payload = request.get_json(silent=True) or {}
    try:
        meeting = data.create_meeting(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(meeting)), 201


@parent_meetings_bp.route("/<meeting_id>", methods=["PUT"])
@_token_required
def update_meeting(meeting_id):
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    if data.get_meeting(meeting_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        meeting = data.update_meeting(meeting_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(meeting))


@parent_meetings_bp.route("/<meeting_id>", methods=["DELETE"])
@_token_required
def delete_meeting(meeting_id):
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    if not data.delete_meeting(meeting_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "meeting_id": meeting_id})


@parent_meetings_bp.route("/pupil-choices", methods=["GET"])
@_token_required
def list_pupil_choices():
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    rows = data.list_pupil_choices()
    items = [{"pupil_id": pid, "label": label} for pid, label in rows]
    return jsonify({"items": items, "count": len(items)})


@parent_meetings_bp.route("/staff-choices", methods=["GET"])
@_token_required
def list_staff_choices():
    from education_system.nursery_system.modules.domain.parent_meetings import (
        parent_meetings as data,
    )

    rows = data.list_staff_choices()
    items = [{"staff_id": sid, "label": label} for sid, label in rows]
    return jsonify({"items": items, "count": len(items)})
