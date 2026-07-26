"""REST API for Nursery Expense Claims.

Exposes CRUD over expense claims plus claim-line sub-resources,
workflow status transitions, and a summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

expense_claims_bp = Blueprint("nsy_expense_claims", __name__, url_prefix="/api/expense-claims")


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


@expense_claims_bp.route("", methods=["GET"])
@expense_claims_bp.route("/", methods=["GET"])
@_token_required
def list_claims():
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    args = request.args

    def _flag(name: str) -> bool:
        return args.get(name, "").lower() in ("1", "true", "yes", "on")

    rows = data.list_claims(
        claimant_type=args.get("claimant_type"),
        claimant_id=args.get("claimant_id"),
        status=args.get("status"),
        category=args.get("category"),
        payment_method=args.get("payment_method"),
        open_only=_flag("open_only"),
        awaiting_payment_only=_flag("awaiting_payment_only"),
        paid_only=_flag("paid_only"),
        title_like=args.get("title_like"),
        date_from=args.get("date_from"),
        date_to=args.get("date_to"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@expense_claims_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    return jsonify(_dump(data.summary()))


@expense_claims_bp.route("/<int:claim_id>", methods=["GET"])
@_token_required
def get_claim(claim_id: int):
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    claim = data.get_claim(claim_id)
    if claim is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(claim))


@expense_claims_bp.route("", methods=["POST"])
@expense_claims_bp.route("/", methods=["POST"])
@_token_required
def create_claim():
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    try:
        claim = data.create_claim(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(claim)), 201


@expense_claims_bp.route("/<int:claim_id>", methods=["PUT"])
@_token_required
def update_claim(claim_id: int):
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        claim = data.update_claim(claim_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(claim))


@expense_claims_bp.route("/<int:claim_id>", methods=["DELETE"])
@_token_required
def delete_claim(claim_id: int):
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    if not data.delete_claim(claim_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "claim_id": claim_id})


@expense_claims_bp.route("/<int:claim_id>/status", methods=["POST"])
@_token_required
def set_status(claim_id: int):
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    payload = request.get_json(force=True, silent=True) or {}
    new_status = payload.get("status")
    if not new_status:
        return jsonify({"error": "status is required"}), 400
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        claim = data.set_status(claim_id, new_status)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(claim))


@expense_claims_bp.route("/<int:claim_id>/lines", methods=["GET"])
@_token_required
def lines_for_claim(claim_id: int):
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.lines_for_claim(claim_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@expense_claims_bp.route("/<int:claim_id>/lines", methods=["POST"])
@_token_required
def add_line(claim_id: int):
    from education_system.systems.nursery.domain.finance.expense_claims import expense_claims as data

    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        line = data.add_line(claim_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(line)), 201
