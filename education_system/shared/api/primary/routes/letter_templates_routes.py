"""REST API for Primary Letter Templates."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

letter_templates_bp = Blueprint(
    "pri_letter_templates", __name__, url_prefix="/api/letter-templates"
)


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
    from education_system.primarysch_system.modules.domain.letter_templates import (
        letter_templates as data,
    )
    return data


@letter_templates_bp.route("", methods=["GET"])
@letter_templates_bp.route("/", methods=["GET"])
@_token_required
def list_templates():
    data = _data()
    args = request.args
    bool_active = args.get("active_only", "").lower() in ("1", "true", "yes")
    rows = data.list_templates(
        category=args.get("category") or None,
        recipient_type=args.get("recipient_type") or None,
        format=args.get("format") or None,
        status=args.get("status") or None,
        active_only=bool_active,
        name_like=args.get("name_like") or None,
        created_by_like=args.get("created_by_like") or None,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@letter_templates_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@letter_templates_bp.route("/<int:template_id>", methods=["GET"])
@_token_required
def get_template(template_id: int):
    data = _data()
    row = data.get_template(template_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@letter_templates_bp.route("", methods=["POST"])
@letter_templates_bp.route("/", methods=["POST"])
@_token_required
def create_template():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_template(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@letter_templates_bp.route("/<int:template_id>", methods=["PUT"])
@_token_required
def update_template(template_id: int):
    data = _data()
    if data.get_template(template_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_template(template_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@letter_templates_bp.route("/<int:template_id>", methods=["DELETE"])
@_token_required
def delete_template(template_id: int):
    data = _data()
    if not data.delete_template(template_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "template_id": template_id})
