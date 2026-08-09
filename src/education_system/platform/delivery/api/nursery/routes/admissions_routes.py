"""REST API for Nursery Admissions & Waiting List.

Exposes CRUD over admission applications plus search, status counts, and
pipeline status transitions (offer/accept/decline/withdraw/enrol).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

admissions_bp = Blueprint("nsy_admissions", __name__, url_prefix="/api/admissions")


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


@admissions_bp.route("", methods=["GET"])
@admissions_bp.route("/", methods=["GET"])
@_token_required
def list_applications():
    from education_system.systems.nursery.domain.admissions import admissions as data

    statuses_arg = request.args.getlist("status")
    if statuses_arg:
        rows = data.list_applications(statuses=tuple(statuses_arg))
    elif request.args.get("waiting") in ("1", "true", "yes"):
        rows = data.list_waiting_list()
    else:
        rows = data.list_applications()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@admissions_bp.route("/search", methods=["GET"])
@_token_required
def search_applications():
    from education_system.systems.nursery.domain.admissions import admissions as data

    rows = data.search_applications(request.args.get("q", ""))
    return jsonify({"items": _dump(rows), "count": len(rows)})


@admissions_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.admissions import admissions as data

    return jsonify({"counts_by_status": data.counts_by_status()})


@admissions_bp.route("/<application_id>", methods=["GET"])
@_token_required
def get_application(application_id):
    from education_system.systems.nursery.domain.admissions import admissions as data

    app = data.get_application(application_id)
    if app is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(app))


@admissions_bp.route("", methods=["POST"])
@admissions_bp.route("/", methods=["POST"])
@_token_required
def create_application():
    from education_system.systems.nursery.domain.admissions import admissions as data

    try:
        app = data.create_application(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app)), 201


@admissions_bp.route("/<application_id>", methods=["PUT"])
@_token_required
def update_application(application_id):
    from education_system.systems.nursery.domain.admissions import admissions as data

    if data.get_application(application_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        app = data.update_application(application_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app))


@admissions_bp.route("/<application_id>", methods=["DELETE"])
@_token_required
def delete_application(application_id):
    from education_system.systems.nursery.domain.admissions import admissions as data

    if not data.delete_application(application_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "application_id": application_id})


@admissions_bp.route("/<application_id>/status", methods=["POST"])
@_token_required
def set_status(application_id):
    from education_system.systems.nursery.domain.admissions import admissions as data

    body = request.get_json(silent=True) or {}
    if data.get_application(application_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        app = data.set_status(
            application_id,
            body.get("status", ""),
            offer_date=body.get("offer_date"),
            pupil_id=body.get("pupil_id"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(app))
