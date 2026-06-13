"""REST API for Primary House Points."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

house_points_bp = Blueprint("pri_house_points", __name__, url_prefix="/api/house-points")


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
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _data():
    from education_system.primarysch_system.modules.domain.house_points import (
        house_points as data,
    )
    return data


# --- Houses ---------------------------------------------------------------

@house_points_bp.route("", methods=["GET"])
@house_points_bp.route("/", methods=["GET"])
@_token_required
def list_houses():
    data = _data()
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    rows = data.list_houses(active_only=active_only)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@house_points_bp.route("/<int:house_id>", methods=["GET"])
@_token_required
def get_house(house_id: int):
    data = _data()
    rec = data.get_house(house_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@house_points_bp.route("", methods=["POST"])
@house_points_bp.route("/", methods=["POST"])
@_token_required
def create_house():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_house(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@house_points_bp.route("/<int:house_id>", methods=["PUT"])
@_token_required
def update_house(house_id: int):
    data = _data()
    if data.get_house(house_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_house(house_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@house_points_bp.route("/<int:house_id>", methods=["DELETE"])
@_token_required
def delete_house(house_id: int):
    data = _data()
    try:
        ok = data.delete_house(house_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@house_points_bp.route("/<int:house_id>/toggle-active", methods=["POST"])
@_token_required
def toggle_house_active(house_id: int):
    data = _data()
    try:
        rec = data.toggle_house_active(house_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(rec))


# --- Awards ---------------------------------------------------------------

@house_points_bp.route("/awards", methods=["GET"])
@_token_required
def list_awards():
    data = _data()
    args = request.args
    house_id = args.get("house_id", type=int)
    limit = args.get("limit", type=int)
    try:
        rows = data.list_awards(
            house_id=house_id,
            pupil_id=args.get("pupil_id") or None,
            awarded_by=args.get("awarded_by") or None,
            from_date=args.get("from_date") or None,
            to_date=args.get("to_date") or None,
            limit=limit,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [
        {"award": _dump(a), "house": _dump(h), "pupil": _dump(p)}
        for (a, h, p) in rows
    ]
    return jsonify({"items": items, "count": len(items)})


@house_points_bp.route("/awards/<int:award_id>", methods=["GET"])
@_token_required
def get_award(award_id: int):
    data = _data()
    rec = data.get_award(award_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@house_points_bp.route("/awards", methods=["POST"])
@_token_required
def create_award():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.award_points(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@house_points_bp.route("/awards/<int:award_id>", methods=["PUT"])
@_token_required
def update_award(award_id: int):
    data = _data()
    if data.get_award(award_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_award(award_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@house_points_bp.route("/awards/<int:award_id>", methods=["DELETE"])
@_token_required
def delete_award(award_id: int):
    data = _data()
    if not data.delete_award(award_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# --- Summaries (read-only) ------------------------------------------------

@house_points_bp.route("/summary/houses", methods=["GET"])
@_token_required
def house_totals_summary():
    data = _data()
    args = request.args
    try:
        rows = data.house_totals(
            from_date=args.get("from_date") or None,
            to_date=args.get("to_date") or None,
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [{"house": _dump(h), "total": total} for (h, total) in rows]
    return jsonify({"items": items, "count": len(items)})


@house_points_bp.route("/summary/pupils", methods=["GET"])
@_token_required
def pupil_totals_summary():
    data = _data()
    args = request.args
    rows = data.pupil_totals(
        house_id=args.get("house_id", type=int),
        limit=args.get("limit", type=int),
    )
    items = [
        {"pupil_id": pid, "total": total, "award_count": count}
        for (pid, total, count) in rows
    ]
    return jsonify({"items": items, "count": len(items)})


@house_points_bp.route("/summary/pupils/<pupil_id>", methods=["GET"])
@_token_required
def pupil_total_summary(pupil_id: str):
    data = _data()
    try:
        total = data.pupil_total(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"pupil_id": pupil_id, "total": total})
