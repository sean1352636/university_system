"""Course API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.i18n import t

course_bp = Blueprint("courses", __name__, url_prefix="/api/courses")

_db_path = None


def init_course_routes(db_path=None):
    global _db_path
    _db_path = db_path


@course_bp.route("", methods=["GET"])
@token_required
def list_courses():
    svc = CourseService(_db_path)
    limit, offset = get_pagination_params()

    courses = svc.list_courses(
        subject_area=request.args.get("subject_area"),
        term=request.args.get("term"),
        qualification_type=request.args.get("qualification_type"),
        status=request.args.get("status"),
        search=request.args.get("search"),
        limit=limit, offset=offset,
    )
    total = svc.count_courses(status=request.args.get("status"))
    return jsonify(paginated_response(courses, total))


@course_bp.route("/<int:course_pk>", methods=["GET"])
@token_required
def get_course(course_pk):
    svc = CourseService(_db_path)
    course = svc.get_course(course_pk)
    if not course:
        return jsonify({"error": t("api.course.not_found")}), 404
    return jsonify({"data": course})


@course_bp.route("/by-code/<course_code>", methods=["GET"])
@token_required
def get_course_by_code(course_code):
    svc = CourseService(_db_path)
    course = svc.get_course_by_code(course_code)
    if not course:
        return jsonify({"error": t("api.course.not_found")}), 404
    return jsonify({"data": course})


@course_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_course():
    data = get_json_body()
    require_fields(data, "course_code", "title")

    svc = CourseService(_db_path)
    course = svc.create_course(
        course_code=data["course_code"],
        title=data["title"],
        guided_learning_hours=data.get("guided_learning_hours", 3),
        capacity=data.get("capacity", 30),
        description=data.get("description"),
        subject_area=data.get("subject_area"),
        teacher=data.get("teacher"),
        term=data.get("term"),
        schedule=data.get("schedule"),
        qualification_type=data.get("qualification_type"),
    )
    return jsonify({"message": t("api.course.created"), "data": course}), 201


@course_bp.route("/<int:course_pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_course(course_pk):
    data = get_json_body()
    svc = CourseService(_db_path)
    course = svc.update_course(course_pk, **data)
    return jsonify({"message": t("api.course.updated"), "data": course})


@course_bp.route("/<int:course_pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_course(course_pk):
    svc = CourseService(_db_path)
    svc.delete_course(course_pk)
    return jsonify({"message": t("api.course.deleted")})


@course_bp.route("/<int:course_pk>/roster", methods=["GET"])
@token_required
def get_roster(course_pk):
    svc = CourseService(_db_path)
    roster = svc.get_roster(course_pk)
    return jsonify({"data": roster, "count": len(roster)})


@course_bp.route("/<int:course_pk>/prerequisites", methods=["GET"])
@token_required
def get_prerequisites(course_pk):
    svc = CourseService(_db_path)
    prereqs = svc.get_prerequisites(course_pk)
    return jsonify({"data": prereqs})


@course_bp.route("/<int:course_pk>/prerequisites", methods=["POST"])
@token_required
@role_required("admin", "staff")
def add_prerequisite(course_pk):
    data = get_json_body()
    require_fields(data, "prerequisite_id")

    svc = CourseService(_db_path)
    svc.add_prerequisite(course_pk, data["prerequisite_id"])
    return jsonify({"message": t("api.course.prereq_added")}), 201
