"""REST API for Nursery Sign In / Sign Out.

Exposes the timestamped arrival/collection log: list, get, create, sign-in,
sign-out, delete, plus a "currently in" roll-call view.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

sign_in_out_bp = Blueprint("nsy_sign_in_out", __name__, url_prefix="/api/sign-in-out")


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
        return dataclasses.asdict(obj)
    return obj


@sign_in_out_bp.route("", methods=["GET"])
@sign_in_out_bp.route("/", methods=["GET"])
@_token_required
def list_events():
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    event_date = request.args.get("event_date") or None
    direction = request.args.get("direction") or None
    rows = data.list_events(event_date=event_date, direction=direction)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@sign_in_out_bp.route("/currently-in", methods=["GET"])
@_token_required
def currently_in():
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    event_date = request.args.get("event_date") or data._today()
    rows = data.currently_in(event_date)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@sign_in_out_bp.route("/<event_id>", methods=["GET"])
@_token_required
def get_event(event_id):
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    ev = data.get_event(event_id)
    if ev is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(ev))


@sign_in_out_bp.route("", methods=["POST"])
@sign_in_out_bp.route("/", methods=["POST"])
@_token_required
def create_event():
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        ev = data.create_event(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ev)), 201


@sign_in_out_bp.route("/sign-in", methods=["POST"])
@_token_required
def sign_in():
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        ev = data.sign_in(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ev)), 201


@sign_in_out_bp.route("/sign-out", methods=["POST"])
@_token_required
def sign_out():
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        ev = data.sign_out(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ev)), 201


@sign_in_out_bp.route("/<event_id>", methods=["DELETE"])
@_token_required
def delete_event(event_id):
    from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
        sign_in_out as data,
    )
    if not data.delete_event(event_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "event_id": event_id})
