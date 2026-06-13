"""REST API for Primary Emergency Events & Drills."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

emergency_bp = Blueprint("pri_emergency", __name__, url_prefix="/api/emergency")


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


@emergency_bp.route("", methods=["GET"])
@emergency_bp.route("/", methods=["GET"])
@_token_required
def list_events():
    from education_system.primarysch_system.modules.domain.emergency import (
        emergency as data,
    )
    args = request.args
    try:
        rows = data.list_events(
            kind=args.get("kind"),
            event_type=args.get("event_type"),
            status=args.get("status"),
            from_date=args.get("from_date"),
            to_date=args.get("to_date"),
            outstanding_only=args.get("outstanding_only",
                                      "").lower() in ("1", "true", "yes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@emergency_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.emergency import (
        emergency as data,
    )
    args = request.args
    try:
        result = data.cohort_summary(
            from_date=args.get("from_date"),
            to_date=args.get("to_date"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@emergency_bp.route("/<int:event_id>", methods=["GET"])
@_token_required
def get_event(event_id):
    from education_system.primarysch_system.modules.domain.emergency import (
        emergency as data,
    )
    rec = data.get(event_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@emergency_bp.route("", methods=["POST"])
@emergency_bp.route("/", methods=["POST"])
@_token_required
def create_event():
    from education_system.primarysch_system.modules.domain.emergency import (
        emergency as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@emergency_bp.route("/<int:event_id>", methods=["PUT"])
@_token_required
def update_event(event_id):
    from education_system.primarysch_system.modules.domain.emergency import (
        emergency as data,
    )
    if data.get(event_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(event_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@emergency_bp.route("/<int:event_id>", methods=["DELETE"])
@_token_required
def delete_event(event_id):
    from education_system.primarysch_system.modules.domain.emergency import (
        emergency as data,
    )
    if not data.delete(event_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "event_id": event_id})
