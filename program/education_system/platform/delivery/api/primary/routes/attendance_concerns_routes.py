"""REST API for Primary Attendance Concerns."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

attendance_concerns_bp = Blueprint(
    "pri_attendance_concerns", __name__,
    url_prefix="/api/attendance-concerns")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


def _data():
    from education_system.systems.primary.domain.pastoral.attendance_concerns import (
        attendance_concerns as data,
    )
    return data


@attendance_concerns_bp.route("", methods=["GET"])
@attendance_concerns_bp.route("/", methods=["GET"])
@_token_required
def list_concerns():
    data = _data()
    try:
        rows = data.list_concerns(
            pupil_id=request.args.get("pupil_id"),
            academic_year=request.args.get("academic_year"),
            status=request.args.get("status"),
            concern_type=request.args.get("concern_type"),
            level=request.args.get("level"),
            key_worker=request.args.get("key_worker"),
            open_only=request.args.get("open_only", "").lower()
            in ("1", "true", "yes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@attendance_concerns_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(data.cohort_summary(
        academic_year=request.args.get("academic_year")))


@attendance_concerns_bp.route("/<int:concern_id>", methods=["GET"])
@_token_required
def get_concern(concern_id: int):
    data = _data()
    rec = data.get(concern_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@attendance_concerns_bp.route("", methods=["POST"])
@attendance_concerns_bp.route("/", methods=["POST"])
@_token_required
def create_concern():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@attendance_concerns_bp.route("/<int:concern_id>", methods=["PUT"])
@_token_required
def update_concern(concern_id: int):
    data = _data()
    if data.get(concern_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(concern_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@attendance_concerns_bp.route("/<int:concern_id>", methods=["DELETE"])
@_token_required
def delete_concern(concern_id: int):
    data = _data()
    if not data.delete(concern_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "concern_id": concern_id})
