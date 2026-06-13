"""REST API for Nursery Paediatric First Aid.

Exposes CRUD over staff PFA certificates plus a summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

first_aid_bp = Blueprint("nsy_first_aid", __name__, url_prefix="/api/first-aid")


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
        data = dataclasses.asdict(obj)
        # Surface derived state that isn't stored as a field.
        for prop in ("validity", "is_current"):
            if hasattr(obj, prop):
                data[prop] = getattr(obj, prop)
        return data
    return obj


@first_aid_bp.route("", methods=["GET"])
@first_aid_bp.route("/", methods=["GET"])
@_token_required
def list_certificates():
    from education_system.nursery_system.modules.domain.first_aid import first_aid as data
    staff_id = request.args.get("staff_id") or None
    rows = data.list_certificates(staff_id=staff_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@first_aid_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.nursery_system.modules.domain.first_aid import first_aid as data
    return jsonify(data.summary())


@first_aid_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_certificate(record_id):
    from education_system.nursery_system.modules.domain.first_aid import first_aid as data
    cert = data.get_certificate(record_id)
    if cert is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(cert))


@first_aid_bp.route("", methods=["POST"])
@first_aid_bp.route("/", methods=["POST"])
@_token_required
def create_certificate():
    from education_system.nursery_system.modules.domain.first_aid import first_aid as data
    try:
        cert = data.create_certificate(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(cert)), 201


@first_aid_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_certificate(record_id):
    from education_system.nursery_system.modules.domain.first_aid import first_aid as data
    if data.get_certificate(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        cert = data.update_certificate(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(cert))


@first_aid_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_certificate(record_id):
    from education_system.nursery_system.modules.domain.first_aid import first_aid as data
    if not data.delete_certificate(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": record_id})
