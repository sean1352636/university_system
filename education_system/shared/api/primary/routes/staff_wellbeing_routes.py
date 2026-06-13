"""REST API for Primary Staff Wellbeing."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_wellbeing_bp = Blueprint("pri_staff_wellbeing", __name__, url_prefix="/api/staff-wellbeing")


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
    from education_system.primarysch_system.modules.domain.staff_wellbeing import (
        staff_wellbeing as data,
    )
    return data


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@staff_wellbeing_bp.route("", methods=["GET"])
@staff_wellbeing_bp.route("/", methods=["GET"])
@_token_required
def list_entries():
    data = _data()
    rows = data.list_entries(
        staff_id=request.args.get("staff_id") or None,
        entry_type=request.args.get("entry_type") or None,
        status=request.args.get("status") or None,
        action_type=request.args.get("action_type") or None,
        open_only=_truthy(request.args.get("open_only")),
        at_risk_only=_truthy(request.args.get("at_risk_only")),
        follow_up_overdue=_truthy(request.args.get("follow_up_overdue")),
        with_concern_flag=request.args.get("with_concern_flag") or None,
        date_from=request.args.get("date_from") or None,
        date_to=request.args.get("date_to") or None,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_wellbeing_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@staff_wellbeing_bp.route("/<int:entry_id>", methods=["GET"])
@_token_required
def get_entry(entry_id: int):
    data = _data()
    row = data.get_entry(entry_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_wellbeing_bp.route("", methods=["POST"])
@staff_wellbeing_bp.route("/", methods=["POST"])
@_token_required
def create_entry():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_entry(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@staff_wellbeing_bp.route("/<int:entry_id>", methods=["PUT"])
@_token_required
def update_entry(entry_id: int):
    data = _data()
    if data.get_entry(entry_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_entry(entry_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@staff_wellbeing_bp.route("/<int:entry_id>", methods=["DELETE"])
@_token_required
def delete_entry(entry_id: int):
    data = _data()
    if not data.delete_entry(entry_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "entry_id": entry_id})
