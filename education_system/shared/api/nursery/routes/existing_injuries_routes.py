"""REST API for Nursery Existing Injuries Log.

Exposes CRUD over the existing-injuries register — injuries a child arrives
WITH (not sustained at the setting) — backed by the ``existing_injuries`` table.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

existing_injuries_bp = Blueprint(
    "nsy_existing_injuries", __name__, url_prefix="/api/existing-injuries")


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


@existing_injuries_bp.route("", methods=["GET"])
@existing_injuries_bp.route("/", methods=["GET"])
@_token_required
def list_existing_injuries():
    from education_system.nursery_system.modules.domain.existing_injuries import (
        existing_injuries as data,
    )

    observed_date = request.args.get("observed_date")
    pupil_id = request.args.get("pupil_id")
    rows = data.list_records(observed_date=observed_date, pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@existing_injuries_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_existing_injury(record_id):
    from education_system.nursery_system.modules.domain.existing_injuries import (
        existing_injuries as data,
    )

    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@existing_injuries_bp.route("", methods=["POST"])
@existing_injuries_bp.route("/", methods=["POST"])
@_token_required
def create_existing_injury():
    from education_system.nursery_system.modules.domain.existing_injuries import (
        existing_injuries as data,
    )

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@existing_injuries_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_existing_injury(record_id):
    from education_system.nursery_system.modules.domain.existing_injuries import (
        existing_injuries as data,
    )

    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(record_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@existing_injuries_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_existing_injury(record_id):
    from education_system.nursery_system.modules.domain.existing_injuries import (
        existing_injuries as data,
    )

    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "record_id": record_id})
