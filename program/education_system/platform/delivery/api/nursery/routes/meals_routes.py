"""REST API for Nursery Meals & Menus.

Exposes CRUD over the per-child meal log (one row per child per meal).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

meals_bp = Blueprint("nsy_meals", __name__, url_prefix="/api/meals")


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


@meals_bp.route("", methods=["GET"])
@meals_bp.route("/", methods=["GET"])
@_token_required
def list_meals():
    from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
    rows = data.list_records(
        meal_date=request.args.get("meal_date"),
        pupil_id=request.args.get("pupil_id"),
        meal_type=request.args.get("meal_type"),
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@meals_bp.route("/<meal_id>", methods=["GET"])
@_token_required
def get_meal(meal_id):
    from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
    rec = data.get_record(meal_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@meals_bp.route("", methods=["POST"])
@meals_bp.route("/", methods=["POST"])
@_token_required
def create_meal():
    from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@meals_bp.route("/<meal_id>", methods=["PUT"])
@_token_required
def update_meal(meal_id):
    from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
    if data.get_record(meal_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(meal_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@meals_bp.route("/<meal_id>", methods=["DELETE"])
@_token_required
def delete_meal(meal_id):
    from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
    if not data.delete_record(meal_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": meal_id})
