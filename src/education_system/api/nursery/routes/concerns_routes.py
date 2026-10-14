"""REST API for Nursery Concerns & Referrals.

Exposes CRUD over the safeguarding concern_referrals records, plus a summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

concerns_bp = Blueprint("nsy_concerns", __name__, url_prefix="/api/concerns")


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


@concerns_bp.route("", methods=["GET"])
@concerns_bp.route("/", methods=["GET"])
@_token_required
def list_concerns():
    from education_system.systems.nursery.domain.safeguarding.concerns import concerns as data
    status = request.args.get("status") or None
    rows = data.list_records(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@concerns_bp.route("/summary", methods=["GET"])
@_token_required
def concerns_summary():
    from education_system.systems.nursery.domain.safeguarding.concerns import concerns as data
    return jsonify(data.summary())


@concerns_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_concern(record_id):
    from education_system.systems.nursery.domain.safeguarding.concerns import concerns as data
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@concerns_bp.route("", methods=["POST"])
@concerns_bp.route("/", methods=["POST"])
@_token_required
def create_concern():
    from education_system.systems.nursery.domain.safeguarding.concerns import concerns as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@concerns_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_concern(record_id):
    from education_system.systems.nursery.domain.safeguarding.concerns import concerns as data
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(record_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@concerns_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_concern(record_id):
    from education_system.systems.nursery.domain.safeguarding.concerns import concerns as data
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": record_id})
