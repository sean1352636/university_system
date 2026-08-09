"""REST API for Nursery Accident & Incident Log.

Exposes CRUD plus status-setting and a summary over the statutory
accident / incident / near-miss register (the ``accident_records`` table).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

accident_log_bp = Blueprint("nsy_accident_log", __name__, url_prefix="/api/accident-log")


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


@accident_log_bp.route("", methods=["GET"])
@accident_log_bp.route("/", methods=["GET"])
@_token_required
def list_accident_records():
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    record_type = request.args.get("record_type")
    status = request.args.get("status")
    riddor_only = request.args.get("riddor_only", "").strip().lower() in (
        "1", "y", "yes", "true", "on")
    rows = data.list_records(
        record_type=record_type, status=status, riddor_only=riddor_only)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@accident_log_bp.route("/summary", methods=["GET"])
@_token_required
def accident_summary():
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    return jsonify(data.summary())


@accident_log_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_accident_record(record_id):
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@accident_log_bp.route("", methods=["POST"])
@accident_log_bp.route("/", methods=["POST"])
@_token_required
def create_accident_record():
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@accident_log_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_accident_record(record_id):
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(record_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@accident_log_bp.route("/<record_id>/status", methods=["PUT"])
@_token_required
def set_accident_status(record_id):
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.set_status(record_id, payload.get("status"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@accident_log_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_accident_record(record_id):
    from education_system.systems.nursery.domain.pastoral.health.accident_log import accident_log as data

    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
