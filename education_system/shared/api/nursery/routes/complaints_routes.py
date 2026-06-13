"""REST API for Nursery Complaints.

Exposes CRUD plus complaint workflow transitions and a summary over the
formal complaints register.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

complaints_bp = Blueprint("nsy_complaints", __name__, url_prefix="/api/complaints")


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


_TRUE = {"1", "true", "yes", "on"}


def _bool_arg(name):
    v = request.args.get(name)
    return v is not None and v.lower() in _TRUE


def _int_arg(name):
    v = request.args.get(name)
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@complaints_bp.route("", methods=["GET"])
@_token_required
def list_complaints():
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    rows = data.list_complaints(
        category=request.args.get("category"),
        stage=request.args.get("stage"),
        status=request.args.get("status"),
        outcome=request.args.get("outcome"),
        complainant_role=request.args.get("complainant_role"),
        severity=_int_arg("severity"),
        severity_min=_int_arg("severity_min"),
        assigned_to_like=request.args.get("assigned_to_like"),
        complainant_like=request.args.get("complainant_like"),
        subject_like=request.args.get("subject_like"),
        open_only=_bool_arg("open_only"),
        overdue_only=_bool_arg("overdue_only"),
        stage2_or_higher=_bool_arg("stage2_or_higher"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@complaints_bp.route("/summary", methods=["GET"])
@_token_required
def complaints_summary():
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    return jsonify(_dump(data.summary()))


@complaints_bp.route("/<int:complaint_id>", methods=["GET"])
@_token_required
def get_complaint(complaint_id):
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    row = data.get_complaint(complaint_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@complaints_bp.route("", methods=["POST"])
@_token_required
def create_complaint():
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    try:
        row = data.create_complaint(request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@complaints_bp.route("/<int:complaint_id>", methods=["PUT"])
@_token_required
def update_complaint(complaint_id):
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    if data.get_complaint(complaint_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_complaint(complaint_id, request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>", methods=["DELETE"])
@_token_required
def delete_complaint(complaint_id):
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    if not data.delete_complaint(complaint_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "complaint_id": complaint_id})


@complaints_bp.route("/<int:complaint_id>/status", methods=["POST"])
@_token_required
def set_status(complaint_id):
    from education_system.nursery_system.modules.domain.complaints import complaints as data
    body = request.get_json(silent=True) or {}
    try:
        row = data.set_status(complaint_id, body.get("status"))
    except data.ValidationError as exc:
        msg = str(exc)
        code = 404 if "No complaint with id" in msg else 400
        return jsonify({"error": msg}), code
    return jsonify(_dump(row))
