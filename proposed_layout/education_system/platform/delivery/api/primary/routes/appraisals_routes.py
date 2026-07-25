"""REST API for Primary Staff Appraisals."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

appraisals_bp = Blueprint("pri_appraisals", __name__, url_prefix="/api/appraisals")


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
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


# ── Appraisals ───────────────────────────────────────────

@appraisals_bp.route("", methods=["GET"])
@appraisals_bp.route("/", methods=["GET"])
@_token_required
def list_appraisals():
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
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
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    return jsonify(_dump(data.summary()))


@appraisals_bp.route("/cycles", methods=["GET"])
@_token_required
def list_cycles():
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    rows = data.list_cycles()
    return jsonify({"items": rows, "count": len(rows)})


@appraisals_bp.route("/<int:appraisal_id>", methods=["GET"])
@_token_required
def get_appraisal(appraisal_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    row = data.get_appraisal(appraisal_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@appraisals_bp.route("", methods=["POST"])
@appraisals_bp.route("/", methods=["POST"])
@_token_required
def create_appraisal():
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_appraisal(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@appraisals_bp.route("/<int:appraisal_id>", methods=["PUT"])
@_token_required
def update_appraisal(appraisal_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    if data.get_appraisal(appraisal_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_appraisal(appraisal_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@appraisals_bp.route("/<int:appraisal_id>", methods=["DELETE"])
@_token_required
def delete_appraisal(appraisal_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    if not data.delete_appraisal(appraisal_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "appraisal_id": appraisal_id})


# ── Objectives (sub-resource) ────────────────────────────

@appraisals_bp.route("/<int:appraisal_id>/objectives", methods=["GET"])
@_token_required
def list_objectives(appraisal_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    if data.get_appraisal(appraisal_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.list_objectives(appraisal_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@appraisals_bp.route("/<int:appraisal_id>/objectives", methods=["POST"])
@_token_required
def add_objective(appraisal_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.add_objective(appraisal_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@appraisals_bp.route("/objectives/<int:objective_id>", methods=["GET"])
@_token_required
def get_objective(objective_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    row = data.get_objective(objective_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@appraisals_bp.route("/objectives/<int:objective_id>", methods=["PUT"])
@_token_required
def update_objective(objective_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    if data.get_objective(objective_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_objective(objective_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@appraisals_bp.route("/objectives/<int:objective_id>", methods=["DELETE"])
@_token_required
def delete_objective(objective_id: int):
    from education_system.systems.primary.domain.staff.appraisals import (
        appraisals as data,
    )
    if not data.delete_objective(objective_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "objective_id": objective_id})
