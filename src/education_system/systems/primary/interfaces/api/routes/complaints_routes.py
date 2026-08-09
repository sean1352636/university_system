"""REST API for Primary Complaints."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

complaints_bp = Blueprint("pri_complaints", __name__, url_prefix="/api/complaints")


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


@complaints_bp.route("", methods=["GET"])
@complaints_bp.route("/", methods=["GET"])
@_token_required
def list_complaints():
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    args = request.args
    kwargs = {}
    for key in ("category", "stage", "status", "outcome",
                "complainant_role", "assigned_to_like",
                "complainant_like", "subject_like", "date_from", "date_to"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    for key in ("severity", "severity_min"):
        val = args.get(key, type=int)
        if val is not None:
            kwargs[key] = val
    for key in ("open_only", "overdue_only", "stage2_or_higher"):
        if args.get(key, "").lower() in ("1", "true", "yes"):
            kwargs[key] = True
    rows = data.list_complaints(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@complaints_bp.route("/summary", methods=["GET"])
@_token_required
def complaints_summary():
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    return jsonify(_dump(data.summary()))


@complaints_bp.route("/<int:complaint_id>", methods=["GET"])
@_token_required
def get_complaint(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    row = data.get_complaint(complaint_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@complaints_bp.route("", methods=["POST"])
@complaints_bp.route("/", methods=["POST"])
@_token_required
def create_complaint():
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_complaint(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@complaints_bp.route("/<int:complaint_id>", methods=["PUT"])
@_token_required
def update_complaint(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    if data.get_complaint(complaint_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_complaint(complaint_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>", methods=["DELETE"])
@_token_required
def delete_complaint(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    if not data.delete_complaint(complaint_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "complaint_id": complaint_id})


# ── Workflow actions ────────────────────────────────────────────────

@complaints_bp.route("/<int:complaint_id>/acknowledge", methods=["POST"])
@_token_required
def acknowledge(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.acknowledge(
            complaint_id,
            assigned_to=payload.get("assigned_to"),
            acknowledged_on=payload.get("acknowledged_on"),
            target_response_date=payload.get("target_response_date"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>/start-investigation", methods=["POST"])
@_token_required
def start_investigation(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    try:
        row = data.start_investigation(complaint_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>/issue-response", methods=["POST"])
@_token_required
def issue_response(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.issue_response(
            complaint_id,
            summary=payload.get("summary", ""),
            outcome=payload.get("outcome", ""),
            issued_on=payload.get("issued_on"),
            actions_taken=payload.get("actions_taken"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>/escalate", methods=["POST"])
@_token_required
def escalate(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.escalate(
            complaint_id,
            to_stage=payload.get("to_stage", ""),
            reason=payload.get("reason"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>/satisfaction", methods=["POST"])
@_token_required
def record_satisfaction(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.record_satisfaction(
            complaint_id,
            satisfaction=payload.get("satisfaction", ""),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>/close", methods=["POST"])
@_token_required
def close_complaint(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    try:
        row = data.close_complaint(complaint_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@complaints_bp.route("/<int:complaint_id>/status", methods=["POST"])
@_token_required
def set_status(complaint_id: int):
    from education_system.systems.primary.domain.pastoral.complaints import complaints as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.set_status(complaint_id, payload.get("status", ""))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))
