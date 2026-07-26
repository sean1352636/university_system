"""REST API for Nursery Observations.

Exposes CRUD over EYFS day-to-day child observations.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

observations_bp = Blueprint("nsy_observations", __name__, url_prefix="/api/observations")


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


@observations_bp.route("", methods=["GET"])
@observations_bp.route("/", methods=["GET"])
@_token_required
def list_observations():
    from education_system.systems.nursery.domain.assessment.observations import (
        observations as data,
    )
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_observations(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@observations_bp.route("/<observation_id>", methods=["GET"])
@_token_required
def get_observation(observation_id):
    from education_system.systems.nursery.domain.assessment.observations import (
        observations as data,
    )
    ob = data.get_observation(observation_id)
    if ob is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(ob))


@observations_bp.route("", methods=["POST"])
@observations_bp.route("/", methods=["POST"])
@_token_required
def create_observation():
    from education_system.systems.nursery.domain.assessment.observations import (
        observations as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        ob = data.create_observation(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ob)), 201


@observations_bp.route("/<observation_id>", methods=["PUT"])
@_token_required
def update_observation(observation_id):
    from education_system.systems.nursery.domain.assessment.observations import (
        observations as data,
    )
    if data.get_observation(observation_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        ob = data.update_observation(observation_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(ob))


@observations_bp.route("/<observation_id>", methods=["DELETE"])
@_token_required
def delete_observation(observation_id):
    from education_system.systems.nursery.domain.assessment.observations import (
        observations as data,
    )
    if not data.delete_observation(observation_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": observation_id})
