"""REST API for Nursery Sibling Discounts.

Exposes CRUD over standing fee-discount arrangements plus a summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

discounts_bp = Blueprint("nsy_discounts", __name__, url_prefix="/api/discounts")


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


@discounts_bp.route("", methods=["GET"])
@discounts_bp.route("/", methods=["GET"])
@_token_required
def list_discounts():
    from education_system.nursery_system.modules.domain.discounts import discounts as data
    pupil_id = request.args.get("pupil_id")
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    rows = data.list_discounts(pupil_id=pupil_id, active_only=active_only)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@discounts_bp.route("/summary", methods=["GET"])
@_token_required
def discounts_summary():
    from education_system.nursery_system.modules.domain.discounts import discounts as data
    return jsonify(data.summary())


@discounts_bp.route("/<discount_id>", methods=["GET"])
@_token_required
def get_discount(discount_id):
    from education_system.nursery_system.modules.domain.discounts import discounts as data
    discount = data.get_discount(discount_id)
    if discount is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(discount))


@discounts_bp.route("", methods=["POST"])
@discounts_bp.route("/", methods=["POST"])
@_token_required
def create_discount():
    from education_system.nursery_system.modules.domain.discounts import discounts as data
    try:
        discount = data.create_discount(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(discount)), 201


@discounts_bp.route("/<discount_id>", methods=["PUT"])
@_token_required
def update_discount(discount_id):
    from education_system.nursery_system.modules.domain.discounts import discounts as data
    if data.get_discount(discount_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        discount = data.update_discount(discount_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(discount))


@discounts_bp.route("/<discount_id>", methods=["DELETE"])
@_token_required
def delete_discount(discount_id):
    from education_system.nursery_system.modules.domain.discounts import discounts as data
    if not data.delete_discount(discount_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "discount_id": discount_id})
