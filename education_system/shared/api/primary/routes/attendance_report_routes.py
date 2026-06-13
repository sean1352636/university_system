"""REST API for Primary Attendance Report (read-only aggregations)."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

attendance_report_bp = Blueprint(
    "pri_attendance_report", __name__, url_prefix="/api/attendance-report"
)


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
        d = dataclasses.asdict(obj)
        # Surface computed properties on PupilAttendance rollups.
        for prop in ("attendance_pct", "absence_pct", "is_persistent_absentee"):
            if hasattr(obj, prop):
                d[prop] = getattr(obj, prop)
        return d
    return obj


def _arg(name: str) -> str | None:
    val = request.args.get(name)
    if val is not None:
        val = val.strip()
    return val or None


@attendance_report_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.primarysch_system.modules.domain.attendance_report import (
        attendance_report as data,
    )

    try:
        result = data.cohort_summary(
            from_date=_arg("from_date"),
            to_date=_arg("to_date"),
            year_group=_arg("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_dump(result))


@attendance_report_bp.route("/by-year-group", methods=["GET"])
@_token_required
def by_year_group():
    from education_system.primarysch_system.modules.domain.attendance_report import (
        attendance_report as data,
    )

    try:
        rows = data.by_year_group(
            from_date=_arg("from_date"),
            to_date=_arg("to_date"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@attendance_report_bp.route("/pupils", methods=["GET"])
@_token_required
def pupil_attendance():
    from education_system.primarysch_system.modules.domain.attendance_report import (
        attendance_report as data,
    )

    try:
        rows = data.pupil_attendance(
            from_date=_arg("from_date"),
            to_date=_arg("to_date"),
            year_group=_arg("year_group"),
            pupil_id=_arg("pupil_id"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@attendance_report_bp.route("/persistent-absentees", methods=["GET"])
@_token_required
def persistent_absentees():
    from education_system.primarysch_system.modules.domain.attendance_report import (
        attendance_report as data,
    )

    threshold = _arg("threshold_pct")
    kwargs = {
        "from_date": _arg("from_date"),
        "to_date": _arg("to_date"),
        "year_group": _arg("year_group"),
    }
    if threshold is not None:
        try:
            kwargs["threshold_pct"] = float(threshold)
        except ValueError:
            return jsonify({"error": "threshold_pct must be a number"}), 400
    try:
        rows = data.persistent_absentees(**kwargs)
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@attendance_report_bp.route("/daily", methods=["GET"])
@_token_required
def daily_breakdown():
    from education_system.primarysch_system.modules.domain.attendance_report import (
        attendance_report as data,
    )

    from_date = _arg("from_date")
    to_date = _arg("to_date")
    if not from_date or not to_date:
        return jsonify({"error": "from_date and to_date are required"}), 400
    try:
        rows = data.daily_breakdown(
            from_date=from_date,
            to_date=to_date,
            year_group=_arg("year_group"),
        )
    except data.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})
