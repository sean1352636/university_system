"""REST API for Secondary School staff comms."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_comms_bp = Blueprint("sec_staff_comms", __name__, url_prefix="/api/staff-comms")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
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


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Staff directory ───────────────────────────────────────────────

@staff_comms_bp.route("/staff", methods=["GET"])
@_token_required
def list_staff():
    from education_system.systems.secondary.domain.staff import (
        staff as data,
    )
    try:
        rows = data.list_staff(
            role=request.args.get("role"),
            department=request.args.get("department"),
            employment_status=request.args.get("employment_status"),
            active_only=request.args.get("active_only", "").lower()
            in ("1", "true", "yes"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_comms_bp.route("/staff/<staff_id>", methods=["GET"])
@_token_required
def get_staff(staff_id):
    from education_system.systems.secondary.domain.staff import (
        staff as data,
    )
    row = data.get_staff(staff_id)
    if row is None:
        return jsonify({"error": "Staff not found"}), 404
    return jsonify(_dump(row))


@staff_comms_bp.route("/staff", methods=["POST"])
@_token_required
def create_staff():
    from education_system.systems.secondary.domain.staff import (
        staff as data,
    )
    try:
        row = data.create_staff(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_comms_bp.route("/staff/<staff_id>", methods=["PUT"])
@_token_required
def update_staff(staff_id):
    from education_system.systems.secondary.domain.staff import (
        staff as data,
    )
    if data.get_staff(staff_id) is None:
        return jsonify({"error": "Staff not found"}), 404
    try:
        row = data.update_staff(staff_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@staff_comms_bp.route("/staff/<staff_id>", methods=["DELETE"])
@_token_required
def delete_staff(staff_id):
    from education_system.systems.secondary.domain.staff import (
        staff as data,
    )
    if not data.delete_staff(staff_id):
        return jsonify({"error": "Staff not found"}), 404
    return jsonify({"deleted": True, "staff_id": staff_id})


# ── Announcements ─────────────────────────────────────────────────

@staff_comms_bp.route("/announcements", methods=["GET"])
@_token_required
def list_announcements():
    from education_system.systems.secondary.domain.operations.communications.announcements import (
        announcements as data,
    )
    pr = request.args.get("priority")
    try:
        rows = data.list_announcements(
            category=request.args.get("category"),
            status=request.args.get("status"),
            priority=int(pr) if pr else None,
            audience=request.args.get("audience"),
            published_only=request.args.get("published_only", "").lower()
            in ("1", "true", "yes"),
            live_only=request.args.get("live_only", "").lower()
            in ("1", "true", "yes"),
        )
    except (data.ValidationError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_comms_bp.route("/announcements/<int:announcement_id>", methods=["GET"])
@_token_required
def get_announcement(announcement_id):
    from education_system.systems.secondary.domain.operations.communications.announcements import (
        announcements as data,
    )
    row = data.get_announcement(announcement_id)
    if row is None:
        return jsonify({"error": "Announcement not found"}), 404
    return jsonify(_dump(row))


@staff_comms_bp.route("/announcements", methods=["POST"])
@_token_required
def create_announcement():
    from education_system.systems.secondary.domain.operations.communications.announcements import (
        announcements as data,
    )
    try:
        row = data.create_announcement(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_comms_bp.route("/announcements/<int:announcement_id>", methods=["PUT"])
@_token_required
def update_announcement(announcement_id):
    from education_system.systems.secondary.domain.operations.communications.announcements import (
        announcements as data,
    )
    if data.get_announcement(announcement_id) is None:
        return jsonify({"error": "Announcement not found"}), 404
    try:
        row = data.update_announcement(announcement_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@staff_comms_bp.route("/announcements/<int:announcement_id>", methods=["DELETE"])
@_token_required
def delete_announcement(announcement_id):
    from education_system.systems.secondary.domain.operations.communications.announcements import (
        announcements as data,
    )
    if not data.delete_announcement(announcement_id):
        return jsonify({"error": "Announcement not found"}), 404
    return jsonify({"deleted": True, "announcement_id": announcement_id})


# ── Messages ──────────────────────────────────────────────────────

@staff_comms_bp.route("/messages", methods=["GET"])
@_token_required
def list_messages():
    from education_system.systems.secondary.domain.operations.communications.messages import (
        messages as data,
    )
    try:
        rows = data.list_messages(
            direction=request.args.get("direction"),
            channel=request.args.get("channel"),
            category=request.args.get("category"),
            status=request.args.get("status"),
            student_id=request.args.get("student_id"),
            staff_id=request.args.get("staff_id"),
            thread_id=request.args.get("thread_id"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@staff_comms_bp.route("/messages/<int:message_id>", methods=["GET"])
@_token_required
def get_message(message_id):
    from education_system.systems.secondary.domain.operations.communications.messages import (
        messages as data,
    )
    row = data.get_message(message_id)
    if row is None:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(_dump(row))


@staff_comms_bp.route("/messages", methods=["POST"])
@_token_required
def create_message():
    from education_system.systems.secondary.domain.operations.communications.messages import (
        messages as data,
    )
    try:
        row = data.create_message(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_comms_bp.route("/messages/<int:message_id>", methods=["PUT"])
@_token_required
def update_message(message_id):
    from education_system.systems.secondary.domain.operations.communications.messages import (
        messages as data,
    )
    if data.get_message(message_id) is None:
        return jsonify({"error": "Message not found"}), 404
    try:
        row = data.update_message(message_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@staff_comms_bp.route("/messages/<int:message_id>", methods=["DELETE"])
@_token_required
def delete_message(message_id):
    from education_system.systems.secondary.domain.operations.communications.messages import (
        messages as data,
    )
    if not data.delete_message(message_id):
        return jsonify({"error": "Message not found"}), 404
    return jsonify({"deleted": True, "message_id": message_id})
