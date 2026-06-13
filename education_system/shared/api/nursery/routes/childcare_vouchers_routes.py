"""REST API for Nursery Tax-Free Childcare / Vouchers.

Exposes CRUD over the standing voucher / Tax-Free Childcare arrangements registry.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

childcare_vouchers_bp = Blueprint("nsy_childcare_vouchers", __name__, url_prefix="/api/childcare-vouchers")


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


@childcare_vouchers_bp.route("", methods=["GET"])
@childcare_vouchers_bp.route("/", methods=["GET"])
@_token_required
def list_vouchers():
    from education_system.nursery_system.modules.domain.childcare_vouchers import (
        childcare_vouchers as data,
    )

    pupil_id = request.args.get("pupil_id") or None
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    rows = data.list_vouchers(pupil_id=pupil_id, active_only=active_only)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@childcare_vouchers_bp.route("/summary", methods=["GET"])
@_token_required
def voucher_summary():
    from education_system.nursery_system.modules.domain.childcare_vouchers import (
        childcare_vouchers as data,
    )

    return jsonify(data.summary())


@childcare_vouchers_bp.route("/<voucher_id>", methods=["GET"])
@_token_required
def get_voucher(voucher_id):
    from education_system.nursery_system.modules.domain.childcare_vouchers import (
        childcare_vouchers as data,
    )

    voucher = data.get_voucher(voucher_id)
    if voucher is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(voucher))


@childcare_vouchers_bp.route("", methods=["POST"])
@childcare_vouchers_bp.route("/", methods=["POST"])
@_token_required
def create_voucher():
    from education_system.nursery_system.modules.domain.childcare_vouchers import (
        childcare_vouchers as data,
    )

    try:
        voucher = data.create_voucher(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(voucher)), 201


@childcare_vouchers_bp.route("/<voucher_id>", methods=["PUT"])
@_token_required
def update_voucher(voucher_id):
    from education_system.nursery_system.modules.domain.childcare_vouchers import (
        childcare_vouchers as data,
    )

    if data.get_voucher(voucher_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        voucher = data.update_voucher(voucher_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(voucher))


@childcare_vouchers_bp.route("/<voucher_id>", methods=["DELETE"])
@_token_required
def delete_voucher(voucher_id):
    from education_system.nursery_system.modules.domain.childcare_vouchers import (
        childcare_vouchers as data,
    )

    if not data.delete_voucher(voucher_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "voucher_id": voucher_id})
