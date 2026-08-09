"""REST API for Nursery Staff Rota.

Exposes CRUD over staff shift scheduling (rota_shifts), plus a status setter.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

rota_bp = Blueprint("nsy_rota", __name__, url_prefix="/api/rota")


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


@rota_bp.route("", methods=["GET"])
@_token_required
def list_shifts():
    from education_system.systems.nursery.domain.staff.rota import rota as data
    shift_date = request.args.get("shift_date")
    staff_id = request.args.get("staff_id")
    include_cancelled = request.args.get("include_cancelled", "true").lower() != "false"
    rows = data.list_shifts(
        shift_date=shift_date,
        staff_id=staff_id,
        include_cancelled=include_cancelled,
    )
    return jsonify({"items": _dump(rows), "count": len(rows)})


@rota_bp.route("/<shift_id>", methods=["GET"])
@_token_required
def get_shift(shift_id):
    from education_system.systems.nursery.domain.staff.rota import rota as data
    shift = data.get_shift(shift_id)
    if shift is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(shift))


@rota_bp.route("", methods=["POST"])
@_token_required
def create_shift():
    from education_system.systems.nursery.domain.staff.rota import rota as data
    try:
        shift = data.create_shift(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(shift)), 201


@rota_bp.route("/<shift_id>", methods=["PUT"])
@_token_required
def update_shift(shift_id):
    from education_system.systems.nursery.domain.staff.rota import rota as data
    if data.get_shift(shift_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        shift = data.update_shift(shift_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(shift))


@rota_bp.route("/<shift_id>", methods=["DELETE"])
@_token_required
def delete_shift(shift_id):
    from education_system.systems.nursery.domain.staff.rota import rota as data
    if not data.delete_shift(shift_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "shift_id": shift_id})


@rota_bp.route("/<shift_id>/status", methods=["PUT"])
@_token_required
def set_status(shift_id):
    from education_system.systems.nursery.domain.staff.rota import rota as data
    payload = request.get_json(silent=True) or {}
    try:
        shift = data.set_status(shift_id, payload.get("status"))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(shift))


@rota_bp.route("/dates", methods=["GET"])
@_token_required
def list_dates():
    from education_system.systems.nursery.domain.staff.rota import rota as data
    rows = data.list_dates()
    return jsonify({"items": rows, "count": len(rows)})
