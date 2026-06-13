"""REST API for Primary Governance (governors and governance meetings)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

governance_bp = Blueprint("pri_governance", __name__, url_prefix="/api/governance")


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
        return {k: _dump(v) for k, v in dataclasses.asdict(obj).items()}
    return obj


def _data():
    from education_system.primarysch_system.modules.domain.governance import (
        governance as data,
    )
    return data


# ── Governors ──────────────────────────────────────────────────────

@governance_bp.route("/governors", methods=["GET"])
@governance_bp.route("/governors/", methods=["GET"])
@_token_required
def list_governors():
    data = _data()
    try:
        rows = data.list_governors(
            status=request.args.get("status"),
            role=request.args.get("role"),
            query=request.args.get("query"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@governance_bp.route("/governors/<int:governor_id>", methods=["GET"])
@_token_required
def get_governor(governor_id: int):
    data = _data()
    row = data.get_governor(governor_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@governance_bp.route("/governors", methods=["POST"])
@governance_bp.route("/governors/", methods=["POST"])
@_token_required
def create_governor():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_governor(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@governance_bp.route("/governors/<int:governor_id>", methods=["PUT"])
@_token_required
def update_governor(governor_id: int):
    data = _data()
    if data.get_governor(governor_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_governor(governor_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@governance_bp.route("/governors/<int:governor_id>", methods=["DELETE"])
@_token_required
def delete_governor(governor_id: int):
    data = _data()
    if not data.delete_governor(governor_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── Meetings ───────────────────────────────────────────────────────

@governance_bp.route("/meetings", methods=["GET"])
@governance_bp.route("/meetings/", methods=["GET"])
@_token_required
def list_meetings():
    data = _data()
    try:
        rows = data.list_meetings(
            status=request.args.get("status"),
            kind=request.args.get("kind"),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
            query=request.args.get("query"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@governance_bp.route("/meetings/<int:meeting_id>", methods=["GET"])
@_token_required
def get_meeting(meeting_id: int):
    data = _data()
    row = data.get_meeting(meeting_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@governance_bp.route("/meetings", methods=["POST"])
@governance_bp.route("/meetings/", methods=["POST"])
@_token_required
def create_meeting():
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.create_meeting(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row)), 201


@governance_bp.route("/meetings/<int:meeting_id>", methods=["PUT"])
@_token_required
def update_meeting(meeting_id: int):
    data = _data()
    if data.get_meeting(meeting_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        row = data.update_meeting(meeting_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


@governance_bp.route("/meetings/<int:meeting_id>", methods=["DELETE"])
@_token_required
def delete_meeting(meeting_id: int):
    data = _data()
    if not data.delete_meeting(meeting_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@governance_bp.route("/meetings/<int:meeting_id>/mark_held", methods=["POST"])
@_token_required
def mark_held(meeting_id: int):
    data = _data()
    payload = request.get_json(silent=True) or {}
    try:
        row = data.mark_held(
            meeting_id,
            attendees=payload.get("attendees"),
            decisions=payload.get("decisions"),
            minutes_ref=payload.get("minutes_ref"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(row))


# ── Summary ────────────────────────────────────────────────────────

@governance_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    data = _data()
    return jsonify(_dump(data.summary()))
