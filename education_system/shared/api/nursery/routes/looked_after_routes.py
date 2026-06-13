"""REST API for Nursery Looked-After Children.

Exposes CRUD over the looked_after_children safeguarding records, plus a summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

looked_after_bp = Blueprint("nsy_looked_after", __name__, url_prefix="/api/looked-after")


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


@looked_after_bp.route("", methods=["GET"])
@looked_after_bp.route("/", methods=["GET"])
@_token_required
def list_looked_after():
    from education_system.nursery_system.modules.domain.looked_after import looked_after as data
    status = request.args.get("status") or None
    rows = data.list_records(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@looked_after_bp.route("/summary", methods=["GET"])
@_token_required
def looked_after_summary():
    from education_system.nursery_system.modules.domain.looked_after import looked_after as data
    return jsonify(data.summary())


@looked_after_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_looked_after(record_id):
    from education_system.nursery_system.modules.domain.looked_after import looked_after as data
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@looked_after_bp.route("", methods=["POST"])
@looked_after_bp.route("/", methods=["POST"])
@_token_required
def create_looked_after():
    from education_system.nursery_system.modules.domain.looked_after import looked_after as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@looked_after_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_looked_after(record_id):
    from education_system.nursery_system.modules.domain.looked_after import looked_after as data
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(record_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@looked_after_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_looked_after(record_id):
    from education_system.nursery_system.modules.domain.looked_after import looked_after as data
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": record_id})
