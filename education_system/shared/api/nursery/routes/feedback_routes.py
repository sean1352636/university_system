"""REST API for Nursery Feedback.

Exposes CRUD plus workflow (respond/status/close) and a summary for the
general-purpose early-years feedback log.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

feedback_bp = Blueprint("nsy_feedback", __name__, url_prefix="/api/feedback")


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


def _bool_arg(name: str) -> bool:
    return request.args.get(name, "").lower() in ("1", "true", "yes", "on")


def _int_arg(name: str):
    v = request.args.get(name)
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@feedback_bp.route("", methods=["GET"])
@feedback_bp.route("/", methods=["GET"])
@_token_required
def list_feedback():
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    rows = data.list_feedback(
        feedback_type=request.args.get("feedback_type"),
        category=request.args.get("category"),
        source=request.args.get("source"),
        submitter_role=request.args.get("submitter_role"),
        status=request.args.get("status"),
        rating=_int_arg("rating"),
        rating_min=_int_arg("rating_min"),
        assigned_to_like=request.args.get("assigned_to_like"),
        subject_like=request.args.get("subject_like"),
        open_only=_bool_arg("open_only"),
        awaiting_response=_bool_arg("awaiting_response"),
        public_only=_bool_arg("public_only"),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@feedback_bp.route("/summary", methods=["GET"])
@_token_required
def feedback_summary():
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    return jsonify(_dump(data.summary()))


@feedback_bp.route("/<int:feedback_id>", methods=["GET"])
@_token_required
def get_feedback(feedback_id: int):
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    row = data.get_feedback(feedback_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@feedback_bp.route("", methods=["POST"])
@feedback_bp.route("/", methods=["POST"])
@_token_required
def create_feedback():
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_feedback(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@feedback_bp.route("/<int:feedback_id>", methods=["PUT"])
@_token_required
def update_feedback(feedback_id: int):
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    if data.get_feedback(feedback_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_feedback(feedback_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@feedback_bp.route("/<int:feedback_id>", methods=["DELETE"])
@_token_required
def delete_feedback(feedback_id: int):
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    if not data.delete_feedback(feedback_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "feedback_id": feedback_id})


@feedback_bp.route("/<int:feedback_id>/status", methods=["POST"])
@_token_required
def set_feedback_status(feedback_id: int):
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    try:
        row = data.set_status(feedback_id, new_status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@feedback_bp.route("/<int:feedback_id>/respond", methods=["POST"])
@_token_required
def respond_feedback(feedback_id: int):
    from education_system.nursery_system.modules.domain.feedback import (
        feedback as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.respond(
            feedback_id,
            response=payload.get("response") or "",
            response_by=payload.get("response_by") or "",
            response_on=payload.get("response_on"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))
