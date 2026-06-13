"""REST API for Primary Early-Warning Alerts."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

early_warning_bp = Blueprint("pri_early_warning", __name__, url_prefix="/api/early-warning")


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


@early_warning_bp.route("", methods=["GET"])
@early_warning_bp.route("/", methods=["GET"])
@_token_required
def list_alerts():
    from education_system.primarysch_system.modules.domain.early_warning import (
        early_warning as data,
    )
    args = request.args
    try:
        rows = data.list_alerts(
            year_group=args.get("year_group"),
            pupil_id=args.get("pupil_id"),
            alert_type=args.get("alert_type"),
            severity=args.get("severity"),
            status=args.get("status"),
            source=args.get("source"),
            assigned_to=args.get("assigned_to"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@early_warning_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.early_warning import (
        early_warning as data,
    )
    try:
        result = data.cohort_summary(year_group=request.args.get("year_group"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@early_warning_bp.route("/<int:alert_id>", methods=["GET"])
@_token_required
def get_alert(alert_id: int):
    from education_system.primarysch_system.modules.domain.early_warning import (
        early_warning as data,
    )
    rec = data.get(alert_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@early_warning_bp.route("", methods=["POST"])
@early_warning_bp.route("/", methods=["POST"])
@_token_required
def create_alert():
    from education_system.primarysch_system.modules.domain.early_warning import (
        early_warning as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@early_warning_bp.route("/<int:alert_id>", methods=["PUT"])
@_token_required
def update_alert(alert_id: int):
    from education_system.primarysch_system.modules.domain.early_warning import (
        early_warning as data,
    )
    if data.get(alert_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(alert_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@early_warning_bp.route("/<int:alert_id>", methods=["DELETE"])
@_token_required
def delete_alert(alert_id: int):
    from education_system.primarysch_system.modules.domain.early_warning import (
        early_warning as data,
    )
    if not data.delete(alert_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "alert_id": alert_id})
