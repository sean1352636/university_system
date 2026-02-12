"""Student CRUD routes."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import validate_student_create, validate_student_update
from university_system.core.exceptions import StudentNotFoundError
from university_system.infrastructure.repositories.student import (
    Student,
    get_student_repository,
)
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_bp = Blueprint("students", __name__, url_prefix="/api/students")


def _student_to_dict(s: Student) -> dict:
    return {
        "student_id": s.student_id,
        "first_name": s.first_name,
        "middle_name": s.middle_name,
        "last_name": s.last_name,
        "full_name": s.full_name,
        "email_address": s.email_address,
        "title": s.title,
        "gender": s.gender,
        "dob": s.dob,
        "age": s.age,
        "course": s.course,
        "status": s.status,
        "enrollment_date": s.enrollment_date,
        "registration_datetime": s.registration_datetime,
    }


@student_bp.route("", methods=["GET"])
@token_required
def list_students():
    repo = get_student_repository()
    search_query = request.args.get("search")
    status_filter = request.args.get("status")
    course_filter = request.args.get("course")

    if search_query:
        students = repo.search(search_query)
    elif status_filter:
        students = repo.find_by_status(status_filter)
    elif course_filter:
        students = repo.find_by_course(course_filter)
    else:
        page, per_page, offset = get_pagination_params()
        students = repo.get_all(limit=per_page, offset=offset)
        total = repo.count()
        log_activity("view", "students", user=g.current_user.get("sub"))
        return jsonify(paginated_response(
            [_student_to_dict(s) for s in students], total, page, per_page
        ))

    log_activity("view", "students", user=g.current_user.get("sub"))
    return jsonify({"items": [_student_to_dict(s) for s in students], "total": len(students)})


@student_bp.route("/<student_id>", methods=["GET"])
@token_required
def get_student(student_id: str):
    repo = get_student_repository()
    student = repo.get_by_id(student_id)
    if not student:
        raise StudentNotFoundError(student_id)
    log_activity("view", "student", user=g.current_user.get("sub"))
    return jsonify(_student_to_dict(student))


@student_bp.route("", methods=["POST"])
@token_required
def create_student():
    data = request.get_json(silent=True) or {}
    validate_student_create(data)

    repo = get_student_repository()
    student = Student(
        student_id=data["student_id"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        middle_name=data.get("middle_name"),
        email_address=data.get("email_address"),
        title=data.get("title"),
        gender=data.get("gender"),
        dob=data.get("dob"),
        age=data.get("age"),
        course=data.get("course"),
        status=data.get("status", "Active"),
        enrollment_date=data.get("enrollment_date"),
    )
    saved = repo.save(student)
    log_activity("create", "student", user=g.current_user.get("sub"))
    return jsonify(_student_to_dict(saved)), 201


@student_bp.route("/<student_id>", methods=["PUT"])
@token_required
def update_student(student_id: str):
    data = request.get_json(silent=True) or {}
    validate_student_update(data)

    repo = get_student_repository()
    student = repo.get_by_id(student_id)
    if not student:
        raise StudentNotFoundError(student_id)

    updatable = [
        "first_name", "middle_name", "last_name", "email_address",
        "title", "gender", "dob", "age", "course", "status", "enrollment_date",
    ]
    for field in updatable:
        if field in data:
            setattr(student, field, data[field])

    saved = repo.save(student)
    log_activity("update", "student", user=g.current_user.get("sub"))
    return jsonify(_student_to_dict(saved))


@student_bp.route("/<student_id>", methods=["DELETE"])
@token_required
def delete_student(student_id: str):
    repo = get_student_repository()
    if not repo.exists(student_id):
        raise StudentNotFoundError(student_id)
    repo.delete(student_id)
    log_activity("delete", "student", user=g.current_user.get("sub"))
    return jsonify({"message": f"Student {student_id} deleted"}), 200
