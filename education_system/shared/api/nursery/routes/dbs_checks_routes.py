"""REST API for Nursery DBS Checks.

Exposes CRUD and safeguarding workflow over the DBS checks register
(single central record) for nursery staff.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

dbs_checks_bp = Blueprint("nsy_dbs_checks", __name__, url_prefix="/api/dbs-checks")


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


def _truthy(value: str | None) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on") if value is not None else False


@dbs_checks_bp.route("", methods=["GET"])
@dbs_checks_bp.route("/", methods=["GET"])
@_token_required
def list_checks():
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    args = request.args
    rows = data.list_checks(
        staff_id=args.get("staff_id") or None,
        level=args.get("level") or None,
        status=args.get("status") or None,
        certificate_type=args.get("certificate_type") or None,
        active_only=_truthy(args.get("active_only")),
        expired=_truthy(args.get("expired")),
        expiring_soon=_truthy(args.get("expiring_soon")),
        update_check_overdue=_truthy(args.get("update_check_overdue")),
        update_service_only=_truthy(args.get("update_service_only")),
        unsigned=_truthy(args.get("unsigned")),
        risk_assessment_pending=_truthy(args.get("risk_assessment_pending")),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@dbs_checks_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    return jsonify(_dump(data.summary()))


@dbs_checks_bp.route("/<int:check_id>", methods=["GET"])
@_token_required
def get_check(check_id: int):
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    row = data.get_check(check_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@dbs_checks_bp.route("", methods=["POST"])
@dbs_checks_bp.route("/", methods=["POST"])
@_token_required
def create_check():
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    try:
        row = data.create_check(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@dbs_checks_bp.route("/<int:check_id>", methods=["PUT"])
@_token_required
def update_check(check_id: int):
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    if data.get_check(check_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_check(check_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@dbs_checks_bp.route("/<int:check_id>", methods=["DELETE"])
@_token_required
def delete_check(check_id: int):
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    if not data.delete_check(check_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "check_id": check_id})


@dbs_checks_bp.route("/<int:check_id>/status", methods=["PUT"])
@_token_required
def set_status(check_id: int):
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    body = request.get_json(force=True, silent=True) or {}
    try:
        row = data.set_status(check_id, (body.get("status") or "").strip())
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@dbs_checks_bp.route("/<int:check_id>/sign-off", methods=["POST"])
@_token_required
def sign_off(check_id: int):
    from education_system.nursery_system.modules.domain.dbs_checks import dbs_checks as data
    body = request.get_json(force=True, silent=True) or {}
    try:
        row = data.sign_off(
            check_id,
            signed_off_by=(body.get("signed_off_by") or "").strip(),
            signed_off_on=body.get("signed_off_on") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))
