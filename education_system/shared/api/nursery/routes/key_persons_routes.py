"""REST API for Nursery Key Person Assignment.

Exposes EYFS key-person assignments per child and practitioner caseloads, plus
endpoints to set/clear a child's key person.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

key_persons_bp = Blueprint("nsy_key_persons", __name__, url_prefix="/api/key-persons")


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


@key_persons_bp.route("", methods=["GET"])
@key_persons_bp.route("/", methods=["GET"])
@_token_required
def list_key_persons():
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    room = request.args.get("room") or None
    unassigned_only = request.args.get("unassigned_only", "").lower() in ("1", "true", "yes")
    rows = data.list_assignments(room=room, unassigned_only=unassigned_only)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@key_persons_bp.route("/unassigned", methods=["GET"])
@_token_required
def list_unassigned():
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    rows = data.list_unassigned()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@key_persons_bp.route("/caseloads", methods=["GET"])
@_token_required
def list_caseloads():
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    include_unassigned = request.args.get("include_unassigned", "true").lower() not in (
        "0", "false", "no",
    )
    rows = data.list_caseloads(include_unassigned=include_unassigned)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@key_persons_bp.route("/summary", methods=["GET"])
@_token_required
def get_summary():
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    return jsonify(data.summary())


@key_persons_bp.route("/staff-choices", methods=["GET"])
@_token_required
def staff_choices():
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    pairs = data.list_staff_choices()
    return jsonify({"items": [{"staff_id": sid, "label": label} for sid, label in pairs]})


@key_persons_bp.route("/<pupil_id>", methods=["GET"])
@_token_required
def get_key_person(pupil_id):
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    a = data.get_assignment(pupil_id)
    if a is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(a))


@key_persons_bp.route("/<pupil_id>", methods=["PUT"])
@_token_required
def set_key_person(pupil_id):
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    payload = request.get_json(silent=True) or {}
    staff_id = payload.get("staff_id") or payload.get("key_person")
    try:
        a = data.assign(pupil_id, staff_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(a))


@key_persons_bp.route("/<pupil_id>", methods=["DELETE"])
@_token_required
def clear_key_person(pupil_id):
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    try:
        a = data.assign(pupil_id, None)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(_dump(a))


@key_persons_bp.route("/rooms/<room>/assign", methods=["POST"])
@_token_required
def assign_room(room):
    from education_system.nursery_system.modules.domain.key_persons import key_persons as data

    payload = request.get_json(silent=True) or {}
    staff_id = payload.get("staff_id") or payload.get("key_person") or ""
    try:
        n = data.assign_room(room, staff_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"room": room, "staff_id": staff_id, "assigned": n})
