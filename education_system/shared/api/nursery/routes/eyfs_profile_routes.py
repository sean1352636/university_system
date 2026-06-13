"""REST API for Nursery EYFS Profile.

Exposes CRUD over per-child EYFS attainment profiles (7 areas of learning).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

eyfs_profile_bp = Blueprint("nsy_eyfs_profile", __name__, url_prefix="/api/eyfs-profile")


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


@eyfs_profile_bp.route("", methods=["GET"])
@eyfs_profile_bp.route("/", methods=["GET"])
@_token_required
def list_profiles():
    from education_system.nursery_system.modules.domain.eyfs_profile import eyfs_profile as data
    pupil_id = request.args.get("pupil_id")
    rows = data.list_profiles(pupil_id=pupil_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})


@eyfs_profile_bp.route("/<profile_id>", methods=["GET"])
@_token_required
def get_profile(profile_id):
    from education_system.nursery_system.modules.domain.eyfs_profile import eyfs_profile as data
    profile = data.get_profile(profile_id)
    if profile is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(profile))


@eyfs_profile_bp.route("", methods=["POST"])
@eyfs_profile_bp.route("/", methods=["POST"])
@_token_required
def create_profile():
    from education_system.nursery_system.modules.domain.eyfs_profile import eyfs_profile as data
    payload = request.get_json(silent=True) or {}
    try:
        profile = data.create_profile(payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(profile)), 201


@eyfs_profile_bp.route("/<profile_id>", methods=["PUT"])
@_token_required
def update_profile(profile_id):
    from education_system.nursery_system.modules.domain.eyfs_profile import eyfs_profile as data
    payload = request.get_json(silent=True) or {}
    if data.get_profile(profile_id) is None:
        return jsonify({"error": "Not found"}), 404
    try:
        profile = data.update_profile(profile_id, payload)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(profile))


@eyfs_profile_bp.route("/<profile_id>", methods=["DELETE"])
@_token_required
def delete_profile(profile_id):
    from education_system.nursery_system.modules.domain.eyfs_profile import eyfs_profile as data
    if not data.delete_profile(profile_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True, "profile_id": profile_id})
