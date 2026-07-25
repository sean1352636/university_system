"""REST API for Nursery Rooms & Age Groups.

Exposes CRUD over the nursery ``rooms`` table plus an open/close status setter.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

rooms_bp = Blueprint("nsy_rooms", __name__, url_prefix="/api/rooms")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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
        data = dataclasses.asdict(obj)
        # Surface computed properties not captured by asdict().
        for prop in ("places_left", "is_full"):
            if hasattr(obj, prop):
                data[prop] = getattr(obj, prop)
        return data
    return obj


@rooms_bp.route("", methods=["GET"])
@rooms_bp.route("/", methods=["GET"])
@_token_required
def list_rooms_view():
    from education_system.systems.nursery.domain.operations.rooms import rooms as data

    include_closed = request.args.get("include_closed", "true").lower() != "false"
    rows = data.list_rooms(include_closed=include_closed)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@rooms_bp.route("/<room_id>", methods=["GET"])
@_token_required
def get_room_view(room_id):
    from education_system.systems.nursery.domain.operations.rooms import rooms as data

    room = data.get_room(room_id)
    if room is None:
        return jsonify({"error": "Room not found"}), 404
    return jsonify(_dump(room))


@rooms_bp.route("", methods=["POST"])
@rooms_bp.route("/", methods=["POST"])
@_token_required
def create_room_view():
    from education_system.systems.nursery.domain.operations.rooms import rooms as data

    payload = request.get_json(silent=True) or {}
    try:
        room = data.create_room(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(room)), 201


@rooms_bp.route("/<room_id>", methods=["PUT"])
@_token_required
def update_room_view(room_id):
    from education_system.systems.nursery.domain.operations.rooms import rooms as data

    if data.get_room(room_id) is None:
        return jsonify({"error": "Room not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        room = data.update_room(room_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(room))


@rooms_bp.route("/<room_id>", methods=["DELETE"])
@_token_required
def delete_room_view(room_id):
    from education_system.systems.nursery.domain.operations.rooms import rooms as data

    try:
        deleted = data.delete_room(room_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    if not deleted:
        return jsonify({"error": "Room not found"}), 404
    return jsonify({"deleted": True, "room_id": room_id})


@rooms_bp.route("/<room_id>/status", methods=["PUT"])
@_token_required
def set_status_view(room_id):
    from education_system.systems.nursery.domain.operations.rooms import rooms as data

    payload = request.get_json(silent=True) or {}
    try:
        room = data.set_status(room_id, payload.get("status"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(room))
