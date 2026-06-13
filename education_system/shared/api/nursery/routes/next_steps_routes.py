"""REST API for Nursery Next Steps Planning.

Exposes CRUD over planned next steps for a child's EYFS learning, plus
read-only pupil/staff choice lookups used when authoring a step.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

next_steps_bp = Blueprint("nsy_next_steps", __name__, url_prefix="/api/next-steps")


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


@next_steps_bp.route("", methods=["GET"])
@next_steps_bp.route("/", methods=["GET"])
@_token_required
def list_next_steps():
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_steps(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@next_steps_bp.route("/pupil-choices", methods=["GET"])
@_token_required
def pupil_choices():
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    rows = data.list_pupil_choices()
    items = [{"pupil_id": pid, "label": label} for pid, label in rows]
    return jsonify({"items": items, "count": len(items)})


@next_steps_bp.route("/staff-choices", methods=["GET"])
@_token_required
def staff_choices():
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    rows = data.list_staff_choices()
    items = [{"staff_id": sid, "label": label} for sid, label in rows]
    return jsonify({"items": items, "count": len(items)})


@next_steps_bp.route("/<step_id>", methods=["GET"])
@_token_required
def get_next_step(step_id):
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    step = data.get_step(step_id)
    if step is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(step))


@next_steps_bp.route("", methods=["POST"])
@next_steps_bp.route("/", methods=["POST"])
@_token_required
def create_next_step():
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    try:
        step = data.create_step(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(step)), 201


@next_steps_bp.route("/<step_id>", methods=["PUT"])
@_token_required
def update_next_step(step_id):
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    if data.get_step(step_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        step = data.update_step(step_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(step))


@next_steps_bp.route("/<step_id>", methods=["DELETE"])
@_token_required
def delete_next_step(step_id):
    from education_system.nursery_system.modules.domain.next_steps import next_steps as data
    if not data.delete_step(step_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "step_id": step_id})
