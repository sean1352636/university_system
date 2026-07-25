"""REST API for Nursery Cohort Tracking.

Exposes CRUD over cohort-level (group) EYFS attainment snapshots.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

cohort_tracking_bp = Blueprint("nsy_cohort_tracking", __name__, url_prefix="/api/cohort-tracking")


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


@cohort_tracking_bp.route("", methods=["GET"])
@cohort_tracking_bp.route("/", methods=["GET"])
@_token_required
def list_cohorts():
    from education_system.systems.nursery.domain.assessment.cohort_tracking import (
        cohort_tracking as data,
    )
    rows = data.list_cohorts()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@cohort_tracking_bp.route("/<cohort_id>", methods=["GET"])
@_token_required
def get_cohort(cohort_id):
    from education_system.systems.nursery.domain.assessment.cohort_tracking import (
        cohort_tracking as data,
    )
    row = data.get_cohort(cohort_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@cohort_tracking_bp.route("", methods=["POST"])
@cohort_tracking_bp.route("/", methods=["POST"])
@_token_required
def create_cohort():
    from education_system.systems.nursery.domain.assessment.cohort_tracking import (
        cohort_tracking as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_cohort(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@cohort_tracking_bp.route("/<cohort_id>", methods=["PUT"])
@_token_required
def update_cohort(cohort_id):
    from education_system.systems.nursery.domain.assessment.cohort_tracking import (
        cohort_tracking as data,
    )
    if data.get_cohort(cohort_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_cohort(cohort_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row))


@cohort_tracking_bp.route("/<cohort_id>", methods=["DELETE"])
@_token_required
def delete_cohort(cohort_id):
    from education_system.systems.nursery.domain.assessment.cohort_tracking import (
        cohort_tracking as data,
    )
    if not data.delete_cohort(cohort_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "cohort_id": cohort_id})
