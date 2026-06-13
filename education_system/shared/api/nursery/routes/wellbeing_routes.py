"""REST API for Nursery Wellbeing.

Exposes CRUD over wellbeing records plus a summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

wellbeing_bp = Blueprint("nsy_wellbeing", __name__, url_prefix="/api/wellbeing")


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


@wellbeing_bp.route("", methods=["GET"])
@wellbeing_bp.route("/", methods=["GET"])
@_token_required
def list_wellbeing():
    from education_system.nursery_system.modules.domain.wellbeing import wellbeing as data
    status = request.args.get("status")
    rows = data.list_records(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@wellbeing_bp.route("/summary", methods=["GET"])
@_token_required
def wellbeing_summary():
    from education_system.nursery_system.modules.domain.wellbeing import wellbeing as data
    return jsonify(data.summary())


@wellbeing_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_wellbeing(record_id):
    from education_system.nursery_system.modules.domain.wellbeing import wellbeing as data
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@wellbeing_bp.route("", methods=["POST"])
@wellbeing_bp.route("/", methods=["POST"])
@_token_required
def create_wellbeing():
    from education_system.nursery_system.modules.domain.wellbeing import wellbeing as data
    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@wellbeing_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_wellbeing(record_id):
    from education_system.nursery_system.modules.domain.wellbeing import wellbeing as data
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@wellbeing_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_wellbeing(record_id):
    from education_system.nursery_system.modules.domain.wellbeing import wellbeing as data
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
