"""REST API for Primary Staff Directory."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_bp = Blueprint("pri_staff", __name__, url_prefix="/api/staff")


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


def _bool_arg(name):
    v = request.args.get(name)
    if v is None:
        return None
    return v.strip().lower() in ("1", "true", "yes", "on")


@staff_bp.route("", methods=["GET"])
@staff_bp.route("/", methods=["GET"])
@_token_required
def list_staff_view():
    from education_system.primarysch_system.modules.domain.staff import staff as data
    try:
        rows = data.list_staff(
            role=request.args.get("role"),
            department=request.args.get("department"),
            employment_status=request.args.get("employment_status"),
            is_tutor=_bool_arg("is_tutor"),
            is_dsl=_bool_arg("is_dsl"),
            is_examiner=_bool_arg("is_examiner"),
            active_only=(_bool_arg("active_only") or False),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_bp.route("/search", methods=["GET"])
@_token_required
def search_staff_view():
    from education_system.primarysch_system.modules.domain.staff import staff as data
    rows = data.search_staff(request.args.get("q", ""))
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_bp.route("/summary", methods=["GET"])
@_token_required
def summary_view():
    from education_system.primarysch_system.modules.domain.staff import staff as data
    return jsonify(_dump(data.summary()))


@staff_bp.route("/<staff_id>", methods=["GET"])
@_token_required
def get_staff_view(staff_id):
    from education_system.primarysch_system.modules.domain.staff import staff as data
    row = data.get_staff(staff_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_bp.route("", methods=["POST"])
@staff_bp.route("/", methods=["POST"])
@_token_required
def create_staff_view():
    from education_system.primarysch_system.modules.domain.staff import staff as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_staff(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_bp.route("/<staff_id>", methods=["PUT"])
@_token_required
def update_staff_view(staff_id):
    from education_system.primarysch_system.modules.domain.staff import staff as data
    if data.get_staff(staff_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_staff(staff_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@staff_bp.route("/<staff_id>", methods=["DELETE"])
@_token_required
def delete_staff_view(staff_id):
    from education_system.primarysch_system.modules.domain.staff import staff as data
    if not data.delete_staff(staff_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": staff_id})
