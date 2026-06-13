"""REST API for Nursery Daily Diary.

Exposes CRUD over the practitioner daily-diary entries (one row per child per day).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

daily_diary_bp = Blueprint("nsy_daily_diary", __name__, url_prefix="/api/daily-diary")


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


@daily_diary_bp.route("", methods=["GET"])
@daily_diary_bp.route("/", methods=["GET"])
@_token_required
def list_entries():
    from education_system.nursery_system.modules.domain.daily_diary import daily_diary as data
    entry_date = request.args.get("entry_date")
    pupil_id = request.args.get("pupil_id")
    rows = data.list_records(entry_date=entry_date, pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@daily_diary_bp.route("/<entry_id>", methods=["GET"])
@_token_required
def get_entry(entry_id):
    from education_system.nursery_system.modules.domain.daily_diary import daily_diary as data
    rec = data.get_record(entry_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@daily_diary_bp.route("", methods=["POST"])
@daily_diary_bp.route("/", methods=["POST"])
@_token_required
def create_entry():
    from education_system.nursery_system.modules.domain.daily_diary import daily_diary as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_record(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@daily_diary_bp.route("/<entry_id>", methods=["PUT"])
@_token_required
def update_entry(entry_id):
    from education_system.nursery_system.modules.domain.daily_diary import daily_diary as data
    if data.get_record(entry_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_record(entry_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@daily_diary_bp.route("/<entry_id>", methods=["DELETE"])
@_token_required
def delete_entry(entry_id):
    from education_system.nursery_system.modules.domain.daily_diary import daily_diary as data
    if not data.delete_record(entry_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "entry_id": entry_id})
