"""REST API for Primary Cover (lesson reassignments)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

cover_bp = Blueprint("pri_cover", __name__, url_prefix="/api/cover")


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
    from education_system.primarysch_system.modules.domain.cover import cover as data
    return data


@cover_bp.route("", methods=["GET"])
@cover_bp.route("/", methods=["GET"])
@_token_required
def list_cover():
    data = _data()
    try:
        rows = data.list_arrangements(
            date=request.args.get("date"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
            teacher=request.args.get("teacher"),
            cover_teacher=request.args.get("cover_teacher"),
            status=request.args.get("status"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@cover_bp.route("/summary", methods=["GET"])
@_token_required
def cover_summary():
    data = _data()
    try:
        counts = data.status_counts(
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(counts)


@cover_bp.route("/daily", methods=["GET"])
@_token_required
def cover_daily():
    data = _data()
    date_iso = request.args.get("date")
    if not date_iso:
        return jsonify({"error": "date query parameter is required"}), 400
    try:
        result = data.daily_load(date_iso)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(result))


@cover_bp.route("/<int:cover_id>", methods=["GET"])
@_token_required
def get_cover(cover_id: int):
    data = _data()
    rec = data.get(cover_id)
    if rec is None:
        return jsonify({"error": f"No cover arrangement #{cover_id}"}), 404
    return jsonify(_dump(rec))


@cover_bp.route("", methods=["POST"])
@cover_bp.route("/", methods=["POST"])
@_token_required
def create_cover():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@cover_bp.route("/<int:cover_id>", methods=["PUT"])
@_token_required
def update_cover(cover_id: int):
    data = _data()
    if data.get(cover_id) is None:
        return jsonify({"error": f"No cover arrangement #{cover_id}"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(cover_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@cover_bp.route("/<int:cover_id>", methods=["DELETE"])
@_token_required
def delete_cover(cover_id: int):
    data = _data()
    if not data.delete(cover_id):
        return jsonify({"error": f"No cover arrangement #{cover_id}"}), 404
    return jsonify({"deleted": True, "cover_id": cover_id})
