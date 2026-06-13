"""REST API for Nursery Settling-In.

Exposes CRUD over EYFS settling-in sessions, plus a per-child summary.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

settling_in_bp = Blueprint("nsy_settling_in", __name__, url_prefix="/api/settling-in")


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


@settling_in_bp.route("", methods=["GET"])
@settling_in_bp.route("/", methods=["GET"])
@_token_required
def list_settling_sessions():
    from education_system.nursery_system.modules.domain.settling_in import settling_in as data
    pupil_id = request.args.get("pupil_id") or None
    rows = data.list_sessions(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@settling_in_bp.route("/by-child", methods=["GET"])
@_token_required
def settling_by_child():
    from education_system.nursery_system.modules.domain.settling_in import settling_in as data
    rows = data.list_by_child()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@settling_in_bp.route("/<session_id>", methods=["GET"])
@_token_required
def get_settling_session(session_id):
    from education_system.nursery_system.modules.domain.settling_in import settling_in as data
    rec = data.get_session(session_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@settling_in_bp.route("", methods=["POST"])
@settling_in_bp.route("/", methods=["POST"])
@_token_required
def create_settling_session():
    from education_system.nursery_system.modules.domain.settling_in import settling_in as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create_session(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@settling_in_bp.route("/<session_id>", methods=["PUT"])
@_token_required
def update_settling_session(session_id):
    from education_system.nursery_system.modules.domain.settling_in import settling_in as data
    if data.get_session(session_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update_session(session_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec))


@settling_in_bp.route("/<session_id>", methods=["DELETE"])
@_token_required
def delete_settling_session(session_id):
    from education_system.nursery_system.modules.domain.settling_in import settling_in as data
    if not data.delete_session(session_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": session_id})
