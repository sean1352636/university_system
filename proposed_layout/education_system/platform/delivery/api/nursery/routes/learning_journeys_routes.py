"""REST API for Nursery Learning Journeys.

Exposes CRUD over EYFS learning-journey entries ("wow moments") per child.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

learning_journeys_bp = Blueprint("nsy_learning_journeys", __name__, url_prefix="/api/learning-journeys")


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


@learning_journeys_bp.route("", methods=["GET"])
@learning_journeys_bp.route("/", methods=["GET"])
@_token_required
def list_journeys():
    from education_system.systems.nursery.domain.academics.learning_journeys import (
        learning_journeys as data,
    )

    pupil_id = request.args.get("pupil_id")
    rows = data.list_entries(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@learning_journeys_bp.route("/<entry_id>", methods=["GET"])
@_token_required
def get_journey(entry_id):
    from education_system.systems.nursery.domain.academics.learning_journeys import (
        learning_journeys as data,
    )

    entry = data.get_entry(entry_id)
    if entry is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(entry))


@learning_journeys_bp.route("", methods=["POST"])
@learning_journeys_bp.route("/", methods=["POST"])
@_token_required
def create_journey():
    from education_system.systems.nursery.domain.academics.learning_journeys import (
        learning_journeys as data,
    )

    payload = request.get_json(silent=True) or {}
    try:
        entry = data.create_entry(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(entry)), 201


@learning_journeys_bp.route("/<entry_id>", methods=["PUT"])
@_token_required
def update_journey(entry_id):
    from education_system.systems.nursery.domain.academics.learning_journeys import (
        learning_journeys as data,
    )

    payload = request.get_json(silent=True) or {}
    if data.get_entry(entry_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        entry = data.update_entry(entry_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(entry))


@learning_journeys_bp.route("/<entry_id>", methods=["DELETE"])
@_token_required
def delete_journey(entry_id):
    from education_system.systems.nursery.domain.academics.learning_journeys import (
        learning_journeys as data,
    )

    if not data.delete_entry(entry_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "entry_id": entry_id})
