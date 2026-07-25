"""REST API for Nursery Leavers.

Exposes CRUD over children who have left the setting, plus reinstate and the
active-pupil candidate picklist.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

leavers_bp = Blueprint("nsy_leavers", __name__, url_prefix="/api/leavers")


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


@leavers_bp.route("", methods=["GET"])
@leavers_bp.route("/", methods=["GET"])
@_token_required
def list_leavers():
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    rows = data.list_leavers()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@leavers_bp.route("/candidates", methods=["GET"])
@_token_required
def list_candidates():
    """Active children still on roll — candidates to become a leaver."""
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    choices = data.list_active_pupil_choices()
    items = [{"pupil_id": pid, "label": label} for pid, label in choices]
    return jsonify({"items": items, "count": len(items)})


@leavers_bp.route("/<leaver_id>", methods=["GET"])
@_token_required
def get_leaver(leaver_id):
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    leaver = data.get_leaver(leaver_id)
    if leaver is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(leaver))


@leavers_bp.route("", methods=["POST"])
@leavers_bp.route("/", methods=["POST"])
@_token_required
def record_leaver():
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    payload = request.get_json(silent=True) or {}
    try:
        leaver = data.record_leaver(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(leaver)), 201


@leavers_bp.route("/<leaver_id>", methods=["PUT"])
@_token_required
def update_leaver(leaver_id):
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    payload = request.get_json(silent=True) or {}
    try:
        leaver = data.update_leaver(leaver_id, payload)
    except data.ValidationError as exc:
        msg = str(exc)
        if msg.startswith(f"No leaver with id {leaver_id}"):
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(_dump(leaver))


@leavers_bp.route("/<leaver_id>", methods=["DELETE"])
@_token_required
def delete_leaver(leaver_id):
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    if not data.delete_leaver(leaver_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "leaver_id": leaver_id})


@leavers_bp.route("/<leaver_id>/reinstate", methods=["POST"])
@_token_required
def reinstate(leaver_id):
    """Reverse a leaver: put the child back on the active roll, drop the record."""
    from education_system.systems.nursery.domain.learners.leavers import leavers as data
    try:
        pupil_id = data.reinstate(leaver_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"reinstated": True, "pupil_id": pupil_id})
