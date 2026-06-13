"""REST API for Primary Clubs / Extracurricular Activities."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

clubs_bp = Blueprint("pri_clubs", __name__, url_prefix="/api/clubs")


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
    from education_system.primarysch_system.modules.domain.clubs import clubs as data
    return data


# --- Clubs ----------------------------------------------------------------

@clubs_bp.route("", methods=["GET"])
@clubs_bp.route("/", methods=["GET"])
@_token_required
def list_clubs():
    data = _data()
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    day = request.args.get("day_of_week") or None
    try:
        rows = data.list_all(active_only=active_only, day_of_week=day)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@clubs_bp.route("/summary", methods=["GET"])
@_token_required
def clubs_summary():
    data = _data()
    return jsonify(data.counts())


@clubs_bp.route("/<int:club_id>", methods=["GET"])
@_token_required
def get_club(club_id: int):
    data = _data()
    rec = data.get(club_id)
    if rec is None:
        return jsonify({"error": f"No club #{club_id}"}), 404
    return jsonify(_dump(rec))


@clubs_bp.route("", methods=["POST"])
@clubs_bp.route("/", methods=["POST"])
@_token_required
def create_club():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@clubs_bp.route("/<int:club_id>", methods=["PUT"])
@_token_required
def update_club(club_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    if data.get(club_id) is None:
        return jsonify({"error": f"No club #{club_id}"}), 404
    try:
        rec = data.update(club_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@clubs_bp.route("/<int:club_id>/toggle-active", methods=["POST"])
@_token_required
def toggle_club_active(club_id: int):
    data = _data()
    try:
        rec = data.toggle_active(club_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump(rec))


@clubs_bp.route("/<int:club_id>", methods=["DELETE"])
@_token_required
def delete_club(club_id: int):
    data = _data()
    if not data.delete(club_id):
        return jsonify({"error": f"No club #{club_id}"}), 404
    return jsonify({"deleted": True, "club_id": club_id})


# --- Memberships ----------------------------------------------------------

@clubs_bp.route("/<int:club_id>/members", methods=["GET"])
@_token_required
def list_club_members(club_id: int):
    data = _data()
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    try:
        rows = data.list_members(club_id, active_only=active_only)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    items = [{"pupil": _dump(p), "membership": _dump(m)} for p, m in rows]
    return jsonify({"items": items, "count": len(items)})


@clubs_bp.route("/<int:club_id>/members", methods=["POST"])
@_token_required
def add_club_member(club_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    pupil_id = payload.get("pupil_id")
    if not pupil_id:
        return jsonify({"error": "pupil_id is required"}), 400
    try:
        rec = data.add_member(
            club_id,
            str(pupil_id),
            joined_on=payload.get("joined_on"),
            notes=payload.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@clubs_bp.route("/memberships/<int:membership_id>/status", methods=["PUT"])
@_token_required
def update_membership_status(membership_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    if not new_status:
        return jsonify({"error": "status is required"}), 400
    try:
        rec = data.set_member_status(membership_id, str(new_status))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@clubs_bp.route("/memberships/<int:membership_id>", methods=["DELETE"])
@_token_required
def remove_club_member(membership_id: int):
    data = _data()
    if not data.remove_member(membership_id):
        return jsonify({"error": f"No membership #{membership_id}"}), 404
    return jsonify({"deleted": True, "membership_id": membership_id})


@clubs_bp.route("/pupils/<pupil_id>/clubs", methods=["GET"])
@_token_required
def list_clubs_for_pupil(pupil_id: str):
    data = _data()
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    try:
        rows = data.list_clubs_for_pupil(pupil_id, active_only=active_only)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    items = [{"club": _dump(c), "membership": _dump(m)} for c, m in rows]
    return jsonify({"items": items, "count": len(items)})
