"""REST API for Nursery Activity & Curriculum Planning.

Exposes CRUD over room/setting-level EYFS curriculum plans.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

curriculum_planning_bp = Blueprint(
    "nsy_curriculum_planning", __name__, url_prefix="/api/curriculum-planning"
)


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


@curriculum_planning_bp.route("", methods=["GET"])
@curriculum_planning_bp.route("/", methods=["GET"])
@_token_required
def list_plans():
    from education_system.systems.nursery.domain.academics.curriculum_planning import (
        curriculum_planning as data,
    )
    rows = data.list_plans()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@curriculum_planning_bp.route("/staff-choices", methods=["GET"])
@_token_required
def staff_choices():
    from education_system.systems.nursery.domain.academics.curriculum_planning import (
        curriculum_planning as data,
    )
    rows = data.list_staff_choices()
    items = [{"staff_id": sid, "label": label} for sid, label in rows]
    return jsonify({"items": items, "count": len(items)})


@curriculum_planning_bp.route("/<plan_id>", methods=["GET"])
@_token_required
def get_plan(plan_id):
    from education_system.systems.nursery.domain.academics.curriculum_planning import (
        curriculum_planning as data,
    )
    plan = data.get_plan(plan_id)
    if plan is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(plan))


@curriculum_planning_bp.route("", methods=["POST"])
@curriculum_planning_bp.route("/", methods=["POST"])
@_token_required
def create_plan():
    from education_system.systems.nursery.domain.academics.curriculum_planning import (
        curriculum_planning as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        plan = data.create_plan(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(plan)), 201


@curriculum_planning_bp.route("/<plan_id>", methods=["PUT"])
@_token_required
def update_plan(plan_id):
    from education_system.systems.nursery.domain.academics.curriculum_planning import (
        curriculum_planning as data,
    )
    if data.get_plan(plan_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        plan = data.update_plan(plan_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(plan))


@curriculum_planning_bp.route("/<plan_id>", methods=["DELETE"])
@_token_required
def delete_plan(plan_id):
    from education_system.systems.nursery.domain.academics.curriculum_planning import (
        curriculum_planning as data,
    )
    if not data.delete_plan(plan_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "plan_id": plan_id})
