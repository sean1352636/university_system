"""Assignment API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.core.i18n import t

assignment_bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")

_db_path = None


def init_assignment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@assignment_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_assignment():
    data = get_json_body()
    require_fields(data, "course_id", "title", "due_date")

    svc = AssignmentService(_db_path)
    assignment = svc.create_assignment(
        course_id=data["course_id"],
        title=data["title"],
        description=data.get("description"),
        due_date=data["due_date"],
        max_score=data.get("max_score", 100),
        allow_late=data.get("allow_late", False),
        created_by=g.current_user["user_id"],
    )
    return jsonify({"message": t("api.assignment.created"), "data": assignment}), 201


@assignment_bp.route("", methods=["GET"])
@token_required
def list_assignments():
    svc = AssignmentService(_db_path)
    course_id = request.args.get("course_id", type=int)
    assignments = svc.list_assignments(course_id)
    return jsonify({"data": assignments, "count": len(assignments)})


@assignment_bp.route("/<int:assignment_id>", methods=["GET"])
@token_required
def get_assignment(assignment_id):
    svc = AssignmentService(_db_path)
    assignment = svc.get_assignment(assignment_id)
    if not assignment:
        return jsonify({"error": t("api.common.not_found")}), 404
    return jsonify({"data": assignment})


@assignment_bp.route("/<int:assignment_id>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_assignment(assignment_id):
    data = get_json_body()
    svc = AssignmentService(_db_path)
    assignment = svc.update_assignment(assignment_id, **data)
    return jsonify({"message": t("api.assignment.updated"), "data": assignment})


@assignment_bp.route("/<int:assignment_id>", methods=["DELETE"])
@token_required
@role_required("admin", "staff", "instructor")
def delete_assignment(assignment_id):
    svc = AssignmentService(_db_path)
    svc.delete_assignment(assignment_id)
    return jsonify({"message": t("api.assignment.deleted")})


@assignment_bp.route("/<int:assignment_id>/submit", methods=["POST"])
@token_required
def submit_assignment(assignment_id):
    data = get_json_body()
    require_fields(data, "student_id")

    svc = AssignmentService(_db_path)
    sub = svc.submit(assignment_id, data["student_id"], data.get("content"))
    return jsonify({"message": t("api.assignment.submitted"), "data": sub}), 201


@assignment_bp.route("/<int:assignment_id>/submissions", methods=["GET"])
@token_required
def get_assignment_submissions(assignment_id):
    svc = AssignmentService(_db_path)
    subs = svc.get_assignment_submissions(assignment_id)
    return jsonify({"data": subs, "count": len(subs)})


@assignment_bp.route("/submissions/<int:submission_id>/grade", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def grade_submission(submission_id):
    data = get_json_body()
    require_fields(data, "score")

    svc = AssignmentService(_db_path)
    result = svc.grade_submission(
        submission_id, data["score"],
        feedback=data.get("feedback"),
        graded_by=g.current_user["user_id"],
    )
    return jsonify({"message": t("api.assignment.graded"), "data": result})


@assignment_bp.route("/student/<int:student_pk>", methods=["GET"])
@token_required
def get_student_submissions(student_pk):
    svc = AssignmentService(_db_path)
    subs = svc.get_student_submissions(student_pk)
    return jsonify({"data": subs, "count": len(subs)})
