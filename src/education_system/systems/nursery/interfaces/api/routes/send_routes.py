"""REST API for Nursery SEND & Additional Needs.

Exposes CRUD over send_records (children on SEN Support / with additional needs).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

send_bp = Blueprint("nsy_send", __name__, url_prefix="/api/send")


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


@send_bp.route("", methods=["GET"])
@send_bp.route("/", methods=["GET"])
@_token_required
def list_send():
    from education_system.systems.nursery.domain.pastoral.send import send as data
    status = request.args.get("status") or None
    rows = data.list_records(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@send_bp.route("/summary", methods=["GET"])
@_token_required
def send_summary():
    from education_system.systems.nursery.domain.pastoral.send import send as data
    return jsonify(data.summary())


@send_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_send(record_id):
    from education_system.systems.nursery.domain.pastoral.send import send as data
    record = data.get_record(record_id)
    if record is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(record))


@send_bp.route("", methods=["POST"])
@send_bp.route("/", methods=["POST"])
@_token_required
def create_send():
    from education_system.systems.nursery.domain.pastoral.send import send as data
    try:
        record = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(record)), 201


@send_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_send(record_id):
    from education_system.systems.nursery.domain.pastoral.send import send as data
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        record = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(record))


@send_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_send(record_id):
    from education_system.systems.nursery.domain.pastoral.send import send as data
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
