"""REST API for Primary Timetable."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

timetable_bp = Blueprint("pri_timetable", __name__, url_prefix="/api/timetable")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


@timetable_bp.route("", methods=["GET"])
@timetable_bp.route("/", methods=["GET"])
@_token_required
def list_slots():
    from education_system.primarysch_system.modules.domain.timetable import (
        timetable as data,
    )
    try:
        rows = data.list_slots(
            year_group=request.args.get("year_group"),
            form_group=request.args.get("form_group"),
            day_of_week=request.args.get("day_of_week"),
            teacher=request.args.get("teacher"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@timetable_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.timetable import (
        timetable as data,
    )
    return jsonify(data.counts())


@timetable_bp.route("/<int:slot_id>", methods=["GET"])
@_token_required
def get_slot(slot_id: int):
    from education_system.primarysch_system.modules.domain.timetable import (
        timetable as data,
    )
    rec = data.get_slot(slot_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@timetable_bp.route("", methods=["POST"])
@timetable_bp.route("/", methods=["POST"])
@_token_required
def create_slot():
    from education_system.primarysch_system.modules.domain.timetable import (
        timetable as data,
    )
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_slot(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@timetable_bp.route("/<int:slot_id>", methods=["PUT"])
@_token_required
def update_slot(slot_id: int):
    from education_system.primarysch_system.modules.domain.timetable import (
        timetable as data,
    )
    payload = request.get_json(silent=True) or {}
    if data.get_slot(slot_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        rec = data.update_slot(slot_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@timetable_bp.route("/<int:slot_id>", methods=["DELETE"])
@_token_required
def delete_slot(slot_id: int):
    from education_system.primarysch_system.modules.domain.timetable import (
        timetable as data,
    )
    if not data.delete_slot(slot_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": slot_id})
