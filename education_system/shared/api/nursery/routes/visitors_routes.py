"""REST API for Nursery Visitors.

Reception sign-in / sign-out log: CRUD plus sign-in/out workflow,
status setter and a summary of who is on site.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

visitors_bp = Blueprint("nsy_visitors", __name__, url_prefix="/api/visitors")


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


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes", "on")


@visitors_bp.route("", methods=["GET"])
@visitors_bp.route("/", methods=["GET"])
@_token_required
def list_visitors():
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    args = request.args
    kwargs = {}
    for key in ("visitor_type", "status", "host_staff_id", "name_like",
                "org_like", "date_from", "date_to"):
        if args.get(key):
            kwargs[key] = args.get(key)
    for key in ("on_site_only", "overdue_only", "today_only",
                "no_show_only", "safeguarding_only"):
        if args.get(key) is not None:
            kwargs[key] = _truthy(args.get(key))
    try:
        rows = data.list_visitors(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@visitors_bp.route("/summary", methods=["GET"])
@_token_required
def visitors_summary():
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    return jsonify(_dump(data.summary()))


@visitors_bp.route("/<int:visitor_id>", methods=["GET"])
@_token_required
def get_visitor(visitor_id: int):
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    row = data.get_visitor(visitor_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@visitors_bp.route("", methods=["POST"])
@visitors_bp.route("/", methods=["POST"])
@_token_required
def create_visitor():
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_visitor(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@visitors_bp.route("/<int:visitor_id>", methods=["PUT"])
@_token_required
def update_visitor(visitor_id: int):
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    if data.get_visitor(visitor_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_visitor(visitor_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@visitors_bp.route("/<int:visitor_id>", methods=["DELETE"])
@_token_required
def delete_visitor(visitor_id: int):
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    if not data.delete_visitor(visitor_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "visitor_id": visitor_id})


@visitors_bp.route("/<int:visitor_id>/status", methods=["PUT"])
@_token_required
def set_status(visitor_id: int):
    from education_system.nursery_system.modules.domain.visitors import (
        visitors as data,
    )
    if data.get_visitor(visitor_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    try:
        row = data.set_status(visitor_id, new_status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))
