"""REST API for Primary Calendar."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("pri_calendar", __name__, url_prefix="/api/calendar")


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


def _data():
    from education_system.primarysch_system.modules.domain.calendar import (
        calendar as data,
    )
    return data


@calendar_bp.route("", methods=["GET"])
@calendar_bp.route("/", methods=["GET"])
@_token_required
def list_events():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("event_type", "audience", "status", "location_like",
                "organiser_like", "title_like", "date_from", "date_to"):
        val = args.get(key)
        if val is not None:
            kwargs[key] = val
    if args.get("overlapping") is not None:
        kwargs["overlapping"] = args.get("overlapping", "").lower() in (
            "1", "true", "yes")
    if args.get("upcoming_only") is not None:
        kwargs["upcoming_only"] = args.get("upcoming_only", "").lower() in (
            "1", "true", "yes")
    try:
        rows = data.list_events(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@calendar_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    window = request.args.get("upcoming_window_days")
    kwargs = {}
    if window is not None:
        try:
            kwargs["upcoming_window_days"] = int(window)
        except (TypeError, ValueError):
            return jsonify({"error": "upcoming_window_days must be an integer"}), 400
    result = data.summary(**kwargs)
    return jsonify(_dump(result))


@calendar_bp.route("/<int:event_id>", methods=["GET"])
@_token_required
def get_event(event_id: int):
    data = _data()
    row = data.get_event(event_id)
    if row is None:
        return jsonify({"error": f"No event #{event_id}"}), 404
    return jsonify(_dump(row))


@calendar_bp.route("", methods=["POST"])
@calendar_bp.route("/", methods=["POST"])
@_token_required
def create_event():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_event(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@calendar_bp.route("/<int:event_id>", methods=["PUT"])
@_token_required
def update_event(event_id: int):
    data = _data()
    if data.get_event(event_id) is None:
        return jsonify({"error": f"No event #{event_id}"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_event(event_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@calendar_bp.route("/<int:event_id>", methods=["DELETE"])
@_token_required
def delete_event(event_id: int):
    data = _data()
    if not data.delete_event(event_id):
        return jsonify({"error": f"No event #{event_id}"}), 404
    return jsonify({"deleted": True, "event_id": event_id})
