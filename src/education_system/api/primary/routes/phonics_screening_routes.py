"""REST API for Primary Phonics Screening."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

phonics_screening_bp = Blueprint(
    "pri_phonics_screening", __name__, url_prefix="/api/phonics-screening"
)


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


def _dump_pair(rec, pupil):
    """Serialize a (ScreeningResult, Pupil|None) tuple from list_results."""
    out = dataclasses.asdict(rec)
    out["passed"] = rec.passed
    out["pupil"] = dataclasses.asdict(pupil) if pupil is not None else None
    return out


@phonics_screening_bp.route("", methods=["GET"])
@phonics_screening_bp.route("/", methods=["GET"])
@_token_required
def list_screening():
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    args = request.args
    passed_arg = args.get("passed")
    passed = None
    if passed_arg is not None:
        passed = passed_arg.lower() in ("1", "true", "yes")
    attempt_arg = args.get("attempt")
    attempt = int(attempt_arg) if attempt_arg not in (None, "") else None
    try:
        rows = data.list_results(
            academic_year=args.get("academic_year"),
            attempt=attempt,
            pupil_id=args.get("pupil_id"),
            passed=passed,
            year_group=args.get("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    items = [_dump_pair(rec, pupil) for rec, pupil in rows]
    return jsonify({"items": items, "count": len(items)})


@phonics_screening_bp.route("/<int:result_id>", methods=["GET"])
@_token_required
def get_screening(result_id):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    rec = data.get(result_id)
    if rec is None:
        return jsonify({"error": "Not found"}), 404
    out = _dump(rec)
    out["passed"] = rec.passed
    return jsonify(out)


@phonics_screening_bp.route("", methods=["POST"])
@phonics_screening_bp.route("/", methods=["POST"])
@_token_required
def create_screening():
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    payload = request.get_json(silent=True) or {}
    try:
        rec = data.create(payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    out = _dump(rec)
    out["passed"] = rec.passed
    return jsonify(out), 201


@phonics_screening_bp.route("/<int:result_id>", methods=["PUT"])
@_token_required
def update_screening(result_id):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    if data.get(result_id) is None:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        rec = data.update(result_id, payload)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    out = _dump(rec)
    out["passed"] = rec.passed
    return jsonify(out)


@phonics_screening_bp.route("/<int:result_id>", methods=["DELETE"])
@_token_required
def delete_screening(result_id):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    if not data.delete(result_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


@phonics_screening_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def list_for_pupil(pupil_id):
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    try:
        rows = data.list_for_pupil(pupil_id)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    items = []
    for rec in rows:
        out = _dump(rec)
        out["passed"] = rec.passed
        items.append(out)
    return jsonify({"items": items, "count": len(items)})


@phonics_screening_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    academic_year = request.args.get("academic_year")
    if not academic_year:
        return jsonify({"error": "academic_year query param is required"}), 400
    try:
        return jsonify(data.year_summary(academic_year))
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@phonics_screening_bp.route("/years", methods=["GET"])
@_token_required
def years():
    from education_system.systems.primary.domain.assessment.phonics_screening import (
        phonics_screening as data,
    )

    rows = data.known_years()
    return jsonify({"items": rows, "count": len(rows)})
