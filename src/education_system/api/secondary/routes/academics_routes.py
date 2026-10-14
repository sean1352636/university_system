"""REST API for Secondary School academics."""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

academics_bp = Blueprint("sec_academics", __name__, url_prefix="/api/academics")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SCHOOL_API_TOKEN")
            got = request.headers.get("X-School-Token")
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


def _validation_error():
    """Return the shared ValidationError class used by the data layers."""
    from education_system.systems.secondary.domain.learners.pupils.pupils import (
        ValidationError,
    )
    return ValidationError


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Subjects ──────────────────────────────────────────────────────

@academics_bp.route("/subjects", methods=["GET"])
@_token_required
def list_subjects():
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as data,
    )
    try:
        rows = data.list_all(
            key_stage=request.args.get("key_stage"),
            qualification=request.args.get("qualification"),
            active_only=request.args.get("active_only", "").lower()
            in ("1", "true", "yes"),
        )
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@academics_bp.route("/subjects/<int:subject_id>", methods=["GET"])
@_token_required
def get_subject(subject_id: int):
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as data,
    )
    rec = data.get(subject_id)
    if rec is None:
        return jsonify({"error": f"No subject #{subject_id}"}), 404
    return jsonify(_dump(rec))


@academics_bp.route("/subjects", methods=["POST"])
@_token_required
def create_subject():
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as data,
    )
    try:
        rec = data.create(_body())
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@academics_bp.route("/subjects/<int:subject_id>", methods=["PUT"])
@_token_required
def update_subject(subject_id: int):
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as data,
    )
    if data.get(subject_id) is None:
        return jsonify({"error": f"No subject #{subject_id}"}), 404
    try:
        rec = data.update(subject_id, _body())
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@academics_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@_token_required
def delete_subject(subject_id: int):
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as data,
    )
    try:
        ok = data.delete(subject_id)
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    if not ok:
        return jsonify({"error": f"No subject #{subject_id}"}), 404
    return jsonify({"deleted": True, "subject_id": subject_id})


# ── Timetable ─────────────────────────────────────────────────────

@academics_bp.route("/timetable", methods=["GET"])
@_token_required
def list_timetable():
    from education_system.systems.secondary.domain.academics.timetable import (
        timetable as data,
    )
    try:
        rows = data.list_slots(
            year_group=request.args.get("year_group"),
            form_group=request.args.get("form_group"),
            day_of_week=request.args.get("day_of_week"),
            teacher=request.args.get("teacher"),
        )
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@academics_bp.route("/timetable/<int:slot_id>", methods=["GET"])
@_token_required
def get_timetable_slot(slot_id: int):
    from education_system.systems.secondary.domain.academics.timetable import (
        timetable as data,
    )
    rec = data.get_slot(slot_id)
    if rec is None:
        return jsonify({"error": f"No timetable slot #{slot_id}"}), 404
    return jsonify(_dump(rec))


@academics_bp.route("/timetable", methods=["POST"])
@_token_required
def create_timetable_slot():
    from education_system.systems.secondary.domain.academics.timetable import (
        timetable as data,
    )
    try:
        rec = data.create_slot(_body())
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@academics_bp.route("/timetable/<int:slot_id>", methods=["PUT"])
@_token_required
def update_timetable_slot(slot_id: int):
    from education_system.systems.secondary.domain.academics.timetable import (
        timetable as data,
    )
    if data.get_slot(slot_id) is None:
        return jsonify({"error": f"No timetable slot #{slot_id}"}), 404
    try:
        rec = data.update_slot(slot_id, _body())
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@academics_bp.route("/timetable/<int:slot_id>", methods=["DELETE"])
@_token_required
def delete_timetable_slot(slot_id: int):
    from education_system.systems.secondary.domain.academics.timetable import (
        timetable as data,
    )
    ok = data.delete_slot(slot_id)
    if not ok:
        return jsonify({"error": f"No timetable slot #{slot_id}"}), 404
    return jsonify({"deleted": True, "slot_id": slot_id})


# ── Homework (assignments) ────────────────────────────────────────

@academics_bp.route("/homework", methods=["GET"])
@_token_required
def list_homework():
    from education_system.systems.secondary.domain.academics.homework import (
        homework as data,
    )
    sid = request.args.get("subject_id")
    try:
        rows = data.list_assignments(
            year_group=request.args.get("year_group"),
            subject_id=int(sid) if sid not in (None, "") else None,
            status=request.args.get("status"),
            teacher=request.args.get("teacher"),
            due_from=request.args.get("due_from"),
            due_to=request.args.get("due_to"),
        )
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "subject_id must be a number"}), 400
    return jsonify({"items": _dump(rows), "count": len(rows)})


@academics_bp.route("/homework/<int:assignment_id>", methods=["GET"])
@_token_required
def get_homework(assignment_id: int):
    from education_system.systems.secondary.domain.academics.homework import (
        homework as data,
    )
    rec = data.get_assignment(assignment_id)
    if rec is None:
        return jsonify({"error": f"No homework assignment #{assignment_id}"}), 404
    return jsonify(_dump(rec))


@academics_bp.route("/homework", methods=["POST"])
@_token_required
def create_homework():
    from education_system.systems.secondary.domain.academics.homework import (
        homework as data,
    )
    try:
        rec = data.create_assignment(_body())
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec)), 201


@academics_bp.route("/homework/<int:assignment_id>", methods=["PUT"])
@_token_required
def update_homework(assignment_id: int):
    from education_system.systems.secondary.domain.academics.homework import (
        homework as data,
    )
    if data.get_assignment(assignment_id) is None:
        return jsonify({"error": f"No homework assignment #{assignment_id}"}), 404
    try:
        rec = data.update_assignment(assignment_id, _body())
    except _validation_error() as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rec))


@academics_bp.route("/homework/<int:assignment_id>", methods=["DELETE"])
@_token_required
def delete_homework(assignment_id: int):
    from education_system.systems.secondary.domain.academics.homework import (
        homework as data,
    )
    ok = data.delete_assignment(assignment_id)
    if not ok:
        return jsonify({"error": f"No homework assignment #{assignment_id}"}), 404
    return jsonify({"deleted": True, "assignment_id": assignment_id})


@academics_bp.route("/homework/<int:assignment_id>/submissions", methods=["GET"])
@_token_required
def list_homework_submissions(assignment_id: int):
    from education_system.systems.secondary.domain.academics.homework import (
        homework as data,
    )
    if data.get_assignment(assignment_id) is None:
        return jsonify({"error": f"No homework assignment #{assignment_id}"}), 404
    rows = data.list_submissions(assignment_id)
    return jsonify({"items": _dump(rows), "count": len(rows)})
