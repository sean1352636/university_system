"""REST API for Nursery Staff Appraisals.

Exposes CRUD over staff appraisals plus nested objectives, status setters
and a summary endpoint, backed by the nursery appraisals data layer.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

appraisals_bp = Blueprint("nsy_appraisals", __name__, url_prefix="/api/appraisals")


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


@appraisals_bp.route("", methods=["GET"])
@appraisals_bp.route("/", methods=["GET"])
@_token_required
def list_appraisals():
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    args = request.args
    grade = args.get("grade")
    rows = data.list_appraisals(
        staff_id=args.get("staff_id") or None,
        cycle=args.get("cycle") or None,
        status=args.get("status") or None,
        grade=int(grade) if grade not in (None, "") else None,
        pay_progression=args.get("pay_progression") or None,
        open_only=args.get("open_only", "").lower() in ("1", "true", "yes"),
        mid_year_overdue=args.get("mid_year_overdue", "").lower()
        in ("1", "true", "yes"),
        appraiser_id=args.get("appraiser_id") or None,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@appraisals_bp.route("/summary", methods=["GET"])
@_token_required
def appraisals_summary():
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    return jsonify(_dump(data.summary()))


@appraisals_bp.route("/<int:appraisal_id>", methods=["GET"])
@_token_required
def get_appraisal(appraisal_id: int):
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    row = data.get_appraisal(appraisal_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@appraisals_bp.route("", methods=["POST"])
@appraisals_bp.route("/", methods=["POST"])
@_token_required
def create_appraisal():
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    try:
        row = data.create_appraisal(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@appraisals_bp.route("/<int:appraisal_id>", methods=["PUT"])
@_token_required
def update_appraisal(appraisal_id: int):
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    if data.get_appraisal(appraisal_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_appraisal(
            appraisal_id, request.get_json(force=True, silent=True) or {}
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@appraisals_bp.route("/<int:appraisal_id>", methods=["DELETE"])
@_token_required
def delete_appraisal(appraisal_id: int):
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    if not data.delete_appraisal(appraisal_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "appraisal_id": appraisal_id})


@appraisals_bp.route("/<int:appraisal_id>/status", methods=["PUT"])
@_token_required
def set_appraisal_status(appraisal_id: int):
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    payload = request.get_json(force=True, silent=True) or {}
    new_status = payload.get("status")
    try:
        row = data.set_appraisal_status(appraisal_id, new_status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@appraisals_bp.route("/<int:appraisal_id>/objectives", methods=["GET"])
@_token_required
def list_objectives(appraisal_id: int):
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    if data.get_appraisal(appraisal_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_objectives(appraisal_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@appraisals_bp.route("/<int:appraisal_id>/objectives", methods=["POST"])
@_token_required
def add_objective(appraisal_id: int):
    from education_system.nursery_system.modules.domain.appraisals import appraisals as data

    try:
        row = data.add_objective(
            appraisal_id, request.get_json(force=True, silent=True) or {}
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201
