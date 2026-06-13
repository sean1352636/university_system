"""REST API for Nursery Staff : Child Ratios.

Read-only HTTP access to the computed EYFS staff:child ratio board (per-room
required adults, compliance, shortfall), plus the single management write
(setting a room's required ratio).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

ratios_bp = Blueprint("nsy_ratios", __name__, url_prefix="/api/ratios")


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
    """Serialize a domain dataclass (or list of them) to JSON-safe data.

    RoomRatio exposes compliance facts via @property (compliant, shortfall,
    children_per_adult) that asdict() would drop, so fold those in.
    """
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        data = dataclasses.asdict(obj)
        for prop in ("compliant", "shortfall", "children_per_adult"):
            if hasattr(obj, prop):
                data[prop] = getattr(obj, prop)
        return data
    return obj


@ratios_bp.route("", methods=["GET"])
@ratios_bp.route("/", methods=["GET"])
@_token_required
def list_ratios():
    """Per-room ratio board, optionally filtered by ?status / ?breaches=true."""
    from education_system.nursery_system.modules.domain.ratios import ratios as data

    rows = data.list_room_ratios()

    status = request.args.get("status")
    if status:
        rows = [r for r in rows if r.status == status]
    if request.args.get("breaches", "").lower() in ("1", "true", "yes"):
        rows = [r for r in rows if r.compliant is False]

    return jsonify({"items": _dump(rows), "count": len(rows)})


@ratios_bp.route("/<room_id>", methods=["GET"])
@_token_required
def get_ratio(room_id: str):
    """Single room's ratio row (404 if no such room)."""
    from education_system.nursery_system.modules.domain.ratios import ratios as data

    for rr in data.list_room_ratios():
        if rr.room_id == room_id:
            return jsonify(_dump(rr))
    return jsonify({"error": f"No room with id {room_id}"}), 404


@ratios_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    """Headline counts: rooms, children, staff, breaches, unplaced children."""
    from education_system.nursery_system.modules.domain.ratios import ratios as data

    return jsonify(data.summary())


@ratios_bp.route("/unplaced", methods=["GET"])
@_token_required
def unplaced():
    """Count of active children whose room matches no defined room."""
    from education_system.nursery_system.modules.domain.ratios import ratios as data

    return jsonify({"unplaced_children": data.list_unplaced_children()})


@ratios_bp.route("/<room_id>", methods=["PUT"])
@_token_required
def set_ratio(room_id: str):
    """Set a room's required staff:child ratio (body: {"ratio": "1:3"})."""
    from education_system.nursery_system.modules.domain.ratios import ratios as data

    payload = request.get_json(silent=True) or {}
    ratio = payload.get("ratio")
    try:
        rr = data.set_room_ratio(room_id, ratio)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rr))
