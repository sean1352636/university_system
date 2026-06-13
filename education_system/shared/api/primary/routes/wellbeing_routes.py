"""REST API for Primary Wellbeing (pupil check-ins)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

wellbeing_bp = Blueprint("pri_wellbeing", __name__, url_prefix="/api/wellbeing")


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


def _truthy(value):
    if value is None:
        return None
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@wellbeing_bp.route("", methods=["GET"])
@wellbeing_bp.route("/", methods=["GET"])
@_token_required
def list_checkins():
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    try:
        rows = data.list_checkins(
            pupil_id=request.args.get("pupil_id"),
            year_group=request.args.get("year_group"),
            status=request.args.get("status"),
            source=request.args.get("source"),
            action_needed=_truthy(request.args.get("action_needed")),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@wellbeing_bp.route("/<int:checkin_id>", methods=["GET"])
@_token_required
def get_checkin(checkin_id: int):
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    rec = data.get(checkin_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@wellbeing_bp.route("", methods=["POST"])
@wellbeing_bp.route("/", methods=["POST"])
@_token_required
def create_checkin():
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.log_checkin(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@wellbeing_bp.route("/<int:checkin_id>", methods=["PUT"])
@_token_required
def update_checkin(checkin_id: int):
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    if data.get(checkin_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(checkin_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@wellbeing_bp.route("/<int:checkin_id>", methods=["DELETE"])
@_token_required
def delete_checkin(checkin_id: int):
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    if not data.delete(checkin_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "checkin_id": checkin_id})


@wellbeing_bp.route("/summary/pupil/<pupil_id>", methods=["GET"])
@_token_required
def pupil_summary(pupil_id: str):
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    try:
        summary = data.pupil_summary(
            pupil_id,
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    summary["checkins"] = _dump(summary.get("checkins", []))
    return jsonify(summary)


@wellbeing_bp.route("/summary/cohort", methods=["GET"])
@_token_required
def cohort_summary():
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    try:
        summary = data.cohort_summary(
            year_group=request.args.get("year_group"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(summary)


@wellbeing_bp.route("/low", methods=["GET"])
@_token_required
def low_wellbeing():
    from education_system.primarysch_system.modules.domain.wellbeing import (
        wellbeing as data,
    )
    raw_threshold = request.args.get("threshold", "2")
    try:
        threshold = int(raw_threshold)
    except (TypeError, ValueError):
        return jsonify({"error": "threshold must be a whole number"}), 400
    try:
        result = data.low_wellbeing(
            threshold=threshold,
            year_group=request.args.get("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = {pid: _dump(rows) for pid, rows in result.items()}
    return jsonify({"items": items, "count": len(items)})
