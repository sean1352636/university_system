"""REST API for Primary Staff Absence."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_absence_bp = Blueprint("pri_staff_absence", __name__, url_prefix="/api/staff-absence")


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


def _data():
    from education_system.primarysch_system.modules.domain.staff_absence import (
        staff_absence as data,
    )
    return data


def _bool_arg(name: str) -> bool:
    val = request.args.get(name)
    return str(val).lower() in ("1", "true", "yes", "on") if val is not None else False


@staff_absence_bp.route("", methods=["GET"])
@staff_absence_bp.route("/", methods=["GET"])
@_token_required
def list_absences():
    data = _data()
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
    data = _data()
    return jsonify(_dump(data.summary()))


@staff_absence_bp.route("/<int:absence_id>", methods=["GET"])
@_token_required
def get_absence(absence_id: int):
    data = _data()
    rec = data.get_absence(absence_id)
    if rec is None:
        return jsonify({"error": f"No absence with id {absence_id}"}), 404
    return jsonify(_dump(rec))


@staff_absence_bp.route("", methods=["POST"])
@staff_absence_bp.route("/", methods=["POST"])
@_token_required
def create_absence():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_absence(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@staff_absence_bp.route("/<int:absence_id>", methods=["PUT"])
@_token_required
def update_absence(absence_id: int):
    data = _data()
    if data.get_absence(absence_id) is None:
        return jsonify({"error": f"No absence with id {absence_id}"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_absence(absence_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@staff_absence_bp.route("/<int:absence_id>", methods=["DELETE"])
@_token_required
def delete_absence(absence_id: int):
    data = _data()
    if not data.delete_absence(absence_id):
        return jsonify({"error": f"No absence with id {absence_id}"}), 404
    return jsonify({"deleted": True, "absence_id": absence_id})
