"""REST API for Sixth Form Staff Communications.

Exposes CRUD over the staff directory (string staff ids) and announcements
(integer announcement ids) submodules of the sixth-form staff_comms domain.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

staff_comms_bp = Blueprint("sf_staff_comms", __name__, url_prefix="/api/sixthform/staff-comms")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe dicts."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _as_bool(value):
    if value is None:
        return None
    return str(value).lower() in ("1", "true", "yes", "on")


# ── Staff directory ─────────────────────────────────────────────────

@staff_comms_bp.route("/staff", methods=["GET"])
@_token_required
def list_staff():
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as data
    kwargs = {}
    for key in ("role", "department", "employment_status"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    for key in ("is_tutor", "is_dsl", "is_examiner"):
        val = _as_bool(request.args.get(key))
        if val is not None:
            kwargs[key] = val
    active_only = _as_bool(request.args.get("active_only"))
    if active_only is not None:
        kwargs["active_only"] = active_only
    try:
        rows = data.list_staff(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"staff": _dump(rows), "count": len(rows)})


@staff_comms_bp.route("/staff/<staff_id>", methods=["GET"])
@_token_required
def get_staff(staff_id):
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as data
    row = data.get_staff(staff_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_comms_bp.route("/staff", methods=["POST"])
@_token_required
def create_staff():
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as data
    try:
        row = data.create_staff(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_comms_bp.route("/staff/<staff_id>", methods=["PUT"])
@_token_required
def update_staff(staff_id):
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as data
    try:
        row = data.update_staff(staff_id, request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        msg = str(e)
        code = 404 if "No staff with id" in msg else 400
        return jsonify({"error": msg}), code
    return jsonify(_dump(row))


@staff_comms_bp.route("/staff/<staff_id>", methods=["DELETE"])
@_token_required
def delete_staff(staff_id):
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import staff as data
    if not data.delete_staff(staff_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": staff_id})


# ── Announcements ───────────────────────────────────────────────────

@staff_comms_bp.route("/announcements", methods=["GET"])
@_token_required
def list_announcements():
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.announcements import (
        announcements as data,
    )
    kwargs = {}
    for key in ("category", "status", "audience", "author_like", "title_like"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    for key in ("priority", "priority_min"):
        val = request.args.get(key)
        if val:
            try:
                kwargs[key] = int(val)
            except ValueError:
                return jsonify({"error": f"{key} must be an integer"}), 400
    for key in ("published_only", "live_only", "pinned_only", "banner_only"):
        val = _as_bool(request.args.get(key))
        if val:
            kwargs[key] = val
    try:
        rows = data.list_announcements(**kwargs)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"announcements": _dump(rows), "count": len(rows)})


@staff_comms_bp.route("/announcements/<int:announcement_id>", methods=["GET"])
@_token_required
def get_announcement(announcement_id):
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.announcements import (
        announcements as data,
    )
    row = data.get_announcement(announcement_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(row))


@staff_comms_bp.route("/announcements", methods=["POST"])
@_token_required
def create_announcement():
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.announcements import (
        announcements as data,
    )
    try:
        row = data.create_announcement(request.get_json(force=True, silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(row)), 201


@staff_comms_bp.route("/announcements/<int:announcement_id>", methods=["PUT"])
@_token_required
def update_announcement(announcement_id):
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.announcements import (
        announcements as data,
    )
    try:
        row = data.update_announcement(
            announcement_id, request.get_json(force=True, silent=True) or {}
        )
    except data.ValidationError as e:
        msg = str(e)
        code = 404 if "No announcement with id" in msg else 400
        return jsonify({"error": msg}), code
    return jsonify(_dump(row))


@staff_comms_bp.route("/announcements/<int:announcement_id>", methods=["DELETE"])
@_token_required
def delete_announcement(announcement_id):
    from education_system.post_16.sixthform_system.modules.domain.staff_comms.announcements import (
        announcements as data,
    )
    if not data.delete_announcement(announcement_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": announcement_id})
