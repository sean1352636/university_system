"""Department API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.departments.services.department_service import DepartmentService
from education_system.college_system.core.i18n import t

department_bp = Blueprint("departments", __name__, url_prefix="/api/departments")

_db_path = None


def init_department_routes(db_path=None):
    global _db_path
    _db_path = db_path


@department_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_department():
    data = get_json_body()
    require_fields(data, "code", "name")
    svc = DepartmentService(_db_path)
    dept = svc.create_department(
        data["code"], data["name"],
        faculty=data.get("faculty"),
        head_of_department=data.get("head_of_department"),
        curriculum_area=data.get("curriculum_area"),
        description=data.get("description"),
    )
    return jsonify({"message": t("api.department.created"), "data": dept}), 201


@department_bp.route("", methods=["GET"])
@token_required
def list_departments():
    svc = DepartmentService(_db_path)
    status = request.args.get("status")
    depts = svc.list_departments(status=status)
    return jsonify({"data": depts, "count": len(depts)})


@department_bp.route("/<int:dept_id>", methods=["GET"])
@token_required
def get_department(dept_id):
    svc = DepartmentService(_db_path)
    dept = svc.get_department(dept_id)
    if not dept:
        return jsonify({"error": t("api.department.not_found")}), 404
    return jsonify({"data": dept})


@department_bp.route("/<int:dept_id>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_department(dept_id):
    data = get_json_body()
    svc = DepartmentService(_db_path)
    dept = svc.update_department(dept_id, **data)
    return jsonify({"message": t("api.department.updated"), "data": dept})


@department_bp.route("/<int:dept_id>", methods=["DELETE"])
@token_required
@role_required("admin", "staff")
def delete_department(dept_id):
    svc = DepartmentService(_db_path)
    svc.delete_department(dept_id)
    return jsonify({"message": t("api.department.deleted")})


@department_bp.route("/<int:dept_id>/courses", methods=["GET"])
@token_required
def department_courses(dept_id):
    svc = DepartmentService(_db_path)
    courses = svc.get_department_courses(dept_id)
    return jsonify({"data": courses, "count": len(courses)})
