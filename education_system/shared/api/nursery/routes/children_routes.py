"""REST API for Nursery Child Directory.

Exposes CRUD plus search and status-setting over the children-on-roll records.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

children_bp = Blueprint("nsy_children", __name__, url_prefix="/api/children")


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


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@children_bp.route("", methods=["GET"])
@children_bp.route("/", methods=["GET"])
@_token_required
def list_children():
    from education_system.nursery_system.modules.domain.children import children as data

    include_left = _truthy(request.args.get("include_left"))
    rows = data.list_children(include_left=include_left)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@children_bp.route("/search", methods=["GET"])
@_token_required
def search_children():
    from education_system.nursery_system.modules.domain.children import children as data

    query = request.args.get("q", "")
    include_left = _truthy(request.args.get("include_left", "true"))
    rows = data.search_children(query, include_left=include_left)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@children_bp.route("/<pupil_id>", methods=["GET"])
@_token_required
def get_child(pupil_id):
    from education_system.nursery_system.modules.domain.children import children as data

    child = data.get_child(pupil_id)
    if child is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(child))


@children_bp.route("", methods=["POST"])
@children_bp.route("/", methods=["POST"])
@_token_required
def create_child():
    from education_system.nursery_system.modules.domain.children import children as data

    payload = request.get_json(silent=True) or {}
    try:
        child = data.create_child(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(child)), 201


@children_bp.route("/<pupil_id>", methods=["PUT"])
@_token_required
def update_child(pupil_id):
    from education_system.nursery_system.modules.domain.children import children as data

    if data.get_child(pupil_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        child = data.update_child(pupil_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(child))


@children_bp.route("/<pupil_id>/status", methods=["PUT"])
@_token_required
def set_status(pupil_id):
    from education_system.nursery_system.modules.domain.children import children as data

    payload = request.get_json(silent=True) or {}
    try:
        child = data.set_status(pupil_id, payload.get("status", ""))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(child))


@children_bp.route("/<pupil_id>", methods=["DELETE"])
@_token_required
def delete_child(pupil_id):
    from education_system.nursery_system.modules.domain.children import children as data

    if not data.delete_child(pupil_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "pupil_id": pupil_id})
