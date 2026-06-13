"""REST API for Primary EYFS Profile."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

eyfs_profile_bp = Blueprint("pri_eyfs_profile", __name__, url_prefix="/api/eyfs-profile")


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


def _dump_profile(profile):
    """Serialize a PupilProfile, including its derived properties."""
    return {
        "pupil_id": profile.pupil_id,
        "academic_year": profile.academic_year,
        "by_code": {code: _dump(rec) for code, rec in profile.by_code.items()},
        "elgs_recorded": profile.elgs_recorded,
        "elgs_total": profile.elgs_total,
        "expected_count": profile.expected_count,
        "has_gld": profile.has_gld,
        "gld_missing": profile.gld_missing,
    }


@eyfs_profile_bp.route("/<int:result_id>", methods=["GET"])
@_token_required
def get_result(result_id: int):
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    rec = data.get(result_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@eyfs_profile_bp.route("", methods=["POST"])
@eyfs_profile_bp.route("/", methods=["POST"])
@_token_required
def set_elg():
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    body = request.get_json(silent=True) or {}
    try:
        rec = data.set_elg(
            body.get("pupil_id"),
            body.get("academic_year"),
            body.get("elg_code"),
            body.get("status"),
            assessed_on=body.get("assessed_on"),
            notes=body.get("notes"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@eyfs_profile_bp.route("/<int:result_id>", methods=["DELETE"])
@_token_required
def delete_result(result_id: int):
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    if not data.delete(result_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": result_id})


@eyfs_profile_bp.route("/profile/<pupil_id>/<academic_year>", methods=["GET"])
@_token_required
def get_profile(pupil_id: str, academic_year: str):
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    try:
        profile = data.get_profile(pupil_id, academic_year)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dump_profile(profile))


@eyfs_profile_bp.route("/profile/<pupil_id>/<academic_year>", methods=["DELETE"])
@_token_required
def clear_pupil_year(pupil_id: str, academic_year: str):
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    try:
        removed = data.clear_pupil_year(pupil_id, academic_year)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"removed": removed})


@eyfs_profile_bp.route("", methods=["GET"])
@eyfs_profile_bp.route("/", methods=["GET"])
@_token_required
def list_profiles():
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    academic_year = request.args.get("academic_year")
    if not academic_year:
        return jsonify({"error": "academic_year query parameter is required"}), 400
    year_group = request.args.get("year_group")
    try:
        pairs = data.list_pupils_with_profiles(
            academic_year, year_group=year_group or None
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = [
        {"pupil": _dump(pupil), "profile": _dump_profile(profile)}
        for pupil, profile in pairs
    ]
    return jsonify({"items": items, "count": len(items)})


@eyfs_profile_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    academic_year = request.args.get("academic_year")
    if not academic_year:
        return jsonify({"error": "academic_year query parameter is required"}), 400
    year_group = request.args.get("year_group")
    try:
        result = data.cohort_summary(academic_year, year_group=year_group or None)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@eyfs_profile_bp.route("/years", methods=["GET"])
@_token_required
def known_years():
    from education_system.primarysch_system.modules.domain.eyfs_profile import (
        eyfs_profile as data,
    )
    rows = data.known_years()
    return jsonify({"items": _dump(rows), "count": len(rows)})
