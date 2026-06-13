"""REST API for Sixth Form students + canonical identity.

Read endpoints the university (or any client) can call over HTTP instead
of importing the sixth-form Python package directly:

* GET /api/sixthform/students/year13          — Year 13 leavers
* GET /api/sixthform/students/<student_id>     — one student
* GET /api/sixthform/identity/<journey_id>     — canonical journey
* GET /api/sixthform/identity/by-student/<system>/<student_id>

Auth mirrors the academic-year routes: a JWT bearer token (validated by
the university ``token_required`` if importable) or an
``X-Sixthform-Token`` header matching ``SIXTHFORM_API_TOKEN``.
"""

from __future__ import annotations

import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

students_bp = Blueprint(
    "sf_students", __name__, url_prefix="/api/sixthform")


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


def _student_dict(s) -> dict:
    return {
        "student_id": s.student_id,
        "first_name": s.first_name,
        "middle_name": s.middle_name,
        "last_name": s.last_name,
        "full_name": s.full_name,
        "title": s.title,
        "gender": s.gender,
        "date_of_birth": s.date_of_birth,
        "status": s.status,
        "subjects": s.subjects,
    }


@students_bp.route("/students/year13", methods=["GET"])
@_token_required
def year13_route():
    from education_system.sixthform_system.modules.domain.students.students import (
        students as data,
    )
    rows = data.list_year_13_students()
    return jsonify({"students": [_student_dict(s) for s in rows],
                    "count": len(rows)})


@students_bp.route("/students/<student_id>", methods=["GET"])
@_token_required
def student_route(student_id: str):
    from education_system.sixthform_system.modules.domain.students.students import (
        students as data,
    )
    s = data.get_student(student_id)
    if s is None:
        return jsonify({"error": f"No student {student_id}"}), 404
    return jsonify(_student_dict(s))


@students_bp.route("/identity/<journey_id>", methods=["GET"])
@_token_required
def identity_route(journey_id: str):
    from education_system.shared.cross_system import identity_service
    j = identity_service.get(journey_id)
    if j is None:
        return jsonify({"error": f"No journey {journey_id}"}), 404
    return jsonify(j)


@students_bp.route("/identity/by-student/<system>/<student_id>",
                   methods=["GET"])
@_token_required
def identity_by_student_route(system: str, student_id: str):
    from education_system.shared.cross_system import identity_service
    try:
        j = identity_service.find_by_student(system, student_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if j is None:
        return jsonify({"error": "No journey for that student"}), 404
    return jsonify(j)
