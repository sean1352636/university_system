"""REST API for Nursery Allergies & Dietary Requirements.

Exposes CRUD over the structured allergy / intolerance / dietary register
(``dietary_requirements``) plus a summary endpoint and a status setter.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

allergies_bp = Blueprint("nsy_allergies", __name__, url_prefix="/api/allergies")


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


@allergies_bp.route("", methods=["GET"])
@allergies_bp.route("/", methods=["GET"])
@_token_required
def list_allergies():
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    rows = data.list_records(
        pupil_id=request.args.get("pupil_id"),
        status=request.args.get("status"),
        category=request.args.get("category"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@allergies_bp.route("/summary", methods=["GET"])
@_token_required
def allergies_summary():
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    return jsonify(data.summary())


@allergies_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_allergy(record_id):
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@allergies_bp.route("", methods=["POST"])
@allergies_bp.route("/", methods=["POST"])
@_token_required
def create_allergy():
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@allergies_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_allergy(record_id):
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@allergies_bp.route("/<record_id>/status", methods=["PUT"])
@_token_required
def set_allergy_status(record_id):
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.set_status(record_id, payload.get("status", ""))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@allergies_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_allergy(record_id):
    from education_system.systems.nursery.domain.pastoral.health.allergies import allergies as data

    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
