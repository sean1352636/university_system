"""REST API for Primary Class Teachers."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

class_teachers_bp = Blueprint("pri_class_teachers", __name__, url_prefix="/api/class-teachers")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _pair(assignment, cls):
    """Serialize a (Assignment, SchoolClass|None) tuple."""
    d = _dump(assignment)
    d["class"] = _dump(cls)
    return d


@class_teachers_bp.route("", methods=["GET"])
@class_teachers_bp.route("/", methods=["GET"])
@_token_required
def list_route():
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    args = request.args
    class_id = args.get("class_id", type=int)
    academic_year = args.get("academic_year")
    role = args.get("role")
    staff_name = args.get("staff_name")
    try:
        rows = data.list_assignments(
            class_id=class_id,
            academic_year=academic_year,
            role=role,
            staff_name=staff_name,
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    items = [_pair(a, c) for (a, c) in rows]
    return jsonify({"items": items, "count": len(items)})


@class_teachers_bp.route("/<int:assignment_id>", methods=["GET"])
@_token_required
def get_route(assignment_id: int):
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    rec = data.get(assignment_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@class_teachers_bp.route("", methods=["POST"])
@class_teachers_bp.route("/", methods=["POST"])
@_token_required
def create_route():
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@class_teachers_bp.route("/<int:assignment_id>", methods=["PUT"])
@_token_required
def update_route(assignment_id: int):
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    payload = request.get_json(silent=True) or {}
    if data.get(assignment_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update(assignment_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@class_teachers_bp.route("/<int:assignment_id>", methods=["DELETE"])
@_token_required
def delete_route(assignment_id: int):
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    if not data.delete(assignment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "id": assignment_id})


@class_teachers_bp.route("/<int:assignment_id>/primary", methods=["POST"])
@_token_required
def set_primary_route(assignment_id: int):
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    if data.get(assignment_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.set_primary(assignment_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@class_teachers_bp.route("/by-class/<int:class_id>", methods=["GET"])
@_token_required
def list_for_class_route(class_id: int):
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    academic_year = request.args.get("academic_year")
    try:
        rows = data.list_for_class(class_id, academic_year)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"items": _dump(rows), "count": len(rows)})


@class_teachers_bp.route("/by-staff/<staff_name>", methods=["GET"])
@_token_required
def list_for_staff_route(staff_name: str):
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    try:
        rows = data.list_for_staff(staff_name)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    items = [_pair(a, c) for (a, c) in rows]
    return jsonify({"items": items, "count": len(items)})


@class_teachers_bp.route("/years", methods=["GET"])
@_token_required
def years_route():
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    rows = data.known_years()
    return jsonify({"items": rows, "count": len(rows)})


@class_teachers_bp.route("/summary", methods=["GET"])
@_token_required
def summary_route():
    from education_system.systems.primary.domain.staff.class_teachers import (
        class_teachers as data,
    )
    academic_year = request.args.get("academic_year")
    return jsonify(data.counts(academic_year))
