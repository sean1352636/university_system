"""Student API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.shared.api.secondary.pagination import get_pagination_params, paginated_response
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService

student_bp = Blueprint("students", __name__, url_prefix="/api/students")

_db_path = None


def init_student_routes(db_path=None):
    global _db_path
    _db_path = db_path


@student_bp.route("", methods=["GET"])
@token_required
def list_students():
    svc = StudentService(_db_path)
    limit, offset = get_pagination_params()

    students = svc.list_students(
        status=request.args.get("status"),
        year_group=request.args.get("year_group"),
        form_group=request.args.get("form_group"),
        key_stage=request.args.get("key_stage"),
        search=request.args.get("search"),
        limit=limit, offset=offset,
    )
    total = svc.count_students(
        status=request.args.get("status"),
        year_group=request.args.get("year_group"),
    )
    return jsonify(paginated_response(students, total))


@student_bp.route("/<int:student_pk>", methods=["GET"])
@token_required
def get_student(student_pk):
    svc = StudentService(_db_path)
    student = svc.get_student(student_pk)
    if not student:
        return jsonify({"error": "Student not found."}), 404
    return jsonify({"data": student})


@student_bp.route("/by-id/<student_id>", methods=["GET"])
@token_required
def get_student_by_id(student_id):
    svc = StudentService(_db_path)
    student = svc.get_student_by_student_id(student_id)
    if not student:
        return jsonify({"error": "Student not found."}), 404
    return jsonify({"data": student})


@student_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_student():
    data = get_json_body()
    require_fields(data, "first_name", "last_name")

    svc = StudentService(_db_path)
    student = svc.create_student(
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data.get("email"),
        date_of_birth=data.get("date_of_birth"),
        address=data.get("address"),
        year_group=data.get("year_group"),
        form_group=data.get("form_group"),
        form_tutor=data.get("form_tutor"),
        sen_status=data.get("sen_status"),
        pupil_premium=data.get("pupil_premium", False),
        parent_name=data.get("parent_name"),
        parent_email=data.get("parent_email"),
        parent_phone=data.get("parent_phone"),
        emergency_contact_name=data.get("emergency_contact_name"),
        emergency_contact_phone=data.get("emergency_contact_phone"),
    )
    return jsonify({"message": "Student created.", "data": student}), 201


@student_bp.route("/<int:student_pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_student(student_pk):
    data = get_json_body()
    svc = StudentService(_db_path)
    student = svc.update_student(student_pk, **data)
    return jsonify({"message": "Student updated.", "data": student})


@student_bp.route("/<int:student_pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_student(student_pk):
    svc = StudentService(_db_path)
    svc.delete_student(student_pk)
    return jsonify({"message": "Student deleted."})
