"""REST API for Primary Announcements."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

announcements_bp = Blueprint("pri_announcements", __name__, url_prefix="/api/announcements")


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


@announcements_bp.route("", methods=["GET"])
@announcements_bp.route("/", methods=["GET"])
@_token_required
def list_announcements():
    from education_system.primarysch_system.modules.domain.announcements import (
        announcements as data,
    )
    try:
        rows = data.list_announcements()
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@announcements_bp.route("/summary", methods=["GET"])
@_token_required
def announcements_summary():
    from education_system.primarysch_system.modules.domain.announcements import (
        announcements as data,
    )
    return jsonify(_dump(data.summary()))


@announcements_bp.route("/<int:announcement_id>", methods=["GET"])
@_token_required
def get_announcement(announcement_id: int):
    from education_system.primarysch_system.modules.domain.announcements import (
        announcements as data,
    )
    row = data.get_announcement(announcement_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@announcements_bp.route("", methods=["POST"])
@announcements_bp.route("/", methods=["POST"])
@_token_required
def create_announcement():
    from education_system.primarysch_system.modules.domain.announcements import (
        announcements as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_announcement(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@announcements_bp.route("/<int:announcement_id>", methods=["PUT"])
@_token_required
def update_announcement(announcement_id: int):
    from education_system.primarysch_system.modules.domain.announcements import (
        announcements as data,
    )
    if data.get_announcement(announcement_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_announcement(announcement_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@announcements_bp.route("/<int:announcement_id>", methods=["DELETE"])
@_token_required
def delete_announcement(announcement_id: int):
    from education_system.primarysch_system.modules.domain.announcements import (
        announcements as data,
    )
    if not data.delete_announcement(announcement_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "announcement_id": announcement_id})
