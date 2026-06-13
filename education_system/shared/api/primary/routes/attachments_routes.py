"""REST API for Primary Attachments."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

attachments_bp = Blueprint("pri_attachments", __name__, url_prefix="/api/attachments")


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
    from education_system.primarysch_system.modules.domain.attachments import (
        attachments as data,
    )
    return data


@attachments_bp.route("", methods=["GET"])
@attachments_bp.route("/", methods=["GET"])
@_token_required
def list_attachments():
    data = _data()
    args = request.args
    rows = data.list_attachments(
        entity_type=args.get("entity_type"),
        entity_id=args.get("entity_id"),
        category=args.get("category"),
        visibility=args.get("visibility"),
        status=args.get("status"),
        active_only=args.get("active_only", "").lower() in ("1", "true", "yes"),
        pii_only=args.get("pii_only", "").lower() in ("1", "true", "yes"),
        retention_expired_only=args.get("retention_expired_only", "").lower()
        in ("1", "true", "yes"),
        title_like=args.get("title_like"),
        keyword_like=args.get("keyword_like"),
        uploaded_by_like=args.get("uploaded_by_like"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@attachments_bp.route("/summary", methods=["GET"])
@_token_required
def attachments_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@attachments_bp.route("/<int:attachment_id>", methods=["GET"])
@_token_required
def get_attachment(attachment_id: int):
    data = _data()
    row = data.get_attachment(attachment_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@attachments_bp.route("", methods=["POST"])
@attachments_bp.route("/", methods=["POST"])
@_token_required
def create_attachment():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_attachment(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@attachments_bp.route("/<int:attachment_id>", methods=["PUT"])
@_token_required
def update_attachment(attachment_id: int):
    data = _data()
    if data.get_attachment(attachment_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_attachment(attachment_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@attachments_bp.route("/<int:attachment_id>", methods=["DELETE"])
@_token_required
def delete_attachment(attachment_id: int):
    data = _data()
    if not data.delete_attachment(attachment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "attachment_id": attachment_id})
