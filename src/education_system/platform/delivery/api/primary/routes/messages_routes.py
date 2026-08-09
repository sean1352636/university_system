"""REST API for Primary Messages / Communication Log."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

messages_bp = Blueprint("pri_messages", __name__, url_prefix="/api/messages")


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
    from education_system.systems.primary.domain.operations.communications.messages import (
        messages as data,
    )
    return data


@messages_bp.route("", methods=["GET"])
@messages_bp.route("/", methods=["GET"])
@_token_required
def list_messages():
    data = _data()
    a = request.args
    kwargs = {}
    for key in ("direction", "channel", "category", "priority", "status",
                "student_id", "staff_id", "thread_id"):
        val = a.get(key)
        if val:
            kwargs[key] = val
    if a.get("alumni_id"):
        try:
            kwargs["alumni_id"] = int(a.get("alumni_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "alumni_id must be an integer"}), 400
    for flag in ("drafts_only", "unsent_only", "sent_only"):
        if a.get(flag, "").lower() in ("1", "true", "yes"):
            kwargs[flag] = True
    try:
        rows = data.list_messages(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@messages_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary())), 200


@messages_bp.route("/search", methods=["GET"])
@_token_required
def search_messages():
    data = _data()
    q = request.args.get("q", "")
    rows = data.search_messages(q)
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@messages_bp.route("/threads", methods=["GET"])
@_token_required
def list_threads():
    data = _data()
    a = request.args
    kwargs = {}
    for key in ("student_id", "staff_id"):
        if a.get(key):
            kwargs[key] = a.get(key)
    rows = data.list_threads(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@messages_bp.route("/threads/<thread_id>", methods=["GET"])
@_token_required
def get_thread(thread_id):
    data = _data()
    rows = data.thread(thread_id)
    return jsonify({"items": _dump(rows), "count": len(rows)}), 200


@messages_bp.route("/<int:message_id>", methods=["GET"])
@_token_required
def get_message(message_id):
    data = _data()
    row = data.get_message(message_id)
    if row is None:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(_dump(row)), 200


@messages_bp.route("", methods=["POST"])
@messages_bp.route("/", methods=["POST"])
@_token_required
def create_message():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_message(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@messages_bp.route("/<int:message_id>", methods=["PUT"])
@_token_required
def update_message(message_id):
    data = _data()
    if data.get_message(message_id) is None:
        return jsonify({"error": "Message not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_message(message_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 200


@messages_bp.route("/<int:message_id>/send", methods=["POST"])
@_token_required
def send_message(message_id):
    data = _data()
    if data.get_message(message_id) is None:
        return jsonify({"error": "Message not found"}), 404
    try:
        row = data.send_message(message_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 200


@messages_bp.route("/<int:message_id>/reply", methods=["POST"])
@_token_required
def reply(message_id):
    data = _data()
    if data.get_message(message_id) is None:
        return jsonify({"error": "Message not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.reply(message_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@messages_bp.route("/<int:message_id>", methods=["DELETE"])
@_token_required
def delete_message(message_id):
    data = _data()
    if not data.delete_message(message_id):
        return jsonify({"error": "Message not found"}), 404
    return jsonify({"deleted": True, "message_id": message_id}), 200
