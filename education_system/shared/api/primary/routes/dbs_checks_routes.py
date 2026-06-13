"""REST API for Primary DBS Checks."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

dbs_checks_bp = Blueprint("pri_dbs_checks", __name__, url_prefix="/api/dbs-checks")


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
    from education_system.primarysch_system.modules.domain.dbs_checks import (
        dbs_checks as data,
    )
    return data


def _bool_arg(name: str) -> bool:
    return request.args.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dbs_checks_bp.route("", methods=["GET"])
@dbs_checks_bp.route("/", methods=["GET"])
@_token_required
def list_checks():
    data = _data()
    rows = data.list_checks(
        staff_id=request.args.get("staff_id") or None,
        level=request.args.get("level") or None,
        status=request.args.get("status") or None,
        certificate_type=request.args.get("certificate_type") or None,
        active_only=_bool_arg("active_only"),
        expired=_bool_arg("expired"),
        expiring_soon=_bool_arg("expiring_soon"),
        update_check_overdue=_bool_arg("update_check_overdue"),
        update_service_only=_bool_arg("update_service_only"),
        unsigned=_bool_arg("unsigned"),
        risk_assessment_pending=_bool_arg("risk_assessment_pending"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@dbs_checks_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@dbs_checks_bp.route("/<int:check_id>", methods=["GET"])
@_token_required
def get_check(check_id: int):
    data = _data()
    obj = data.get_check(check_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@dbs_checks_bp.route("", methods=["POST"])
@dbs_checks_bp.route("/", methods=["POST"])
@_token_required
def create_check():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_check(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@dbs_checks_bp.route("/<int:check_id>", methods=["PUT"])
@_token_required
def update_check(check_id: int):
    data = _data()
    if data.get_check(check_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_check(check_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@dbs_checks_bp.route("/<int:check_id>", methods=["DELETE"])
@_token_required
def delete_check(check_id: int):
    data = _data()
    if not data.delete_check(check_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "check_id": check_id})
