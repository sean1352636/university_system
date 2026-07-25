"""REST API for Primary Activity Feed."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

activity_feed_bp = Blueprint("pri_activity_feed", __name__, url_prefix="/api/activity-feed")


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


def _data():
    from education_system.systems.primary.domain.operations.communications.activity_feed import (
        activity_feed as data,
    )
    return data


@activity_feed_bp.route("", methods=["GET"])
@activity_feed_bp.route("/", methods=["GET"])
@_token_required
def list_events():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("actor", "actor_role", "action", "entity_type", "entity_id",
                "severity", "source", "summary_like", "date_from", "date_to"):
        val = args.get(key)
        if val is not None and val != "":
            kwargs[key] = val
    limit = args.get("limit")
    if limit is not None and limit != "":
        try:
            kwargs["limit"] = int(limit)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be a whole number"}), 400
    try:
        rows = data.list_events(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@activity_feed_bp.route("/summary", methods=["GET"])
@_token_required
def get_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@activity_feed_bp.route("/<int:event_id>", methods=["GET"])
@_token_required
def get_event(event_id: int):
    data = _data()
    row = data.get_event(event_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@activity_feed_bp.route("", methods=["POST"])
@activity_feed_bp.route("/", methods=["POST"])
@_token_required
def create_event():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_event(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@activity_feed_bp.route("/<int:event_id>", methods=["DELETE"])
@_token_required
def delete_event(event_id: int):
    data = _data()
    if not data.delete_event(event_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "event_id": event_id})
