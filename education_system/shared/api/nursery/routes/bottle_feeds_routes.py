"""REST API for Nursery Bottle Feeds.

Exposes CRUD over the baby milk-feed log, plus child/staff picker lookups.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

bottle_feeds_bp = Blueprint("nsy_bottle_feeds", __name__, url_prefix="/api/bottle-feeds")


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


@bottle_feeds_bp.route("", methods=["GET"])
@_token_required
def list_bottle_feeds():
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    feed_date = request.args.get("feed_date")
    pupil_id = request.args.get("pupil_id")
    rows = data.list_records(feed_date=feed_date, pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@bottle_feeds_bp.route("/<feed_id>", methods=["GET"])
@_token_required
def get_bottle_feed(feed_id):
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    rec = data.get_record(feed_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@bottle_feeds_bp.route("", methods=["POST"])
@_token_required
def create_bottle_feed():
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@bottle_feeds_bp.route("/<feed_id>", methods=["PUT"])
@_token_required
def update_bottle_feed(feed_id):
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    if data.get_record(feed_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(feed_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@bottle_feeds_bp.route("/<feed_id>", methods=["DELETE"])
@_token_required
def delete_bottle_feed(feed_id):
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    if not data.delete_record(feed_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "feed_id": feed_id})


@bottle_feeds_bp.route("/pupil-choices", methods=["GET"])
@_token_required
def bottle_feed_pupil_choices():
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    rows = data.list_pupil_choices()
    items = [{"pupil_id": pid, "label": label} for pid, label in rows]
    return jsonify({"items": items, "count": len(items)})


@bottle_feeds_bp.route("/staff-choices", methods=["GET"])
@_token_required
def bottle_feed_staff_choices():
    from education_system.nursery_system.modules.domain.bottle_feeds import bottle_feeds as data
    rows = data.list_staff_choices()
    items = [{"staff_id": sid, "label": label} for sid, label in rows]
    return jsonify({"items": items, "count": len(items)})
