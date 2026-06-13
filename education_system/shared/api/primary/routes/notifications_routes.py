"""REST API for Primary Notifications."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("pri_notifications", __name__, url_prefix="/api/notifications")


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
    from education_system.primarysch_system.modules.domain.notifications import (
        notifications as data,
    )
    return data


def _bad(msg):
    return jsonify({"error": str(msg)}), 400


@notifications_bp.route("", methods=["GET"])
@notifications_bp.route("/", methods=["GET"])
@_token_required
def list_notifications():
    data = _data()
    args = request.args
    kwargs = {}
    for key in ("recipient_type", "recipient_id", "notification_type",
                "channel", "status", "sent_by_like", "title_like",
                "date_from", "date_to"):
        val = args.get(key)
        if val:
            kwargs[key] = val
    for key in ("priority", "priority_min"):
        val = args.get(key)
        if val:
            try:
                kwargs[key] = int(val)
            except ValueError:
                return _bad(f"{key} must be an integer")
    for key in ("unread_only", "needs_action_only", "urgent_only",
                "pending_only"):
        if args.get(key, "").lower() in ("1", "true", "yes"):
            kwargs[key] = True
    rows = data.list_notifications(**kwargs)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@notifications_bp.route("/summary", methods=["GET"])
@_token_required
def notifications_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@notifications_bp.route("/<int:notification_id>", methods=["GET"])
@_token_required
def get_notification(notification_id):
    data = _data()
    obj = data.get_notification(notification_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("", methods=["POST"])
@notifications_bp.route("/", methods=["POST"])
@_token_required
def create_notification():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_notification(payload)
    except data.ValidationError as exc:
        return _bad(exc)
    return jsonify(_dump(obj)), 201


@notifications_bp.route("/<int:notification_id>", methods=["PUT"])
@_token_required
def update_notification(notification_id):
    data = _data()
    if data.get_notification(notification_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_notification(notification_id, payload)
    except data.ValidationError as exc:
        return _bad(exc)
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>", methods=["DELETE"])
@_token_required
def delete_notification(notification_id):
    data = _data()
    if not data.delete_notification(notification_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Workflow transitions ─────────────────────────────────────

@notifications_bp.route("/<int:notification_id>/schedule", methods=["POST"])
@_token_required
def schedule_notification(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    scheduled_for = payload.get("scheduled_for")
    if not scheduled_for:
        return _bad("scheduled_for is required")
    try:
        obj = data.schedule(notification_id, scheduled_for=scheduled_for)
    except data.ValidationError as exc:
        msg = str(exc)
        if msg.startswith("No notification with id"):
            return jsonify({"error": msg}), 404
        return _bad(msg)
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/send", methods=["POST"])
@_token_required
def send_notification(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.mark_sent(notification_id, sent_at=payload.get("sent_at"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/deliver", methods=["POST"])
@_token_required
def deliver_notification(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.mark_delivered(
            notification_id, delivered_at=payload.get("delivered_at"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@_token_required
def read_notification(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.mark_read(notification_id, read_at=payload.get("read_at"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/acknowledge", methods=["POST"])
@_token_required
def acknowledge_notification(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.acknowledge(notification_id, ack_at=payload.get("ack_at"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/dismiss", methods=["POST"])
@_token_required
def dismiss_notification(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.dismiss(
            notification_id, dismissed_at=payload.get("dismissed_at"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/complete-action", methods=["POST"])
@_token_required
def complete_action(notification_id):
    data = _data()
    try:
        obj = data.mark_action_completed(notification_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/fail", methods=["POST"])
@_token_required
def fail_notification(notification_id):
    data = _data()
    try:
        obj = data.mark_failed(notification_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(obj))


@notifications_bp.route("/<int:notification_id>/status", methods=["POST"])
@_token_required
def set_notification_status(notification_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    if not new_status:
        return _bad("status is required")
    try:
        obj = data.set_status(notification_id, new_status)
    except data.ValidationError as exc:
        msg = str(exc)
        if msg.startswith("No notification with id"):
            return jsonify({"error": msg}), 404
        return _bad(msg)
    return jsonify(_dump(obj))


@notifications_bp.route("/broadcast", methods=["POST"])
@_token_required
def broadcast_notifications():
    data = _data()
    payload = request.get_json(silent=True) or {}
    recipients = payload.get("recipients") or []
    if not recipients:
        return _bad("recipients is required")
    try:
        tuples = [
            (r["recipient_type"], r["recipient_id"], r.get("recipient_name"))
            for r in recipients
        ]
    except (TypeError, KeyError):
        return _bad("each recipient needs recipient_type and recipient_id")
    if not payload.get("title"):
        return _bad("title is required")
    kwargs = {
        k: payload[k]
        for k in ("body", "notification_type", "priority", "channel",
                  "sent_by", "status", "expires_on", "linked_to")
        if k in payload
    }
    try:
        rows = data.broadcast(
            recipients=tuples, title=payload["title"], **kwargs)
    except data.ValidationError as exc:
        return _bad(exc)
    return jsonify({"items": _dump(rows), "count": len(rows)}), 201


@notifications_bp.route("/auto-expire", methods=["POST"])
@_token_required
def auto_expire_notifications():
    data = _data()
    updated = data.auto_expire()
    return jsonify({"expired": updated})
