"""REST API for Nursery Funded Hours (15/30 & 2-Year-Old).

Exposes CRUD over funded-hours entitlement records, plus a summary and a
status setter.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

funded_hours_bp = Blueprint("nsy_funded_hours", __name__, url_prefix="/api/funded-hours")


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


@funded_hours_bp.route("", methods=["GET"])
@funded_hours_bp.route("/", methods=["GET"])
@_token_required
def list_funded_hours():
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    include_ended = request.args.get("include_ended", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )
    rows = data.list_records(include_ended=include_ended)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@funded_hours_bp.route("/summary", methods=["GET"])
@_token_required
def funded_hours_summary():
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    return jsonify(data.summary())


@funded_hours_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_funded_hours(record_id):
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@funded_hours_bp.route("", methods=["POST"])
@funded_hours_bp.route("/", methods=["POST"])
@_token_required
def create_funded_hours():
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@funded_hours_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_funded_hours(record_id):
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    if data.get_record(record_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@funded_hours_bp.route("/<record_id>/status", methods=["PUT"])
@_token_required
def set_funded_hours_status(record_id):
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.set_status(record_id, payload.get("status", ""))
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@funded_hours_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_funded_hours(record_id):
    from education_system.systems.nursery.domain.finance.funded_hours import (
        funded_hours as data,
    )
    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})
