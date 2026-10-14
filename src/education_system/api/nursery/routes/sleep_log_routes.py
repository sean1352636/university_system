"""REST API for Nursery Sleep Log.

Exposes CRUD over nap (sleep) records plus a per-day summary endpoint.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

sleep_log_bp = Blueprint("nsy_sleep_log", __name__, url_prefix="/api/sleep-log")


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


@sleep_log_bp.route("", methods=["GET"])
@sleep_log_bp.route("/", methods=["GET"])
@_token_required
def list_sleep_records():
    from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
    sleep_date = request.args.get("sleep_date")
    pupil_id = request.args.get("pupil_id")
    rows = data.list_records(sleep_date=sleep_date, pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@sleep_log_bp.route("/<sleep_id>", methods=["GET"])
@_token_required
def get_sleep_record(sleep_id):
    from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
    rec = data.get_record(sleep_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@sleep_log_bp.route("", methods=["POST"])
@sleep_log_bp.route("/", methods=["POST"])
@_token_required
def create_sleep_record():
    from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@sleep_log_bp.route("/<sleep_id>", methods=["PUT"])
@_token_required
def update_sleep_record(sleep_id):
    from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
    if data.get_record(sleep_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(sleep_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@sleep_log_bp.route("/<sleep_id>", methods=["DELETE"])
@_token_required
def delete_sleep_record(sleep_id):
    from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
    if not data.delete_record(sleep_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "sleep_id": sleep_id})


@sleep_log_bp.route("/summary", methods=["GET"])
@_token_required
def sleep_summary():
    from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
    sleep_date = request.args.get("sleep_date")
    if not sleep_date:
        return jsonify({"error": "sleep_date query parameter is required"}), 400
    return jsonify(data.summary(sleep_date))
