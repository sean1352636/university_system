"""REST API for Primary Expense Claims."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

expense_claims_bp = Blueprint("pri_expense_claims", __name__, url_prefix="/api/expense-claims")


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


def _data():
    from education_system.systems.primary.domain.finance.expense_claims import (
        expense_claims as data,
    )
    return data


# ── Claims ───────────────────────────────────────────────

@expense_claims_bp.route("", methods=["GET"])
@expense_claims_bp.route("/", methods=["GET"])
@_token_required
def list_claims():
    data = _data()
    args = request.args
    rows = data.list_claims(
        claimant_type=args.get("claimant_type"),
        claimant_id=args.get("claimant_id"),
        status=args.get("status"),
        category=args.get("category"),
        payment_method=args.get("payment_method"),
        open_only=args.get("open_only", "").lower() in ("1", "true", "yes"),
        awaiting_payment_only=args.get("awaiting_payment_only", "").lower()
        in ("1", "true", "yes"),
        paid_only=args.get("paid_only", "").lower() in ("1", "true", "yes"),
        title_like=args.get("title_like"),
        date_from=args.get("date_from"),
        date_to=args.get("date_to"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@expense_claims_bp.route("/summary", methods=["GET"])
@_token_required
def claims_summary():
    data = _data()
    return jsonify(_dump(data.summary()))


@expense_claims_bp.route("/<int:claim_id>", methods=["GET"])
@_token_required
def get_claim(claim_id):
    data = _data()
    obj = data.get_claim(claim_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@expense_claims_bp.route("", methods=["POST"])
@expense_claims_bp.route("/", methods=["POST"])
@_token_required
def create_claim():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.create_claim(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@expense_claims_bp.route("/<int:claim_id>", methods=["PUT"])
@_token_required
def update_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_claim(claim_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>", methods=["DELETE"])
@_token_required
def delete_claim(claim_id):
    data = _data()
    if not data.delete_claim(claim_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Claim lines (sub-resource) ───────────────────────────

@expense_claims_bp.route("/<int:claim_id>/lines", methods=["GET"])
@_token_required
def list_lines(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    rows = data.lines_for_claim(claim_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@expense_claims_bp.route("/<int:claim_id>/lines", methods=["POST"])
@_token_required
def add_line(claim_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.add_line(claim_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj)), 201


@expense_claims_bp.route("/lines/<int:line_id>", methods=["GET"])
@_token_required
def get_line(line_id):
    data = _data()
    obj = data.get_line(line_id)
    if obj is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(obj))


@expense_claims_bp.route("/lines/<int:line_id>", methods=["PUT"])
@_token_required
def update_line(line_id):
    data = _data()
    if data.get_line(line_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.update_line(line_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/lines/<int:line_id>", methods=["DELETE"])
@_token_required
def delete_line(line_id):
    data = _data()
    if not data.delete_line(line_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Workflow actions ─────────────────────────────────────

@expense_claims_bp.route("/<int:claim_id>/submit", methods=["POST"])
@_token_required
def submit_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        obj = data.submit(claim_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>/begin-review", methods=["POST"])
@_token_required
def begin_review_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        obj = data.begin_review(claim_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>/approve", methods=["POST"])
@_token_required
def approve_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.approve(claim_id, approved_by=payload.get("approved_by"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>/reject", methods=["POST"])
@_token_required
def reject_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.reject(claim_id, reason=payload.get("reason"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>/pay", methods=["POST"])
@_token_required
def pay_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.pay(
            claim_id,
            payment_reference=payload.get("payment_reference"),
            paid_on=payload.get("paid_on"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>/cancel", methods=["POST"])
@_token_required
def cancel_claim(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        obj = data.cancel(claim_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))


@expense_claims_bp.route("/<int:claim_id>/status", methods=["POST"])
@_token_required
def set_claim_status(claim_id):
    data = _data()
    if data.get_claim(claim_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        obj = data.set_status(claim_id, payload.get("status"))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(obj))
