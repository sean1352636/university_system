"""REST API for Primary Reading Levels."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

reading_levels_bp = Blueprint("pri_reading_levels", __name__, url_prefix="/api/reading-levels")


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


def _data():
    from education_system.primarysch_system.modules.domain.reading_levels import (
        reading_levels as data,
    )
    return data


@reading_levels_bp.route("", methods=["GET"])
@reading_levels_bp.route("/", methods=["GET"])
@_token_required
def list_reading_levels():
    data = _data()
    try:
        rows = data.list_records(
            year_group=request.args.get("year_group"),
            band=request.args.get("band"),
            status=request.args.get("status"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [
        {"pupil": _dump(p), "reading_level": _dump(rec)}
        for p, rec in rows
    ]
    return jsonify({"items": items, "count": len(items)})


@reading_levels_bp.route("/summary", methods=["GET"])
@_token_required
def reading_levels_summary():
    data = _data()
    return jsonify(data.band_summary())


@reading_levels_bp.route("/<pupil_id>", methods=["GET"])
@_token_required
def get_reading_level(pupil_id):
    data = _data()
    try:
        rec = data.get_record(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@reading_levels_bp.route("/<pupil_id>/history", methods=["GET"])
@_token_required
def list_reading_level_history(pupil_id):
    data = _data()
    try:
        rows = data.list_history(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"items": _dump(rows), "count": len(rows)})


@reading_levels_bp.route("/<pupil_id>", methods=["POST"])
@_token_required
def record_reading_assessment(pupil_id):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.record_assessment(pupil_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@reading_levels_bp.route("/<pupil_id>", methods=["DELETE"])
@_token_required
def clear_reading_level(pupil_id):
    data = _data()
    if not data.clear_pupil(pupil_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"status": "deleted"})


@reading_levels_bp.route("/assessments/<int:assessment_id>", methods=["DELETE"])
@_token_required
def delete_reading_assessment(assessment_id):
    data = _data()
    if not data.delete_assessment(assessment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"status": "deleted"})
