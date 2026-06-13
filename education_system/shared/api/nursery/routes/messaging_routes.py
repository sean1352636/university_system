"""REST API for Nursery Parent Messaging.

Exposes CRUD over the two-way parent_messages log between the setting and parents.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

messaging_bp = Blueprint("nsy_messaging", __name__, url_prefix="/api/messaging")


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


@messaging_bp.route("", methods=["GET"])
@messaging_bp.route("/", methods=["GET"])
@_token_required
def list_messages_view():
    from education_system.nursery_system.modules.domain.messaging import messaging as data
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_messages(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@messaging_bp.route("/<message_id>", methods=["GET"])
@_token_required
def get_message_view(message_id):
    from education_system.nursery_system.modules.domain.messaging import messaging as data
    msg = data.get_message(message_id)
    if msg is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(msg))


@messaging_bp.route("", methods=["POST"])
@messaging_bp.route("/", methods=["POST"])
@_token_required
def create_message_view():
    from education_system.nursery_system.modules.domain.messaging import messaging as data
    payload = request.get_json(silent=True) or {}
    try:
        msg = data.create_message(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(msg)), 201


@messaging_bp.route("/<message_id>", methods=["PUT"])
@_token_required
def update_message_view(message_id):
    from education_system.nursery_system.modules.domain.messaging import messaging as data
    if data.get_message(message_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        msg = data.update_message(message_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(msg))


@messaging_bp.route("/<message_id>", methods=["DELETE"])
@_token_required
def delete_message_view(message_id):
    from education_system.nursery_system.modules.domain.messaging import messaging as data
    if not data.delete_message(message_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "message_id": message_id})
