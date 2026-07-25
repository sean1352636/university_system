"""REST API for Nursery EHC Plans.

Exposes CRUD over the Education, Health and Care plans register
(``ehc_plans``) plus a summary endpoint, scoped by status.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

ehc_plans_bp = Blueprint("nsy_ehc_plans", __name__, url_prefix="/api/ehc-plans")


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


@ehc_plans_bp.route("", methods=["GET"])
@ehc_plans_bp.route("/", methods=["GET"])
@_token_required
def list_ehc_plans():
    from education_system.systems.nursery.domain.pastoral.send.ehc_plans import ehc_plans as data

    rows = data.list_records(status=request.args.get("status"))
    return jsonify({"items": _dump(rows), "count": len(rows)})


@ehc_plans_bp.route("/summary", methods=["GET"])
@_token_required
def ehc_plans_summary():
    from education_system.systems.nursery.domain.pastoral.send.ehc_plans import ehc_plans as data

    return jsonify(data.summary())


@ehc_plans_bp.route("/<record_id>", methods=["GET"])
@_token_required
def get_ehc_plan(record_id):
    from education_system.systems.nursery.domain.pastoral.send.ehc_plans import ehc_plans as data

    rec = data.get_record(record_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@ehc_plans_bp.route("", methods=["POST"])
@ehc_plans_bp.route("/", methods=["POST"])
@_token_required
def create_ehc_plan():
    from education_system.systems.nursery.domain.pastoral.send.ehc_plans import ehc_plans as data

    try:
        rec = data.create_record(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@ehc_plans_bp.route("/<record_id>", methods=["PUT"])
@_token_required
def update_ehc_plan(record_id):
    from education_system.systems.nursery.domain.pastoral.send.ehc_plans import ehc_plans as data

    try:
        rec = data.update_record(record_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        msg = str(e)
        if "No record with id" in msg:
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(_dump(rec))


@ehc_plans_bp.route("/<record_id>", methods=["DELETE"])
@_token_required
def delete_ehc_plan(record_id):
    from education_system.systems.nursery.domain.pastoral.send.ehc_plans import ehc_plans as data

    if not data.delete_record(record_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": record_id})
