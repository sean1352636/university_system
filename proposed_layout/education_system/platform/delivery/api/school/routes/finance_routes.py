"""REST API for Secondary School finance."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

finance_bp = Blueprint("sec_finance", __name__, url_prefix="/api/finance")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
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


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Fees ───────────────────────────────────────────────────────────

@finance_bp.route("/fees", methods=["GET"])
@_token_required
def list_fees():
    from education_system.systems.secondary.domain.finance.fees import fees as data
    try:
        rows = data.list_items(
            student_id=request.args.get("student_id"),
            category=request.args.get("category"),
            academic_year=request.args.get("academic_year"),
            stored_status=request.args.get("stored_status"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@finance_bp.route("/fees/<int:fee_id>", methods=["GET"])
@_token_required
def get_fee(fee_id: int):
    from education_system.systems.secondary.domain.finance.fees import fees as data
    row = data.get_item(fee_id)
    if row is None:
        return jsonify({"error": f"No fee with id {fee_id}"}), 404
    return jsonify(_dump(row))


@finance_bp.route("/fees", methods=["POST"])
@_token_required
def create_fee():
    from education_system.systems.secondary.domain.finance.fees import fees as data
    try:
        row = data.create_item(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@finance_bp.route("/fees/<int:fee_id>", methods=["PUT"])
@_token_required
def update_fee(fee_id: int):
    from education_system.systems.secondary.domain.finance.fees import fees as data
    if data.get_item(fee_id) is None:
        return jsonify({"error": f"No fee with id {fee_id}"}), 404
    try:
        row = data.update_item(fee_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@finance_bp.route("/fees/<int:fee_id>", methods=["DELETE"])
@_token_required
def delete_fee(fee_id: int):
    from education_system.systems.secondary.domain.finance.fees import fees as data
    if not data.delete_item(fee_id):
        return jsonify({"error": f"No fee with id {fee_id}"}), 404
    return jsonify({"deleted": fee_id})


# ── Trips ──────────────────────────────────────────────────────────

@finance_bp.route("/trips", methods=["GET"])
@_token_required
def list_trips():
    from education_system.systems.secondary.domain.finance.trips import trips as data
    try:
        rows = data.list_trips(
            year_group=request.args.get("year_group"),
            status=request.args.get("status"),
            open_only=request.args.get("open_only", "").lower() in ("1", "true", "yes"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@finance_bp.route("/trips/<int:trip_id>", methods=["GET"])
@_token_required
def get_trip(trip_id: int):
    from education_system.systems.secondary.domain.finance.trips import trips as data
    row = data.get_trip(trip_id)
    if row is None:
        return jsonify({"error": f"No trip with id {trip_id}"}), 404
    return jsonify(_dump(row))


@finance_bp.route("/trips", methods=["POST"])
@_token_required
def create_trip():
    from education_system.systems.secondary.domain.finance.trips import trips as data
    try:
        row = data.create_trip(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@finance_bp.route("/trips/<int:trip_id>", methods=["PUT"])
@_token_required
def update_trip(trip_id: int):
    from education_system.systems.secondary.domain.finance.trips import trips as data
    if data.get_trip(trip_id) is None:
        return jsonify({"error": f"No trip with id {trip_id}"}), 404
    try:
        row = data.update_trip(trip_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@finance_bp.route("/trips/<int:trip_id>", methods=["DELETE"])
@_token_required
def delete_trip(trip_id: int):
    from education_system.systems.secondary.domain.finance.trips import trips as data
    if not data.delete_trip(trip_id):
        return jsonify({"error": f"No trip with id {trip_id}"}), 404
    return jsonify({"deleted": trip_id})


# ── Expense claims ─────────────────────────────────────────────────

@finance_bp.route("/expense-claims", methods=["GET"])
@_token_required
def list_expense_claims():
    from education_system.systems.secondary.domain.finance.expense_claims import expense_claims as data
    try:
        rows = data.list_claims(
            claimant_type=request.args.get("claimant_type"),
            claimant_id=request.args.get("claimant_id"),
            status=request.args.get("status"),
            category=request.args.get("category"),
            payment_method=request.args.get("payment_method"),
            open_only=request.args.get("open_only", "").lower() in ("1", "true", "yes"),
            paid_only=request.args.get("paid_only", "").lower() in ("1", "true", "yes"),
            title_like=request.args.get("title_like"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@finance_bp.route("/expense-claims/<int:claim_id>", methods=["GET"])
@_token_required
def get_expense_claim(claim_id: int):
    from education_system.systems.secondary.domain.finance.expense_claims import expense_claims as data
    row = data.get_claim(claim_id)
    if row is None:
        return jsonify({"error": f"No claim with id {claim_id}"}), 404
    return jsonify(_dump(row))


@finance_bp.route("/expense-claims", methods=["POST"])
@_token_required
def create_expense_claim():
    from education_system.systems.secondary.domain.finance.expense_claims import expense_claims as data
    try:
        row = data.create_claim(_body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@finance_bp.route("/expense-claims/<int:claim_id>", methods=["PUT"])
@_token_required
def update_expense_claim(claim_id: int):
    from education_system.systems.secondary.domain.finance.expense_claims import expense_claims as data
    if data.get_claim(claim_id) is None:
        return jsonify({"error": f"No claim with id {claim_id}"}), 404
    try:
        row = data.update_claim(claim_id, _body())
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@finance_bp.route("/expense-claims/<int:claim_id>", methods=["DELETE"])
@_token_required
def delete_expense_claim(claim_id: int):
    from education_system.systems.secondary.domain.finance.expense_claims import expense_claims as data
    if not data.delete_claim(claim_id):
        return jsonify({"error": f"No claim with id {claim_id}"}), 404
    return jsonify({"deleted": claim_id})
