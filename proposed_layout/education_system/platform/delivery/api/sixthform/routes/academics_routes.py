"""REST API for Sixth Form Academics.

Exposes CRUD over the two most central academics submodules — courses
(teaching offerings: subject + year group + academic year) and subjects
(the qualifications catalogue). The academic_year submodule is served by
its own blueprint and is deliberately not covered here.

Auth mirrors the other sixth-form route modules: a JWT bearer token
(validated by the university ``token_required`` if importable) or an
``X-Sixthform-Token`` header matching ``SIXTHFORM_API_TOKEN``.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

academics_bp = Blueprint(
    "sf_academics", __name__, url_prefix="/api/sixthform/academics")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
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


# ── Courses ─────────────────────────────────────────────────────────

@academics_bp.route("/courses", methods=["GET"])
@_token_required
def list_courses_route():
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as data,
    )
    yg = request.args.get("year_group")
    rows = data.list_courses(
        subject=request.args.get("subject"),
        year_group=int(yg) if yg not in (None, "") else None,
        academic_year=request.args.get("academic_year"),
        search=request.args.get("search"),
    )
    return jsonify({"courses": _dump(rows), "count": len(rows)})


@academics_bp.route("/courses/<int:course_id>", methods=["GET"])
@_token_required
def get_course_route(course_id: int):
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as data,
    )
    course = data.get_course(course_id)
    if course is None:
        return jsonify({"error": f"No course with id {course_id}"}), 404
    return jsonify(_dump(course))


@academics_bp.route("/courses", methods=["POST"])
@_token_required
def create_course_route():
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as data,
    )
    try:
        course = data.create_course(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(course)), 201


@academics_bp.route("/courses/<int:course_id>", methods=["PUT"])
@_token_required
def update_course_route(course_id: int):
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as data,
    )
    if data.get_course(course_id) is None:
        return jsonify({"error": f"No course with id {course_id}"}), 404
    try:
        course = data.update_course(course_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(course))


@academics_bp.route("/courses/<int:course_id>", methods=["DELETE"])
@_token_required
def delete_course_route(course_id: int):
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as data,
    )
    if not data.delete_course(course_id):
        return jsonify({"error": f"No course with id {course_id}"}), 404
    return jsonify({"deleted": course_id})


# ── Subjects ────────────────────────────────────────────────────────

@academics_bp.route("/subjects", methods=["GET"])
@_token_required
def list_subjects_route():
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as data,
    )
    include_inactive = request.args.get("include_inactive", "true").lower() != "false"
    rows = data.list_subjects(
        qualification=request.args.get("qualification"),
        exam_board=request.args.get("exam_board"),
        include_inactive=include_inactive,
        search=request.args.get("search"),
    )
    return jsonify({"subjects": _dump(rows), "count": len(rows)})


@academics_bp.route("/subjects/<int:subject_id>", methods=["GET"])
@_token_required
def get_subject_route(subject_id: int):
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as data,
    )
    s = data.get_subject(subject_id)
    if s is None:
        return jsonify({"error": f"No subject with id {subject_id}"}), 404
    return jsonify(_dump(s))


@academics_bp.route("/subjects", methods=["POST"])
@_token_required
def create_subject_route():
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as data,
    )
    try:
        s = data.create_subject(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(s)), 201


@academics_bp.route("/subjects/<int:subject_id>", methods=["PUT"])
@_token_required
def update_subject_route(subject_id: int):
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as data,
    )
    if data.get_subject(subject_id) is None:
        return jsonify({"error": f"No subject with id {subject_id}"}), 404
    try:
        s = data.update_subject(subject_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(s))


@academics_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@_token_required
def delete_subject_route(subject_id: int):
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as data,
    )
    try:
        deleted = data.delete_subject(subject_id)
    except data.ValidationError as e:
        # Refused because still referenced — surface as 409 Conflict.
        return jsonify({"error": str(e)}), 409
    if not deleted:
        return jsonify({"error": f"No subject with id {subject_id}"}), 404
    return jsonify({"deleted": subject_id})
