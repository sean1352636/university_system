"""REST API for Primary Feedback."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

feedback_bp = Blueprint("pri_feedback", __name__, url_prefix="/api/feedback")


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


@feedback_bp.route("", methods=["GET"])
@feedback_bp.route("/", methods=["GET"])
@_token_required
def list_feedback():
    from education_system.primarysch_system.modules.domain.feedback import (
        feedback as data,
    )
    args = request.args
    kwargs = {}
    for key in (
        "feedback_type", "category", "source", "submitter_role",
        "status", "assigned_to_like", "subject_like",
        "date_from", "date_to",
    ):
        if args.get(key):
            kwargs[key] = args.get(key)
    for key in ("rating", "rating_min"):
        if args.get(key):
            try:
                kwargs[key] = int(args.get(key))
            except (TypeError, ValueError):
                return jsonify({"error": f"{key} must be an integer"}), 400
    for key in ("open_only", "awaiting_response", "public_only"):
        if args.get(key) is not None and args.get(key) != "":
            kwargs[key] = args.get(key, "").lower() in ("1", "true", "yes", "on")
    rows = data.list_feedback(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@feedback_bp.route("/summary", methods=["GET"])
@_token_required
def feedback_summary():
    from education_system.primarysch_system.modules.domain.feedback import (
        feedback as data,
    )
    return jsonify(_dump(data.summary()))


@feedback_bp.route("/<int:feedback_id>", methods=["GET"])
@_token_required
def get_feedback(feedback_id: int):
    from education_system.primarysch_system.modules.domain.feedback import (
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
    from education_system.primarysch_system.modules.domain.feedback import (
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
    from education_system.primarysch_system.modules.domain.feedback import (
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
    from education_system.primarysch_system.modules.domain.feedback import (
        feedback as data,
    )
    if not data.delete_feedback(feedback_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
