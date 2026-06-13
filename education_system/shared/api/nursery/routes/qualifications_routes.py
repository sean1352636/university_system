"""REST API for Nursery Qualifications & Training.

Exposes CRUD over structured staff training/qualification records, plus
expiring-soon and summary views.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

qualifications_bp = Blueprint("nsy_qualifications", __name__, url_prefix="/api/qualifications")


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
        out = dataclasses.asdict(obj)
        # expiry_status is a derived property, not a field — include it.
        if hasattr(obj, "expiry_status"):
            out["expiry_status"] = obj.expiry_status
        return out
    return obj


@qualifications_bp.route("", methods=["GET"])
@qualifications_bp.route("/", methods=["GET"])
@_token_required
def list_qualifications():
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    staff_id = request.args.get("staff_id")
    rows = data.list_records(staff_id=staff_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@qualifications_bp.route("/expiring", methods=["GET"])
@_token_required
def list_expiring_qualifications():
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    include_expired = request.args.get("include_expired", "true").lower() != "false"
    rows = data.list_expiring(include_expired=include_expired)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@qualifications_bp.route("/summary", methods=["GET"])
@_token_required
def qualifications_summary():
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    return jsonify(data.summary())


@qualifications_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_qualification(record_id):
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@qualifications_bp.route("", methods=["POST"])
@qualifications_bp.route("/", methods=["POST"])
@_token_required
def create_qualification():
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@qualifications_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_qualification(record_id):
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(record_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@qualifications_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_qualification(record_id):
    from education_system.nursery_system.modules.domain.qualifications import qualifications as data

    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
