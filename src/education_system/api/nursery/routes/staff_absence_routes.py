"""REST API for Nursery Staff Absence.

Exposes CRUD plus workflow (confirm, arrange-cover, record-return, RTW,
status, summary) over the operational daily staff-absence tracker.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_absence_bp = Blueprint("nsy_staff_absence", __name__, url_prefix="/api/staff-absence")


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


def _bool_arg(name: str) -> bool:
    return request.args.get(name, "").lower() in ("1", "true", "yes", "on")


@staff_absence_bp.route("", methods=["GET"])
@_token_required
def list_absences():
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    try:
        rows = data.list_absences(
            staff_id=request.args.get("staff_id"),
            absence_type=request.args.get("absence_type"),
            status=request.args.get("status"),
            cover_source=request.args.get("cover_source"),
            open_only=_bool_arg("open_only"),
            active_today=_bool_arg("active_today"),
            critical_only=_bool_arg("critical_only"),
            cover_outstanding=_bool_arg("cover_outstanding"),
            rtw_overdue=_bool_arg("rtw_overdue"),
            return_overdue=_bool_arg("return_overdue"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_absence_bp.route("/summary", methods=["GET"])
@_token_required
def absence_summary():
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    return jsonify(_dump(data.summary()))


@staff_absence_bp.route("/<int:absence_id>", methods=["GET"])
@_token_required
def get_absence(absence_id: int):
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    row = data.get_absence(absence_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_absence_bp.route("", methods=["POST"])
@_token_required
def create_absence():
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    try:
        row = data.create_absence(request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@staff_absence_bp.route("/<int:absence_id>", methods=["PUT"])
@_token_required
def update_absence(absence_id: int):
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    if data.get_absence(absence_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_absence(absence_id, request.get_json(silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@staff_absence_bp.route("/<int:absence_id>", methods=["DELETE"])
@_token_required
def delete_absence(absence_id: int):
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    if not data.delete_absence(absence_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "absence_id": absence_id})


@staff_absence_bp.route("/<int:absence_id>/status", methods=["POST"])
@_token_required
def set_status(absence_id: int):
    from education_system.systems.nursery.domain.staff.staff_absence import (
        staff_absence as data,
    )
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    if not new_status:
        return jsonify({"error": "status is required"}), 400
    if data.get_absence(absence_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.set_status(absence_id, new_status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))
