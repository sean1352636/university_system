"""REST API for Nursery Welfare Requirements.

Exposes CRUD over EYFS welfare requirement records (area / status / review
schedule) plus a status summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

welfare_bp = Blueprint("nsy_welfare", __name__, url_prefix="/api/welfare")


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


@welfare_bp.route("", methods=["GET"])
@welfare_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    from education_system.systems.nursery.domain.pastoral.welfare import welfare as data

    status = request.args.get("status") or None
    rows = data.list_records(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@welfare_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.pastoral.welfare import welfare as data

    return jsonify(data.summary())


@welfare_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_record(record_id):
    from education_system.systems.nursery.domain.pastoral.welfare import welfare as data

    record = data.get_record(record_id)
    if record is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(record))


@welfare_bp.route("", methods=["POST"])
@welfare_bp.route("/", methods=["POST"])
@_token_required
def create_record():
    from education_system.systems.nursery.domain.pastoral.welfare import welfare as data

    payload = request.get_json(silent=True) or {}
    try:
        record = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(record)), 201


@welfare_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_record(record_id):
    from education_system.systems.nursery.domain.pastoral.welfare import welfare as data

    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        record = data.update_record(record_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(record))


@welfare_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_record(record_id):
    from education_system.systems.nursery.domain.pastoral.welfare import welfare as data

    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": record_id})
