"""REST API for Nursery Invoices & Fees.

Exposes CRUD over fee invoices raised to a child's account, plus a billing
summary and an invoice-status setter.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

invoices_bp = Blueprint("nsy_invoices", __name__, url_prefix="/api/invoices")


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


@invoices_bp.route("", methods=["GET"])
@invoices_bp.route("/", methods=["GET"])
@_token_required
def list_invoices():
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    pupil_id = request.args.get("pupil_id")
    status = request.args.get("status")
    rows = data.list_invoices(pupil_id=pupil_id, status=status)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@invoices_bp.route("/summary", methods=["GET"])
@_token_required
def invoices_summary():
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    return jsonify(data.summary())


@invoices_bp.route("/<invoice_id>", methods=["GET"])
@_token_required
def get_invoice(invoice_id):
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    invoice = data.get_invoice(invoice_id)
    if invoice is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(invoice))


@invoices_bp.route("", methods=["POST"])
@invoices_bp.route("/", methods=["POST"])
@_token_required
def create_invoice():
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    try:
        invoice = data.create_invoice(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(invoice)), 201


@invoices_bp.route("/<invoice_id>", methods=["PUT"])
@_token_required
def update_invoice(invoice_id):
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    if data.get_invoice(invoice_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        invoice = data.update_invoice(invoice_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(invoice))


@invoices_bp.route("/<invoice_id>/status", methods=["PUT"])
@_token_required
def set_invoice_status(invoice_id):
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    if data.get_invoice(invoice_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        invoice = data.set_status(invoice_id, payload.get("status", ""))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(invoice))


@invoices_bp.route("/<invoice_id>", methods=["DELETE"])
@_token_required
def delete_invoice(invoice_id):
    from education_system.systems.nursery.domain.finance.invoices import invoices as data
    if not data.delete_invoice(invoice_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "invoice_id": invoice_id})
