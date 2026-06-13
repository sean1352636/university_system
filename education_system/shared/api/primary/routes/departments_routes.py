"""REST API for Primary Departments."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

departments_bp = Blueprint("pri_departments", __name__, url_prefix="/api/departments")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── Departments ──────────────────────────────────────────────

@departments_bp.route("", methods=["GET"])
@departments_bp.route("/", methods=["GET"])
@_token_required
def list_departments():
    from education_system.primarysch_system.modules.domain.departments import departments as data
    args = request.args
    rows = data.list_departments(
        faculty=args.get("faculty"),
        status=args.get("status"),
        active_only=args.get("active_only", "").lower() in ("1", "true", "yes"),
        over_budget=args.get("over_budget", "").lower() in ("1", "true", "yes"),
        name_like=args.get("name_like"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@departments_bp.route("/summary", methods=["GET"])
@_token_required
def departments_summary():
    from education_system.primarysch_system.modules.domain.departments import departments as data
    return jsonify(_dump(data.summary()))


@departments_bp.route("/<int:department_id>", methods=["GET"])
@_token_required
def get_department(department_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    obj = data.get_department(department_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@departments_bp.route("", methods=["POST"])
@departments_bp.route("/", methods=["POST"])
@_token_required
def create_department():
    from education_system.primarysch_system.modules.domain.departments import departments as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_department(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@departments_bp.route("/<int:department_id>", methods=["PUT"])
@_token_required
def update_department(department_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    if data.get_department(department_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_department(department_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@departments_bp.route("/<int:department_id>", methods=["DELETE"])
@_token_required
def delete_department(department_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    if not data.delete_department(department_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": department_id})


# ── Memberships (nested under a department) ──────────────────

@departments_bp.route("/<int:department_id>/members", methods=["GET"])
@_token_required
def list_memberships(department_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    if data.get_department(department_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_memberships(department_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@departments_bp.route("/<int:department_id>/members", methods=["POST"])
@_token_required
def add_member(department_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.add_member(department_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@departments_bp.route("/members/<int:membership_id>", methods=["GET"])
@_token_required
def get_membership(membership_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    obj = data.get_membership(membership_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@departments_bp.route("/members/<int:membership_id>", methods=["PUT"])
@_token_required
def update_membership(membership_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    if data.get_membership(membership_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_membership(membership_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@departments_bp.route("/members/<int:membership_id>", methods=["DELETE"])
@_token_required
def delete_membership(membership_id: int):
    from education_system.primarysch_system.modules.domain.departments import departments as data
    if not data.delete_membership(membership_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": membership_id})
