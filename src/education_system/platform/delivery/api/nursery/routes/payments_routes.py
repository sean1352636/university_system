"""REST API for Nursery Payments.

Exposes CRUD over family payments (optionally allocated to an invoice), plus a
summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

payments_bp = Blueprint("nsy_payments", __name__, url_prefix="/api/payments")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


@payments_bp.route("", methods=["GET"])
@payments_bp.route("/", methods=["GET"])
@_token_required
def list_payments():
    from education_system.systems.nursery.domain.finance.payments import payments as data
    rows = data.list_payments(
        pupil_id=request.args.get("pupil_id"),
        invoice_id=request.args.get("invoice_id"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@payments_bp.route("/summary", methods=["GET"])
@_token_required
def payment_summary():
    from education_system.systems.nursery.domain.finance.payments import payments as data
    return jsonify(data.summary())


@payments_bp.route("/<payment_id>", methods=["GET"])
@_token_required
def get_payment(payment_id):
    from education_system.systems.nursery.domain.finance.payments import payments as data
    pay = data.get_payment(payment_id)
    if pay is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(pay))


@payments_bp.route("", methods=["POST"])
@payments_bp.route("/", methods=["POST"])
@_token_required
def create_payment():
    from education_system.systems.nursery.domain.finance.payments import payments as data
    try:
        pay = data.create_payment(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pay)), 201


@payments_bp.route("/<payment_id>", methods=["PUT"])
@_token_required
def update_payment(payment_id):
    from education_system.systems.nursery.domain.finance.payments import payments as data
    if data.get_payment(payment_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        pay = data.update_payment(payment_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pay))


@payments_bp.route("/<payment_id>", methods=["DELETE"])
@_token_required
def delete_payment(payment_id):
    from education_system.systems.nursery.domain.finance.payments import payments as data
    if not data.delete_payment(payment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": payment_id})
