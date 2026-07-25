"""REST API for Primary Compliance Register."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

compliance_bp = Blueprint("pri_compliance", __name__, url_prefix="/api/compliance")


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


@compliance_bp.route("", methods=["GET"])
@compliance_bp.route("/", methods=["GET"])
@_token_required
def list_items():
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    args = request.args
    kwargs = {}
    if args.get("category"):
        kwargs["category"] = args.get("category")
    if args.get("status"):
        kwargs["status"] = args.get("status")
    if args.get("owner"):
        kwargs["owner"] = args.get("owner")
    if args.get("overdue_only") in ("1", "true", "True", "yes"):
        kwargs["overdue_only"] = True
    if args.get("query"):
        kwargs["query"] = args.get("query")
    try:
        rows = data.list_items(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@compliance_bp.route("/summary", methods=["GET"])
@_token_required
def get_summary():
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    due_soon_days = request.args.get("due_soon_days", type=int)
    if due_soon_days is None:
        result = data.summary()
    else:
        result = data.summary(due_soon_days=due_soon_days)
    return jsonify(_dump(result))


@compliance_bp.route("/<int:item_id>", methods=["GET"])
@_token_required
def get_item(item_id: int):
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    row = data.get_item(item_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@compliance_bp.route("", methods=["POST"])
@compliance_bp.route("/", methods=["POST"])
@_token_required
def create_item():
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_item(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@compliance_bp.route("/<int:item_id>", methods=["PUT"])
@_token_required
def update_item(item_id: int):
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    if data.get_item(item_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_item(item_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@compliance_bp.route("/<int:item_id>/review", methods=["POST"])
@_token_required
def mark_reviewed(item_id: int):
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    if data.get_item(item_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.mark_reviewed(
            item_id,
            reviewed_on=payload.get("reviewed_on"),
            notes=payload.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@compliance_bp.route("/<int:item_id>", methods=["DELETE"])
@_token_required
def delete_item(item_id: int):
    from education_system.systems.primary.domain.governance.compliance import compliance as data
    if not data.delete_item(item_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
