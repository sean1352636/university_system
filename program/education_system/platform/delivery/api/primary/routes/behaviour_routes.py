"""REST API for Primary Behaviour."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

behaviour_bp = Blueprint("pri_behaviour", __name__, url_prefix="/api/behaviour")


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


def _summary_dump(summary: dict) -> dict:
    """Serialize a summary dict that may contain dataclass lists."""
    return {k: _dump(v) for k, v in summary.items()}


@behaviour_bp.route("", methods=["GET"])
@behaviour_bp.route("/", methods=["GET"])
@_token_required
def list_incidents():
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    args = request.args
    try:
        rows = data.list_incidents(
            pupil_id=args.get("pupil_id"),
            year_group=args.get("year_group"),
            incident_type=args.get("incident_type"),
            polarity=args.get("polarity"),
            severity=args.get("severity"),
            status=args.get("status"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@behaviour_bp.route("/<int:incident_id>", methods=["GET"])
@_token_required
def get_incident(incident_id: int):
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    rec = data.get(incident_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@behaviour_bp.route("", methods=["POST"])
@behaviour_bp.route("/", methods=["POST"])
@_token_required
def create_incident():
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.log_incident(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@behaviour_bp.route("/<int:incident_id>", methods=["PUT"])
@_token_required
def update_incident(incident_id: int):
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    if data.get(incident_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(incident_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@behaviour_bp.route("/<int:incident_id>", methods=["DELETE"])
@_token_required
def delete_incident(incident_id: int):
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    if not data.delete(incident_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "incident_id": incident_id})


@behaviour_bp.route("/summary/pupil/<pupil_id>", methods=["GET"])
@_token_required
def pupil_summary(pupil_id: str):
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    args = request.args
    try:
        result = data.pupil_summary(
            pupil_id,
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_summary_dump(result))


@behaviour_bp.route("/summary/cohort", methods=["GET"])
@_token_required
def cohort_summary():
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    args = request.args
    try:
        result = data.cohort_summary(
            year_group=args.get("year_group"),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_summary_dump(result))


@behaviour_bp.route("/flagged", methods=["GET"])
@_token_required
def flagged_pupils():
    from education_system.systems.primary.domain.pastoral.behaviour import (
        behaviour as data,
    )
    args = request.args
    points_below_raw = args.get("points_below")
    try:
        points_below = int(points_below_raw) if points_below_raw else -10
    except (TypeError, ValueError):
        return jsonify({"error": "points_below must be an integer"}), 400
    try:
        rows = data.pupils_above_threshold(
            points_below=points_below,
            year_group=args.get("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [{"pupil_id": pid, "total_points": pts} for pid, pts in rows]
    return jsonify({"items": items, "count": len(items)})
