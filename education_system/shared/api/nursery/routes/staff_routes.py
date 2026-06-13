"""REST API for Nursery Staff Directory.

Exposes CRUD plus search and summary over Early-Years practitioner records.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_bp = Blueprint("nsy_staff", __name__, url_prefix="/api/staff")


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


def _bool_param(name):
    raw = request.args.get(name)
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


@staff_bp.route("", methods=["GET"])
@staff_bp.route("/", methods=["GET"])
@_token_required
def list_staff():
    from education_system.nursery_system.modules.domain.staff import staff as data
    try:
        rows = data.list_staff(
            role=request.args.get("role"),
            room=request.args.get("room"),
            employment_status=request.args.get("employment_status"),
            is_dsl=_bool_param("is_dsl"),
            is_paediatric_first_aider=_bool_param("is_paediatric_first_aider"),
            dbs_checked=_bool_param("dbs_checked"),
            active_only=bool(_bool_param("active_only")),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_bp.route("/search", methods=["GET"])
@_token_required
def search_staff():
    from education_system.nursery_system.modules.domain.staff import staff as data
    rows = data.search_staff(request.args.get("q", ""))
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_bp.route("/summary", methods=["GET"])
@_token_required
def staff_summary():
    from education_system.nursery_system.modules.domain.staff import staff as data
    return jsonify(_dump(data.summary()))


@staff_bp.route("/<staff_id>", methods=["GET"])
@_token_required
def get_staff(staff_id):
    from education_system.nursery_system.modules.domain.staff import staff as data
    row = data.get_staff(staff_id)
    if row is None:
        return jsonify({"error": "Staff member not found"}), 404
    return jsonify(_dump(row))


@staff_bp.route("", methods=["POST"])
@staff_bp.route("/", methods=["POST"])
@_token_required
def create_staff():
    from education_system.nursery_system.modules.domain.staff import staff as data
    try:
        row = data.create_staff(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_bp.route("/<staff_id>", methods=["PUT"])
@_token_required
def update_staff(staff_id):
    from education_system.nursery_system.modules.domain.staff import staff as data
    if data.get_staff(staff_id) is None:
        return jsonify({"error": "Staff member not found"}), 404
    try:
        row = data.update_staff(staff_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@staff_bp.route("/<staff_id>/leave", methods=["POST"])
@_token_required
def mark_left(staff_id):
    from education_system.nursery_system.modules.domain.staff import staff as data
    if data.get_staff(staff_id) is None:
        return jsonify({"error": "Staff member not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        row = data.mark_left(staff_id, body.get("end_date"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@staff_bp.route("/<staff_id>", methods=["DELETE"])
@_token_required
def delete_staff(staff_id):
    from education_system.nursery_system.modules.domain.staff import staff as data
    if not data.delete_staff(staff_id):
        return jsonify({"error": "Staff member not found"}), 404
    return jsonify({"deleted": True, "staff_id": staff_id})
