"""REST API for Primary Phonics tracking."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

phonics_bp = Blueprint("pri_phonics", __name__, url_prefix="/api/phonics")


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


@phonics_bp.route("", methods=["GET"])
@phonics_bp.route("/", methods=["GET"])
@_token_required
def list_records():
    """List phonics records for pupils, optionally filtered."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    try:
        pairs = data.list_records(
            year_group=request.args.get("year_group"),
            phase=request.args.get("phase"),
            status=request.args.get("status"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    rows = [
        {"pupil": _dump(pupil), "phonics": _dump(rec)}
        for pupil, rec in pairs
    ]
    return jsonify({"items": rows, "count": len(rows)})


@phonics_bp.route("/summary", methods=["GET"])
@_token_required
def phase_summary():
    """Counts of pupils by phonics phase."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    return jsonify(data.phase_summary())


@phonics_bp.route("/<pupil_id>", methods=["GET"])
@_token_required
def get_record(pupil_id: str):
    """Get a single pupil's current phonics record."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    try:
        rec = data.get_record(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_dump(rec))


@phonics_bp.route("/<pupil_id>/history", methods=["GET"])
@_token_required
def list_history(pupil_id: str):
    """List a pupil's phonics assessment history."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    try:
        rows = data.list_history(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"items": _dump(rows), "count": len(rows)})


@phonics_bp.route("/<pupil_id>", methods=["POST"])
@_token_required
def record_assessment(pupil_id: str):
    """Record a phonics assessment for a pupil (updates current state)."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.record_assessment(pupil_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(rec)), 201


@phonics_bp.route("/<pupil_id>", methods=["DELETE"])
@_token_required
def clear_pupil(pupil_id: str):
    """Clear a pupil's current phonics record (history is kept)."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    if not data.clear_pupil(pupil_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"status": "cleared"})


@phonics_bp.route("/assessments/<int:assessment_id>", methods=["DELETE"])
@_token_required
def delete_assessment(assessment_id: int):
    """Delete a single phonics assessment history row."""
    from education_system.primarysch_system.modules.domain.phonics import phonics as data
    if not data.delete_assessment(assessment_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"status": "deleted"})
