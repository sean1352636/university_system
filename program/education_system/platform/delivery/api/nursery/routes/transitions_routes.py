"""REST API for Nursery Transition to School.

Exposes CRUD over a child's transition to primary school (Reception),
plus a status setter and status counts summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

transitions_bp = Blueprint("nsy_transitions", __name__, url_prefix="/api/transitions")


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


@transitions_bp.route("", methods=["GET"])
@transitions_bp.route("/", methods=["GET"])
@_token_required
def list_transitions():
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    statuses = request.args.getlist("status") or None
    if statuses:
        statuses = tuple(statuses)
    rows = data.list_transitions(statuses=statuses)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@transitions_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    return jsonify(data.counts_by_status())


@transitions_bp.route("/<transition_id>", methods=["GET"])
@_token_required
def get_transition(transition_id):
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    row = data.get_transition(transition_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@transitions_bp.route("", methods=["POST"])
@transitions_bp.route("/", methods=["POST"])
@_token_required
def create_transition():
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    try:
        row = data.create_transition(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@transitions_bp.route("/<transition_id>", methods=["PUT"])
@_token_required
def update_transition(transition_id):
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    if data.get_transition(transition_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        row = data.update_transition(transition_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@transitions_bp.route("/<transition_id>/status", methods=["PUT"])
@_token_required
def set_status(transition_id):
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    payload = request.get_json(silent=True) or {}
    try:
        row = data.set_status(transition_id, payload.get("status", ""))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@transitions_bp.route("/<transition_id>", methods=["DELETE"])
@_token_required
def delete_transition(transition_id):
    from education_system.systems.nursery.domain.progression.transitions import transitions as data
    if not data.delete_transition(transition_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": transition_id})
