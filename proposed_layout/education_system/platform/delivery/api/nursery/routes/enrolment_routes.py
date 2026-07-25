"""REST API for Nursery Registration & Enrolment.

Exposes CRUD over the ``enrolments`` table plus search, by-pupil lookup, and a
withdraw action for the nursery early-years enrolment module.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

enrolment_bp = Blueprint("nsy_enrolment", __name__, url_prefix="/api/enrolment")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "y", "yes", "true", "on")


@enrolment_bp.route("", methods=["GET"])
@_token_required
def list_enrolments():
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    q = request.args.get("q")
    if q:
        rows = data.search_enrolments(q)
    else:
        include_withdrawn = not _truthy(request.args.get("active_only"))
        rows = data.list_enrolments(include_withdrawn=include_withdrawn)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@enrolment_bp.route("/<enrolment_id>", methods=["GET"])
@_token_required
def get_enrolment(enrolment_id):
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    enr = data.get_enrolment(enrolment_id)
    if enr is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(enr))


@enrolment_bp.route("/by-pupil/<pupil_id>", methods=["GET"])
@_token_required
def get_by_pupil(pupil_id):
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    enr = data.get_by_pupil(pupil_id)
    if enr is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(enr))


@enrolment_bp.route("", methods=["POST"])
@_token_required
def create_enrolment():
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    try:
        enr = data.create_enrolment(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(enr)), 201


@enrolment_bp.route("/<enrolment_id>", methods=["PUT"])
@_token_required
def update_enrolment(enrolment_id):
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    if data.get_enrolment(enrolment_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        enr = data.update_enrolment(enrolment_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(enr))


@enrolment_bp.route("/<enrolment_id>", methods=["DELETE"])
@_token_required
def delete_enrolment(enrolment_id):
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    if not data.delete_enrolment(enrolment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "enrolment_id": enrolment_id})


@enrolment_bp.route("/<enrolment_id>/withdraw", methods=["POST"])
@_token_required
def withdraw_enrolment(enrolment_id):
    from education_system.systems.nursery.domain.admissions.enrolment import enrolment as data
    body = request.get_json(silent=True) or {}
    take_off_roll = bool(body.get("take_off_roll", True))
    try:
        enr = data.withdraw(enrolment_id, take_off_roll=take_off_roll)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(_dump(enr))
