"""REST API for Nursery Activity Feed.

Exposes the system-wide activity/audit event log: list with filters,
fetch one, append an event, delete an event, and a summary aggregate.
The feed is append-only, so there is no update endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

activity_feed_bp = Blueprint("nsy_activity_feed", __name__, url_prefix="/api/activity-feed")


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


@activity_feed_bp.route("", methods=["GET"])
@activity_feed_bp.route("/", methods=["GET"])
@_token_required
def list_events_route():
    from education_system.nursery_system.modules.domain.activity_feed import (
        activity_feed as data,
    )

    args = request.args
    kwargs = {}
    for key in (
        "actor", "actor_role", "action", "entity_type", "entity_id",
        "severity", "source", "summary_like", "date_from", "date_to",
    ):
        val = args.get(key)
        if val:
            kwargs[key] = val
    limit = args.get("limit")
    if limit is not None:
        try:
            kwargs["limit"] = int(limit)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be a whole number"}), 400

    try:
        rows = data.list_events(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@activity_feed_bp.route("/<int:event_id>", methods=["GET"])
@_token_required
def get_event_route(event_id: int):
    from education_system.nursery_system.modules.domain.activity_feed import (
        activity_feed as data,
    )

    event = data.get_event(event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(_dump(event))


@activity_feed_bp.route("", methods=["POST"])
@activity_feed_bp.route("/", methods=["POST"])
@_token_required
def create_event_route():
    from education_system.nursery_system.modules.domain.activity_feed import (
        activity_feed as data,
    )

    payload = request.get_json(silent=True) or {}
    try:
        event = data.create_event(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(event)), 201


@activity_feed_bp.route("/<int:event_id>", methods=["DELETE"])
@_token_required
def delete_event_route(event_id: int):
    from education_system.nursery_system.modules.domain.activity_feed import (
        activity_feed as data,
    )

    if not data.delete_event(event_id):
        return jsonify({"error": "Event not found"}), 404
    return jsonify({"deleted": True, "event_id": event_id})


@activity_feed_bp.route("/summary", methods=["GET"])
@_token_required
def summary_route():
    from education_system.nursery_system.modules.domain.activity_feed import (
        activity_feed as data,
    )

    return jsonify(_dump(data.summary()))
