"""REST API for Primary Dinner Money."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

dinner_money_bp = Blueprint("pri_dinner_money", __name__, url_prefix="/api/dinner-money")


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


def _dump_listing(rows):
    """list_entries returns (LedgerEntry, Pupil | None) tuples."""
    out = []
    for entry, pupil in rows:
        item = _dump(entry)
        item["pupil"] = _dump(pupil)
        out.append(item)
    return out


@dinner_money_bp.route("", methods=["GET"])
@dinner_money_bp.route("/", methods=["GET"])
@_token_required
def list_dinner_money():
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    args = request.args
    limit = args.get("limit", type=int)
    try:
        rows = data.list_entries(
            pupil_id=args.get("pupil_id"),
            kind=args.get("kind"),
            meal_type=args.get("meal_type"),
            from_date=args.get("from_date"),
            to_date=args.get("to_date"),
            limit=limit,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = _dump_listing(rows)
    return jsonify({"items": items, "count": len(items)})


@dinner_money_bp.route("/<int:entry_id>", methods=["GET"])
@_token_required
def get_dinner_money(entry_id: int):
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    entry = data.get(entry_id)
    if entry is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(entry))


@dinner_money_bp.route("", methods=["POST"])
@dinner_money_bp.route("/", methods=["POST"])
@_token_required
def create_dinner_money():
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        entry = data.record(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(entry)), 201


@dinner_money_bp.route("/<int:entry_id>", methods=["PUT"])
@_token_required
def update_dinner_money(entry_id: int):
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    if data.get(entry_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        entry = data.update(entry_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(entry))


@dinner_money_bp.route("/<int:entry_id>", methods=["DELETE"])
@_token_required
def delete_dinner_money(entry_id: int):
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    if not data.delete(entry_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@dinner_money_bp.route("/summary", methods=["GET"])
@_token_required
def summary_dinner_money():
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    args = request.args
    try:
        result = data.summary(
            from_date=args.get("from_date"),
            to_date=args.get("to_date"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@dinner_money_bp.route("/balances", methods=["GET"])
@_token_required
def balances_dinner_money():
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    args = request.args
    try:
        rows = data.balances(
            year_group=args.get("year_group"),
            owing_only=args.get("owing_only", "").lower() in ("1", "true", "yes"),
            limit=args.get("limit", type=int),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [
        {"pupil": _dump(pupil), "balance_pence": bal}
        for pupil, bal in rows
    ]
    return jsonify({"items": items, "count": len(items)})


@dinner_money_bp.route("/pupil/<pupil_id>/balance", methods=["GET"])
@_token_required
def pupil_balance_dinner_money(pupil_id: str):
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    try:
        bal = data.pupil_balance(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"pupil_id": pupil_id, "balance_pence": bal})


@dinner_money_bp.route("/pupil/<pupil_id>/statement", methods=["GET"])
@_token_required
def pupil_statement_dinner_money(pupil_id: str):
    from education_system.systems.primary.domain.finance.dinner_money import (
        dinner_money as data,
    )
    try:
        stmt = data.pupil_statement(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    stmt["entries"] = _dump(stmt.get("entries", []))
    return jsonify(stmt)
