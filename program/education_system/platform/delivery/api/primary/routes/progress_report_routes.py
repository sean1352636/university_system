"""REST API for Primary Progress Report (read-only roll-ups)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

progress_report_bp = Blueprint("pri_progress_report", __name__, url_prefix="/api/progress-report")


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
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


@progress_report_bp.route("/pupil/<pupil_id>", methods=["GET"])
@_token_required
def get_pupil_progress(pupil_id):
    from education_system.systems.primary.domain.operations.reporting.progress_report import (
        progress_report as data,
    )
    try:
        pp = data.pupil_progress(pupil_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(pp))


@progress_report_bp.route("/pupil/<pupil_id>/trajectory", methods=["GET"])
@_token_required
def get_pupil_trajectory(pupil_id):
    from education_system.systems.primary.domain.operations.reporting.progress_report import (
        progress_report as data,
    )
    try:
        rows = data.pupil_trajectory(pupil_id)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@progress_report_bp.route("/cohort/subject-summary", methods=["GET"])
@_token_required
def get_cohort_subject_summary():
    from education_system.systems.primary.domain.operations.reporting.progress_report import (
        progress_report as data,
    )
    try:
        result = data.cohort_subject_summary(
            academic_year=request.args.get("academic_year"),
            term=request.args.get("term"),
            subject=request.args.get("subject"),
            year_group=request.args.get("year_group"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))


@progress_report_bp.route("/cohort/overview", methods=["GET"])
@_token_required
def get_cohort_overview():
    from education_system.systems.primary.domain.operations.reporting.progress_report import (
        progress_report as data,
    )
    try:
        result = data.cohort_overview(
            academic_year=request.args.get("academic_year"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))


@progress_report_bp.route("/pupils-with-data", methods=["GET"])
@_token_required
def get_pupils_with_data():
    from education_system.systems.primary.domain.operations.reporting.progress_report import (
        progress_report as data,
    )
    try:
        rows = data.find_pupils_with_data(
            year_group=request.args.get("year_group"),
            academic_year=request.args.get("academic_year"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    items = [{"pupil": _dump(p), "data_points": n} for p, n in rows]
    return jsonify({"items": items, "count": len(items)})
