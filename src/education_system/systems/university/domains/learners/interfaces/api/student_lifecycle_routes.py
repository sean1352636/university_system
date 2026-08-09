"""Formal student registration and module-selection API."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.systems.university.domains.learners.domain import student_lifecycle
from education_system.systems.university.infrastructure.exceptions import ValidationError

student_lifecycle_bp = Blueprint(
    "student_lifecycle",
    __name__,
    url_prefix="/api/student-lifecycle",
)


@student_lifecycle_bp.post("/students/<student_id>/registrations")
@token_required
def register_student(student_id: str):
    data = request.get_json(silent=True) or {}
    if not data.get("academic_year"):
        raise ValidationError("academic_year is required")
    try:
        registration_id = student_lifecycle.register(
            student_id,
            str(data["academic_year"]),
            actor_id=str(g.current_user.get("sub") or ""),
            mode_of_study=str(data.get("mode_of_study") or "full-time"),
            campus_code=str(data.get("campus_code") or "MAIN"),
            declarations=dict(data.get("declarations") or {}),
            returning=bool(data.get("returning", False)),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return jsonify({"registration_id": registration_id}), 201


@student_lifecycle_bp.post("/students/<student_id>/module-selections")
@token_required
def select_student_module(student_id: str):
    data = request.get_json(silent=True) or {}
    for field in ("academic_year", "module_code"):
        if not data.get(field):
            raise ValidationError(f"{field} is required")
    try:
        enrolment_id = student_lifecycle.select_module(
            student_id,
            str(data["module_code"]),
            academic_year=str(data["academic_year"]),
            teaching_period=data.get("teaching_period"),
            actor_id=str(g.current_user.get("sub") or ""),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return jsonify({"module_enrolment_id": enrolment_id}), 201


__all__ = ["student_lifecycle_bp"]
