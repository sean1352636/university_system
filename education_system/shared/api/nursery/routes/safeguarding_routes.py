"""REST API for Nursery Safeguarding / Child Protection.

Exposes CRUD over child-protection concerns (open -> monitoring -> referred ->
closed workflow) plus a status summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

safeguarding_bp = Blueprint("nsy_safeguarding", __name__, url_prefix="/api/safeguarding")


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


@safeguarding_bp.route("", methods=["GET"])
@safeguarding_bp.route("/", methods=["GET"])
@_token_required
def list_concerns():
    from education_system.nursery_system.modules.domain.safeguarding import safeguarding as data

    status = request.args.get("status") or None
    rows = data.list_concerns(status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@safeguarding_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.nursery_system.modules.domain.safeguarding import safeguarding as data

    return jsonify(data.summary())


@safeguarding_bp.route("/<concern_id>", methods=["GET"])
@_token_required
def get_concern(concern_id):
    from education_system.nursery_system.modules.domain.safeguarding import safeguarding as data

    concern = data.get_concern(concern_id)
    if concern is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(concern))


@safeguarding_bp.route("", methods=["POST"])
@safeguarding_bp.route("/", methods=["POST"])
@_token_required
def create_concern():
    from education_system.nursery_system.modules.domain.safeguarding import safeguarding as data

    payload = request.get_json(silent=True) or {}
    try:
        concern = data.create_concern(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(concern)), 201


@safeguarding_bp.route("/<concern_id>", methods=["PUT"])
@_token_required
def update_concern(concern_id):
    from education_system.nursery_system.modules.domain.safeguarding import safeguarding as data

    if data.get_concern(concern_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        concern = data.update_concern(concern_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(concern))


@safeguarding_bp.route("/<concern_id>", methods=["DELETE"])
@_token_required
def delete_concern(concern_id):
    from education_system.nursery_system.modules.domain.safeguarding import safeguarding as data

    if not data.delete_concern(concern_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": concern_id})
