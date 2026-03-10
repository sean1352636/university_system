"""Student CRUD routes."""

from __future__ import annotations

import logging
import random
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import validate_student_create, validate_student_update
from education_system.university_system.core.exceptions import StudentNotFoundError
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.repositories.student import (
    Student,
    get_student_repository,
)
from education_system.university_system.modules.domain.academics.services.modules import (
    compulsory_module_1,
    compulsory_module_2,
    optional_module_1,
    optional_module_2,
    optional_module_3,
    optional_module_4,
    CS_optional_module_1,
    CS_optional_module_2,
    CS_optional_module_3,
    CS_optional_module_4,
    DS_optional_module_1,
    DS_optional_module_2,
    DS_optional_module_3,
    DS_optional_module_4,
)
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_bp = Blueprint("students", __name__, url_prefix="/api/students")

COMPULSORY_MODULES = [compulsory_module_1, compulsory_module_2]

OPTIONAL_MODULES = [
    optional_module_1, optional_module_2,
    optional_module_3, optional_module_4,
]

COURSE_MODULES = {
    "CS": [CS_optional_module_1, CS_optional_module_2,
           CS_optional_module_3, CS_optional_module_4],
    "DS": [DS_optional_module_1, DS_optional_module_2,
           DS_optional_module_3, DS_optional_module_4],
}


def _generate_unique_student_id(repo) -> str:
    """Generate a random 7-digit student ID that doesn't already exist."""
    for _ in range(10):
        sid = str(random.randint(1000000, 9999999)).zfill(7)
        if not repo.exists(sid):
            return sid
    raise RuntimeError("Failed to generate a unique student ID after 10 attempts")


def _select_modules(course: str) -> list[str]:
    """Pick 6 modules: 2 compulsory + 2 random optional + 2 random course-specific."""
    codes = [m["code"] for m in COMPULSORY_MODULES]
    codes += [m["code"] for m in random.sample(OPTIONAL_MODULES, 2)]
    course_pool = COURSE_MODULES.get(course, [])
    if len(course_pool) >= 2:
        codes += [m["code"] for m in random.sample(course_pool, 2)]
    return codes


def _enroll_student_modules(student_id: str, module_codes: list[str]) -> None:
    """Insert rows into the student_modules table."""
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)",
            [(student_id, code) for code in module_codes],
        )


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

    first_name = data["first_name"]
    last_name = data["last_name"]

    repo = get_student_repository()

    # Auto-generate fields (mirrors the GUI logic)
    student_id = _generate_unique_student_id(repo)
    course = random.choice(["CS", "DS"])
    email_address = f"C{student_id}@tees.ac.uk"
    registration_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    gender = data.get("gender")
    title = data.get("title")
    if not title and gender:
        title = "Mr" if gender.lower() == "male" else "Ms"

    student = Student(
        student_id=student_id,
        first_name=first_name,
        last_name=last_name,
        middle_name=data.get("middle_name"),
        email_address=email_address,
        title=title,
        gender=gender,
        dob=data.get("dob"),
        age=data.get("age"),
        course=course,
        status="Active",
        enrollment_date=data.get("enrollment_date"),
        registration_datetime=registration_datetime,
    )
    saved = repo.save(student)

    # Auto-enroll in 6 modules
    enrolled_modules = _select_modules(course)
    try:
        _enroll_student_modules(student_id, enrolled_modules)
    except Exception:
        logger.warning("Module enrollment failed for %s", student_id, exc_info=True)
        enrolled_modules = []

    # Auto-create user account
    temp_password = f"{first_name.lower()}123456"
    user_account_created = False
    try:
        auth = UserAuth()
        user_account_created = bool(auth.create_user(
            username=student_id,
            password=temp_password,
            email=email_address,
            first_name=first_name,
            last_name=last_name,
            role="student",
            student_id=student_id,
        ))
    except Exception:
        logger.warning("User account creation failed for %s", student_id, exc_info=True)

    log_activity("create", "student", user=g.current_user.get("sub"))

    result = _student_to_dict(saved)
    result["enrolled_modules"] = enrolled_modules
    result["temp_password"] = temp_password
    result["user_account_created"] = user_account_created
    return jsonify(result), 201


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
