"""REST API for Nursery Daily Updates.

Exposes CRUD over the daily_updates table — the "how was my child's day"
summary shared with parents (mood, meals, sleep, nappies, activities, notes).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

daily_updates_bp = Blueprint("nsy_daily_updates", __name__, url_prefix="/api/daily-updates")


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


@daily_updates_bp.route("", methods=["GET"])
@daily_updates_bp.route("/", methods=["GET"])
@_token_required
def list_updates():
    from education_system.nursery_system.modules.domain.daily_updates import daily_updates as data

    pupil_id = request.args.get("pupil_id")
    rows = data.list_updates(pupil_id=pupil_id or None)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@daily_updates_bp.route("/<update_id>", methods=["GET"])
@_token_required
def get_update(update_id):
    from education_system.nursery_system.modules.domain.daily_updates import daily_updates as data

    row = data.get_update(update_id)
    if row is None:
        return jsonify({"error": "Daily update not found"}), 404
    return jsonify(_dump(row))


@daily_updates_bp.route("", methods=["POST"])
@daily_updates_bp.route("/", methods=["POST"])
@_token_required
def create_update():
    from education_system.nursery_system.modules.domain.daily_updates import daily_updates as data

    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_update(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@daily_updates_bp.route("/<update_id>", methods=["PUT"])
@_token_required
def update_update(update_id):
    from education_system.nursery_system.modules.domain.daily_updates import daily_updates as data

    if data.get_update(update_id) is None:
        return jsonify({"error": "Daily update not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_update(update_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@daily_updates_bp.route("/<update_id>", methods=["DELETE"])
@_token_required
def delete_update(update_id):
    from education_system.nursery_system.modules.domain.daily_updates import daily_updates as data

    if not data.delete_update(update_id):
        return jsonify({"error": "Daily update not found"}), 404
    return jsonify({"deleted": update_id})
