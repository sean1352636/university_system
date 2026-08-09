"""REST API for Primary Enrolment (year-group roll, moves, promotions)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

enrolment_bp = Blueprint("pri_enrolment", __name__, url_prefix="/api/enrolment")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


@enrolment_bp.route("", methods=["GET"])
@enrolment_bp.route("/", methods=["GET"])
@_token_required
def roll_by_year():
    """Return the full school roll grouped by year group."""
    from education_system.systems.primary.domain.admissions.enrolment import (
        enrolment as data,
    )
    grouped = data.roll_by_year()
    items = {year: _dump(pupils) for year, pupils in grouped.items()}
    count = sum(len(v) for v in grouped.values())
    return jsonify({"items": items, "count": count})


@enrolment_bp.route("/leavers", methods=["GET"])
@_token_required
def leavers():
    """Return pupils in the final year (leavers)."""
    from education_system.systems.primary.domain.admissions.enrolment import (
        enrolment as data,
    )
    rows = data.leavers()
    return jsonify({"items": _dump(rows), "count": len(rows)})


@enrolment_bp.route("/promote/<from_year>", methods=["GET"])
@_token_required
def promote_preview(from_year):
    """Dry-run preview of promoting a year group to the next year."""
    from education_system.systems.primary.domain.admissions.enrolment import (
        enrolment as data,
    )
    try:
        summary = data.promote_year(from_year, dry_run=True)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(summary))


@enrolment_bp.route("/promote/<from_year>", methods=["POST"])
@_token_required
def promote_year(from_year):
    """Promote all pupils in a year group to the next year."""
    from education_system.systems.primary.domain.admissions.enrolment import (
        enrolment as data,
    )
    try:
        summary = data.promote_year(from_year, dry_run=False)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(summary)), 200


@enrolment_bp.route("/move/<pupil_id>", methods=["POST"])
@_token_required
def move_pupil(pupil_id):
    """Move a single pupil to a new year group (and optionally class)."""
    from education_system.systems.primary.domain.admissions.enrolment import (
        enrolment as data,
    )
    payload = request.get_json(silent=True) or {}
    new_year = payload.get("new_year")
    new_class = payload.get("new_class")
    if not new_year:
        return jsonify({"error": "new_year is required"}), 400
    try:
        pupil = data.move_pupil(pupil_id, new_year, new_class)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(pupil)), 200
